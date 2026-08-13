import httpx
import pytest

from saletool.models import SearchCriteria
from saletool.providers.apollo import ORGANIZATION_SEARCH_URL, PEOPLE_SEARCH_URL, ApolloProvider


def test_apollo_provider_requires_api_key():
    with pytest.raises(ValueError):
        ApolloProvider(api_key="")


def test_apollo_search_companies_and_contacts(httpx_mock):
    httpx_mock.add_response(
        url=ORGANIZATION_SEARCH_URL,
        method="POST",
        json={
            "organizations": [
                {
                    "id": "org-1",
                    "name": "Acme Fintech",
                    "linkedin_url": "https://www.linkedin.com/company/acme-fintech",
                    "primary_domain": "acmefintech.com",
                    "industry": "Financial Services",
                    "city": "Ho Chi Minh City",
                    "estimated_num_employees": 250,
                }
            ]
        },
    )
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={
            "people": [
                {
                    "name": "Nguyen Van A",
                    "title": "CEO",
                    "seniority": "c_suite",
                    "linkedin_url": "https://www.linkedin.com/in/nguyenvana",
                    "email": "a@acmefintech.com",
                }
            ]
        },
    )

    provider = ApolloProvider(api_key="test-key", client=httpx.Client())
    criteria = SearchCriteria(keywords=["fintech"], max_companies=5, max_contacts_per_company=5)

    companies = provider.search_companies(criteria)
    assert len(companies) == 1
    assert companies[0].name == "Acme Fintech"
    assert companies[0].provider_id == "org-1"

    contacts = provider.search_contacts(companies[0], criteria)
    assert len(contacts) == 1
    assert contacts[0].full_name == "Nguyen Van A"
    assert contacts[0].seniority == "c_suite"
    assert contacts[0].company_name == "Acme Fintech"


def test_apollo_search_contacts_without_provider_id_returns_empty():
    from saletool.models import Company

    provider = ApolloProvider(api_key="test-key")
    criteria = SearchCriteria()
    company = Company(name="No ID Co")

    assert provider.search_contacts(company, criteria) == []
