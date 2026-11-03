from saletool.enrichment.discovery import build_search_queries, normalize_domain
from saletool.enrichment.search import SearchResult, get_search_provider
from saletool.models import SearchSettings


def test_normalize_domain_strips_scheme_www_path_and_port():
    assert normalize_domain("https://www.ABC.com/about?x=1") == "abc.com"
    assert normalize_domain("abc.com") == "abc.com"
    assert normalize_domain("http://abc.com:8080") == "abc.com"
    assert normalize_domain("") is None


def test_search_queries_exclude_own_domain():
    queries = build_search_queries("Acme Fintech", "acmefintech.vn", None)

    assert any("-site:acmefintech.vn" in q for q in queries)
    assert all("Acme Fintech" in q for q in queries)


def test_search_queries_include_extra_context():
    queries = build_search_queries("Acme", None, "fintech in Ho Chi Minh City")
    assert any("fintech in Ho Chi Minh City" in q for q in queries)


def test_factory_returns_no_op_provider_by_default():
    provider = get_search_provider(SearchSettings())
    assert provider.name == "none"


def test_factory_rejects_unknown_provider():
    import pytest

    with pytest.raises(ValueError):
        get_search_provider(SearchSettings(provider="not-real"))


def test_paid_providers_require_api_key():
    import pytest

    for name in ("brave", "tavily", "serper", "exa"):
        with pytest.raises(ValueError):
            get_search_provider(SearchSettings(provider=name))


def test_exa_is_registered_and_needs_a_key():
    from saletool.models import SEARCH_PROVIDERS, SEARCH_PROVIDERS_REQUIRING_KEY

    # All three lists must match, or the frontend will show a provider rejected by the backend.
    assert "exa" in SEARCH_PROVIDERS
    assert "exa" in SEARCH_PROVIDERS_REQUIRING_KEY
    assert get_search_provider(SearchSettings(provider="exa", api_key="k")).name == "exa"


async def _run(coro):
    return await coro


def test_no_provider_returns_empty_instead_of_raising():
    import asyncio

    provider = get_search_provider(SearchSettings())
    assert asyncio.run(provider.search("anything")) == []


def test_search_result_model():
    result = SearchResult(url="https://example.com", title="T", snippet="S")
    assert result.url == "https://example.com"


def test_skips_build_assets_and_functional_pages():
    from saletool.enrichment.discovery import _should_skip

    assert _should_skip("https://acme.vn/_next/static/chunks/webpack-01d756.js")
    assert _should_skip("https://acme.vn/static/css/main.6cf63a.css")
    # A cache-busting query follows the extension; it must still be identified as CSS.
    assert _should_skip("https://acme.vn/assets/app.css?v=9f2a")
    assert _should_skip("https://acme.vn/logo.png")
    assert _should_skip("https://acme.vn/login")

    assert not _should_skip("https://acme.vn/about-us")
    assert not _should_skip("https://acme.vn/lien-he")
    assert not _should_skip("https://acme.vn/")


def test_exa_sends_the_documented_request_shape(httpx_mock):
    """Verify the Exa HTTP contract: endpoint, auth header, and body field names."""
    import asyncio

    httpx_mock.add_response(
        url="https://api.exa.ai/search",
        json={"results": [{"url": "https://vnexpress.net/acme", "title": "Acme"}]},
    )

    provider = get_search_provider(SearchSettings(provider="exa", api_key="secret"))
    results = asyncio.run(provider.search("Acme company profile", max_results=3))

    request = httpx_mock.get_requests()[0]
    assert request.headers["Authorization"] == "Bearer secret"

    import json

    body = json.loads(request.content)
    assert body["query"] == "Acme company profile"
    assert body["numResults"] == 3
    # Do not request `contents`: Exa charges extra for extraction, while the
    # pipeline only uses `url`. That would pay for data immediately discarded.
    assert "contents" not in body

    assert [r.url for r in results] == ["https://vnexpress.net/acme"]


def test_exa_skips_results_without_a_url(httpx_mock):
    """Results without a URL are useless to the pipeline; exclude them from the list."""
    import asyncio

    httpx_mock.add_response(
        url="https://api.exa.ai/search",
        json={"results": [{"title": "missing URL"}, {"url": "https://ok.vn"}]},
    )

    provider = get_search_provider(SearchSettings(provider="exa", api_key="k"))
    results = asyncio.run(provider.search("q"))

    assert [r.url for r in results] == ["https://ok.vn"]
