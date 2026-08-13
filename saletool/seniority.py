"""Suy luận seniority (cấp bậc) từ chức danh (title) dạng tự do.

Hữu ích khi dữ liệu được import thủ công (vd: export từ Sales Navigator)
và không có sẵn cột "seniority" chuẩn hoá như các API provider (Apollo...).
"""

from __future__ import annotations

import re

# Thứ tự ưu tiên: kiểm tra theo thứ tự này, khớp đầu tiên thắng.
# Dùng \b (word boundary) khi so khớp để tránh khớp nhầm chuỗi con bên trong
# từ khác (vd: "cto" không được khớp nhầm vào "director").
_KEYWORD_TO_SENIORITY: list[tuple[str, list[str]]] = [
    ("owner", ["owner", "proprietor"]),
    ("founder", ["founder", "co-founder", "cofounder"]),
    (
        "c_suite",
        [
            "chief executive officer", "ceo",
            "chief financial officer", "cfo",
            "chief operating officer", "coo",
            "chief technology officer", "cto",
            "chief marketing officer", "cmo",
            "chief revenue officer", "cro",
            "chief product officer", "cpo",
            "chief people officer", "chro",
            "president", "chairman", "chairwoman", "chairperson",
            "chief", "managing director",
        ],
    ),
    ("partner", ["partner"]),
    ("vp", ["vice president", "vp", "svp", "evp"]),
    ("head", ["head of"]),
    ("director", ["director"]),
    ("manager", ["manager", "team lead", "lead"]),
    ("senior", ["senior"]),
    ("intern", ["intern", "internship"]),
]

def infer_seniority(title: str | None) -> str | None:
    """Đoán seniority level từ chuỗi title tự do. Trả về None nếu không đoán được."""

    if not title:
        return None

    normalized = re.sub(r"\s+", " ", title.strip().lower())

    for level, keywords in _KEYWORD_TO_SENIORITY:
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, normalized):
                return level
    return None
