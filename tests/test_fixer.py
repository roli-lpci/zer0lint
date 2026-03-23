"""Tests for config application and backup."""

import json
import tempfile
from pathlib import Path

import pytest

from zer0lint.fixer import (
    apply_prompt,
    backup_config,
    detect_extraction_model,
    detect_vector_store,
)


def test_backup_config():
    """Test config backup creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config_path.write_text('{"test": "data"}')

        backup_path = backup_config(config_path)

        assert Path(backup_path).exists()
        assert "backup" in backup_path


def test_apply_prompt_new():
    """Test applying a new prompt to config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config = {
            "llm": {"provider": "ollama"},
            "custom_fact_extraction_prompt": "old prompt",
        }
        config_path.write_text(json.dumps(config))

        result = apply_prompt(config_path, "new prompt", backup=True)

        assert result["success"] is True
        assert result["backup_path"] is not None

        # Verify new prompt was written
        updated = json.loads(config_path.read_text())
        assert updated["custom_fact_extraction_prompt"] == "new prompt"


def test_apply_prompt_no_backup():
    """Test applying prompt without backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        config_path.write_text('{"custom_fact_extraction_prompt": "old"}')

        result = apply_prompt(config_path, "new", backup=False)

        assert result["success"] is True
        assert result["backup_path"] is None


def test_apply_prompt_file_not_found():
    """Test error handling for missing config."""
    with pytest.raises(FileNotFoundError):
        apply_prompt("/nonexistent/path/config.json", "new prompt")


def test_detect_extraction_model_ollama():
    """Test model detection for Ollama config."""
    config = {
        "llm": {
            "provider": "ollama",
            "config": {"model": "mistral:7b", "ollama_base_url": "http://localhost:11434"},
        }
    }

    model = detect_extraction_model(config)

    assert model == "mistral:7b"


def test_detect_extraction_model_openai():
    """Test model detection for OpenAI config."""
    config = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
        }
    }

    model = detect_extraction_model(config)

    assert model == "gpt-4o"


def test_detect_extraction_model_unknown():
    """Test fallback for unknown config structure."""
    config = {"llm": {}}

    model = detect_extraction_model(config)

    assert model == "unknown"


def test_detect_vector_store_chroma():
    """Test vector store detection for Chroma."""
    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {"collection_name": "mem0", "path": ".mem0_chroma"},
        }
    }

    store = detect_vector_store(config)

    assert store == "chroma"


def test_detect_vector_store_qdrant():
    """Test vector store detection for Qdrant."""
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {"collection_name": "mem0", "url": "http://localhost:6333"},
        }
    }

    store = detect_vector_store(config)

    assert store == "qdrant"


def test_detect_vector_store_unknown():
    """Test fallback for unknown vector store."""
    config = {"vector_store": {}}

    store = detect_vector_store(config)

    assert store == "unknown"
