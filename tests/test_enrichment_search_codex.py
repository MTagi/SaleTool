"""Test CodexSearchProvider — web search with GPT's `web_search` tool.

Unlike other providers, this one returns results written by an LLM. The important
test is not parsing JSON from a fixed API, but **the reliability order of three
URL sources** in one response: citations, the model's own list, and the tool-call
source list.
"""

import asyncio
import json

import httpx
import pytest

from saletool.enrichment.search import get_search_provider
from saletool.enrichment.search.providers import DEFAULT_CODEX_BASE_URL, DEFAULT_CODEX_MODEL
from saletool.models import SEARCH_PROVIDERS, SEARCH_PROVIDERS_REQUIRING_KEY, SearchSettings

RESPONSES_URL = f"{DEFAULT_CODEX_BASE_URL}/responses"


def _message(text: str, annotations: list[dict] | None = None) -> dict:
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": annotations or []}],
    }


def _answer(rows: list[dict]) -> str:
    return json.dumps({"results": rows})


def _provider(**overrides):
    settings = SearchSettings(provider="codex", **overrides)
    return get_search_provider(settings)


def _search(provider, query: str = "Acme company profile", max_results: int = 5):
    return asyncio.run(provider.search(query, max_results=max_results))


# --- Registration -----------------------------------------------------------


def test_codex_is_registered_and_needs_no_api_key():
    # All three lists must match, or the frontend shows a provider rejected by the backend.
    assert "codex" in SEARCH_PROVIDERS
    assert "codex" not in SEARCH_PROVIDERS_REQUIRING_KEY
    assert _provider().name == "codex"


def test_defaults_point_at_a_local_9router():
    provider = _provider()
    assert provider.base_url == DEFAULT_CODEX_BASE_URL
    assert provider.model == DEFAULT_CODEX_MODEL
    assert provider.api_key is None


# --- HTTP contract ----------------------------------------------------------


def test_request_shape_matches_the_responses_api(httpx_mock):
    """Verify the endpoint, tool name, and disabled streaming.

    `tools: [{"type": "web_search"}]` is the core feature; a wrong name makes
    the model answer from memory, returning results with fabricated URLs.
    """
    httpx_mock.add_response(url=RESPONSES_URL, method="POST", json={"output": []})

    _search(_provider(), max_results=3)

    request = httpx_mock.get_requests()[0]
    body = json.loads(request.content)

    assert body["model"] == DEFAULT_CODEX_MODEL
    assert body["tools"] == [{"type": "web_search"}]
    assert body["stream"] is False
    assert "3" in body["input"][0]["content"]
    # Local 9Router does not require a key by default; do not add an empty header.
    assert "authorization" not in request.headers


def test_api_key_is_sent_only_when_configured(httpx_mock):
    httpx_mock.add_response(url=RESPONSES_URL, method="POST", json={"output": []})

    _search(_provider(api_key="9r-secret"))

    assert httpx_mock.get_requests()[0].headers["Authorization"] == "Bearer 9r-secret"


def test_custom_endpoint_and_model_are_used(httpx_mock):
    """The same code works with real OpenAI, using only a different base_url and model."""
    httpx_mock.add_response(url="https://api.openai.com/v1/responses", json={"output": []})

    _search(_provider(base_url="https://api.openai.com/v1/", model="gpt-5"))

    assert json.loads(httpx_mock.get_requests()[0].content)["model"] == "gpt-5"


def test_http_error_is_raised_not_swallowed(httpx_mock):
    httpx_mock.add_response(url=RESPONSES_URL, status_code=401, json={})

    with pytest.raises(httpx.HTTPStatusError):
        _search(_provider())


def test_error_object_inside_a_200_is_raised(httpx_mock):
    """When Codex quota is exhausted, 9Router still returns 200 with `error`.
    Silently returning empty results would make "Test search connection" succeed
    despite no results being available."""
    httpx_mock.add_response(
        url=RESPONSES_URL, json={"error": {"message": "usage limit reached"}, "output": []}
    )

    with pytest.raises(RuntimeError, match="usage limit reached"):
        _search(_provider())


