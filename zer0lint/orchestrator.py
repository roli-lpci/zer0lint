"""Main orchestrator for zer0lint v0.2 — config-level injection, validated flow."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from zer0lint.fixer import apply_prompt, detect_extraction_model
from zer0lint.tester import (
    generate_test_facts_for_categories,
    validate_extraction_prompt,
    cleanup_test_memories,
    count_stored_memories,
)


# mem0's built-in default (personal assistant focused)
MEM0_DEFAULT_PROMPT = """You are a Personal Information Organizer. Extract facts from conversations.
Types: personal preferences, dates, relationships, activities, health, professional details.
Return as JSON: {"facts": ["fact1", ...]}
Input: Hi. Output: {"facts": []}"""

# zer0lint's technical-domain prompt (validated: 5/5 recall vs 2/5 with personal prompt)
TECHNICAL_EXTRACTION_PROMPT = """You are a Technical Memory Organizer for an AI agent workspace. Extract ALL factual statements from the input — technical decisions, infrastructure changes, product details, research findings, scores, dates, names, URLs, versions, and architectural choices.

Types of information to extract:
1. Infrastructure changes (services started/stopped, configs changed, versions installed)
2. Technical decisions and their rationale
3. Product/project details (names, versions, stars, URLs, status)
4. Research findings and experiment results (scores, percentages, benchmarks)
5. People, organizations, and relationships
6. Dates, deadlines, and timelines
7. File paths, port numbers, model names, and system specifics
8. Security findings and audit scores
9. Architecture patterns and design decisions
10. Task assignments and status changes

Examples:

Input: We forked OpenClaw and installed it as v2026.3.14
Output: {"facts": ["Forked OpenClaw, installed as version 2026.3.14"]}

Input: The security audit scored 7.2 out of 10, up from 6.1
Output: {"facts": ["Security audit score: 7.2/10", "Previous security audit score was 6.1"]}

Input: Little Canary runs as HTTP server on port 18421 in full blocking mode
Output: {"facts": ["Little Canary runs as HTTP server on port 18421", "Little Canary is in full blocking mode"]}

Input: Hi, how are you?
Output: {"facts": []}

Return facts as JSON with key "facts" and a list of strings. Extract generously — it's better to capture too much than too little. Every concrete fact matters."""


def _make_memory(base_config: dict, custom_prompt: Optional[str] = None, collection_suffix: str = "test"):
    """Create a mem0 Memory instance with optional config-level prompt injection."""
    from mem0 import Memory

    config = json.loads(json.dumps(base_config))  # deep copy

    # Swap collection to an isolated test namespace
    if "vector_store" in config and "config" in config["vector_store"]:
        orig_name = config["vector_store"]["config"].get("collection_name", "mem0")
        config["vector_store"]["config"]["collection_name"] = f"{orig_name}_{collection_suffix}"

    # Config-level prompt injection (the correct way in mem0 v1.x)
    if custom_prompt:
        config["custom_fact_extraction_prompt"] = custom_prompt
    elif "custom_fact_extraction_prompt" in config:
        del config["custom_fact_extraction_prompt"]

    return Memory.from_config(config)


def run_check(
    base_config: dict,
    verbose: bool = False,
    n_facts: int = 5,
) -> dict:
    """
    Phase 1: Baseline recall test.
    Tests current config as-is against domain-relevant synthetic facts.

    Returns dict: score, total, pct, status, details
    """
    if verbose:
        model = detect_extraction_model(base_config)
        print(f"[CHECK] Using model: {model}")
        print(f"[CHECK] Testing with {n_facts} synthetic facts...")

    memory = _make_memory(base_config, collection_suffix="check")
    uid = "zer0lint_check"
    cleanup_test_memories(memory, user_id=uid)

    facts = generate_test_facts_for_categories(["technical", "research"], count=n_facts)
    results = validate_extraction_prompt(memory, facts, "", user_id=uid, wait_seconds=1.5)

    score = results["score"]
    total = results["total"]
    pct = score / total * 100 if total > 0 else 0

    if pct >= 80:
        status = "HEALTHY"
    elif pct >= 60:
        status = "ACCEPTABLE"
    elif pct >= 40:
        status = "DEGRADED"
    else:
        status = "CRITICAL"

    if verbose:
        print(f"[CHECK] Score: {score}/{total} ({pct:.0f}%) — {status}")
        for d in results["details"]:
            icon = "✅" if d["found"] else ("⚠ " if d.get("stored") else "❌")
            print(f"  {icon} {d['label']}: {d['text'][:55]}...")

    return {
        "score": score,
        "total": total,
        "pct": pct,
        "status": status,
        "details": results["details"],
        "failures": results["failures"],
    }


