"""Test ApolloProvider.

Focus on four places that can fail silently: endpoint paths, industry filtering,
pagination, and email lookup (the only step that costs credits).
"""

import httpx
import pytest

from saletool.models import Company, SearchCriteria
from saletool.providers.apollo import (
    ORGANIZATION_SEARCH_URL,
    PEOPLE_ENRICH_URL,
    PEOPLE_SEARCH_URL,
    ApolloProvider,
)


def _provider(**kwargs) -> ApolloProvider:
    kwargs.setdefault("api_key", "test-key")
    kwargs.setdefault("client", httpx.Client())
    return ApolloProvider(**kwargs)


def _org(org_id: str, name: str) -> dict:
    return {
        "id": org_id,
        "name": name,
        "linkedin_url": f"https://www.linkedin.com/company/{org_id}",
        "primary_domain": f"{org_id}.com",
        "industry": "Financial Services",
        "city": "Ho Chi Minh City",
        "estimated_num_employees": 250,
    }


def test_apollo_provider_requires_api_key():
    with pytest.raises(ValueError):
        ApolloProvider(api_key="")


def test_company_profile_fields_survive_serialization(httpx_mock):
    org = _org("demo", "Demo")
    org.update(short_description="Warehouse software", founded_year=2010,
               primary_phone={"number": "+123"}, raw_address="Example street",
               annual_revenue=1200000, total_funding_printed="2M",
               current_technologies=[{"name": "Python"}, None, {}],
               keywords=["logistics"], state="Example state", country="Vietnam")
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST",
                            json={"organizations": [org]})
    company = _provider().search_companies(SearchCriteria(max_companies=1))[0]
    restored = Company.model_validate_json(company.model_dump_json())
    assert restored.description == "Warehouse software"
    assert restored.phone == "+123"
    assert restored.founded_year == 2010
    assert restored.annual_revenue == "1200000"
    assert restored.total_funding == "2M"
    assert restored.technologies == ["Python"]
    assert restored.keywords == ["logistics"]
    assert restored.location == "Ho Chi Minh City, Example state, Vietnam"
    assert restored.address == "Example street"


# --- Endpoint ---------------------------------------------------------------


def test_endpoints_use_the_api_v1_base_and_api_search():
    """`/v1/...` is the old path, and `mixed_people/search` returns 403 on the Basic plan."""
    assert ORGANIZATION_SEARCH_URL.startswith("https://api.apollo.io/api/v1/")
    assert PEOPLE_SEARCH_URL.endswith("/mixed_people/api_search")
    assert PEOPLE_ENRICH_URL.endswith("/people/bulk_match")


def test_403_gives_an_actionable_message(httpx_mock):
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", status_code=403, json={})

    with pytest.raises(RuntimeError, match="403"):
        _provider().search_companies(SearchCriteria(max_companies=1))


# --- Industry filtering -----------------------------------------------------


def test_industry_names_go_to_keyword_tags_not_tag_ids(httpx_mock):
    """Apollo silently ignores industry names in `organization_industry_tag_ids`."""
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": []})

    _provider().search_companies(
        SearchCriteria(industries=["Fintech"], keywords=["payments"], max_companies=5)
    )

    payload = httpx_mock.get_requests()[0].read().decode()
    assert "Fintech" in payload
    assert "q_organization_keyword_tags" in payload
    assert "organization_industry_tag_ids" not in payload


def test_real_apollo_tag_ids_still_use_the_tag_id_filter(httpx_mock):
    """A real tag ID can be entered in the same field and is recognized automatically."""
    import json

    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": []})

    _provider().search_companies(
        SearchCriteria(industries=["5567cd4773696439b10b0000", "Fintech"], max_companies=5)
    )

    body = json.loads(httpx_mock.get_requests()[0].read())
    assert body["organization_industry_tag_ids"] == ["5567cd4773696439b10b0000"]
    assert body["q_organization_keyword_tags"] == ["Fintech"]


# --- Pagination -------------------------------------------------------------


