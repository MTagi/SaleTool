"""Convert HTML to clean text using trafilatura.

This stage determines LLM costs: raw HTML for a typical company page is ~150 KB
(~40,000 tokens), while extracted text is ~4 KB (~1,000 tokens), about 40x smaller.
Without it, every downstream step costs dozens of times more.

trafilatura was selected based on independent benchmarks: F1 ~0.945 on
ScrapingHub's article-extraction-benchmark, with multiple fallbacks (heuristics
-> readability-lxml -> jusText), so it rarely returns empty content.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def extract_text(html: str, url: str | None = None) -> str | None:
    """Extract the main content. Return None if nothing meaningful is found."""
    if not html:
        return None

    try:
        import trafilatura
    except ImportError:
        logger.error("trafilatura is not installed — pip install trafilatura")
        return None

    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,  # /about and /team pages are often short; prioritize recall.
            no_fallback=False,
        )
    except Exception as exc:  # noqa: BLE001 - Invalid HTML must not fail the job.
        logger.debug("trafilatura failed at %s: %s", url, exc)
        return None

    if not text:
        return None

    cleaned = text.strip()
    return cleaned or None


def truncate_for_llm(text: str, max_chars: int = 12000) -> str:
    """Truncate before sending to the LLM to cap costs for unusually long pages."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…[truncated]"
