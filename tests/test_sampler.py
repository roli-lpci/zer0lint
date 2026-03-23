"""Tests for memory sampling."""

from unittest.mock import MagicMock

import pytest

from zer0lint.sampler import MemorySample, analyze_sample_content, sample_memories


def test_memory_sample_model():
    """Test MemorySample dataclass."""
    sample = MemorySample(id="1", content="API runs on port 8421", metadata={"tag": "tech"})
    assert sample.id == "1"
    assert sample.content == "API runs on port 8421"
    assert sample.metadata["tag"] == "tech"


def test_sample_memories_with_search():
    """Test sampling memories via search method."""
    mock_memory = MagicMock()
    mock_memory.search.return_value = [
        {"id": "1", "memory": "API runs on port 8421", "metadata": None},
        {"id": "2", "memory": "Using gpt-4o-mini", "metadata": None},
    ]

    samples = sample_memories(mock_memory, limit=30)

    assert len(samples) == 2
    assert samples[0].id == "1"
    assert "port 8421" in samples[0].content
    mock_memory.search.assert_called_once()


def test_sample_memories_fallback_to_direct():
    """Test fallback to direct store access when search fails."""
    mock_memory = MagicMock()
    mock_memory.search.side_effect = Exception("Search failed")
    mock_memory.vector_store.get_all.return_value = [
        {"id": "1", "content": "Memory 1", "text": None},
        {"id": "2", "content": "Memory 2", "text": None},
    ]

    samples = sample_memories(mock_memory, limit=30)

    assert len(samples) >= 1
    assert samples[0].id == "1"


def test_sample_memories_empty():
    """Test handling empty memories."""
    mock_memory = MagicMock()
    mock_memory.search.return_value = []
    mock_memory.vector_store.get_all.side_effect = Exception("No store")

    samples = sample_memories(mock_memory)

    assert samples == []


def test_analyze_sample_content_technical():
    """Test pattern analysis for technical content."""
    samples = [
        MemorySample(id="1", content="API server runs on port 8421"),
        MemorySample(id="2", content="Updated to gpt-4o-mini model"),
        MemorySample(id="3", content="Redis version 7.2.4 deployed"),
    ]

    patterns = analyze_sample_content(samples)

    assert "technical" in patterns
    assert any(kw in patterns["technical"] for kw in ["port", "version", "model"])


def test_analyze_sample_content_mixed():
    """Test pattern analysis with mixed content."""
    samples = [
        MemorySample(id="1", content="API on port 8421"),
        MemorySample(id="2", content="Diagnosis: acute bronchitis"),
        MemorySample(id="3", content="Contract clause specifies indemnification"),
    ]

    patterns = analyze_sample_content(samples)

    # Should detect multiple domains
    detected_domains = list(patterns.keys())
    assert len(detected_domains) > 0


def test_analyze_sample_content_empty():
    """Test pattern analysis with no samples."""
    patterns = analyze_sample_content([])
    assert patterns == {}
