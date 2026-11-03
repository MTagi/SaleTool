"""Look up companies and contacts in a search snapshot without guessing on name collisions."""

from saletool.history import same_company
from saletool.models import CompanyMatch, CompanyResult, Contact, MessageTarget, SearchRunDetail


def resolve_message_target(
    run: SearchRunDetail, target: MessageTarget
) -> tuple[CompanyResult | None, Contact | None]:
    companies = [
        result
        for result in run.results
        if (
            result.company.id == target.company_id
            if target.company_id
            else result.company.name.strip().casefold() == target.company_name.strip().casefold()
        )
    ]
    if len(companies) > 1:
        raise ValueError("Company name is ambiguous. Reload the search and select a company by ID.")
    if not companies:
        return None, None
    result = companies[0]
    contacts = [
        contact
        for contact in result.contacts
        if (
            contact.id == target.contact_id
            if target.contact_id
            else contact.full_name.strip().casefold() == target.contact_name.strip().casefold()
        )
    ]
    if len(contacts) > 1:
        raise ValueError("Contact name is ambiguous. Reload the search and select a contact by ID.")
    return result, contacts[0] if contacts else None


def lookup_company_match(matches: list[CompanyMatch], result: CompanyResult) -> CompanyMatch | None:
    company = result.company
    candidates = [
        match
        for match in matches
        if (
            match.company_id == company.id
            if match.company_id
            else same_company(company.name, company.domain, match.company_name, match.domain)
        )
    ]
    return candidates[0] if len(candidates) == 1 else None
