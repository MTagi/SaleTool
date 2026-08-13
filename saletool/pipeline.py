"""Điều phối luồng chính: tìm công ty phù hợp -> lấy liên hệ cấp cao của từng công ty."""

from __future__ import annotations

import logging

from saletool.models import CompanyResult, SearchCriteria
from saletool.providers.base import CompanyContactProvider

logger = logging.getLogger(__name__)


def run_search(criteria: SearchCriteria, provider: CompanyContactProvider) -> list[CompanyResult]:
    """Chạy toàn bộ pipeline và trả về danh sách công ty kèm liên hệ cấp cao."""

    logger.info("Đang tìm công ty phù hợp qua provider '%s'...", provider.name)
    companies = provider.search_companies(criteria)
    logger.info("Tìm thấy %d công ty phù hợp.", len(companies))

    results: list[CompanyResult] = []
    for company in companies:
        try:
            contacts = provider.search_contacts(company, criteria)
        except Exception:  # noqa: BLE001 - không để 1 công ty lỗi làm hỏng cả batch
            logger.exception("Lỗi khi lấy liên hệ cho công ty '%s', bỏ qua.", company.name)
            contacts = []
        results.append(CompanyResult(company=company, contacts=contacts))

    return results
