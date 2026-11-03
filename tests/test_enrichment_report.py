import asyncio
from unittest.mock import AsyncMock

from saletool.enrichment.report import summarize_report
from saletool.models import AppSettings, CompanyEnrichment


def test_summary_preserves_raw_and_roundtrips(monkeypatch):
    settings = AppSettings()
    settings.llm.api_key = "test"
    result = CompanyEnrichment(company_name="Acme", raw_markdown="SOURCE URL: https://example.com\nOriginal text")
    monkeypatch.setattr("saletool.enrichment.report.post_chat", AsyncMock(return_value="## Overview\nEnglish report"))
    asyncio.run(summarize_report(result, settings))
    restored = CompanyEnrichment.model_validate_json(result.model_dump_json())
    assert restored.raw_markdown == "SOURCE URL: https://example.com\nOriginal text"
    assert restored.summary_markdown == "## Overview\nEnglish report"
    assert restored.report_status == "completed"


def test_failure_keeps_raw(monkeypatch):
    settings = AppSettings()
    settings.llm.api_key = "test"
    result = CompanyEnrichment(company_name="Acme", raw_markdown="Original")
    monkeypatch.setattr("saletool.enrichment.report.post_chat", AsyncMock(side_effect=TimeoutError))
    asyncio.run(summarize_report(result, settings))
    assert result.report_status == "failed"
    assert result.raw_markdown == "Original"
    assert result.summary_markdown is None


def test_missing_key_skips_summary():
    result = CompanyEnrichment(company_name="Acme", raw_markdown="Original")
    asyncio.run(summarize_report(result, AppSettings()))
    assert result.report_status == "no_llm"
