"""Find URLs worth reading for a company.

Two distinct sources:
1. The company's own website — no search API needed. With a domain, reading
   sitemap.xml or shallow crawling is free and more complete than search.
2. External pages about the company — these require a SearchProvider.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

from saletool.enrichment.fetcher import DomainRateLimiter, RobotsCache
from saletool.enrichment.safe_url import UnsafeURLError, public_get
from saletool.enrichment.search import SearchProvider

logger = logging.getLogger(__name__)

# Paths that often contain company information, in both English and Vietnamese.
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

# File extensions that are not content pages. Include css/js because Next.js,
# Nuxt, etc. embed bundle paths in the homepage HTML; shallow crawling can find
# them, wasting a request and rate-limit delay before the fetcher rejects them
# for an incorrect content type.
_SKIP_EXT_RE = re.compile(
    r"\.(css|js|mjs|map|json|pdf|jpg|jpeg|png|gif|svg|webp|ico|zip|rar"
    r"|docx?|xlsx?|pptx?|mp4|mp3|woff2?|ttf|otf|eot)$",
    re.IGNORECASE,
)

# Directories containing only build assets or functionality, never company information.
_SKIP_PATH_RE = re.compile(
    r"/_next/static/|/_nuxt/|/static/(?:js|css|media)/|/wp-json/|/wp-admin/"
    r"|/wp-includes/|/wp-content/|/cdn-cgi/|/cart|/checkout|/login|/dang-nhap",
    re.IGNORECASE,
)


def _should_skip(url: str) -> bool:
    """Is this URL worth fetching?

    Match the path, not the full URL: file extensions often have cache-busting
    query strings (`/app.css?v=9f2a`), so anchoring `$` to the full URL misses them.
    """
    path = urlparse(url).path
    return bool(_SKIP_EXT_RE.search(path) or _SKIP_PATH_RE.search(path))


_SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def normalize_domain(raw: str) -> str | None:
    """Convert 'https://www.ABC.com/x' to 'abc.com'. Domain is the best key for joining data."""
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
    return normalize_domain(url) == domain


def _rank(url: str) -> int:
    """Prioritized pages first, homepage next, and all others last."""
    path = urlparse(url).path or "/"
    if _PRIORITY_RE.search(path):
        return 0
    if path in ("", "/"):
        return 1
    return 2


async def _get(
    client: httpx.AsyncClient,
    url: str,
    user_agent: str,
    robots: RobotsCache | None = None,
    limiter: DomainRateLimiter | None = None,
) -> httpx.Response | None:
    try:
        resp = await public_get(
            client,
            url,
            headers={"User-Agent": user_agent},
            allowed=robots.allowed if robots else None,
            wait=limiter.wait if limiter else None,
        )
    except (httpx.HTTPError, UnsafeURLError):
        return None
    return resp if resp.status_code == 200 else None


def _origin_candidates(domain: str) -> list[str]:
    """URL bases to try, in priority order.

    Include http:// because many small business websites (especially Vietnamese
    SMEs) still do not use HTTPS; trying only https would miss them entirely.
    """
    return [
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    ]


async def urls_from_sitemap(
    domain: str,
    user_agent: str,
    timeout: float = 15.0,
    max_urls: int = 200,
    robots: RobotsCache | None = None,
    limiter: DomainRateLimiter | None = None,
) -> list[str]:
    """Read sitemap.xml (including one level of sitemap index). Return empty if absent."""
    found: list[str] = []

    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        for base in _origin_candidates(domain):
            resp = await _get(client, f"{base}/sitemap.xml", user_agent, robots, limiter)
            if not resp:
                continue

            locs = _SITEMAP_LOC_RE.findall(resp.text)

            # Sitemap index -> fetch child sitemaps (limit to five to avoid runaway requests).
            if locs and locs[0].rstrip("/").endswith(".xml"):
                for child in locs[:5]:
                    child_resp = await _get(client, child, user_agent, robots, limiter)
                    if child_resp:
                        found.extend(_SITEMAP_LOC_RE.findall(child_resp.text))
            else:
                found.extend(locs)

            if found:
                break

    unique = [u for u in dict.fromkeys(found) if not _should_skip(u)]
    return unique[:max_urls]


async def urls_from_homepage(
    domain: str,
    user_agent: str,
    timeout: float = 15.0,
    max_urls: int = 100,
    robots: RobotsCache | None = None,
    limiter: DomainRateLimiter | None = None,
) -> list[str]:
    """Fallback when no sitemap exists: collect links from the homepage (one-level shallow crawl)."""
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        for base in _origin_candidates(domain):
            resp = await _get(client, base, user_agent, robots, limiter)
            if not resp:
                continue

            urls = []
            for href in _HREF_RE.findall(resp.text):
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                absolute = urljoin(str(resp.url), href)
                if not absolute.startswith("http"):
                    continue
                if not _same_site(absolute, domain) or _should_skip(absolute):
                    continue
                urls.append(absolute.split("#")[0])

            return [str(resp.url), *list(dict.fromkeys(urls))[:max_urls]]

    return []


async def discover_company_site_urls(
    domain: str,
    user_agent: str,
    max_pages: int,
    timeout: float = 15.0,
    robots: RobotsCache | None = None,
    limiter: DomainRateLimiter | None = None,
) -> list[str]:
    """Prioritized URLs to read on the company's own website."""
    urls = await urls_from_sitemap(
        domain, user_agent, timeout=timeout, robots=robots, limiter=limiter
    )
    if not urls:
        urls = await urls_from_homepage(
            domain, user_agent, timeout=timeout, robots=robots, limiter=limiter
        )

    same_site = [u for u in urls if _same_site(u, domain)]
    if not same_site:
        same_site = [f"https://{domain}"]  # If nothing else is found, at least try the homepage.

    same_site.sort(key=_rank)
    return same_site[:max_pages]


def build_search_queries(
    company_name: str, domain: str | None, extra_context: str | None
) -> list[str]:
    """Queries for finding EXTERNAL pages about the company."""
    name = company_name.strip()
    queries = [f'"{name}" company profile', f'"{name}" leadership OR CEO OR "managing director"']

    if extra_context:
        queries.append(f'"{name}" {extra_context.strip()}')
    if domain:
        # Exclude results from the company's own website; it was crawled directly.
        queries.append(f'"{name}" -site:{domain}')

    return queries


async def discover_external_urls(
    provider: SearchProvider,
    company_name: str,
    domain: str | None,
    extra_context: str | None,
    max_results: int,
    queries: list[str] | None = None,
) -> list[str]:
    """Run queries through the SearchProvider, then merge and deduplicate URLs."""
    seen: list[str] = []

    for query in queries or build_search_queries(company_name, domain, extra_context):
        try:
            results = await provider.search(query, max_results=max_results)
        except Exception as exc:  # noqa: BLE001 - Search failures must not stop enrichment.
            logger.warning("Search '%s' failed: %s", query, exc)
            continue

        for item in results:
            url = item.url.split("#")[0]
            if _should_skip(url) or url in seen:
                continue
            # Skip pages on the company's own domain; it was crawled separately.
            if domain and _same_site(url, domain):
                continue
            seen.append(url)

        if len(seen) >= max_results:
            break

    return seen[:max_results]
