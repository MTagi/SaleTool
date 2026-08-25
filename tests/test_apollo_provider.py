"""Test ApolloProvider.

Trọng tâm là bốn chỗ dễ sai âm thầm: đường dẫn endpoint, cách lọc ngành, phân
trang, và bước tra email (chỗ duy nhất tốn credit).
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


# --- Endpoint ---------------------------------------------------------------


def test_endpoints_use_the_api_v1_base_and_api_search():
    """`/v1/...` là đường dẫn cũ, và `mixed_people/search` trả 403 trên gói Basic."""
    assert ORGANIZATION_SEARCH_URL.startswith("https://api.apollo.io/api/v1/")
    assert PEOPLE_SEARCH_URL.endswith("/mixed_people/api_search")
    assert PEOPLE_ENRICH_URL.endswith("/people/bulk_match")


def test_403_gives_an_actionable_message(httpx_mock):
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", status_code=403, json={})

    with pytest.raises(RuntimeError, match="403"):
        _provider().search_companies(SearchCriteria(max_companies=1))


# --- Lọc ngành --------------------------------------------------------------


def test_industry_names_go_to_keyword_tags_not_tag_ids(httpx_mock):
    """Tên ngành nhét vào `organization_industry_tag_ids` thì Apollo lặng lẽ bỏ qua."""
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": []})

    _provider().search_companies(
        SearchCriteria(industries=["Fintech"], keywords=["payments"], max_companies=5)
    )

    payload = httpx_mock.get_requests()[0].read().decode()
    assert "Fintech" in payload
    assert "q_organization_keyword_tags" in payload
    assert "organization_industry_tag_ids" not in payload


def test_real_apollo_tag_ids_still_use_the_tag_id_filter(httpx_mock):
    """Ai đã tra được tag ID thật thì dán vào cùng ô đó, code tự nhận ra."""
    import json

    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": []})

    _provider().search_companies(
        SearchCriteria(industries=["5567cd4773696439b10b0000", "Fintech"], max_companies=5)
    )

    body = json.loads(httpx_mock.get_requests()[0].read())
    assert body["organization_industry_tag_ids"] == ["5567cd4773696439b10b0000"]
    assert body["q_organization_keyword_tags"] == ["Fintech"]


# --- Phân trang -------------------------------------------------------------


def test_more_than_one_page_is_fetched(httpx_mock):
    """Apollo trả tối đa 100/trang; xin 150 mà chỉ lấy trang 1 là thiếu âm thầm."""
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
    """Apollo không phải lúc nào cũng trả `pagination` — trang rỗng là tín hiệu dừng."""
    httpx_mock.add_response(
        url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": [_org("org-1", "A")]}
    )
    httpx_mock.add_response(url=ORGANIZATION_SEARCH_URL, method="POST", json={"organizations": []})

    assert len(_provider().search_companies(SearchCriteria(max_companies=50))) == 1


# --- Liên hệ + email --------------------------------------------------------


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
    """Mỗi lần tra là 1 credit — không trả tiền cho bản ghi chắc chắn không có email."""
    httpx_mock.add_response(
        url=PEOPLE_SEARCH_URL,
        method="POST",
        json={"people": [{"id": "p-1", "name": "No Email", "email_status": "unavailable"}]},
    )

    contacts = _provider().search_contacts(
        Company(name="Acme", provider_id="org-1"), SearchCriteria(max_contacts_per_company=5)
    )

    assert contacts[0].email is None
    assert len(httpx_mock.get_requests()) == 1  # không gọi bulk_match


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
    """Email cá nhân tốn thêm credit và bị chặn ở vùng GDPR — phải là opt-in."""
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
    """Mất email thì vẫn còn LinkedIn URL; mất cả danh sách thì không còn gì."""
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
    """bulk_match nhận tối đa 10 người/lần."""
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
    """Chỉ một phần danh sách được tra — kết quả phải ghép đúng vị trí gốc."""
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
