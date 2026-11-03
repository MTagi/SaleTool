"""Orchestrate the main flow: find matching companies, then get each company's senior contacts."""

from __future__ import annotations

import logging

from saletool.models import CompanyResult, SearchCriteria
from saletool.providers.base import CompanyContactProvider

logger = logging.getLogger(__name__)


def run_search(criteria: SearchCriteria, provider: CompanyContactProvider) -> list[CompanyResult]:
    """Run the full pipeline and return companies with their senior contacts."""

    logger.info("Searching for matching companies with provider '%s'...", provider.name)
    companies = provider.search_companies(criteria)
    logger.info("Found %d matching companies.", len(companies))

    contact_criteria = criteria.model_copy(update={"target_titles": criteria.expanded_target_titles or criteria.target_titles})
    results: list[CompanyResult] = []
    for company in companies:
        try:
            contacts = provider.search_contacts(company, contact_criteria)
        except Exception:
            logger.exception("Failed to get contacts for company '%s'; skipping.", company.name)
            contacts = []
        results.append(CompanyResult(company=company, contacts=contacts))

    return results
