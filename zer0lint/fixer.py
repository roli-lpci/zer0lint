"""Apply generated extraction prompts to mem0 config."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


def backup_config(config_path: str | Path) -> str:
    """
    Backup the current config before modifying.

    Args:
        config_path: Path to mem0 config file

    Returns:
        Path to backup file
    """
    config_path = Path(config_path)
    backup_path = config_path.parent / f"{config_path.stem}.backup.{datetime.now().isoformat()}"
    shutil.copy2(config_path, backup_path)
    return str(backup_path)


def apply_prompt(
    config_path: str | Path, new_prompt: str, backup: bool = True
) -> dict:
    """
    Apply a new extraction prompt to mem0 config file.

    Args:
        config_path: Path to mem0 config.json
        new_prompt: The new extraction prompt to set
        backup: Whether to backup the original config (default True)

    Returns:
        Dict with keys: success (bool), backup_path (str), config_path (str), changes (dict)
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    # Read current config
    with open(config_path) as f:
        config = json.load(f)

    # Backup
    backup_path = None
    if backup:
        backup_path = backup_config(config_path)

    # Record the old prompt for comparison
    old_prompt = config.get("custom_fact_extraction_prompt", "(none)")

    # Apply new prompt
    config["custom_fact_extraction_prompt"] = new_prompt

    # Write back
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "success": True,
        "config_path": str(config_path),
        "backup_path": backup_path,
        "changes": {
            "field": "custom_fact_extraction_prompt",
            "old_length": len(old_prompt),
            "new_length": len(new_prompt),
        },
    }


def detect_extraction_model(config: dict) -> str:
    """
    Detect which LLM is configured for extraction in mem0 config.

    Args:
        config: Parsed mem0 config dict

    Returns:
        String describing the extraction model (e.g., "mistral:7b", "gpt-4o", "unknown")
    """
    # Most configs have an llm.config.model field
    llm_config = config.get("llm", {})
    if isinstance(llm_config, dict):
        if "config" in llm_config:
            model = llm_config["config"].get("model")
            if model:
                return model
        if "model" in llm_config:
            return llm_config["model"]

    return "unknown"


def detect_vector_store(config: dict) -> str:
    """
    Detect which vector store is configured in mem0.

    Args:
        config: Parsed mem0 config dict

    Returns:
        String describing the vector store (e.g., "chroma", "qdrant", "unknown")
    """
    vs_config = config.get("vector_store", {})
    if isinstance(vs_config, dict):
        provider = vs_config.get("provider")
        if provider:
            return provider
    return "unknown"
