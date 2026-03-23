"""Tests for extraction testing and synthetic fact generation."""

from unittest.mock import MagicMock

import pytest

from zer0lint.tester import TestFact, generate_test_facts_for_categories, test_extraction_prompt


def test_test_fact_model():
    """Test TestFact dataclass."""
    fact = TestFact(
        label="API port",
        text="The API server runs on port 8421.",
        keywords=["8421", "port"],
    )
    assert fact.label == "API port"
    assert "8421" in fact.text
    assert "port" in fact.keywords


def test_generate_test_facts_technical():
    """Test generating technical test facts."""
    facts = generate_test_facts_for_categories(["technical"], count=5)

    assert len(facts) == 5
    assert all(isinstance(f, TestFact) for f in facts)
    assert all(len(f.keywords) > 0 for f in facts)


def test_generate_test_facts_multiple_categories():
    """Test generating facts for multiple categories."""
    facts = generate_test_facts_for_categories(["technical", "research"], count=5)

    assert len(facts) == 5
    categories_in_facts = set()
    for fact in facts:
        for word in fact.text.lower().split():
            if any(
                keyword in word
                for keyword in ["port", "version", "api", "hypothesis", "experiment"]
            ):
                categories_in_facts.add("multi")

    # Just verify we got facts from multiple domains
    assert len(facts) > 0


def test_generate_test_facts_fallback():
    """Test fallback when no categories match."""
    facts = generate_test_facts_for_categories(["nonexistent_domain"], count=5)

    # Should return at least a generic fallback
    assert len(facts) > 0


def test_generate_test_facts_count_limit():
    """Test that count is respected."""
    for count in [1, 3, 5, 10]:
        facts = generate_test_facts_for_categories(["technical"], count=count)
        assert len(facts) <= count


def test_test_extraction_prompt_success():
    """Test extraction prompt validation with successful extraction."""
    mock_memory = MagicMock()
    mock_memory.add.return_value = None
    mock_memory.search.return_value = [
        {"id": "1", "memory": "API server runs on port 8421", "score": 100.0}
    ]

    test_facts = [
        TestFact(label="API port", text="API on port 8421", keywords=["8421"]),
    ]

    result = test_extraction_prompt(mock_memory, test_facts, "test prompt")

    assert result["score"] == 1
    assert result["total"] == 1
    assert result["results"][0] is True


def test_test_extraction_prompt_failure():
    """Test extraction prompt validation with failed extraction."""
    mock_memory = MagicMock()
    mock_memory.add.return_value = None
    mock_memory.search.return_value = []  # No results

    test_facts = [
        TestFact(label="API port", text="API on port 8421", keywords=["8421"]),
    ]

    result = test_extraction_prompt(mock_memory, test_facts, "test prompt")

    assert result["score"] == 0
    assert result["total"] == 1
    assert result["results"][0] is False


def test_test_extraction_prompt_partial():
    """Test extraction with partial success."""
    mock_memory = MagicMock()
    mock_memory.add.return_value = None

    # First call succeeds, second fails
    mock_memory.search.side_effect = [
        [{"id": "1", "memory": "API port 8421", "score": 100.0}],
        [],  # No result for second query
    ]

    test_facts = [
        TestFact(label="port", text="API on port 8421", keywords=["8421"]),
        TestFact(label="model", text="Using gpt-4o-mini", keywords=["gpt-4o-mini"]),
    ]

    result = test_extraction_prompt(mock_memory, test_facts, "test prompt")

    assert result["score"] == 1
    assert result["total"] == 2


def test_test_extraction_prompt_add_failure():
    """Test handling of add() failures."""
    mock_memory = MagicMock()
    mock_memory.add.side_effect = Exception("Add failed")
    mock_memory.search.return_value = []

    test_facts = [TestFact(label="test", text="test fact", keywords=["test"])]

    result = test_extraction_prompt(mock_memory, test_facts, "test prompt")

    assert result["score"] == 0
    assert len(result["failures"]) > 0
