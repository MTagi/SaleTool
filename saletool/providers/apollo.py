"""Provider dựa trên Apollo.io API (https://docs.apollo.io).

Apollo.io tổng hợp dữ liệu công ty/liên hệ (bao gồm link LinkedIn, chức danh,
seniority...) và cung cấp qua REST API chính thức, có gói miễn phí giới hạn.
Cần API key hợp lệ (biến môi trường APOLLO_API_KEY hoặc truyền trực tiếp).
"""

from __future__ import annotations

import httpx

from saletool.models import Company, Contact, SearchCriteria
from saletool.providers.base import CompanyContactProvider

ORGANIZATION_SEARCH_URL = "https://api.apollo.io/v1/mixed_companies/search"
PEOPLE_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"


class ApolloProvider(CompanyContactProvider):
    name = "apollo"

    def __init__(self, api_key: str, client: httpx.Client | None = None, timeout: float = 30.0):
        if not api_key:
            raise ValueError("Thiếu Apollo API key (APOLLO_API_KEY)")
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=timeout)

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        payload: dict = {
            "page": 1,
            "per_page": min(criteria.max_companies, 100),
        }
        if criteria.keywords:
            payload["q_organization_keyword_tags"] = criteria.keywords
        if criteria.industries:
            payload["organization_industry_tag_ids"] = criteria.industries
        if criteria.locations:
            payload["organization_locations"] = criteria.locations
        if criteria.company_size_min is not None or criteria.company_size_max is not None:
            payload["organization_num_employees_ranges"] = [
                f"{criteria.company_size_min or 1},{criteria.company_size_max or ''}"
            ]

        resp = self._client.post(ORGANIZATION_SEARCH_URL, json=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        companies = []
        for org in data.get("organizations", [])[: criteria.max_companies]:
            companies.append(
                Company(
                    name=org.get("name", ""),
                    linkedin_url=org.get("linkedin_url"),
                    domain=org.get("primary_domain") or org.get("website_url"),
                    industry=org.get("industry"),
                    location=org.get("city") or org.get("country"),
                    employee_count=org.get("estimated_num_employees"),
                    provider_id=org.get("id"),
                )
            )
        return companies

    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        if not company.provider_id:
            return []

        payload: dict = {
            "page": 1,
            "per_page": min(criteria.max_contacts_per_company, 100),
            "organization_ids": [company.provider_id],
        }
        if criteria.seniority_levels:
            payload["person_seniorities"] = criteria.seniority_levels
        if criteria.target_titles:
            payload["person_titles"] = criteria.target_titles

        resp = self._client.post(PEOPLE_SEARCH_URL, json=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        contacts = []
        for person in data.get("people", [])[: criteria.max_contacts_per_company]:
            contacts.append(
                Contact(
                    full_name=person.get("name", ""),
                    title=person.get("title"),
                    seniority=person.get("seniority"),
                    linkedin_url=person.get("linkedin_url"),
                    email=person.get("email"),
                    company_name=company.name,
                )
            )
        return contacts
