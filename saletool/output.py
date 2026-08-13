"""Xuất kết quả (danh sách công ty + liên hệ) ra CSV hoặc JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from saletool.models import CompanyResult

CSV_FIELDS = [
    "company_name",
    "company_linkedin_url",
    "company_domain",
    "company_industry",
    "company_location",
    "company_employee_count",
    "contact_full_name",
    "contact_title",
    "contact_seniority",
    "contact_linkedin_url",
    "contact_email",
]


def _flatten(results: list[CompanyResult]) -> list[dict]:
    rows = []
    for result in results:
        c = result.company
        if not result.contacts:
            rows.append(
                {
                    "company_name": c.name,
                    "company_linkedin_url": c.linkedin_url,
                    "company_domain": c.domain,
                    "company_industry": c.industry,
                    "company_location": c.location,
                    "company_employee_count": c.employee_count,
                    "contact_full_name": None,
                    "contact_title": None,
                    "contact_seniority": None,
                    "contact_linkedin_url": None,
                    "contact_email": None,
                }
            )
            continue
        for contact in result.contacts:
            rows.append(
                {
                    "company_name": c.name,
                    "company_linkedin_url": c.linkedin_url,
                    "company_domain": c.domain,
                    "company_industry": c.industry,
                    "company_location": c.location,
                    "company_employee_count": c.employee_count,
                    "contact_full_name": contact.full_name,
                    "contact_title": contact.title,
                    "contact_seniority": contact.seniority,
                    "contact_linkedin_url": contact.linkedin_url,
                    "contact_email": contact.email,
                }
            )
    return rows


def write_csv(results: list[CompanyResult], path: str | Path) -> None:
    rows = _flatten(results)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(results: list[CompanyResult], path: str | Path) -> None:
    data = [result.model_dump() for result in results]
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
