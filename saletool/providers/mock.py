"""Provider giả lập, không gọi mạng — dùng để demo/test pipeline mà không cần API key."""

from __future__ import annotations

from saletool.models import Company, Contact, SearchCriteria
from saletool.providers.base import CompanyContactProvider


class MockProvider(CompanyContactProvider):
    name = "mock"

    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        keyword = criteria.keywords[0] if criteria.keywords else "Demo"
        companies = []
        for i in range(1, criteria.max_companies + 1):
            companies.append(
                Company(
                    name=f"{keyword} Company {i}",
                    linkedin_url=f"https://www.linkedin.com/company/{keyword.lower()}-company-{i}",
                    domain=f"{keyword.lower()}company{i}.example.com",
                    industry=criteria.industries[0] if criteria.industries else "Technology",
                    location=criteria.locations[0] if criteria.locations else "Vietnam",
                    employee_count=100 * i,
                    provider_id=f"mock-org-{i}",
                )
            )
        return companies

    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        levels = criteria.seniority_levels or ["c_suite"]
        contacts = []
        for i in range(1, criteria.max_contacts_per_company + 1):
            contacts.append(
                Contact(
                    full_name=f"Contact {i} of {company.name}",
                    title=criteria.target_titles[0] if criteria.target_titles else "CEO",
                    seniority=levels[(i - 1) % len(levels)],
                    linkedin_url=f"{company.linkedin_url}/employee-{i}" if company.linkedin_url else None,
                    email=f"contact{i}@{company.domain}" if company.domain else None,
                    company_name=company.name,
                )
            )
        return contacts
