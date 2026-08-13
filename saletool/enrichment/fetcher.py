"""Tầng tải trang: HTTP trước, browser chỉ khi cần.

Thiết kế theo interface để sau này thay bằng Firecrawl/Lightpanda mà không phải
sửa pipeline — xem docs/research/linkedin-company-search/ để biết lý do chọn hướng này.

Nguyên tắc lịch sự (giữ bước enrich ở phía "rủi ro thấp"):
- tôn trọng robots.txt
- nghỉ giữa 2 request tới cùng 1 domain
- User-Agent trung thực, có thông tin liên hệ
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
        """Tải 1 URL. Không raise — trả về FetchedPage với ok=False khi lỗi."""


class RobotsCache:
    """Cache robots.txt theo domain để không tải lại mỗi request."""

    def __init__(self, user_agent: str, timeout: float = 10.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}

    async def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._cache:
            self._cache[origin] = await self._load(origin)

        parser = self._cache[origin]
        if parser is None:
            # Không đọc được robots.txt -> cho phép (hành vi chuẩn của crawler).
            return True
        return parser.can_fetch(self.user_agent, url)

    async def _load(self, origin: str) -> RobotFileParser | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(f"{origin}/robots.txt", headers={"User-Agent": self.user_agent})
        except httpx.HTTPError:
            return None

        if resp.status_code != 200:
            return None

        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser


class DomainRateLimiter:
    """Đảm bảo khoảng nghỉ tối thiểu giữa 2 request tới cùng 1 domain."""

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
    """Tải bằng HTTP thuần — đủ cho phần lớn trang /about, /team của doanh nghiệp."""

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
        if self.robots and not await self.robots.allowed(url):
            return FetchedPage(url=url, ok=False, error="Blocked by robots.txt", method=self.name)

        if self.limiter:
            await self.limiter.wait(url)

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
        except httpx.HTTPError as exc:
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
    """Fallback cho trang render bằng JS. Chậm hơn HTTP nhiều — chỉ dùng khi cần.

    Playwright là dependency tuỳ chọn (extras `browser`); nếu chưa cài thì báo
    lỗi rõ ràng thay vì làm sập pipeline.
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
                browser = await p.chromium.launch()
                try:
                    page = await browser.new_page(user_agent=self.user_agent)
                    await page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
                    html = await page.content()
                finally:
                    await browser.close()
        except Exception as exc:  # noqa: BLE001 - lỗi browser rất đa dạng, không để sập job
            return FetchedPage(url=url, ok=False, error=str(exc), method=self.name)

        return FetchedPage(url=url, html=html, ok=True, method=self.name)


class FallbackFetcher(ContentFetcher):
    """Thử HTTP trước; nếu fail hoặc nội dung quá nghèo (dấu hiệu render JS) thì
    mới dùng browser. Đây là fetcher mặc định của pipeline."""

    name = "fallback"

    # Dưới ngưỡng này coi như trang không có nội dung thật (thường là SPA shell).
    MIN_HTML_LENGTH = 500

    def __init__(self, primary: ContentFetcher, secondary: ContentFetcher | None):
        self.primary = primary
        self.secondary = secondary

    async def fetch(self, url: str) -> FetchedPage:
        page = await self.primary.fetch(url)

        if self.secondary is None:
            return page

        # robots.txt chặn thì browser cũng không được phép — đừng thử lại.
        if page.error and "robots.txt" in page.error:
            return page

        if page.ok and page.html and len(page.html) >= self.MIN_HTML_LENGTH:
            return page

        logger.debug("HTTP fetch thiếu nội dung cho %s, thử lại bằng browser", url)
        fallback = await self.secondary.fetch(url)
        return fallback if fallback.ok else page
