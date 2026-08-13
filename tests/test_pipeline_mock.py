from saletool.models import SearchCriteria
from saletool.pipeline import run_search
from saletool.providers.mock import MockProvider


def test_run_search_with_mock_provider():
    criteria = SearchCriteria(
        keywords=["fintech"],
        max_companies=3,
        max_contacts_per_company=2,
    )
    provider = MockProvider()

    results = run_search(criteria, provider)

    assert len(results) == 3
    for result in results:
        assert result.company.name.startswith("fintech")
        assert len(result.contacts) == 2
        for contact in result.contacts:
            assert contact.company_name == result.company.name
