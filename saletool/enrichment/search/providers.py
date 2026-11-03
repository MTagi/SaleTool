"""SearchProvider implementations.

Free-tier status, checked 2026-09 — a key factor when choosing a provider:

- `none`    : no web search (read only the company website) — default
- `tavily`  : **1,000 recurring credits/month, no card required.** Basic search
              costs 1 credit; currently the best actual free option
- `exa`     : **1,000 recurring requests/month, no card required.** Combined
              with Tavily, this is ~2,000 free queries/month
- `serper`  : 2,500 credits **once only** (expire after 6 months), not a monthly
              free tier. It also scrapes Google SERPs, which carries ToS risk;
              see docs/research/linkedin-company-search/05-phap-ly-tuan-thu.md
- `brave`   : **free tier removed 2026-02.** Now prepaid credits, a card is
              required, and there is NO spending cap. Avoid for an internal tool
- `codex`   : not a search API; uses GPT's built-in `web_search` tool through
              the 9Router Responses API. **No added cost with an existing
              ChatGPT/Codex plan**, but it is much slower and uses Codex quota.
              See CodexSearchProvider at the end of this file
"""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx

from saletool.enrichment.search.base import SearchProvider, SearchResult
from saletool.llm_api import strip_code_fence

_TIMEOUT = 20.0


