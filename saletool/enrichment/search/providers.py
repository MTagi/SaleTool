"""Các implementation SearchProvider.

Tình trạng free tier, tra lại 09/2026 — đây là thứ quyết định nên chọn cái nào:

- `none`    : không dùng web search (chỉ đọc website công ty) — mặc định
- `tavily`  : **1.000 credit/tháng, lặp lại, không cần thẻ.** Search cơ bản 1
              credit. Lựa chọn free thật đáng dùng nhất hiện nay
- `exa`     : **1.000 request/tháng, lặp lại, không cần thẻ.** Cộng với Tavily
              là ~2.000 query/tháng miễn phí
- `serper`  : 2.500 credit **một lần duy nhất** (hết hạn sau 6 tháng), không
              phải free tier hàng tháng. Và nó scrape SERP Google — rủi ro ToS,
              xem docs/research/linkedin-company-search/05-phap-ly-tuan-thu.md
- `searxng` : meta-search tự host, không cần key, không giới hạn query. Nhưng
              từ 2026 Google chặn tích cực các instance SearXNG (instance đứng
              ra proxy cho bot nên bị coi là bot) — cần ghim engine sang
              DuckDuckGo/Mojeek/Brave thay vì để mặc định
- `brave`   : **đã bỏ free tier 02/2026.** Giờ là credit trả trước, bắt buộc
              gắn thẻ và KHÔNG có trần chi tiêu. Tránh cho tool nội bộ
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


class ExaSearchProvider(SearchProvider):
    """Exa — 1.000 request/tháng miễn phí, không cần thẻ.

    Cố tình KHÔNG gửi `contents`: Exa tính thêm tiền cho phần trích nội dung,
    mà pipeline ở đây chỉ dùng `url` (xem discovery.py::discover_external_urls
    — title/snippet không đi tới đâu cả). Trả nội dung về là trả tiền cho thứ
    bị vứt đi ngay sau đó.

    `type: fast` thay vì mặc định `auto`: ta chỉ cần danh sách URL của một công
    ty cụ thể, không cần Exa suy luận sâu.
    """

    name = "exa"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Exa requires an API key.")
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                json={"query": query, "numResults": max_results, "type": "fast"},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        resp.raise_for_status()

        payload = resp.json()
        results = []
        for item in payload.get("results", [])[:max_results]:
            url = item.get("url")
            if not url:
                continue
            # Không xin `contents` nên không có snippet — đúng như dự tính.
            results.append(SearchResult(url=url, title=item.get("title")))
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
