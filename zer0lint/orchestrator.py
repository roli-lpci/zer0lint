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
    if not base_config:
        raise ValueError(
            "No mem0 config provided. Either pass --config or use HTTP mode "
            "(--add-url + --search-url)."
        )
    try:
        from mem0 import Memory
    except ImportError:
        raise RuntimeError(
            "mem0ai is not installed. Install with: pip install zer0lint[mem0]\n"
            "Or use HTTP mode: zer0lint check --add-url <url> --search-url <url>"
        )

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


def _make_backend(
    base_config: Optional[dict] = None,
    add_url: Optional[str] = None,
    search_url: Optional[str] = None,
    http_timeout: float = 15.0,
    http_user_id: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    collection_suffix: str = "test",
) -> object:
    """
    Return a memory backend — either a mem0 Memory instance or an HttpMemoryAdapter.

    HTTP mode (add_url + search_url provided): returns HttpMemoryAdapter.
    mem0 mode (base_config provided): returns mem0 Memory.
    """
    if add_url and search_url:
        from zer0lint.http_adapter import HttpMemoryAdapter
        return HttpMemoryAdapter(
            add_url=add_url,
            search_url=search_url,
            timeout=http_timeout,
            user_id=http_user_id,
        )
    return _make_memory(base_config, custom_prompt=custom_prompt, collection_suffix=collection_suffix)


def run_check(
    base_config: Optional[dict] = None,
    verbose: bool = False,
    n_facts: int = 5,
    add_url: Optional[str] = None,
    search_url: Optional[str] = None,
    http_timeout: float = 15.0,
    http_user_id: Optional[str] = None,
    wait_seconds: float = 1.5,
) -> dict:
    """
    Baseline recall test — works with mem0 config or any HTTP memory endpoint.

    Returns dict: score, total, pct, status, details
    """
    is_http = bool(add_url and search_url)

    if verbose:
        if not is_http:
            model = detect_extraction_model(base_config)
            print(f"[CHECK] Using model: {model}")
        print(f"[CHECK] Testing with {n_facts} synthetic facts...")

    memory = _make_backend(
        base_config=base_config,
        add_url=add_url,
        search_url=search_url,
        http_timeout=http_timeout,
        http_user_id=http_user_id,
        collection_suffix="check",
    )
    uid = "zer0lint_check"
    if not is_http:
        cleanup_test_memories(memory, user_id=uid)

    facts = generate_test_facts_for_categories(["technical", "research"], count=n_facts)
    results = validate_extraction_prompt(memory, facts, "", user_id=uid, wait_seconds=wait_seconds)

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
    base_config: Optional[dict] = None,
    config_path: Optional[str | Path] = None,
    verbose: bool = False,
    n_facts: int = 5,
    add_url: Optional[str] = None,
    search_url: Optional[str] = None,
    http_timeout: float = 15.0,
    http_user_id: Optional[str] = None,
    save_prompt_path: Optional[str | Path] = None,
    wait_seconds: float = 1.5,
) -> dict:
    """
    Full zer0lint generate flow (3 phases) — works with mem0 config or HTTP endpoints.

      Phase 1: Baseline recall test
      Phase 2: Re-test with zer0lint technical extraction prompt
      Phase 3: Apply fix — writes to config (mem0 mode) or saves to file (HTTP mode)

    Returns dict with: initial_score, improved_score, improvement_pp, applied, prompt, status
    """
    is_http = bool(add_url and search_url)

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
        "saved_prompt_path": None,
        "verdict": None,
    }

    facts = generate_test_facts_for_categories(["technical", "research"], count=n_facts)
    uid_baseline = "zer0lint_baseline"
    uid_improved = "zer0lint_improved"

    # --- Phase 1: Baseline ---
    if verbose:
        print("\n[1/3] Baseline — testing current config as-is...")

    mem_baseline = _make_backend(
        base_config=base_config,
        add_url=add_url, search_url=search_url,
        http_timeout=http_timeout, http_user_id=http_user_id,
        collection_suffix="baseline",
    )
    if not is_http:
        cleanup_test_memories(mem_baseline, user_id=uid_baseline)
    res_baseline = validate_extraction_prompt(mem_baseline, facts, "", user_id=uid_baseline, wait_seconds=wait_seconds)

    initial_score = res_baseline["score"]
    initial_pct = initial_score / n_facts * 100
    result["initial_score"] = initial_score
    result["initial_pct"] = initial_pct

    if verbose:
        print(f"  Baseline score: {initial_score}/{n_facts} ({initial_pct:.0f}%)")
        for d in res_baseline["details"]:
            icon = "✅" if d["found"] else "❌"
            print(f"    {icon} {d['label']}")

    if initial_score >= n_facts:
        if verbose:
            print("\n✅ Extraction is already perfect. No changes needed.")
        result["success"] = True
        result["verdict"] = "already_healthy"
        result["prompt"] = TECHNICAL_EXTRACTION_PROMPT  # still available via --save-prompt
        return result

    # --- Phase 2: Re-test with zer0lint technical prompt ---
    if verbose:
        print("\n[2/3] Re-testing with zer0lint technical extraction prompt...")

    mem_improved = _make_backend(
        base_config=base_config,
        add_url=add_url, search_url=search_url,
        http_timeout=http_timeout, http_user_id=http_user_id,
        custom_prompt=TECHNICAL_EXTRACTION_PROMPT,
        collection_suffix="improved",
    )
    if not is_http:
        cleanup_test_memories(mem_improved, user_id=uid_improved)
    res_improved = validate_extraction_prompt(mem_improved, facts, "", user_id=uid_improved, wait_seconds=wait_seconds)

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

    # --- Phase 3: Apply ---
    if improvement_pp > 0 and improved_score >= max(initial_score, 4):
        result["verdict"] = "improved"
        if is_http:
            # HTTP mode: no config to write — save prompt to file if requested
            if save_prompt_path:
                p = Path(save_prompt_path)
                p.write_text(TECHNICAL_EXTRACTION_PROMPT)
                result["saved_prompt_path"] = str(p)
                if verbose:
                    print(f"\n[3/3] Prompt saved to {p}")
            else:
                if verbose:
                    print(f"\n[3/3] Use --save-prompt <file> to save the prompt, then add it to your memory system's extraction config.")
        elif config_path:
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
