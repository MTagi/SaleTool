"""Test pipeline enrich với HTTP đã mock — không gọi mạng thật, không gọi LLM thật."""

import asyncio

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
<p>Acme Fintech is a payments platform for SMEs in Vietnam. Mã số thuế: 0312345678</p>
</body></html>
"""


class _StubFetcher:
    """Thay FallbackFetcher: trả HTML cố định, ghi lại URL đã gọi."""

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
    s.enrichment.use_llm = False  # test này chỉ kiểm tra tầng 0
    s.enrichment.use_web_search = False
    s.enrichment.request_delay_seconds = 0
    return s


@pytest.fixture
def no_network(monkeypatch):
    """Chặn mọi khám phá URL thật; trả về danh sách cố định."""

    async def fake_discover(domain, user_agent, max_pages, timeout=15.0):
        return [f"https://{domain}/about"]

    monkeypatch.setattr(pipeline_module, "discover_company_site_urls", fake_discover)


def test_enriches_from_structured_data_without_llm(settings, no_network, monkeypatch):
    stub = _StubFetcher({"https://acme.vn/about": ABOUT_HTML})
    monkeypatch.setattr(pipeline_module, "_build_fetcher", lambda _s: stub)

    result = asyncio.run(
        enrich_company(EnrichTarget(company_name="Acme Fintech", domain="https://www.acme.vn"), settings)
    )

    assert result.domain == "acme.vn"  # đã chuẩn hoá
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
    stub = _StubFetcher({})  # mọi URL đều 404
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
    assert stub.requested == []  # không có gì để tải


def test_respects_max_pages_per_company(settings, monkeypatch):
    settings.enrichment.max_pages_per_company = 2

    async def many_urls(domain, user_agent, max_pages, timeout=15.0):
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

    # Trang không có description/executive sẵn -> buộc phải gọi LLM
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
