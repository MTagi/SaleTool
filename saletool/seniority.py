"""Infer seniority from free-form job titles.

Useful when data is imported manually (e.g. from Sales Navigator) and lacks a
normalized "seniority" field like those provided by APIs such as Apollo.
"""

from __future__ import annotations

import re

# Priority order: check in this order; the first match wins.
# Use \b (word boundary) to avoid matching substrings inside other words
# (e.g. "cto" should not match "director").
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
    """Infer seniority from a free-form title. Return None if it cannot be inferred."""

    if not title:
        return None

    normalized = re.sub(r"\s+", " ", title.strip().lower())

    for level, keywords in _KEYWORD_TO_SENIORITY:
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, normalized):
                return level
    return None
