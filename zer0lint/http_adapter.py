"""HTTP adapter for zer0lint — works with any memory system over HTTP.

Contract for the remote endpoints:

  Add endpoint:
    POST <add-url>
    Content-Type: application/json
    {"text": "<fact text>", "user_id": "<uid>"}
    → any 2xx = success (response body ignored)

  Search endpoint:
    POST <search-url>
    Content-Type: application/json
    {"text": "<query>", "limit": <N>, "user_id": "<uid>"}
    → JSON response; handled shapes:
        {"results": [{"memory": "..."}, ...]}   (mem0-style)
        [{"text": "..."}, ...]                  (cogito-ergo recall_b)
        {"hits": [...]}                         (elasticsearch-style)
        plain list of strings

Each result is normalized to have a "memory" key before returning, so the
existing _extract_memory_text() in tester.py works without changes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from uuid import uuid4


class HttpMemoryAdapter:
    """
    Duck-typed replacement for mem0.Memory that speaks HTTP.

    Provides .add() and .search() with signatures compatible with
    validate_extraction_prompt() in tester.py. Cleanup (.get_all, .delete)
    is stubbed — HTTP mode relies on random user_id isolation instead.
    """

    def __init__(
        self,
        add_url: str,
        search_url: str,
        timeout: float = 15.0,
        user_id: str | None = None,
    ) -> None:
        self._add_url = add_url.rstrip("/")
        self._search_url = search_url.rstrip("/")
        self._timeout = timeout
        # Per-run random user_id so test facts don't pollute real data.
        # If the backend doesn't support user_id scoping, this is a no-op.
        self._default_user_id = user_id or f"zer0lint_{str(uuid4())[:8]}"

    # ------------------------------------------------------------------
    # mem0-compatible interface
    # ------------------------------------------------------------------

    def add(self, text: str, user_id: str | None = None, **kwargs) -> dict:
        """Store a fact. Returns {"results": []} on success."""
        uid = user_id or self._default_user_id
        payload = json.dumps({"text": text, "user_id": uid}).encode()
        req = urllib.request.Request(
            self._add_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status >= 400:
                    raise RuntimeError(f"add() returned HTTP {resp.status}")
                return {"results": []}
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"add() HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"add() unreachable: {e.reason}") from e

    def search(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 10,
        **kwargs,
    ) -> dict:
        """
        Search for relevant memories.

        Returns {"results": [{"memory": "..."}, ...]} — compatible with
        _get_results_list() and _extract_memory_text() in tester.py.
        """
        uid = user_id or self._default_user_id
        payload = json.dumps({"text": query, "limit": limit, "user_id": uid}).encode()
        req = urllib.request.Request(
            self._search_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status >= 400:
                    raise RuntimeError(f"search() returned HTTP {resp.status}")
                raw = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"search() HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"search() unreachable: {e.reason}") from e

        # Normalize to {"results": [{"memory": "..."}]} for tester.py helpers
        return {"results": _normalize_results(raw)}

    def get_all(self, user_id: str | None = None) -> dict:
        """Stub — HTTP mode skips cleanup (relies on user_id isolation)."""
        return {"results": []}

    def delete(self, memory_id: str) -> None:
        """Stub — HTTP mode skips cleanup."""
        pass


# ------------------------------------------------------------------
# Response normalization
# ------------------------------------------------------------------

def _normalize_results(raw: object) -> list[dict]:
    """
    Extract a list of result dicts from an arbitrary JSON response.

    Handles:
      {"results": [...]}              — mem0, wrapped cogito-ergo
      [...]                           — cogito-ergo /recall_b direct
      {"hits": [...]}                 — elasticsearch-style
      {"memories": [...]}
      {"data": {"results": [...]}}    — nested wrapper

    Each item is normalized to have a "memory" key so that
    _extract_memory_text() in tester.py can read it.
    """
    # --- Unwrap outer container ---
    items: list | None = None

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        for key in ("results", "hits", "memories"):
            val = raw.get(key)
            if isinstance(val, list):
                items = val
                break
        if items is None:
            # Try one level of nesting: {"data": {"results": [...]}}
            nested = raw.get("data")
            if isinstance(nested, dict):
                for key in ("results", "hits", "memories"):
                    val = nested.get(key)
                    if isinstance(val, list):
                        items = val
                        break

    if not items:
        return []

    # --- Normalize each item to have "memory" key ---
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"memory": item})
        elif isinstance(item, dict):
            if "memory" in item:
                normalized.append(item)
            elif "content" in item:
                normalized.append({**item, "memory": item["content"]})
            elif "text" in item:
                normalized.append({**item, "memory": item["text"]})
            elif "value" in item:
                normalized.append({**item, "memory": item["value"]})
            elif "passage" in item:
                normalized.append({**item, "memory": item["passage"]})
            else:
                # Unknown shape — preserve as-is; _extract_memory_text will str() it
                normalized.append(item)

    return normalized
