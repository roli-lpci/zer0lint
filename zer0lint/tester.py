"""Generate synthetic test facts and validate extraction quality."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class TestFact:
    """A synthetic fact used to test extraction quality."""

    label: str
    text: str
    keywords: list[str]


def generate_test_facts_for_categories(categories: list[str], count: int = 5) -> list[TestFact]:
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
            TestFact(
                label="API endpoint",
                text="The API service runs on port 8421 with TLS 1.3 enabled.",
                keywords=["8421", "port", "api"],
            ),
            TestFact(
                label="Model upgrade",
                text="We switched from gpt-3.5-turbo to gpt-4o-mini to reduce token costs by 40%.",
                keywords=["gpt-4o-mini", "model", "tokens"],
            ),
            TestFact(
                label="Version update",
                text="Updated Redis cluster to v7.2.4 with improved persistence.",
                keywords=["7.2.4", "redis", "version"],
            ),
            TestFact(
                label="CI status",
                text="CI pipeline passed on 2026-03-22 at commit a3f8c12.",
                keywords=["2026-03-22", "ci", "passed"],
            ),
            TestFact(
                label="Configuration",
                text="Auth tokens expire after 3600 seconds; max connections set to 500.",
                keywords=["3600", "token", "config"],
            ),
        ],
        "research": [
            TestFact(
                label="Hypothesis",
                text="We hypothesize that embedding-based routing reduces inference latency by 60%.",
                keywords=["hypothesis", "embedding", "latency"],
            ),
            TestFact(
                label="Finding",
                text="Our experiments show null-result bias affects 19.6-56.7pp of LLM outputs across domains.",
                keywords=["finding", "null-result", "bias"],
            ),
            TestFact(
                label="Dataset",
                text="We use Banking77 (77 classes, 3080 queries) for classification benchmarking.",
                keywords=["banking77", "dataset", "classes"],
            ),
            TestFact(
                label="Methodology",
                text="Twin-environment simulation allows testing without production access.",
                keywords=["methodology", "simulation", "test"],
            ),
            TestFact(
                label="Citation",
                text="See Wittgenstein's Philosophical Investigations (1953) on language games.",
                keywords=["citation", "wittgenstein", "1953"],
            ),
        ],
        "medical": [
            TestFact(
                label="Symptom",
                text="Patient reported fever (39.2°C), headache, and fatigue for 3 days.",
                keywords=["fever", "symptom", "temperature"],
            ),
            TestFact(
                label="Diagnosis",
                text="Diagnosed with acute bronchitis based on chest X-ray and clinical presentation.",
                keywords=["diagnosis", "bronchitis", "x-ray"],
            ),
            TestFact(
                label="Medication",
                text="Prescribed amoxicillin 500mg three times daily for 10 days.",
                keywords=["amoxicillin", "medication", "dosage"],
            ),
            TestFact(
                label="Test result",
                text="Blood glucose level: 112 mg/dL (normal range 70-100).",
                keywords=["glucose", "test", "112"],
            ),
            TestFact(
                label="Procedure",
                text="Performed lumbar puncture to collect cerebrospinal fluid for analysis.",
                keywords=["lumbar", "procedure", "csf"],
            ),
        ],
        "legal": [
            TestFact(
                label="Contract clause",
                text="Section 3.2 specifies indemnification obligations for both parties.",
                keywords=["clause", "section", "indemnification"],
            ),
            TestFact(
                label="Deadline",
                text="Closing date for acquisition is June 30, 2026.",
                keywords=["deadline", "closing", "2026-06-30"],
            ),
            TestFact(
                label="Statute",
                text="This is governed by the Commercial Code Section 2-501 (Risk of Loss).",
                keywords=["statute", "commercial", "2-501"],
            ),
            TestFact(
                label="Party information",
                text="Seller: Acme Corp (Delaware corporation); Buyer: TechStart Inc (California).",
                keywords=["party", "seller", "buyer"],
            ),
            TestFact(
                label="Obligation",
                text="Buyer must complete due diligence within 45 days of execution.",
                keywords=["obligation", "due diligence", "45"],
            ),
        ],
        "financial": [
            TestFact(
                label="Transaction",
                text="Invested $50,000 in NVDA shares at $875.42 on 2026-03-20.",
                keywords=["50000", "nvda", "transaction"],
            ),
            TestFact(
                label="Rate",
                text="Fixed rate mortgage: 4.85% for 30 years, payment $2,145/month.",
                keywords=["4.85%", "rate", "mortgage"],
            ),
            TestFact(
                label="Position",
                text="Current portfolio: 40% stocks, 35% bonds, 15% cash, 10% alternatives.",
                keywords=["position", "40%", "portfolio"],
            ),
            TestFact(
                label="Risk parameter",
                text="Set stop-loss at 15% below entry; take-profit at 30%.",
                keywords=["risk", "stop-loss", "15%"],
            ),
            TestFact(
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
            TestFact(
                label="Generic fact",
                text="This is a test fact to validate extraction is working.",
                keywords=["test", "fact"],
            )
        ]

    return test_facts[:count]


def test_extraction_prompt(
    memory: object, test_facts: list[TestFact], extraction_prompt: str
) -> dict:
    """
    Test an extraction prompt against synthetic facts.

    Args:
        memory: mem0.Memory instance with the prompt configured
        test_facts: List of TestFact objects to test
        extraction_prompt: The prompt to test

    Returns:
        Dict with score (int), total (int), results (list of bool per fact)
    """
    results = {"score": 0, "total": len(test_facts), "results": [], "failures": []}

    for fact in test_facts:
        # Add the test fact
        try:
            memory.add(fact.text, user_id="zer0lint_test_user")
        except Exception as e:
            results["failures"].append(f"add({fact.label}): {e}")
            results["results"].append(False)
            continue

        # Try to retrieve it using keywords
        found = False
        try:
            search_results = memory.search(
                query=" ".join(fact.keywords), limit=5, user_id="zer0lint_test_user"
            )
            if search_results:
                for result in search_results:
                    memory_text = result.get("memory") or result.get("content") or ""
                    # Check if any keyword appears in the result
                    if any(kw.lower() in memory_text.lower() for kw in fact.keywords):
                        found = True
                        break
        except Exception as e:
            results["failures"].append(f"search({fact.label}): {e}")

        results["results"].append(found)
        if found:
            results["score"] += 1

    return results
