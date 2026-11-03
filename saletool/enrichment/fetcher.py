"""Page fetching stage: HTTP first, browser only when needed.

Designed around an interface so Firecrawl/Lightpanda can be added later without
changing the pipeline. See docs/research/linkedin-company-search/ for the rationale.

Polite crawling principles (keeping enrichment "low-risk"):
- respect robots.txt
- wait between requests to the same domain
- provide a truthful User-Agent with contact information
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import BaseModel

from saletool.enrichment.safe_url import UnsafeURLError, public_get, resolve_public_url

logger = logging.getLogger(__name__)


class FetchedPage(BaseModel):
    url: str
    html: str | None = None
    status_code: int | None = None
    method: str = "http"
    ok: bool = False
    error: str | None = None


class ContentFetcher(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, url: str) -> FetchedPage:
        """Fetch one URL. Never raise; return FetchedPage with ok=False on failure."""


class RobotsCache:
    """Cache robots.txt by domain to avoid fetching it for every request."""

    def __init__(self, user_agent: str, timeout: float = 10.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}

    async def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._cache:
            try:
                self._cache[origin] = await self._load(origin)
            except UnsafeURLError:
                return False

        parser = self._cache[origin]
        if parser is None:
            # If robots.txt cannot be read, allow access (standard crawler behavior).
            return True
        return parser.can_fetch(self.user_agent, url)

    async def _load(self, origin: str) -> RobotFileParser | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                resp = await public_get(
                    client, f"{origin}/robots.txt", headers={"User-Agent": self.user_agent}
                )
        except httpx.HTTPError:
            return None

        if resp.status_code != 200:
            return None

        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser


class DomainRateLimiter:
    """Enforce a minimum delay between requests to the same domain."""

    def __init__(self, delay_seconds: float):
        self.delay = delay_seconds
        self._last_hit: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str) -> None:
        if self.delay <= 0:
            return

        domain = urlparse(url).netloc
        async with self._lock:
            last = self._last_hit.get(domain)
            now = time.monotonic()
            if last is not None:
                remaining = self.delay - (now - last)
                if remaining > 0:
                    await asyncio.sleep(remaining)
                    now = time.monotonic()
            self._last_hit[domain] = now


class HttpFetcher(ContentFetcher):
    """Fetch with plain HTTP, which is sufficient for most company /about and /team pages."""

    name = "http"

    def __init__(
        self,
        user_agent: str,
        timeout: float = 15.0,
        robots: RobotsCache | None = None,
        limiter: DomainRateLimiter | None = None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.robots = robots
        self.limiter = limiter

    async def fetch(self, url: str) -> FetchedPage:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                resp = await public_get(
                    client,
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    allowed=self.robots.allowed if self.robots else None,
                    wait=self.limiter.wait if self.limiter else None,
                )
        except (httpx.HTTPError, UnsafeURLError) as exc:
            return FetchedPage(url=url, ok=False, error=str(exc), method=self.name)

        if resp.status_code >= 400:
            return FetchedPage(
                url=url,
                ok=False,
                status_code=resp.status_code,
                error=f"HTTP {resp.status_code}",
                method=self.name,
            )

        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type and "xml" not in content_type:
            return FetchedPage(
                url=url,
                ok=False,
                status_code=resp.status_code,
                error=f"Unsupported content-type: {content_type}",
                method=self.name,
            )

        return FetchedPage(
            url=url, html=resp.text, status_code=resp.status_code, ok=True, method=self.name
        )


class PlaywrightFetcher(ContentFetcher):
    """Fallback for JavaScript-rendered pages. Much slower than HTTP, so use only when needed.

    Playwright is an optional dependency (the `browser` extra); if it is not
    installed, report a clear error instead of failing the pipeline.
    """

    name = "browser"

    def __init__(
        self,
        user_agent: str,
        timeout: float = 30.0,
        robots: RobotsCache | None = None,
        limiter: DomainRateLimiter | None = None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.robots = robots
        self.limiter = limiter

    async def fetch(self, url: str) -> FetchedPage:
        try:
            await resolve_public_url(url, self.timeout)
        except (httpx.HTTPError, UnsafeURLError) as exc:
            return FetchedPage(url=url, ok=False, error=str(exc), method=self.name)
        if self.robots and not await self.robots.allowed(url):
            return FetchedPage(url=url, ok=False, error="Blocked by robots.txt", method=self.name)

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return FetchedPage(
                url=url,
                ok=False,
                method=self.name,
                error="Playwright is not installed (pip install 'saletool[browser]').",
            )

        if self.limiter:
            await self.limiter.wait(url)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    args=[
                        "--disable-quic",
                        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    ]
                )
                try:
                    context = await browser.new_context(
                        user_agent=self.user_agent, service_workers="block"
                    )
                    async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:

                        async def route_request(route):
                            # Page resources also go through the same IP checks.
                            if route.request.method != "GET":
                                await route.abort()
                                return
                            try:
                                response = await public_get(
                                    client,
                                    route.request.url,
                                    headers=await route.request.all_headers(),
                                    allowed=self.robots.allowed if self.robots else None,
                                    wait=self.limiter.wait if self.limiter else None,
                                    follow_redirects=False,
                                )
                            except (httpx.HTTPError, UnsafeURLError):
                                await route.abort()
                                return
                            headers = {
                                key: value
                                for key, value in response.headers.items()
                                if key
                                not in ("content-encoding", "content-length", "transfer-encoding")
                            }
                            await route.fulfill(
                                status=response.status_code, headers=headers, body=response.content
                            )

                        async def block_socket(socket_route):
                            await socket_route.close()

                        await context.route("**/*", route_request)
                        await context.route_web_socket("**/*", block_socket)
                        page = await context.new_page()
                        await page.goto(
                            url, timeout=self.timeout * 1000, wait_until="domcontentloaded"
                        )
                        html = await page.content()
                finally:
                    await browser.close()
        except Exception as exc:  # noqa: BLE001 - Browser errors vary widely; do not fail the job.
            return FetchedPage(url=url, ok=False, error=str(exc), method=self.name)

        return FetchedPage(url=url, html=html, ok=True, method=self.name)


class FallbackFetcher(ContentFetcher):
    """Try HTTP first; use a browser only if it fails or returns little content
    (a sign of JavaScript rendering). This is the pipeline's default fetcher."""

    name = "fallback"

    # Below this threshold, assume the page has no real content (usually an SPA shell).
    MIN_HTML_LENGTH = 500

    def __init__(self, primary: ContentFetcher, secondary: ContentFetcher | None):
        self.primary = primary
        self.secondary = secondary

    async def fetch(self, url: str) -> FetchedPage:
        page = await self.primary.fetch(url)

        if self.secondary is None:
            return page

        # If robots.txt blocks access, a browser is not allowed either; do not retry.
        if page.error and ("robots.txt" in page.error or page.error.startswith("Blocked URL:")):
            return page

        if page.ok and page.html and len(page.html) >= self.MIN_HTML_LENGTH:
            return page

        logger.debug("HTTP fetch returned little content for %s; retrying with a browser", url)
        fallback = await self.secondary.fetch(url)
        return fallback if fallback.ok else page
