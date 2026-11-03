import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from saletool.models import Company, LLMSettings, SearchCriteria
from saletool.pipeline import run_search
from saletool.title_expansion import expand_titles


def test_aliases_preserve_original_and_deduplicate_case(monkeypatch):
    request = AsyncMock(return_value={"titles": ["ceo", "Chief Executive Officer", "CEO"]})
    monkeypatch.setattr("saletool.title_expansion.request_json", request)
    titles, status = asyncio.run(expand_titles(["CEO", "COO"], LLMSettings(api_key="test")))
    assert titles == ["CEO", "COO", "Chief Executive Officer"]
    assert status == "expanded"
    request.assert_awaited_once()


@pytest.mark.parametrize("response", [{}, {"titles": "CEO"}, {"titles": [None]}, {"titles": []}])
def test_bad_response_falls_back(monkeypatch, response):
    monkeypatch.setattr("saletool.title_expansion.request_json", AsyncMock(return_value=response))
    assert asyncio.run(expand_titles(["CEO"], LLMSettings(api_key="test"))) == (["CEO"], "fallback")


def test_missing_key_and_empty_input_do_not_call_llm(monkeypatch):
    request = AsyncMock()
    monkeypatch.setattr("saletool.title_expansion.request_json", request)
    assert asyncio.run(expand_titles(["CEO"], LLMSettings())) == (["CEO"], "no_llm")
    assert asyncio.run(expand_titles([], LLMSettings(api_key="test"))) == ([], "empty")
    request.assert_not_called()


def test_timeout_falls_back(monkeypatch):
    monkeypatch.setattr("saletool.title_expansion.request_json", AsyncMock(side_effect=TimeoutError))
    assert asyncio.run(expand_titles(["CEO"], LLMSettings(api_key="test"))) == (["CEO"], "fallback")


def test_contacts_use_aliases_without_mutating_company_criteria():
    criteria = SearchCriteria(target_titles=["CEO"], expanded_target_titles=["CEO", "Chief Executive Officer"])
    provider = Mock()
    provider.search_companies.return_value = [Company(name="A"), Company(name="B")]
    provider.search_contacts.return_value = []
    run_search(criteria, provider)
    assert criteria.target_titles == ["CEO"]
    assert provider.search_contacts.call_count == 2
    for call in provider.search_contacts.call_args_list:
        assert call.args[1].target_titles == criteria.expanded_target_titles
