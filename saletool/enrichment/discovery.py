"""Tìm ra những URL nào đáng đọc cho 1 công ty.

Hai nguồn tách bạch:
1. Website của chính công ty — KHÔNG cần search API. Đã có domain thì đọc
   sitemap.xml / crawl nông là đủ, vừa miễn phí vừa đầy đủ hơn search.
2. Trang bên ngoài nói về công ty — chỗ này mới cần SearchProvider.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

from saletool.enrichment.search import SearchProvider

logger = logging.getLogger(__name__)

# Đường dẫn hay chứa thông tin công ty — cả tiếng Anh lẫn tiếng Việt.
PRIORITY_PATH_PATTERNS = [
    r"/about",
    r"/gioi-thieu",
    r"/ve-chung-toi",
    r"/company",
    r"/team",
    r"/lanh-dao",
    r"/ban-lanh-dao",
    r"/nhan-su",
    r"/leadership",
    r"/management",
    r"/contact",
    r"/lien-he",
    r"/careers",
    r"/tuyen-dung",
]

_PRIORITY_RE = re.compile("|".join(PRIORITY_PATH_PATTERNS), re.IGNORECASE)

# Không phí lượt tải vào các trang này.
_SKIP_RE = re.compile(
    r"\.(pdf|jpg|jpeg|png|gif|svg|webp|zip|rar|docx?|xlsx?|pptx?|mp4|mp3)$"
    r"|/wp-json/|/wp-admin/|/cart|/checkout|/login|/dang-nhap",
    re.IGNORECASE,
)

_SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def normalize_domain(raw: str) -> str | None:
    """'https://www.ABC.com/x' -> 'abc.com'. Domain là khoá nối dữ liệu tốt nhất."""
    if not raw:
        return None

    value = raw.strip().lower()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    netloc = urlparse(value).netloc
    if not netloc:
        return None

    netloc = netloc.split("@")[-1].split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def _same_site(url: str, domain: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc == domain


def _rank(url: str) -> int:
    """Trang ưu tiên trước, trang chủ kế, còn lại sau."""
    path = urlparse(url).path or "/"
    if _PRIORITY_RE.search(path):
        return 0
    if path in ("", "/"):
        return 1
    return 2


async def _get(client: httpx.AsyncClient, url: str, user_agent: str) -> httpx.Response | None:
    try:
        resp = await client.get(url, headers={"User-Agent": user_agent}, follow_redirects=True)
    except httpx.HTTPError:
        return None
    return resp if resp.status_code == 200 else None


def _origin_candidates(domain: str) -> list[str]:
    """Các gốc URL nên thử, theo thứ tự ưu tiên.

    Có cả http:// vì không ít website doanh nghiệp nhỏ (đặc biệt SME Việt Nam)
    vẫn chưa bật HTTPS — nếu chỉ thử https thì sẽ bỏ sót hẳn nhóm này.
    """
    return [
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    ]


async def urls_from_sitemap(
    domain: str, user_agent: str, timeout: float = 15.0, max_urls: int = 200
) -> list[str]:
    """Đọc sitemap.xml (kể cả sitemap index 1 tầng). Trả rỗng nếu site không có."""
    found: list[str] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for base in _origin_candidates(domain):
            resp = await _get(client, f"{base}/sitemap.xml", user_agent)
            if not resp:
                continue

            locs = _SITEMAP_LOC_RE.findall(resp.text)

            # Sitemap index -> lấy tiếp các sitemap con (giới hạn 5 để không nổ).
            if locs and locs[0].rstrip("/").endswith(".xml"):
                for child in locs[:5]:
                    child_resp = await _get(client, child, user_agent)
                    if child_resp:
                        found.extend(_SITEMAP_LOC_RE.findall(child_resp.text))
            else:
                found.extend(locs)

            if found:
                break

    unique = [u for u in dict.fromkeys(found) if not _SKIP_RE.search(u)]
    return unique[:max_urls]


async def urls_from_homepage(
    domain: str, user_agent: str, timeout: float = 15.0, max_urls: int = 100
) -> list[str]:
    """Fallback khi không có sitemap: lấy link từ trang chủ (crawl nông 1 tầng)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for base in _origin_candidates(domain):
            resp = await _get(client, base, user_agent)
            if not resp:
                continue

            urls = []
            for href in _HREF_RE.findall(resp.text):
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                absolute = urljoin(str(resp.url), href)
                if not absolute.startswith("http"):
                    continue
                if not _same_site(absolute, domain) or _SKIP_RE.search(absolute):
                    continue
                urls.append(absolute.split("#")[0])

            return [str(resp.url)] + [u for u in dict.fromkeys(urls)][:max_urls]

    return []


async def discover_company_site_urls(
    domain: str, user_agent: str, max_pages: int, timeout: float = 15.0
) -> list[str]:
    """URL nên đọc trên website của chính công ty, đã xếp theo độ ưu tiên."""
    urls = await urls_from_sitemap(domain, user_agent, timeout=timeout)
    if not urls:
        urls = await urls_from_homepage(domain, user_agent, timeout=timeout)

    same_site = [u for u in urls if _same_site(u, domain)]
    if not same_site:
        same_site = [f"https://{domain}"]  # không tìm được gì -> ít nhất thử trang chủ

    same_site.sort(key=_rank)
    return same_site[:max_pages]


def build_search_queries(company_name: str, domain: str | None, extra_context: str | None) -> list[str]:
    """Câu truy vấn tìm trang BÊN NGOÀI nói về công ty."""
    name = company_name.strip()
    queries = [f'"{name}" giới thiệu công ty', f'"{name}" ban lãnh đạo OR CEO OR "giám đốc"']

    if extra_context:
        queries.append(f'"{name}" {extra_context.strip()}')
    if domain:
        # Loại kết quả từ chính website công ty — phần đó đã crawl trực tiếp rồi.
        queries.append(f'"{name}" -site:{domain}')

    return queries


async def discover_external_urls(
    provider: SearchProvider,
    company_name: str,
    domain: str | None,
    extra_context: str | None,
    max_results: int,
) -> list[str]:
    """Chạy các query qua SearchProvider, gộp và khử trùng URL."""
    seen: list[str] = []

    for query in build_search_queries(company_name, domain, extra_context):
        try:
            results = await provider.search(query, max_results=max_results)
        except Exception as exc:  # noqa: BLE001 - search hỏng không được làm sập enrich
            logger.warning("Search '%s' lỗi: %s", query, exc)
            continue

        for item in results:
            url = item.url.split("#")[0]
            if _SKIP_RE.search(url) or url in seen:
                continue
            # Bỏ trang thuộc chính domain công ty — đã crawl riêng.
            if domain and _same_site(url, domain):
                continue
            seen.append(url)

        if len(seen) >= max_results:
            break

    return seen[:max_results]
