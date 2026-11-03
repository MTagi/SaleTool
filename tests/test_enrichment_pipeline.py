"""Test the enrichment pipeline with mocked HTTP; no real network or LLM calls."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from saletool.enrichment import pipeline as pipeline_module
from saletool.enrichment.fetcher import FetchedPage
from saletool.enrichment.pipeline import enrich_company
from saletool.models import AppSettings, EnrichTarget

ABOUT_HTML = """
<html><head>
<title>Acme Fintech</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization",
 "name":"Acme Fintech JSC","email":"hello@acme.vn","foundingDate":"2018"}
</script>
</head><body>
<a href="mailto:sales@acme.vn">Sales</a>
<p>Acme Fintech is a payments platform for SMEs in Vietnam. M\xe3 s\u1ed1 thu\u1ebf: 0312345678</p>
</body></html>
"""


@pytest.mark.parametrize("external_count,reserved", [(0, 4), (4, 4), (2, 2), (5, 20)])
def test_web_search_gets_budget_even_when_sitemap_is_full(settings, monkeypatch, external_count, reserved):
    settings.enrichment.use_web_search = True
    settings.search.provider = "tavily"
    settings.enrichment.max_pages_per_company = 8
    settings.enrichment.web_search_reserved_pages = reserved
    website = [f"https://acme.vn/{i}" for i in range(8)]
    external = [f"https://news.example/{i}" for i in range(external_count)]
    monkeypatch.setattr(pipeline_module, "discover_company_site_urls", AsyncMock(return_value=website))
    monkeypatch.setattr(pipeline_module, "get_search_provider", lambda _: object())
    search = AsyncMock(return_value=external)
    monkeypatch.setattr(pipeline_module, "discover_external_urls", search)
    stub = _StubFetcher({u: ABOUT_HTML for u in website + external})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _: stub)
    result = asyncio.run(enrich_company(EnrichTarget(company_name="Acme", domain="acme.vn"), settings))
    search.assert_awaited_once()
    assert search.call_args.kwargs["max_results"] == min(reserved, 8, settings.search.max_results)
    assert len(stub.requested) == 8
    assert set(external).issubset(stub.requested)
    assert result.search_queries


class _StubFetcher:
    """Replacement for FallbackFetcher: return fixed HTML and record requested URLs."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requested: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.requested.append(url)
        html = self.pages.get(url)
        if html is None:
            return FetchedPage(url=url, ok=False, error="HTTP 404", method="http")
        return FetchedPage(url=url, html=html, ok=True, status_code=200, method="http")


@pytest.fixture
def settings():
    s = AppSettings()
    s.enrichment.use_llm = False  # This test checks only stage 0.
    s.enrichment.use_web_search = False
    s.enrichment.request_delay_seconds = 0
    return s


@pytest.fixture
def no_network(monkeypatch):
    """Block real URL discovery and return a fixed list."""

    async def fake_discover(domain, user_agent, max_pages, timeout=15.0, **kwargs):
        return [f"https://{domain}/about"]

    monkeypatch.setattr(pipeline_module, "discover_company_site_urls", fake_discover)


def test_enriches_from_structured_data_without_llm(settings, no_network, monkeypatch):
    stub = _StubFetcher({"https://acme.vn/about": ABOUT_HTML})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(
        enrich_company(EnrichTarget(company_name="Acme Fintech", domain="https://www.acme.vn"), settings)
    )

    assert result.domain == "acme.vn"  # Normalized.
    assert result.pages_fetched == 1
    assert result.llm_calls == 0
    assert "hello@acme.vn" in result.emails
    assert "sales@acme.vn" in result.emails
    assert result.founded_year == 2018
    assert result.tax_code == "0312345678"
    assert not result.is_empty()


def test_records_provenance_for_every_page(settings, no_network, monkeypatch):
    stub = _StubFetcher({"https://acme.vn/about": ABOUT_HTML})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(
        enrich_company(EnrichTarget(company_name="Acme", domain="acme.vn"), settings)
    )

    assert result.sources
    assert all(s.url and s.fetched_at for s in result.sources)
    assert result.enriched_at is not None


def test_failed_page_is_recorded_not_raised(settings, no_network, monkeypatch):
    stub = _StubFetcher({})  # Every URL returns 404.
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(
        enrich_company(EnrichTarget(company_name="Ghost", domain="ghost.vn"), settings)
    )

    assert result.pages_fetched == 0
    assert result.is_empty()
    assert any(not s.ok for s in result.sources)


def test_no_domain_and_no_search_yields_empty_result(settings, monkeypatch):
    stub = _StubFetcher({})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(enrich_company(EnrichTarget(company_name="Unknown Co"), settings))

    assert result.is_empty()
    assert stub.requested == []  # Nothing to fetch.


def test_respects_max_pages_per_company(settings, monkeypatch):
    settings.enrichment.max_pages_per_company = 2

    async def many_urls(domain, user_agent, max_pages, timeout=15.0, **kwargs):
        return [f"https://{domain}/p{i}" for i in range(10)][:max_pages]

    monkeypatch.setattr(pipeline_module, "discover_company_site_urls", many_urls)
    stub = _StubFetcher({f"https://acme.vn/p{i}": ABOUT_HTML for i in range(10)})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(
        enrich_company(EnrichTarget(company_name="Acme", domain="acme.vn"), settings)
    )

    assert result.pages_fetched == 2
    assert len(stub.requested) == 2


def test_llm_is_called_when_enabled_and_data_missing(settings, no_network, monkeypatch):
    settings.enrichment.use_llm = True
    settings.llm.api_key = "sk-test"

    from saletool.enrichment.llm import LLMExtraction
    from saletool.models import Executive

    class FakeLLM:
        def __init__(self, _settings):
            self.calls = 0

        async def extract_company_info(self, company_name, page_text, source_url=None):
            self.calls += 1
            return LLMExtraction(
                description="A payments platform.",
                industry="Fintech",
                executives=[Executive(full_name="Nguyen Van A", title="CEO")],
            )

    monkeypatch.setattr(pipeline_module, "LLMClient", FakeLLM)

    # The page has no description/executives, so the LLM must be called.
    bare_html = "<html><body><p>Some long text about the company operations.</p></body></html>"
    stub = _StubFetcher({"https://acme.vn/about": bare_html})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(
        enrich_company(EnrichTarget(company_name="Acme", domain="acme.vn"), settings)
    )

    assert result.llm_calls == 1
    assert result.industry == "Fintech"
    assert result.executives[0].full_name == "Nguyen Van A"
    assert result.executives[0].source_url == "https://acme.vn/about"
