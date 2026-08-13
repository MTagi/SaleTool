import pytest

from saletool.models import SearchCriteria
from saletool.providers.csv_import import CsvImportProvider

COMPANIES_CSV = "examples/companies_export.example.csv"
CONTACTS_CSV = "examples/contacts_export.example.csv"


def test_csv_import_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        CsvImportProvider(companies_csv="does_not_exist.csv")


def test_search_companies_reads_and_maps_columns():
    provider = CsvImportProvider(companies_csv=COMPANIES_CSV, contacts_csv=CONTACTS_CSV)
    criteria = SearchCriteria(max_companies=10)

    companies = provider.search_companies(criteria)

    assert len(companies) == 2
    acme = next(c for c in companies if c.name == "Acme Fintech")
    assert acme.linkedin_url == "https://www.linkedin.com/company/acme-fintech"
    assert acme.industry == "Financial Services"
    assert acme.employee_count == 250


def test_search_companies_filters_by_location():
    provider = CsvImportProvider(companies_csv=COMPANIES_CSV)
    criteria = SearchCriteria(locations=["Singapore"], max_companies=10)

    companies = provider.search_companies(criteria)

    assert len(companies) == 1
    assert companies[0].name == "Beta Payments"


def test_search_contacts_filters_senior_only_by_default():
    provider = CsvImportProvider(companies_csv=COMPANIES_CSV, contacts_csv=CONTACTS_CSV)
    criteria = SearchCriteria(max_companies=10, max_contacts_per_company=10)

    companies = provider.search_companies(criteria)
    acme = next(c for c in companies if c.name == "Acme Fintech")
    contacts = provider.search_contacts(acme, criteria)

    # "Software Engineer" không phải cấp cao -> bị lọc bỏ mặc định.
    names = {c.full_name for c in contacts}
    assert "Nguyen Van A" in names  # CEO -> c_suite
    assert "Tran Thi B" in names  # Head of Sales -> head
    assert "Le Van C" not in names  # Software Engineer -> không xác định seniority


def test_search_contacts_without_contacts_csv_returns_empty():
    from saletool.models import Company

    provider = CsvImportProvider(companies_csv=COMPANIES_CSV)
    criteria = SearchCriteria()

    assert provider.search_contacts(Company(name="Acme Fintech"), criteria) == []
