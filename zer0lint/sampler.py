"""Sample existing memories from mem0 to identify patterns."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MemorySample(BaseModel):
    """A single memory from the user's mem0."""

    id: str
    content: str
    metadata: Optional[dict] = None


def sample_memories(memory: object, limit: int = 30) -> list[MemorySample]:
    """
    Read existing memories from the user's mem0 instance.

    Args:
        memory: mem0.Memory instance (initialized with user's config)
        limit: How many memories to sample (default 30)

    Returns:
        List of MemorySample objects with id, content, metadata

    Notes:
        - Handles graceful degradation if mem0 has no memories yet
        - Tries search-based retrieval first (generic query)
        - Falls back to direct store access if available
        - Returns empty list if no memories exist (expected for new users)
    """
    samples = []

    try:
        # Try: search for generic broad query to pull recent memories
        # This works across all mem0 backends
        search_results = memory.search(
            query="information about system configuration and work",
            limit=limit,
        )
        if search_results:
            # mem0.search() returns list of dicts with 'memory' or 'content' key
            for result in search_results:
                memory_text = result.get("memory") or result.get("content") or str(result)
                samples.append(
                    MemorySample(
                        id=result.get("id", f"search_{len(samples)}"),
                        content=memory_text,
                        metadata=result.get("metadata"),
                    )
                )
    except Exception as e:
        print(f"[sampler] Search-based retrieval failed: {e}")

    # If search failed or returned few results, try direct store access
    if len(samples) < limit // 2:
        try:
            # Some backends expose .vector_store.get_all() or similar
            if hasattr(memory, "vector_store") and hasattr(memory.vector_store, "get_all"):
                all_items = memory.vector_store.get_all()
                for item in all_items[: limit - len(samples)]:
                    samples.append(
                        MemorySample(
                            id=item.get("id", f"direct_{len(samples)}"),
                            content=item.get("content") or item.get("text") or str(item),
                        )
                    )
        except Exception as e:
            print(f"[sampler] Direct store access failed: {e}")

    return samples


def analyze_sample_content(samples: list[MemorySample]) -> dict[str, list[str]]:
    """
    Simple pattern recognition on sample memories.

    Identifies common keywords/themes without calling an LLM.
    Useful for bootstrapping when LLM analysis is unavailable.

    Returns dict of {"category": [sample_keywords, ...]}
    """
    if not samples:
        return {}

    # Combine all sample text
    combined_text = " ".join(s.content for s in samples).lower()

    # Pattern keywords for common categories
    patterns = {
        "technical": [
            "port",
            "version",
            "api",
            "endpoint",
            "model",
            "config",
            "package",
            "benchmark",
            "ci",
            "deployment",
            "git",
            "commit",
            "code",
        ],
        "research": [
            "hypothesis",
            "experiment",
            "finding",
            "dataset",
            "methodology",
            "paper",
            "citation",
            "result",
            "study",
            "evidence",
        ],
        "medical": [
            "symptom",
            "diagnosis",
            "medication",
            "treatment",
            "patient",
            "procedure",
            "test",
            "result",
            "clinical",
            "medical",
        ],
        "legal": [
            "clause",
            "contract",
            "party",
            "obligation",
            "deadline",
            "statute",
            "regulation",
            "agreement",
            "legal",
            "law",
        ],
        "financial": [
            "amount",
            "rate",
            "ticker",
            "position",
            "transaction",
            "budget",
            "price",
            "investment",
            "risk",
            "financial",
        ],
    }

    results = {}
    for category, keywords in patterns.items():
        found_keywords = [kw for kw in keywords if kw in combined_text]
        if found_keywords:
            results[category] = found_keywords

    return results
