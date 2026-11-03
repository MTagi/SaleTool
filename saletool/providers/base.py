"""Shared interface for company/contact data providers.

Important: SaleTool does NOT automate a browser to scrape linkedin.com directly
(this violates its Terms of Service and risks legal action or account bans).
Instead, each provider calls an official API from a third-party data provider
that has legally aggregated/enriched public data (e.g. Apollo.io, People Data
Labs, Proxycurl). You need a valid account/API key for the selected provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from saletool.models import Company, Contact, SearchCriteria


class CompanyContactProvider(ABC):
    """A provider must support two operations: find companies and find their contacts."""

    name: str = "base"

    @abstractmethod
    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        """Return companies matching the criteria (up to criteria.max_companies)."""

    @abstractmethod
    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        """Return contacts for one company, prioritizing seniority."""
