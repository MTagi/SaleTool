"""Tầng 0 — lấy dữ liệu ĐÃ có cấu trúc sẵn trong HTML, không cần LLM.

Lý do tầng này chạy trước: với dữ liệu đã có cấu trúc, code thường **chính xác
hơn LLM**. Email lấy từ `mailto:` là chắc chắn đúng; LLM có thể đọc nhầm hoặc
bịa. Đồng thời nó cắt phần lớn số lần gọi LLM.

Nguồn khai thác:
- JSON-LD schema.org/Organization  (tên, địa chỉ, điện thoại, email, logo, social)
- Thẻ meta / OpenGraph             (tên, mô tả)
- mailto: / tel:                    (liên hệ)
- regex                             (email, điện thoại VN, mã số thuế/MSDN)
"""

from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Mã số thuế / mã số doanh nghiệp VN: 10 số, hoặc 10 số + "-" + 3 số (đơn vị phụ thuộc).
TAX_CODE_RE = re.compile(r"\b(\d{10}(?:-\d{3})?)\b")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Số điện thoại VN: +84 / 84 / 0 + 9-10 chữ số, cho phép dấu cách, chấm, gạch.
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

# Email dùng chung của nền tảng/ảnh — không phải liên hệ thật của công ty.
_EMAIL_NOISE = ("example.com", "sentry.io", "wixpress.com", "@2x", ".png", ".jpg", ".webp")


class StructuredData(BaseModel):
    """Kết quả tầng 0 cho 1 trang."""

    name: str | None = None
    description: str | None = None
    emails: list[str] = []
    phones: list[str] = []
    addresses: list[str] = []
    social_links: dict[str, str] = {}
    tax_code: str | None = None
    founded_year: int | None = None


class _MetaAndLinkParser(HTMLParser):
    """Bóc thẻ <meta>, <script type=application/ld+json>, và href mailto/tel/social.

    Dùng html.parser của stdlib để không thêm dependency parser HTML riêng.
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
            href = attr.get("href", "")
            low = href.lower()
            if low.startswith("mailto:"):
                self.mailto.append(href[7:].split("?")[0].strip())
            elif low.startswith("tel:"):
                self.tel.append(href[4:].strip())
            elif low.startswith("http"):
                for domain, key in _SOCIAL_DOMAINS.items():
                    if domain in low and key not in self.social:
                        self.social[key] = href
                        break

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
    """Duyệt mọi object trong các khối JSON-LD, kể cả @graph và mảng lồng nhau."""
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
    """Đưa số điện thoại về dạng chuẩn để so trùng.

    Cùng một số hay xuất hiện ở nhiều định dạng trên các trang khác nhau
    ('+84 28 3822 1234', '+842838221234', '028 3822 1234'). Bỏ ký tự phân cách
    rồi bỏ tiền tố quốc gia/số 0 đứng đầu để cả ba quy về một khoá.
    """
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("84"):
        digits = digits[2:]
    return digits.lstrip("0")


def _clean_phones(candidates: list[str], exclude: set[str] | None = None) -> list[str]:
    """Giữ bản gốc dễ đọc, nhưng khử trùng theo dạng chuẩn hoá."""
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
    """Trích dữ liệu có cấu trúc từ 1 trang HTML.

    `text` là nội dung đã làm sạch (từ trafilatura) — dùng để chạy regex trên
    phần nội dung thật thay vì toàn bộ HTML, giảm nhiễu rất nhiều.
    """
    data = StructuredData()

    parser = _MetaAndLinkParser()
    try:
        parser.feed(html)
    except Exception as exc:  # noqa: BLE001 - HTML lỗi cú pháp là chuyện thường
        logger.debug("Lỗi parse HTML ở tầng structured: %s", exc)

    # --- JSON-LD Organization: nguồn tốt nhất, ưu tiên cao nhất ---
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
            for domain, key in _SOCIAL_DOMAINS.items():
                if domain in link.lower():
                    data.social_links.setdefault(key, link)

    # --- Thẻ meta / OpenGraph ---
    data.name = data.name or parser.metas.get("og:site_name") or parser.title
    data.description = (
        data.description or parser.metas.get("og:description") or parser.metas.get("description")
    )

    # --- Liên kết mailto:/tel:/social ---
    data.emails.extend(parser.mailto)
    data.phones.extend(parser.tel)
    for key, link in parser.social.items():
        data.social_links.setdefault(key, link)

    # --- Regex trên nội dung đã làm sạch (ít nhiễu hơn HTML thô) ---
    haystack = text or ""
    data.emails.extend(EMAIL_RE.findall(haystack))
    data.phones.extend(PHONE_RE.findall(haystack))

    if tax_match := TAX_CODE_RE.search(haystack):
        # Chỉ nhận khi gần đó có từ khoá — tránh nhận nhầm số điện thoại/số nhà.
        window = haystack[max(0, tax_match.start() - 60) : tax_match.start()].lower()
        if any(kw in window for kw in ("mã số thuế", "mst", "mã số doanh nghiệp", "msdn", "tax code")):
            data.tax_code = tax_match.group(1)

    data.emails = _clean_emails(data.emails)
    # Mã số thuế cũng là 10 chữ số bắt đầu bằng 0 nên khớp luôn pattern số điện
    # thoại VN. Đã nhận diện được là mã số thuế thì loại khỏi danh sách số ĐT.
    exclude = {normalize_phone(data.tax_code)} if data.tax_code else set()
    data.phones = _clean_phones(data.phones, exclude=exclude)
    data.addresses = [a for a in dict.fromkeys(data.addresses) if a]

    return data
