"""Utilities for trimming text before adding it to a prompt.

Shared by matching and messaging: both build a company brief from the same data
and need a length limit. Longer prompts do not improve results; they use more
tokens and push important details away from the model's focus.
"""

from __future__ import annotations

MAX_DESCRIPTION_CHARS = 800
MAX_LIST_ITEMS = 12


def clip_text(text: str | None, limit: int = MAX_DESCRIPTION_CHARS) -> str | None:
    """Collapse whitespace and truncate at `limit` characters, adding … to mark truncation."""
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"