def test_more_than_one_page_is_fetched(httpx_mock):
    """Apollo returns at most 100 per page; requesting 150 but fetching only page 1 silently misses results."""
    httpx_mock.add_response(
        url=ORGANIZATION_SEARCH_URL,
        method="POST",
        json={
            "organizations": [_org(f"org-{i}", f"Company {i}") for i in range(100)],
            "pagination": {"total_pages": 2},
        },
    )
    httpx_mock.add_response(
        url=ORGANIZATION_SEARCH_URL,
        method="POST",
        json={
            "organizations": [_org(f"org-{i}", f"Company {i}") for i in range(100, 150)],
            "pagination": {"total_pages": 2},
        },
    )

    companies = _provider().search_companies(SearchCriteria(max_companies=150))

    assert len(companies) == 150
    assert len(httpx_mock.get_requests()) == 2


def test_pagination_keeps_page_size_and_returns_distinct_companies(httpx_mock):
    import json

    def page_response(request):
        body = json.loads(request.content)
        start = (body["page"] - 1) * body["per_page"]
        return httpx.Response(200, json={
            "organizations": [_org(f"org-{i}", f"Company {i}")
                              for i in range(start, min(start + body["per_page"], 150))],
            "pagination": {"total_pages": 2},
        })

    httpx_mock.add_callback(page_response, url=ORGANIZATION_SEARCH_URL, is_reusable=True)
    companies = _provider().search_companies(SearchCriteria(max_companies=150))
    assert len(companies) == len({c.provider_id for c in companies}) == 150
    assert [c.provider_id for c in companies] == [f"org-{i}" for i in range(150)]


def test_pagination_stops_at_the_last_page(httpx_mock):
    httpx_mock.add_response(
        url=ORGANIZATION_SEARCH_URL,
        method="POST",
        json={"organizations": [_org("org-1", "Only One")], "pagination": {"total_pages": 1}},
    )

    companies = _provider().search_companies(SearchCriteria(max_companies=50))

    assert len(companies) == 1
    assert len(httpx_mock.get_requests()) == 1


def test_pagination_stops_on_an_empty_page(httpx_mock):
    """Apollo does not always return `pagination`; an empty page signals completion."""
    httpx_mock.add_response(
        url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": [_org("org-1", "A")]}
    )
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": []})

    assert len(_provider().search_companies(SearchCriteria(max_companies=50))) == 1


# --- Contacts and email -----------------------------------------------------


def test_contacts_without_provider_id_returns_empty():
    assert _provider().search_contacts(Company(name="No ID Co"), SearchCriteria()) == []


def test_locked_email_is_revealed_via_enrichment(httpx_mock):
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={
            "people": [
                {
                    "id": "p-1",
                    "name": "Nguyen Van A",
                    "title": "CEO",
                    "seniority": "c_suite",
                    "email": "email_not_unlocked@domain.com",
                    "email_status": "verified",
                }
            ]
        },
    )
    httpx_mock.add_response(
        url=PEOPLE_ENRICH_URL,
        method="POST",
        json={"matches": [{"id": "p-1", "email": "a@acme.com"}]},
    )

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert contacts[0].email == "a@acme.com"


def test_people_without_an_email_are_not_enriched(httpx_mock):
    """Each lookup costs one credit; do not pay for records that certainly have no email."""
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={"people": [{"id": "p-1", "name": "No Email", "email_status": "unavailable"}]},
    )

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert contacts[0].email is None
    assert len(httpx_mock.get_requests()) == 1  # bulk_match is not called.


def test_an_already_usable_email_is_not_re_enriched(httpx_mock):
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={"people": [{"id": "p-1", "name": "Has Email", "email": "real@acme.com"}]},
    )

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert contacts[0].email == "real@acme.com"
    assert len(httpx_mock.get_requests()) == 1


def test_reveal_emails_false_skips_the_paid_call(httpx_mock):
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={"people": [{"id": "p-1", "name": "A", "has_email": True}]},
    )

    contacts = _provider(reveal_emails=False).search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert contacts[0].email is None
    assert len(httpx_mock.get_requests()) == 1


