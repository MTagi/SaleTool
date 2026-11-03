"""Stage 0 — extract data already structured in HTML, without an LLM.

This stage runs first because code is usually **more accurate than an LLM** for
structured data. An email from `mailto:` is reliable; an LLM can misread or
invent one. This also avoids most LLM calls.

Sources:
- JSON-LD schema.org/Organization  (name, address, phone, email, logo, social)
- Meta / OpenGraph tags             (name, description)
- mailto: / tel:                    (contacts)
- regex                             (email, Vietnamese phone, tax/business IDs)
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Vietnamese tax/business IDs: 10 digits, or 10 digits + "-" + 3 digits (dependent entities).
TAX_CODE_RE = re.compile(r"\b(\d{10}(?:-\d{3})?)\b")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Vietnamese phone numbers: +84 / 84 / 0 plus 9–10 digits; spaces, dots, and hyphens are allowed.
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}\b")

_SOCIAL_DOMAINS = {
    "linkedin.com": "linkedin",
    "facebook.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "zalo.me": "zalo",
}

# "Share this page" buttons point to these domains but are not company profiles
# (facebook.com/sharer/sharer.php?u=..., twitter.com/intent/tweet...). Nearly every
# page has a share button; without filtering, it often precedes the real profile link.
_SOCIAL_SHARE_RE = re.compile(
    r"/(?:sharer|share|sharearticle|share-offsite|sharing|intent)\b|[?&]u=http|/pin/create",
    re.IGNORECASE,
)

# Link to a specific video or post, not a company profile.
_SOCIAL_ITEM_RE = re.compile(r"youtube\.com/watch|youtu\.be/|/posts/|/videos/", re.IGNORECASE)


def social_profile(url: str) -> tuple[str, str] | None:
    """Return `(network, url)` for a social profile, or `None` otherwise.

    HTML href values often have surrounding whitespace or newlines. Without
    stripping them, the database stores invalid URLs that cannot be opened.
    """
    link = (url or "").strip()
    if not link:
        return None

    low = link.lower()
    if _SOCIAL_SHARE_RE.search(low) or _SOCIAL_ITEM_RE.search(low):
        return None

    for domain, key in _SOCIAL_DOMAINS.items():
        if domain in low:
            return key, link
    return None

# Platform or image service email addresses, not real company contacts.
_EMAIL_NOISE = ("example.com", "sentry.io", "wixpress.com", "@2x", ".png", ".jpg", ".webp")


class StructuredData(BaseModel):
    """Stage 0 results for one page."""

    name: str | None = None
    description: str | None = None
    emails: list[str] = []
    phones: list[str] = []
    addresses: list[str] = []
    social_links: dict[str, str] = {}
    tax_code: str | None = None
    founded_year: int | None = None


class _MetaAndLinkParser(HTMLParser):
    """Extract <meta> tags, <script type=application/ld+json>, and mailto/tel/social hrefs.

    Use the standard-library html.parser to avoid an additional HTML parser dependency.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metas: dict[str, str] = {}
        self.jsonld_blocks: list[str] = []
        self.mailto: list[str] = []
        self.tel: list[str] = []
        self.social: dict[str, str] = {}
        self.title: str | None = None

        self._in_jsonld = False
        self._in_title = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}

        if tag == "meta":
            key = attr.get("property") or attr.get("name")
            content = attr.get("content")
            if key and content:
                self.metas[key.lower()] = content

        elif tag == "script" and attr.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._buffer = []

        elif tag == "title":
            self._in_title = True
            self._buffer = []

        elif tag == "a":
            # Strip here before prefix checks: a multiline href may start with
            # whitespace or a newline, causing startswith("http"/"mailto:"/"tel:")
            # to incorrectly reject a valid link.
            href = (attr.get("href") or "").strip()
            low = href.lower()
            if low.startswith("mailto:"):
                self.mailto.append(href[7:].split("?")[0].strip())
            elif low.startswith("tel:"):
                self.tel.append(href[4:].strip())
            elif low.startswith("http") and (profile := social_profile(href)):
                key, link = profile
                self.social.setdefault(key, link)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            self.jsonld_blocks.append("".join(self._buffer))
            self._in_jsonld = False
            self._buffer = []
        elif tag == "title" and self._in_title:
            self.title = "".join(self._buffer).strip() or None
            self._in_title = False
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_jsonld or self._in_title:
            self._buffer.append(data)


def _iter_jsonld_objects(blocks: list[str]):
    """Visit every object in JSON-LD blocks, including @graph and nested arrays."""
    for block in blocks:
        try:
            payload = json.loads(block)
        except (ValueError, TypeError):
            continue

        stack: list[Any] = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                yield node
                if "@graph" in node:
                    stack.append(node["@graph"])
            elif isinstance(node, list):
                stack.extend(node)