def run_generate(
    base_config: dict,
    config_path: Optional[str | Path] = None,
    verbose: bool = False,
    n_facts: int = 5,
) -> dict:
    """
    Full zer0lint v0.2 generate flow (3 phases):
      Phase 1: Baseline recall test (current config)
      Phase 2: Re-test with zer0lint technical prompt (config-level injection)
      Phase 3: If improved → write to config

    Args:
        base_config: Parsed mem0 config dict
        config_path: Path to mem0 config.json (for applying the fix)
        verbose: Print detailed output
        n_facts: Number of test facts per run

    Returns dict with: initial_score, improved_score, improvement_pp, applied, prompt, status
    """
    result = {
        "success": False,
        "initial_score": None,
        "initial_pct": None,
        "improved_score": None,
        "improved_pct": None,
        "improvement_pp": None,
        "prompt": None,
        "applied": False,
        "backup_path": None,
        "verdict": None,
    }

    facts = generate_test_facts_for_categories(["technical", "research"], count=n_facts)
    uid_baseline = "zer0lint_baseline"
    uid_improved = "zer0lint_improved"

    # --- Phase 1: Baseline (current config, no changes) ---
    if verbose:
        print("\n[1/3] Baseline — testing current config as-is...")

    mem_baseline = _make_memory(base_config, collection_suffix="baseline")
    cleanup_test_memories(mem_baseline, user_id=uid_baseline)
    res_baseline = validate_extraction_prompt(mem_baseline, facts, "", user_id=uid_baseline, wait_seconds=1.5)

    initial_score = res_baseline["score"]
    initial_pct = initial_score / n_facts * 100
    result["initial_score"] = initial_score
    result["initial_pct"] = initial_pct

    if verbose:
        print(f"  Baseline score: {initial_score}/{n_facts} ({initial_pct:.0f}%)")
        for d in res_baseline["details"]:
            icon = "✅" if d["found"] else "❌"
            print(f"    {icon} {d['label']}")

    # If already perfect, done
    if initial_score >= n_facts:
        if verbose:
            print("\n✅ Extraction is already perfect. No changes needed.")
        result["success"] = True
        result["verdict"] = "already_healthy"
        return result

    # --- Phase 2: Re-test with zer0lint technical prompt (config-level) ---
    if verbose:
        print("\n[2/3] Re-testing with zer0lint technical extraction prompt (config-level)...")

    mem_improved = _make_memory(base_config, custom_prompt=TECHNICAL_EXTRACTION_PROMPT, collection_suffix="improved")
    cleanup_test_memories(mem_improved, user_id=uid_improved)
    res_improved = validate_extraction_prompt(mem_improved, facts, "", user_id=uid_improved, wait_seconds=1.5)

    improved_score = res_improved["score"]
    improved_pct = improved_score / n_facts * 100
    improvement_pp = improved_pct - initial_pct
    result["improved_score"] = improved_score
    result["improved_pct"] = improved_pct
    result["improvement_pp"] = improvement_pp
    result["prompt"] = TECHNICAL_EXTRACTION_PROMPT

    if verbose:
        print(f"  Improved score: {improved_score}/{n_facts} ({improved_pct:.0f}%)")
        print(f"  Improvement: {improvement_pp:+.0f}pp")
        for d in res_improved["details"]:
            icon = "✅" if d["found"] else "❌"
            print(f"    {icon} {d['label']}")

    # --- Phase 3: Apply if improved and above threshold ---
    if improvement_pp > 0 and improved_score >= max(initial_score, 4):
        result["verdict"] = "improved"
        if config_path:
            if verbose:
                print(f"\n[3/3] Applying fix to config ({initial_pct:.0f}% → {improved_pct:.0f}%)...")
            apply_result = apply_prompt(config_path, TECHNICAL_EXTRACTION_PROMPT, backup=True)
            result["applied"] = apply_result["success"]
            result["backup_path"] = apply_result.get("backup_path")
            if verbose:
                print(f"  ✅ Config updated. Backup at: {apply_result.get('backup_path')}")
        else:
            if verbose:
                print(f"\n[3/3] Would apply fix but no --config path given (dry run).")
    elif improvement_pp <= 0:
        result["verdict"] = "no_improvement"
        if verbose:
            print(f"\n⚠ Prompt did not improve score — not applying.")
    else:
        result["verdict"] = "below_threshold"
        if verbose:
            print(f"\n⚠ Score improved but still below threshold — not applying.")

    result["success"] = True
    return result