def test_personal_emails_are_off_by_default(httpx_mock):
    """Personal emails cost extra credits and are blocked in GDPR regions, so they must be opt-in."""
    import json

    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={"people": [{"id": "p-1", "name": "A", "has_email": True}]},
    )
    httpx_mock.add_response(url=PEOPLE_ENRICH_URL, method="POST", json={"matches": []})

    _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    body = json.loads(httpx_mock.get_requests()[1].read())
    assert body["reveal_personal_emails"] is False


def test_enrichment_failure_still_returns_the_contacts(httpx_mock):
    """If email lookup fails, the LinkedIn URL remains; losing both leaves nothing."""
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={
            "people": [
                {
                    "id": "p-1",
                    "name": "Nguyen Van A",
                    "linkedin_url": "https://linkedin.com/in/a",
                    "has_email": True,
                }
            ]
        },
    )
    httpx_mock.add_response(url=PEOPLE_ENRICH_URL, method="POST", status_code=500, json={})

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert len(contacts) == 1
    assert contacts[0].email is None
    assert contacts[0].linkedin_url == "https://linkedin.com/in/a"


def test_enrichment_batches_at_ten_people(httpx_mock):
    """bulk_match accepts at most 10 people per request."""
    people = [{"id": f"p-{i}", "name": f"P{i}", "has_email": True} for i in range(12)]
    httpx_mock.add_response(url=PEOPLE_SEARCH_URL, method="POST", json={"people": people})
    httpx_mock.add_response(
        url=PEOPLE_ENRICH_URL,
        method="POST",
        json={"matches": [{"email": f"p{i}@acme.com"} for i in range(10)]},
    )
    httpx_mock.add_response(
        url=PEOPLE_ENRICH_URL,
        method="POST",
        json={"matches": [{"email": f"p{i}@acme.com"} for i in range(10, 12)]},
    )

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=12)
    )

    assert [c.email for c in contacts] == [f"p{i}@acme.com" for i in range(12)]
    assert len(httpx_mock.get_requests()) == 3  # 1 search + 2 batch


def test_revealed_emails_land_on_the_right_person(httpx_mock):
    """Only part of the list is looked up; results must map to their original positions."""
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={
            "people": [
                {"id": "p-1", "name": "Skip Me", "email_status": "unavailable"},
                {"id": "p-2", "name": "Reveal Me", "has_email": True},
                {"id": "p-3", "name": "Already Has", "email": "c@acme.com"},
            ]
        },
    )
    httpx_mock.add_response(
        url=PEOPLE_ENRICH_URL, method="POST", json={"matches": [{"email": "b@acme.com"}]}
    )

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert [c.email for c in contacts] == [None, "b@acme.com", "c@acme.com"]


# --- Contact names before reveal -------------------------------------------


def test_first_name_survives_when_apollo_obfuscates_the_last_name(httpx_mock):
    """Before reveal, Apollo returns `name: null` and `last_name_obfuscated`.

    Observed on the current plan on 2026-09-04. Previously, the provider read only
    `name`, leaving every contact nameless even though Apollo provides a first
    name at no cost and the Messages step requires recipient names.
    """
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={
            "people": [
                {
                    "id": "p-1",
                    "name": None,
                    "first_name": "Phi",
                    "last_name_obfuscated": "S***",
                    "title": "Director of Retail",
                    "has_email": True,
                }
            ]
        },
    )

    contacts = _provider(reveal_emails=False).search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=1)
    )

    assert contacts[0].full_name == "Phi"
    # The hidden portion must not appear in the name: "Phi S***" looks real.
    assert "*" not in contacts[0].full_name


def test_full_name_is_preferred_when_apollo_returns_it(httpx_mock):
    """After reveal (or on a higher plan), Apollo returns the full `name`; prefer it."""
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={
            "people": [
                {"id": "p-1", "name": "Nguyen Van Phi", "first_name": "Phi", "title": "CEO"}
            ]
        },
    )

    contacts = _provider(reveal_emails=False).search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=1)
    )

    assert contacts[0].full_name == "Nguyen Van Phi"