def _as_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list) and value:
        return _as_text(value[0])
    return None


def _format_address(node: Any) -> str | None:
    if isinstance(node, str):
        return node.strip() or None
    if isinstance(node, list) and node:
        return _format_address(node[0])
    if not isinstance(node, dict):
        return None

    parts = [
        _as_text(node.get("streetAddress")),
        _as_text(node.get("addressLocality")),
        _as_text(node.get("addressRegion")),
        _as_text(node.get("postalCode")),
        _as_text(node.get("addressCountry")),
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def _clean_emails(candidates: list[str]) -> list[str]:
    seen: list[str] = []
    for raw in candidates:
        email = raw.strip().lower()
        if not email or any(noise in email for noise in _EMAIL_NOISE):
            continue
        if email not in seen:
            seen.append(email)
    return seen


def normalize_phone(raw: str) -> str:
    """Normalize phone numbers for deduplication.

    The same number often appears in different formats across pages
    ('+84 28 3822 1234', '+842838221234', '028 3822 1234'). Remove separators and
    the leading country code/zero so all three map to one key.
    """
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("84"):
        digits = digits[2:]
    return digits.lstrip("0")


def _clean_phones(candidates: list[str], exclude: set[str] | None = None) -> list[str]:
    """Keep the original readable value, but deduplicate using its normalized form."""
    exclude = exclude or set()
    seen: list[str] = []
    seen_keys: set[str] = set()

    for raw in candidates:
        if len(re.sub(r"\D", "", raw or "")) < 9:
            continue
        key = normalize_phone(raw)
        if not key or key in seen_keys or key in exclude:
            continue
        seen.append(raw.strip())
        seen_keys.add(key)
    return seen


def extract_structured(html: str, text: str | None = None) -> StructuredData:
    """Extract structured data from one HTML page.

    `text` is cleaned content (from trafilatura); run regex against the actual
    page text instead of all HTML to greatly reduce noise.
    """
    data = StructuredData()

    parser = _MetaAndLinkParser()
    try:
        parser.feed(html)
    except Exception as exc:  # noqa: BLE001 - Malformed HTML is common.
        logger.debug("HTML parsing failed in the structured stage: %s", exc)

    # --- JSON-LD Organization: best and highest-priority source ---
    for node in _iter_jsonld_objects(parser.jsonld_blocks):
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        types = [str(t).lower() for t in types if t]
        if not any(t in ("organization", "corporation", "localbusiness") for t in types):
            continue

        data.name = data.name or _as_text(node.get("name"))
        data.description = data.description or _as_text(node.get("description"))

        if email := _as_text(node.get("email")):
            data.emails.append(email)
        if phone := _as_text(node.get("telephone")):
            data.phones.append(phone)
        if address := _format_address(node.get("address")):
            data.addresses.append(address)
        if founded := _as_text(node.get("foundingDate")):
            match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", founded)
            if match:
                data.founded_year = int(match.group(1))

        same_as = node.get("sameAs")
        for link in same_as if isinstance(same_as, list) else [same_as]:
            if not isinstance(link, str):
                continue
            if profile := social_profile(link):
                data.social_links.setdefault(*profile)

    # --- Meta / OpenGraph tags ---
    data.name = data.name or parser.metas.get("og:site_name") or parser.title
    data.description = (
        data.description or parser.metas.get("og:description") or parser.metas.get("description")
    )

    # --- mailto:/tel:/social links ---
    data.emails.extend(parser.mailto)
    data.phones.extend(parser.tel)
    for key, link in parser.social.items():
        data.social_links.setdefault(key, link)

    # --- Regex over cleaned text (less noisy than raw HTML) ---
    haystack = text or ""
    data.emails.extend(EMAIL_RE.findall(haystack))
    data.phones.extend(PHONE_RE.findall(haystack))

    if tax_match := TAX_CODE_RE.search(haystack):
        # Accept only when a nearby keyword is present; avoid mistaking phone or street numbers.
        window = haystack[max(0, tax_match.start() - 60) : tax_match.start()].lower()
        # Keep Vietnamese terms because this extractor processes Vietnamese company websites.
        if any(
            kw in window
            for kw in (
                "m\xe3 s\u1ed1 thu\u1ebf", "mst", "m\xe3 s\u1ed1 doanh nghi\u1ec7p", "msdn",
                "tax code", "business registration number",
            )
        ):
            data.tax_code = tax_match.group(1)

    data.emails = _clean_emails(data.emails)
    # Tax IDs are also 10 digits starting with 0, so they match the Vietnamese
    # phone pattern. Once identified as a tax ID, remove them from the phone list.
    exclude = {normalize_phone(data.tax_code)} if data.tax_code else set()
    data.phones = _clean_phones(data.phones, exclude=exclude)
    data.addresses = [a for a in dict.fromkeys(data.addresses) if a]

    return data
