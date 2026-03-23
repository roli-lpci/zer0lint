"""Analyze memory samples to identify domain patterns and generate extraction prompt."""

from __future__ import annotations

import json
from typing import Optional


def analyze_with_llm(
    llm: object, samples_text: str, existing_prompt: Optional[str] = None
) -> str:
    """
    Use an LLM to analyze memory samples and generate a domain-specific extraction prompt.

    Args:
        llm: mem0's configured LLM instance (any provider: Ollama, OpenAI, etc.)
        samples_text: Combined text of 20-30 memory samples
        existing_prompt: Current extraction prompt (to avoid regression)

    Returns:
        A domain-specific extraction prompt tailored to the user's actual data
    """

    analysis_prompt = f"""You are an expert at designing data extraction prompts for AI memory systems.

A user has a memory system (mem0) that stores facts from their work and interactions.
These are their actual recent memories:

---
{samples_text}
---

Based on these memories, your task is to:

1. Identify 5-8 PRIMARY CATEGORIES of information they need to remember
   (e.g., "code decisions", "version numbers", "test results", etc.)

2. For each category, identify the most important KEYWORDS that signal that type of information

3. Design a focused extraction prompt that will capture facts matching these categories

The prompt should:
- Be specific to their actual work (not generic)
- Include concrete examples (Input → Output in JSON)
- Use clear categories with descriptions
- End with "Return facts as JSON with key \\"facts\\" and a list of strings."

Return ONLY the extraction prompt text, nothing else. No markdown, no preamble.

Start writing the prompt now:
"""

    if existing_prompt:
        analysis_prompt += (
            f"\n\nNOTE: Their current prompt is:\n{existing_prompt}\n"
            "If their current extraction is working well, preserve its core ideas.\n"
            "Only improve if there are obvious gaps in what they're trying to capture.\n"
        )

    # Call the LLM (works with any provider mem0 supports)
    try:
        response = llm.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": analysis_prompt,
                }
            ],
            temperature=0.3,  # Lower temperature for more deterministic prompt generation
        )
        # Handle different response formats
        if isinstance(response, dict):
            prompt_text = response.get("message", response.get("content", ""))
        else:
            prompt_text = str(response)

        return prompt_text.strip()
    except Exception as e:
        raise RuntimeError(f"LLM analysis failed: {e}")


def fallback_prompt_from_patterns(patterns: dict[str, list[str]]) -> str:
    """
    Generate a basic extraction prompt from keyword patterns when LLM is unavailable.

    Args:
        patterns: Dict of category -> [keywords, ...] from sample analysis

    Returns:
        A functional (but generic) extraction prompt
    """
    if not patterns:
        return (
            "Extract all factual information from the conversation. "
            "Return as JSON with key 'facts' and a list of strings."
        )

    categories_text = "\n".join(
        [f"{i+1}. {cat.capitalize()}: {', '.join(words)}" for i, (cat, words) in enumerate(patterns.items())]
    )

    return f"""You are a memory organizer for a system that works with {', '.join(patterns.keys())} data.

Extract ALL significant facts from the conversation. Focus on:
{categories_text}

Return facts as JSON with key "facts" and a list of strings. Extract generously."""
