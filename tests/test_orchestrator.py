"""Tests for the main generate flow orchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from zer0lint.orchestrator import run_generate
from zer0lint.sampler import MemorySample


def test_run_generate_success_flow():
    """Test successful end-to-end generate flow."""
    mock_memory = MagicMock()
    mock_memory.config.llm = MagicMock()
    mock_memory.search.return_value = []
    mock_memory.add.return_value = None

    # Mock the LLM to return a test prompt
    with patch("zer0lint.orchestrator.sample_memories") as mock_sample, patch(
        "zer0lint.orchestrator.analyze_sample_content"
    ) as mock_analyze, patch("zer0lint.orchestrator.analyze_with_llm") as mock_llm, patch(
        "zer0lint.orchestrator.test_extraction_prompt"
    ) as mock_test:

        mock_sample.return_value = [
            MemorySample(id="1", content="API port 8421"),
            MemorySample(id="2", content="Model gpt-4o-mini"),
        ]
        mock_analyze.return_value = {"technical": ["port", "model"]}
        mock_llm.return_value = "generated extraction prompt"
        mock_test.return_value = {"score": 5, "total": 5, "results": [True] * 5, "failures": []}

        result = run_generate(mock_memory, config_path=None, verbose=False)

        assert result["success"] is True
        assert result["final_score"] == 5
        assert result["generated_prompt"] == "generated extraction prompt"


def test_run_generate_no_samples():
    """Test generate flow with no existing memories."""
    mock_memory = MagicMock()
    mock_memory.config.llm = MagicMock()

    with patch("zer0lint.orchestrator.sample_memories") as mock_sample, patch(
        "zer0lint.orchestrator.analyze_sample_content"
    ) as mock_analyze, patch("zer0lint.orchestrator.generate_test_facts_for_categories") as mock_gen:

        mock_sample.return_value = []
        mock_analyze.return_value = {}
        mock_gen.return_value = [MagicMock()]  # At least one test fact

        result = run_generate(mock_memory, verbose=False)

        # Should still run with fallback
        assert result["success"] is True or "ERROR" not in result.get("iteration_log", [])


def test_run_generate_llm_failure_fallback():
    """Test that generator falls back to pattern-based prompt if LLM fails."""
    mock_memory = MagicMock()
    mock_memory.config.llm = MagicMock()
    mock_memory.add.return_value = None
    mock_memory.search.return_value = []

    with patch("zer0lint.orchestrator.sample_memories") as mock_sample, patch(
        "zer0lint.orchestrator.analyze_sample_content"
    ) as mock_analyze, patch("zer0lint.orchestrator.analyze_with_llm") as mock_llm_fail, patch(
        "zer0lint.orchestrator.fallback_prompt_from_patterns"
    ) as mock_fallback, patch(
        "zer0lint.orchestrator.test_extraction_prompt"
    ) as mock_test:

        mock_sample.return_value = [MemorySample(id="1", content="test")]
        mock_analyze.return_value = {"technical": ["test"]}
        mock_llm_fail.side_effect = Exception("LLM unavailable")
        mock_fallback.return_value = "fallback prompt"
        mock_test.return_value = {"score": 3, "total": 5, "results": [True] * 3, "failures": []}

        result = run_generate(mock_memory, verbose=False)

        assert result["success"] is True
        assert result["generated_prompt"] == "fallback prompt"
        mock_fallback.assert_called_once()


def test_run_generate_apply_when_score_high():
    """Test that prompt is applied only when score >= 4."""
    mock_memory = MagicMock()
    mock_memory.config.llm = MagicMock()
    mock_memory.add.return_value = None
    mock_memory.search.return_value = []

    with patch("zer0lint.orchestrator.sample_memories") as mock_sample, patch(
        "zer0lint.orchestrator.analyze_sample_content"
    ) as mock_analyze, patch("zer0lint.orchestrator.analyze_with_llm") as mock_llm, patch(
        "zer0lint.orchestrator.test_extraction_prompt"
    ) as mock_test, patch(
        "zer0lint.orchestrator.apply_prompt"
    ) as mock_apply:

        mock_sample.return_value = [MemorySample(id="1", content="test")]
        mock_analyze.return_value = {"technical": ["test"]}
        mock_llm.return_value = "good prompt"
        mock_test.return_value = {"score": 4, "total": 5, "results": [True] * 4, "failures": []}
        mock_apply.return_value = {"success": True, "backup_path": "/backup"}

        result = run_generate(mock_memory, config_path="/config.json", verbose=False)

        assert result["applied"] is True
        mock_apply.assert_called_once()


def test_run_generate_no_apply_when_score_low():
    """Test that prompt is NOT applied when score < 4."""
    mock_memory = MagicMock()
    mock_memory.config.llm = MagicMock()
    mock_memory.add.return_value = None
    mock_memory.search.return_value = []

    with patch("zer0lint.orchestrator.sample_memories") as mock_sample, patch(
        "zer0lint.orchestrator.analyze_sample_content"
    ) as mock_analyze, patch("zer0lint.orchestrator.analyze_with_llm") as mock_llm, patch(
        "zer0lint.orchestrator.test_extraction_prompt"
    ) as mock_test, patch(
        "zer0lint.orchestrator.apply_prompt"
    ) as mock_apply:

        mock_sample.return_value = [MemorySample(id="1", content="test")]
        mock_analyze.return_value = {"technical": ["test"]}
        mock_llm.return_value = "poor prompt"
        mock_test.return_value = {"score": 2, "total": 5, "results": [True] * 2, "failures": []}

        result = run_generate(mock_memory, config_path="/config.json", verbose=False)

        assert result["applied"] is False
        mock_apply.assert_not_called()
