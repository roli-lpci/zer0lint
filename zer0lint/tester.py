"""Generate synthetic test facts and validate extraction quality."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class SyntheticFact:
    """A synthetic fact used to test extraction quality."""

    label: str
    text: str
    keywords: list[str]


def generate_test_facts_for_categories(categories: list[str], count: int = 5) -> list[SyntheticFact]:
    """
    Generate synthetic test facts matching detected categories.

    Args:
        categories: List of domain categories (e.g., ["technical", "research"])
        count: Number of facts to generate (default 5)

    Returns:
        List of TestFact objects with label, text, keywords
    """
    # Category-specific fact generators
    generators = {
        "technical": [
            SyntheticFact(
                label="API endpoint",
                text="The API service runs on port 8421 with TLS 1.3 enabled.",
                keywords=["8421", "port", "api"],
            ),
            SyntheticFact(
                label="Model upgrade",
                text="We switched from gpt-3.5-turbo to gpt-4o-mini to reduce token costs by 40%.",
                keywords=["gpt-4o-mini", "model", "tokens"],
            ),
            SyntheticFact(
                label="Version update",
                text="Updated Redis cluster to v7.2.4 with improved persistence.",
                keywords=["7.2.4", "redis", "version"],
            ),
            SyntheticFact(
                label="CI status",
                text="CI pipeline passed on 2026-03-22 at commit a3f8c12.",
                keywords=["2026-03-22", "ci", "passed"],
            ),
            SyntheticFact(
                label="Configuration",
                text="Auth tokens expire after 3600 seconds; max connections set to 500.",
                keywords=["3600", "token", "config"],
            ),
        ],
        "research": [
            SyntheticFact(
                label="Hypothesis",
                text="We hypothesize that embedding-based routing reduces inference latency by 60%.",
                keywords=["hypothesis", "embedding", "latency"],
            ),
            SyntheticFact(
                label="Finding",
                text="Our experiments show null-result bias affects 19.6-56.7pp of LLM outputs across domains.",
                keywords=["finding", "null-result", "bias"],
            ),
            SyntheticFact(
                label="Dataset",
                text="We use Banking77 (77 classes, 3080 queries) for classification benchmarking.",
                keywords=["banking77", "dataset", "classes"],
            ),
            SyntheticFact(
                label="Methodology",
                text="Twin-environment simulation allows testing without production access.",
                keywords=["methodology", "simulation", "test"],
            ),
            SyntheticFact(
                label="Citation",
                text="See Wittgenstein's Philosophical Investigations (1953) on language games.",
                keywords=["citation", "wittgenstein", "1953"],
            ),
        ],
        "medical": [
            SyntheticFact(
                label="Symptom",
                text="Patient reported fever (39.2°C), headache, and fatigue for 3 days.",
                keywords=["fever", "symptom", "temperature"],
            ),
            SyntheticFact(
                label="Diagnosis",
                text="Diagnosed with acute bronchitis based on chest X-ray and clinical presentation.",
                keywords=["diagnosis", "bronchitis", "x-ray"],
            ),
            SyntheticFact(
                label="Medication",
                text="Prescribed amoxicillin 500mg three times daily for 10 days.",
                keywords=["amoxicillin", "medication", "dosage"],
            ),
            SyntheticFact(
                label="Test result",
                text="Blood glucose level: 112 mg/dL (normal range 70-100).",
                keywords=["glucose", "test", "112"],
            ),
            SyntheticFact(
                label="Procedure",
                text="Performed lumbar puncture to collect cerebrospinal fluid for analysis.",
                keywords=["lumbar", "procedure", "csf"],
            ),
        ],
        "legal": [
            SyntheticFact(
                label="Contract clause",
                text="Section 3.2 specifies indemnification obligations for both parties.",
                keywords=["clause", "section", "indemnification"],
            ),
            SyntheticFact(
                label="Deadline",
                text="Closing date for acquisition is June 30, 2026.",
                keywords=["deadline", "closing", "2026-06-30"],
            ),
            SyntheticFact(
                label="Statute",
                text="This is governed by the Commercial Code Section 2-501 (Risk of Loss).",
                keywords=["statute", "commercial", "2-501"],
            ),
            SyntheticFact(
                label="Party information",
                text="Seller: Acme Corp (Delaware corporation); Buyer: TechStart Inc (California).",
                keywords=["party", "seller", "buyer"],
            ),
            SyntheticFact(
                label="Obligation",
                text="Buyer must complete due diligence within 45 days of execution.",
                keywords=["obligation", "due diligence", "45"],
            ),
        ],
        "financial": [
            SyntheticFact(
                label="Transaction",
                text="Invested $50,000 in NVDA shares at $875.42 on 2026-03-20.",
                keywords=["50000", "nvda", "transaction"],
            ),
            SyntheticFact(
                label="Rate",
                text="Fixed rate mortgage: 4.85% for 30 years, payment $2,145/month.",
                keywords=["4.85%", "rate", "mortgage"],
            ),
            SyntheticFact(
                label="Position",
                text="Current portfolio: 40% stocks, 35% bonds, 15% cash, 10% alternatives.",
                keywords=["position", "40%", "portfolio"],
            ),
            SyntheticFact(
                label="Risk parameter",
                text="Set stop-loss at 15% below entry; take-profit at 30%.",
                keywords=["risk", "stop-loss", "15%"],
            ),
            SyntheticFact(
                label="Budget item",
                text="Marketing spend budgeted at $250K for Q2 2026.",
                keywords=["budget", "250k", "marketing"],
            ),
        ],
    }

    test_facts = []
    for category in categories:
        if category in generators:
            # Pick `count` random facts from this category
            available = generators[category]
            selected = random.sample(available, min(count, len(available)))
            test_facts.extend(selected)

    # If no categories matched, use a generic fallback
    if not test_facts:
        test_facts = [
            SyntheticFact(
                label="Generic fact",
                text="This is a test fact to validate extraction is working.",
                keywords=["test", "fact"],
            )
        ]

    return test_facts[:count]


def _extract_memory_text(result: object) -> str:
    """Safely extract text from a mem0 result (handles v1.x dict format)."""
    if isinstance(result, dict):
        return result.get("memory") or result.get("content") or str(result)
    return str(result)


def _get_results_list(response: object) -> list:
    """Unwrap mem0 v1.x response dict or return list as-is."""
    if isinstance(response, dict):
        return response.get("results", [])
    if isinstance(response, list):
        return response
    return []


def validate_extraction_prompt(
    memory: object,
    test_facts: list[SyntheticFact],
    extraction_prompt: str,
    user_id: str = "zer0lint_test_user",
    wait_seconds: float = 1.0,
) -> dict:
    """
    Test extraction quality against synthetic facts.

    Compatible with mem0 v1.x (returns {"results": [...]}).

    Args:
        memory: mem0.Memory instance
        test_facts: List of SyntheticFact objects to test
        extraction_prompt: Optional extraction prompt to inject per add() call
        user_id: Isolated user_id for test isolation (don't pollute prod data)
        wait_seconds: Seconds to wait after add() before searching (async lag)

    Returns:
        Dict with score, total, results (per-fact bool), failures, details
    """
    import time

    results = {
        "score": 0,
        "total": len(test_facts),
        "results": [],
        "failures": [],
        "details": [],
    }

    prompt_kwargs = {}
    if extraction_prompt:
        prompt_kwargs["prompt"] = extraction_prompt

    for fact in test_facts:
        detail = {"label": fact.label, "text": fact.text, "stored": False, "found": False}

        # Store the fact
        try:
            memory.add(fact.text, user_id=user_id, **prompt_kwargs)
            detail["stored"] = True
        except Exception as e:
            err = f"add({fact.label}): {str(e)[:80]}"
            results["failures"].append(err)
            detail["error"] = err
            results["results"].append(False)
            results["details"].append(detail)
            continue

        # Brief wait for async extraction
        if wait_seconds > 0:
            time.sleep(wait_seconds)

        # Search for it back
        found = False
        try:
            response = memory.search(
                query=" ".join(fact.keywords),
                user_id=user_id,
                limit=10,
            )
            search_results = _get_results_list(response)
            for result in search_results:
                memory_text = _extract_memory_text(result)
                if any(kw.lower() in memory_text.lower() for kw in fact.keywords):
                    found = True
                    detail["matched_memory"] = memory_text[:120]
                    break
        except Exception as e:
            err = f"search({fact.label}): {str(e)[:80]}"
            results["failures"].append(err)
            detail["search_error"] = err

        detail["found"] = found
        results["results"].append(found)
        results["details"].append(detail)
        if found:
            results["score"] += 1

    return results


def count_stored_memories(memory: object, user_id: str = "zer0lint_test_user") -> int:
    """Return count of stored memories for a user_id (mem0 v1.x safe)."""
    try:
        response = memory.get_all(user_id=user_id)
        return len(_get_results_list(response))
    except Exception:
        return -1


def cleanup_test_memories(memory: object, user_id: str = "zer0lint_test_user") -> int:
    """Delete all test memories for isolation. Returns count deleted."""
    deleted = 0
    try:
        response = memory.get_all(user_id=user_id)
        memories = _get_results_list(response)
        for m in memories:
            mem_id = m.get("id") if isinstance(m, dict) else None
            if mem_id:
                try:
                    memory.delete(memory_id=mem_id)
                    deleted += 1
                except Exception:
                    pass
    except Exception:
        pass
    return deleted
