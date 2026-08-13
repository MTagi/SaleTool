"""HTML -> text sạch, bằng trafilatura.

Đây là tầng quyết định chi phí LLM: HTML thô của 1 trang giới thiệu điển hình
~150KB (~40.000 token), sau khi bóc còn ~4KB (~1.000 token). Chênh khoảng 40 lần.
Không có tầng này thì mọi thứ phía sau đắt gấp hàng chục lần.

trafilatura được chọn vì có benchmark độc lập (không phải tự quảng cáo):
F1 ~0.945 trên bộ article-extraction-benchmark của ScrapingHub, và có cơ chế
fallback nhiều tầng (heuristic -> readability-lxml -> jusText) nên hiếm khi rỗng.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def extract_text(html: str, url: str | None = None) -> str | None:
    """Bóc nội dung chính. Trả về None nếu không lấy được gì đáng kể."""
    if not html:
        return None

    try:
        import trafilatura
    except ImportError:
        logger.error("Chưa cài trafilatura — pip install trafilatura")
        return None

    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,  # trang /about, /team thường ngắn — ưu tiên không bỏ sót
            no_fallback=False,
        )
    except Exception as exc:  # noqa: BLE001 - HTML lỗi không được làm sập job
        logger.debug("trafilatura lỗi ở %s: %s", url, exc)
        return None

    if not text:
        return None

    cleaned = text.strip()
    return cleaned or None


def truncate_for_llm(text: str, max_chars: int = 12000) -> str:
    """Cắt bớt trước khi đưa vào LLM để chặn trần chi phí trên các trang bất thường."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…[truncated]"
