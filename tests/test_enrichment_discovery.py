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
    queries = build_search_queries("Acme", None, "fintech tại TP.HCM")
    assert any("fintech tại TP.HCM" in q for q in queries)


def test_factory_returns_no_op_provider_by_default():
    provider = get_search_provider(SearchSettings())
    assert provider.name == "none"


def test_factory_rejects_unknown_provider():
    import pytest

    with pytest.raises(ValueError):
        get_search_provider(SearchSettings(provider="not-real"))


def test_searxng_requires_url():
    import pytest

    with pytest.raises(ValueError):
        get_search_provider(SearchSettings(provider="searxng"))


def test_paid_providers_require_api_key():
    import pytest

    for name in ("brave", "tavily", "serper"):
        with pytest.raises(ValueError):
            get_search_provider(SearchSettings(provider=name))


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
    # Query cache-busting đứng sau đuôi file -> vẫn phải nhận ra là CSS.
    assert _should_skip("https://acme.vn/assets/app.css?v=9f2a")
    assert _should_skip("https://acme.vn/logo.png")
    assert _should_skip("https://acme.vn/login")

    assert not _should_skip("https://acme.vn/about-us")
    assert not _should_skip("https://acme.vn/lien-he")
    assert not _should_skip("https://acme.vn/")
