"""Provider đọc dữ liệu từ CSV do người dùng tự export/copy thủ công
(vd: từ LinkedIn Sales Navigator qua trình duyệt của chính họ).

Đây là cách "human-in-the-loop": bước tương tác với LinkedIn do người dùng
tự thực hiện thủ công (đúng ToS), SaleTool chỉ chuẩn hoá + lọc + xuất kết quả.

Hỗ trợ 2 file CSV độc lập:
- companies_csv: danh sách công ty (bắt buộc)
- contacts_csv: danh sách liên hệ, có cột liên kết về tên/LinkedIn URL công ty
  (tuỳ chọn — nếu không có, kết quả sẽ chỉ có danh sách công ty, không có liên hệ)

Tên cột không cần khớp chính xác — provider tự nhận diện qua bảng alias
(không phân biệt hoa/thường, khoảng trắng) để tương thích với các định dạng
export phổ biến (Sales Navigator, LinkedIn export, CSV tự tổng hợp...).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from saletool.models import Company, Contact, SearchCriteria
from saletool.providers.base import CompanyContactProvider
from saletool.seniority import infer_seniority

COMPANY_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["company name", "company", "account name", "organization", "name"],
    "linkedin_url": ["company linkedin url", "linkedin url", "linkedin", "company profile url", "company url"],
    "domain": ["website", "domain", "company website", "website url"],
    "industry": ["industry"],
    "location": ["location", "hq location", "country", "city", "headquarters"],
    "employee_count": ["employee count", "company size", "employees", "# employees", "number of employees"],
}

CONTACT_COLUMN_ALIASES: dict[str, list[str]] = {
    "full_name": ["full name", "name", "contact name", "first name last name"],
    "title": ["title", "job title", "position", "headline"],
    "seniority": ["seniority", "seniority level"],
    "linkedin_url": ["linkedin url", "profile url", "linkedin", "contact linkedin url"],
    "email": ["email", "email address", "work email"],
    "company_name": ["company name", "company", "account name", "organization"],
    "company_linkedin_url": ["company linkedin url"],
}


def _normalize(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower())


def _build_field_map(fieldnames: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    """Trả về map {canonical_field: actual_csv_column_name}."""

    normalized_to_actual = {_normalize(fn): fn for fn in fieldnames}
    field_map: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            if candidate in normalized_to_actual:
                field_map[canonical] = normalized_to_actual[candidate]
                break
    return field_map


def _get(row: dict, field_map: dict[str, str], canonical: str) -> str | None:
    col = field_map.get(canonical)
    if not col:
        return None
    value = row.get(col)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _matches_any(value: str | None, needles: list[str]) -> bool:
    if not needles:
        return True
    if not value:
        return False
    value_lower = value.lower()
    return any(needle.lower() in value_lower for needle in needles)


def _parse_employee_count(raw: str | None) -> int | None:
    if not raw:
        return None
    numbers = re.findall(r"\d+", raw.replace(",", ""))
    if not numbers:
        return None
    # Với dải kiểu "51-200" lấy số đầu tiên làm ước lượng.
    return int(numbers[0])


class CsvImportProvider(CompanyContactProvider):
    name = "csv_import"

    def __init__(self, companies_csv: str | Path, contacts_csv: str | Path | None = None):
        self.companies_path = Path(companies_csv)
        if not self.companies_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file companies CSV: {self.companies_path}")

        self.contacts_path = Path(contacts_csv) if contacts_csv else None
        if self.contacts_path and not self.contacts_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file contacts CSV: {self.contacts_path}")

    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        with self.companies_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            field_map = _build_field_map(reader.fieldnames or [], COMPANY_COLUMN_ALIASES)

            companies: list[Company] = []
            for row in reader:
                name = _get(row, field_map, "name")
                if not name:
                    continue

                industry = _get(row, field_map, "industry")
                location = _get(row, field_map, "location")

                # Lọc "mềm" theo tiêu chí: chỉ áp dụng nếu criteria có yêu cầu,
                # vì dữ liệu đã được người dùng tự chọn lọc sẵn trên Sales Navigator.
                if not _matches_any(industry, criteria.industries):
                    continue
                if not _matches_any(location, criteria.locations):
                    continue
                if criteria.keywords and not _matches_any(f"{name} {industry or ''}", criteria.keywords):
                    continue

                employee_count = _parse_employee_count(_get(row, field_map, "employee_count"))
                if employee_count is not None:
                    if criteria.company_size_min is not None and employee_count < criteria.company_size_min:
                        continue
                    if criteria.company_size_max is not None and employee_count > criteria.company_size_max:
                        continue

                companies.append(
                    Company(
                        name=name,
                        linkedin_url=_get(row, field_map, "linkedin_url"),
                        domain=_get(row, field_map, "domain"),
                        industry=industry,
                        location=location,
                        employee_count=employee_count,
                    )
                )
                if len(companies) >= criteria.max_companies:
                    break

        return companies

    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        if not self.contacts_path:
            return []

        with self.contacts_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            field_map = _build_field_map(reader.fieldnames or [], CONTACT_COLUMN_ALIASES)

            contacts: list[Contact] = []
            for row in reader:
                row_company_name = _get(row, field_map, "company_name")
                row_company_url = _get(row, field_map, "company_linkedin_url")

                same_company = (row_company_name and row_company_name.strip().lower() == company.name.strip().lower()) or (
                    row_company_url and company.linkedin_url and row_company_url.strip() == company.linkedin_url.strip()
                )
                if not same_company:
                    continue

                full_name = _get(row, field_map, "full_name")
                if not full_name:
                    continue

                title = _get(row, field_map, "title")
                seniority = _get(row, field_map, "seniority") or infer_seniority(title)

                if criteria.seniority_levels and seniority not in criteria.seniority_levels:
                    continue
                if criteria.target_titles and not _matches_any(title, criteria.target_titles):
                    continue

                contacts.append(
                    Contact(
                        full_name=full_name,
                        title=title,
                        seniority=seniority,
                        linkedin_url=_get(row, field_map, "linkedin_url"),
                        email=_get(row, field_map, "email"),
                        company_name=company.name,
                    )
                )
                if len(contacts) >= criteria.max_contacts_per_company:
                    break

        return contacts
