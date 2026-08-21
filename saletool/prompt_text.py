"""Tiện ích cắt gọn text trước khi đưa vào prompt.

Dùng chung cho matching và messaging: cả hai đều dựng "brief" về công ty từ cùng
một nguồn dữ liệu, và cả hai đều cần chặn độ dài. Prompt dài hơn không làm kết
quả tốt hơn — chỉ tốn token và đẩy phần quan trọng ra xa khỏi chỗ model chú ý.
"""

from __future__ import annotations

MAX_DESCRIPTION_CHARS = 800
MAX_LIST_ITEMS = 12


def clip_text(text: str | None, limit: int = MAX_DESCRIPTION_CHARS) -> str | None:
    """Gộp khoảng trắng và cắt ở `limit` ký tự, có dấu … để thấy là đã bị cắt."""
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"
