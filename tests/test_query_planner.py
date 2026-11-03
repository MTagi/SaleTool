import asyncio
from unittest.mock import AsyncMock

import pytest

from saletool.enrichment.query_planner import plan_queries
from saletool.models import AppSettings, Company, EnrichTarget


def test_uses_apollo_profile_and_anchors_queries(monkeypatch):
    request = AsyncMock(return_value={"queries": ["warehouse expansion", "Acme leadership"]})
    monkeypatch.setattr("saletool.enrichment.query_planner.request_json", request)
    settings = AppSettings()
    settings.llm.api_key = "test"
    target = EnrichTarget(company_name="Acme", company_profile=Company(name="Acme", description="Logistics operator"))
    queries, status = asyncio.run(plan_queries(target, settings))
    assert status == "llm"
    assert queries == ['"Acme" warehouse expansion', 'Acme leadership']
    assert "Logistics operator" in request.call_args.args[1]["messages"][1]["content"]


@pytest.mark.parametrize("response", [{}, {"queries": []}, {"queries": [None]}, {"queries": "bad"}])
def test_invalid_plan_falls_back(monkeypatch, response):
    monkeypatch.setattr("saletool.enrichment.query_planner.request_json", AsyncMock(return_value=response))
    settings = AppSettings()
    settings.llm.api_key = "test"
    queries, status = asyncio.run(plan_queries(EnrichTarget(company_name="Acme"), settings))
    assert status == "fallback"
    assert all("Acme" in q for q in queries)


def test_without_key_skips_model(monkeypatch):
    request = AsyncMock()
    monkeypatch.setattr("saletool.enrichment.query_planner.request_json", request)
    _, status = asyncio.run(plan_queries(EnrichTarget(company_name="Acme"), AppSettings()))
    assert status == "no_llm"
    request.assert_not_called()