class NoSearchProvider(SearchProvider):
    """Do not use web search. Return empty results instead of an error so the pipeline continues."""

    name = "none"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return []


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
    """Exa — 1,000 free requests/month, no card required.

    Deliberately do NOT send `contents`: Exa charges extra for content extraction,
    while this pipeline only uses `url` (see discovery.py::discover_external_urls;
    title/snippet are discarded). Returning content would pay for data that is
    immediately thrown away.

    Use `type: fast` instead of the default `auto`: we only need URLs for a
    specific company and do not need deep Exa reasoning.
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
            # No `contents` requested, so there is no snippet; this is expected.
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


# --- Codex / Responses API ---------------------------------------------------

# 9Router listens on 20128 by default. In Docker Compose use
# http://9router:20128/v1 — the service name on the Compose network, NOT
# localhost from the backend container. See docs/docker.md.
DEFAULT_CODEX_BASE_URL = "http://localhost:20128/v1"

# `cx/` is the 9Router prefix for routing to the connected Codex account; the
# remainder is the model. Users can change it in Settings when OpenAI releases a new model.
DEFAULT_CODEX_MODEL = "cx/gpt-5.4"

# One call runs a real search, reads results, and writes JSON, taking tens of
# seconds rather than the milliseconds of a search API; the _TIMEOUT 20s is too short.
_CODEX_TIMEOUT = 120.0

# Models often add an introduction before JSON despite instructions. Extract the
# largest {...} block instead of requiring the entire response to be JSON.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _build_prompt(query: str, max_results: int) -> str:
    """Prompt for one search call.

    Deliberately do NOT use structured output (`text.format`): Codex backends
    often reject schemas when using a hosted tool. Even if JSON is malformed,
    citations can still be read from `output` (see _merge_results).
    """
    return (
        "Search the web for the query below, then reply with JSON only "
        "(no prose, no markdown fences):\n"
        '{"results": [{"url": "...", "title": "...", "snippet": "..."}]}\n'
        f"Rules: at most {max_results} results; every URL must come from the "
        "search results you just read, never from memory; no duplicate URLs; "
        "keep each snippet under 200 characters.\n\n"
        f"Query: {query}"
    )


def _as_text(value: object) -> str | None:
    """Models sometimes return a number/list for title, which Pydantic rejects;
    a malformed title should not fail the entire search."""
    return value if isinstance(value, str) and value.strip() else None


def _clean_url(value: object) -> str | None:
    """Remove fragments and tracking parameters.

    OpenAI adds `?utm_source=openai` to citation URLs, so the same page from two
    sources would otherwise appear as separate results during deduplication.
    """
    if not isinstance(value, str) or not value.strip():
        return None

    parsed = urlsplit(value.strip().split("#")[0])
    if not parsed.query:
        return parsed.geturl()

    kept = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    return parsed._replace(query=urlencode(kept)).geturl()


def _output_items(body: dict) -> list[dict]:
    """Responses API `output`: a list of items (message, web_search_call, etc.)."""
    items = body.get("output")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _citations(items: list[dict]) -> list[tuple[str, str | None]]:
    """URL in the response's `url_citation` annotation.

    Accept both flat (`{"type": "url_citation", "url": ...}`) and nested
    (`{"url_citation": {...}}`) forms: direct OpenAI calls and 9Router do not
    return identical structures, and this is not a place to be strict.
    """
    found: list[tuple[str, str | None]] = []
    for item in items:
        for block in item.get("content") or []:
            if not isinstance(block, dict):
                continue
            for annotation in block.get("annotations") or []:
                if not isinstance(annotation, dict):
                    continue
                cite = annotation.get("url_citation")
                if not isinstance(cite, dict):
                    cite = annotation
                url = _clean_url(cite.get("url"))
                if url:
                    found.append((url, _as_text(cite.get("title"))))
    return found


def _tool_sources(items: list[dict]) -> list[tuple[str, str | None]]:
    """`web_search_call.action.sources` — every page opened by the tool, NOT ranked."""
    found: list[tuple[str, str | None]] = []
    for item in items:
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        for source in action.get("sources") or []:
            if not isinstance(source, dict):
                continue
            url = _clean_url(source.get("url"))
            if url:
                found.append((url, _as_text(source.get("title"))))
    return found


def _answer_text(items: list[dict]) -> str:
    """Text written by the model, excluding reasoning and tool-call items."""
    parts = []
    for item in items:
        if item.get("type") != "message":
            continue
        for block in item.get("content") or []:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n".join(parts)


def _listed_by_model(items: list[dict]) -> list[SearchResult]:
    """JSON list written by the model. Return empty if parsing fails; this is
    normal when the model responds in prose, not an error."""
    match = _JSON_OBJECT_RE.search(strip_code_fence(_answer_text(items)))
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return []

    rows = parsed.get("results") if isinstance(parsed, dict) else parsed
    results = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        url = _clean_url(row.get("url"))
        if url:
            results.append(
                SearchResult(
                    url=url, title=_as_text(row.get("title")), snippet=_as_text(row.get("snippet"))
                )
            )
    return results


def _merge_results(items: list[dict], max_results: int) -> list[SearchResult]:
    """Merge the three URL sources in a response, in decreasing order of reliability.

    1. `url_citation`: real URLs opened by the tool, ordered as cited by the model;
       highest priority.
    2. Model-written JSON: ranked by the model and the only source with snippets,
       but URLs *may* be fabricated. Use it to fill titles/snippets for (1), and
       add new URLs only when (1) has fewer than `max_results`. A bad URL costs
       one failed fetch in discovery but does not corrupt data.
    3. `action.sources`: use only when both sources above are empty; some Responses
       versions emit no annotations, making this the only remaining source.
    """
    listed = _listed_by_model(items)
    by_url = {result.url: result for result in listed}

    merged: dict[str, SearchResult] = {}
    for url, title in _citations(items):
        if url in merged:
            continue
        listed_row = by_url.get(url)
        merged[url] = SearchResult(
            url=url,
            title=title or (listed_row.title if listed_row else None),
            snippet=listed_row.snippet if listed_row else None,
        )

    for result in listed:
        if len(merged) >= max_results:
            break
        merged.setdefault(result.url, result)

    if not merged:
        for url, title in _tool_sources(items):
            merged.setdefault(url, SearchResult(url=url, title=title))

    return list(merged.values())[:max_results]


class CodexSearchProvider(SearchProvider):
    """Web search using GPT's own `web_search` tool through the Responses API.

    Unlike the providers above, this is not a search API but an LLM with a
    server-side search tool. We send a query; the model runs web_search and
    returns an answer with citations. Trade-offs:

    - **Free with an existing ChatGPT/Codex plan** — no extra search account or
      separate credits. That is why this provider exists.
    - Much slower (seconds to tens of seconds, not hundreds of milliseconds) and
      uses Codex quota. Avoid it while Tavily/Exa quota is available.

    Do not call `chatgpt.com/backend-api/codex` directly: ChatGPT tokens expire
    frequently and need OAuth PKCE refresh, which 9Router handles
    (`docker compose --profile 9router up -d`, see docs/docker.md). This uses a
    standard OpenAI Responses endpoint, so pointing `base_url` at OpenAI with
    `model: gpt-5` works the same way without code changes.
    """

    name = "codex"

    def __init__(self, base_url: str | None, model: str | None, api_key: str | None = None):
        self.base_url = (base_url or DEFAULT_CODEX_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_CODEX_MODEL
        # The key is optional at this layer, but 9Router only skips it for
        # requests from loopback *inside* its container. With Compose, the
        # backend calls over the Docker network, so a key is always required even
        # if REQUIRE_API_KEY=false. Only a host-run 9Router on the backend machine
        # can omit it, so keep it optional instead of raising here.
        self.api_key = api_key or None

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": _build_prompt(query, max_results)}],
            # OpenAI-hosted tool runs server-side; there is nothing extra to
            # install and no client-side tool call to handle.
            "tools": [{"type": "web_search"}],
            # GPT-5 models can spend a long time reasoning by default. This task
            # only copies search results into JSON, so lower the effort to reduce latency.
            "reasoning": {"effort": "low"},
            "stream": False,
            "store": False,
        }

        async with httpx.AsyncClient(timeout=_CODEX_TIMEOUT) as client:
            resp = await client.post(f"{self.base_url}/responses", headers=headers, json=payload)
        resp.raise_for_status()

        body = resp.json()
        # 9Router/OpenAI may return 200 with `error` when quota is exhausted or
        # the model is rejected. Silently returning empty results would make the
        # "Test search connection" button report success with no results.
        if isinstance(body.get("error"), dict):
            raise RuntimeError(str(body["error"].get("message") or body["error"]))

        return _merge_results(_output_items(body), max_results)
