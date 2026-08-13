"""Các implementation SearchProvider: 1 lựa chọn free tự host + 3 lựa chọn trả phí.

- `none`    : không dùng web search (chỉ đọc website công ty) — mặc định
- `searxng` : meta-search tự host, KHÔNG cần API key, không giới hạn query
- `brave`   : Brave Search API (đã bỏ free tier từ 02/2026, tính tiền theo request)
- `tavily`  : tối ưu cho LLM, trả sẵn nội dung đã làm sạch
- `serper`  : rẻ nhất nhưng là scrape SERP Google — có rủi ro ToS, xem
              docs/research/linkedin-company-search/05-phap-ly-tuan-thu.md
"""

from __future__ import annotations

import httpx

from saletool.enrichment.search.base import SearchProvider, SearchResult

_TIMEOUT = 20.0


class NoSearchProvider(SearchProvider):
    """Không dùng web search. Trả rỗng thay vì lỗi, để pipeline vẫn chạy tiếp."""

    name = "none"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return []


class SearxngSearchProvider(SearchProvider):
    """SearXNG tự host — free, không cần API key.

    Đánh đổi: chính IP của bạn bị các search engine gốc rate-limit, nên kém ổn
    định hơn API trả phí. Chấp nhận được ở quy mô nội bộ.
    """

    name = "searxng"

    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("SearXNG requires an instance URL.")
        self.base_url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/search",
                params={"q": query, "format": "json"},
                headers={"Accept": "application/json"},
            )
        resp.raise_for_status()

        payload = resp.json()
        results = []
        for item in payload.get("results", [])[:max_results]:
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResult(url=url, title=item.get("title"), snippet=item.get("content"))
            )
        return results


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Brave Search requires an API key.")
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
            )
        resp.raise_for_status()

        payload = resp.json()
        results = []
        for item in payload.get("web", {}).get("results", [])[:max_results]:
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResult(url=url, title=item.get("title"), snippet=item.get("description"))
            )
        return results


class TavilySearchProvider(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Tavily requires an API key.")
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
        resp.raise_for_status()

        payload = resp.json()
        results = []
        for item in payload.get("results", [])[:max_results]:
            url = item.get("url")
            if not url:
                continue
            results.append(
                SearchResult(url=url, title=item.get("title"), snippet=item.get("content"))
            )
        return results


class SerperSearchProvider(SearchProvider):
    name = "serper"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Serper requires an API key.")
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": max_results},
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            )
        resp.raise_for_status()

        payload = resp.json()
        results = []
        for item in payload.get("organic", [])[:max_results]:
            url = item.get("link")
            if not url:
                continue
            results.append(
                SearchResult(url=url, title=item.get("title"), snippet=item.get("snippet"))
            )
        return results