# --- Merge results ----------------------------------------------------------


def test_citations_win_and_borrow_title_snippet_from_the_answer(httpx_mock):
    """Get URLs from citations (actually opened by the tool), and title/snippet from JSON."""
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                _message(
                    _answer([{"url": "https://vnexpress.net/acme", "title": "Acme", "snippet": "S"}]),
                    annotations=[
                        {"type": "url_citation", "url": "https://vnexpress.net/acme", "title": None}
                    ],
                )
            ]
        },
    )

    results = _search(_provider())

    assert [r.url for r in results] == ["https://vnexpress.net/acme"]
    assert results[0].title == "Acme"
    assert results[0].snippet == "S"


def test_nested_url_citation_shape_is_accepted(httpx_mock):
    """Direct OpenAI and 9Router calls do not return identical annotations."""
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                _message(
                    "not JSON",
                    annotations=[{"url_citation": {"url": "https://cafef.vn/acme", "title": "T"}}],
                )
            ]
        },
    )

    results = _search(_provider())

    assert [(r.url, r.title) for r in results] == [("https://cafef.vn/acme", "T")]


def test_tracking_params_are_stripped_so_one_page_is_one_result(httpx_mock):
    """OpenAI adds `?utm_source=openai` to citation URLs; without removing it,
    one page appears twice, once from the citation and once from JSON."""
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                _message(
                    _answer([{"url": "https://acme.vn/about", "title": "About"}]),
                    annotations=[
                        {
                            "type": "url_citation",
                            "url": "https://acme.vn/about?utm_source=openai#top",
                        }
                    ],
                )
            ]
        },
    )

    results = _search(_provider())

    assert [r.url for r in results] == ["https://acme.vn/about"]


def test_model_list_fills_up_when_there_are_no_citations(httpx_mock):
    """The model returns JSON without citations; results must still be returned."""
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                {"type": "reasoning", "summary": []},
                _message(
                    "```json\n"
                    + _answer(
                        [
                            {"url": "https://a.vn", "title": "A"},
                            {"url": "https://b.vn", "title": "B"},
                        ]
                    )
                    + "\n```"
                ),
            ]
        },
    )

    results = _search(_provider())

    assert [r.url for r in results] == ["https://a.vn", "https://b.vn"]


def test_tool_sources_are_the_last_resort_only(httpx_mock):
    """Some Responses versions emit no annotations and the model writes prose;
    then the tool-call source list is the only remaining source."""
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "type": "search",
                        "sources": [{"url": "https://c.vn"}, {"url": "https://d.vn"}],
                    },
                },
                _message("I found two pages about this company."),
            ]
        },
    )

    results = _search(_provider())

    assert [r.url for r in results] == ["https://c.vn", "https://d.vn"]


def test_max_results_caps_the_merged_list(httpx_mock):
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                _message(
                    _answer([{"url": f"https://site{i}.vn"} for i in range(6)]),
                    annotations=[{"type": "url_citation", "url": "https://site0.vn"}],
                )
            ]
        },
    )

    results = _search(_provider(), max_results=2)

    assert len(results) == 2
    assert results[0].url == "https://site0.vn"


def test_bad_types_from_the_model_do_not_crash_the_run(httpx_mock):
    """If the model returns a numeric title or a row without a URL, skip the row instead of raising."""
    httpx_mock.add_response(
        url=RESPONSES_URL,
        json={
            "output": [
                _message(
                    _answer(
                        [
                            {"title": "missing URL"},
                            {"url": "https://ok.vn", "title": 123, "snippet": ["x"]},
                        ]
                    )
                )
            ]
        },
    )

    results = _search(_provider())

    assert [(r.url, r.title, r.snippet) for r in results] == [("https://ok.vn", None, None)]


def test_empty_output_returns_nothing(httpx_mock):
    httpx_mock.add_response(url=RESPONSES_URL, json={"output": []})

    assert _search(_provider()) == []
