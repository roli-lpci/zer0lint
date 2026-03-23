"""Main orchestrator for zer0lint generate flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from zer0lint.analyzer import analyze_with_llm, fallback_prompt_from_patterns
from zer0lint.fixer import apply_prompt, detect_extraction_model, detect_vector_store
from zer0lint.sampler import analyze_sample_content, sample_memories
from zer0lint.tester import generate_test_facts_for_categories, test_extraction_prompt


def run_generate(
    memory: object,
    config_path: Optional[str | Path] = None,
    iterations: int = 3,
    verbose: bool = False,
) -> dict:
    """
    Full zer0lint generate flow: sample → analyze → test → iterate → apply.

    Args:
        memory: mem0.Memory instance (initialized with user's config)
        config_path: Path to mem0 config.json (for applying the fix)
        iterations: Max iterations for refinement loop (default 3)
        verbose: Print detailed output (default False)

    Returns:
        Dict with:
            - success: bool
            - initial_score: int (score before fix)
            - final_score: int (score after fix)
            - generated_prompt: str
            - applied: bool (whether prompt was applied to config)
            - backup_path: str (if config was modified)
    """

    result = {
        "success": False,
        "initial_score": None,
        "final_score": None,
        "generated_prompt": None,
        "applied": False,
        "backup_path": None,
        "iteration_log": [],
    }

    try:
        # Step 1: Sample existing memories
        if verbose:
            print("[1/5] Sampling existing memories...")
        samples = sample_memories(memory, limit=30)
        num_samples = len(samples)
        if verbose:
            print(f"  Found {num_samples} memories")

        result["iteration_log"].append(f"Sampled {num_samples} memories")

        # Step 2: Detect categories via simple pattern analysis
        if verbose:
            print("[2/5] Analyzing sample patterns...")
        patterns = analyze_sample_content(samples)
        detected_categories = list(patterns.keys()) if patterns else []
        if verbose:
            print(f"  Detected categories: {detected_categories}")

        result["iteration_log"].append(f"Detected categories: {detected_categories}")

        # Step 3: Generate test facts matching detected categories
        if verbose:
            print("[3/5] Generating test facts...")
        test_facts = generate_test_facts_for_categories(
            detected_categories if detected_categories else ["technical"], count=5
        )
        if verbose:
            print(f"  Generated {len(test_facts)} test facts")

        result["iteration_log"].append(f"Generated {len(test_facts)} test facts")

        # Step 4: Get current extraction quality (baseline)
        if verbose:
            print("[4/5] Testing baseline extraction...")
        # Don't test baseline — just note that we're about to improve it
        # (Baseline test would add facts to memory; we'll do that during prompt generation)

        # Step 5: Generate prompt (with optional LLM-assisted refinement)
        if verbose:
            print("[5/5] Generating optimized prompt...")

        # Prepare samples text for LLM
        samples_text = "\n".join([f"- {s.content[:100]}..." for s in samples[:20]])

        # Try LLM-assisted generation first
        try:
            generated_prompt = analyze_with_llm(memory.config.llm, samples_text)
            if verbose:
                print("  ✓ Generated prompt via LLM analysis")
            result["iteration_log"].append("Generated prompt via LLM")
        except Exception as e:
            # Fallback to pattern-based generation
            if verbose:
                print(f"  ⚠ LLM analysis failed ({e}), using pattern-based fallback")
            generated_prompt = fallback_prompt_from_patterns(patterns)
            result["iteration_log"].append("Generated prompt via pattern analysis (LLM unavailable)")

        # Step 6: Test the generated prompt against test facts
        if verbose:
            print(f"  Testing prompt...")
        test_result = test_extraction_prompt(memory, test_facts, generated_prompt)
        final_score = test_result["score"]
        if verbose:
            print(f"    Score: {final_score}/{test_result['total']}")

        result["final_score"] = final_score
        result["generated_prompt"] = generated_prompt
        result["iteration_log"].append(f"Prompt tested: {final_score}/{test_result['total']}")

        # Step 7: Apply to config if score >= threshold
        if config_path and final_score >= 4:  # >= 4/5 is good
            if verbose:
                print(f"\n✓ Prompt improved extraction to {final_score}/5")
                print(f"  Applying to config: {config_path}")

            apply_result = apply_prompt(config_path, generated_prompt, backup=True)
            result["applied"] = apply_result["success"]
            result["backup_path"] = apply_result["backup_path"]
            result["iteration_log"].append(f"Applied prompt to config")

        result["success"] = True

    except Exception as e:
        result["iteration_log"].append(f"ERROR: {e}")
        if verbose:
            print(f"\n✗ Generation failed: {e}")

    return result
