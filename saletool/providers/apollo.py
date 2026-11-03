"""Provider based on the Apollo.io API (https://docs.apollo.io).

Apollo aggregates company and contact data (including LinkedIn URLs, titles, and
seniority) and provides it through its official REST API. A valid API key is
required (APOLLO_API_KEY environment variable or passed directly).

Four API details determine how this code is implemented:

1. **The base path is `/api/v1`**, not `/v1`.
2. **People search must use `mixed_people/api_search`**, not
   `mixed_people/search` — the latter returns 403 on the Basic plan.
3. **Search does NOT return email addresses.** Results only indicate whether a
   person *has* an email; retrieving it requires a People Enrichment request, and
   **that is where credits are charged**. Only enrich people whose search result
   indicates an email is available; paying for a lookup that is certain to fail
   is wasteful.
4. **`organization_industry_tag_ids` accepts Apollo tag IDs**, not industry
   names. If users enter "Fintech", Apollo silently ignores it. See
   `_industry_filters()`.
"""

from __future__ import annotations

import logging
import re

import httpx

from saletool.models import Company, Contact, SearchCriteria
from saletool.providers.base import CompanyContactProvider

logger = logging.getLogger(__name__)

API_BASE = "https://api.apollo.io/api/v1"
ORGANIZATION_SEARCH_URL = f"{API_BASE}/mixed_companies/search"
PEOPLE_SEARCH_URL = f"{API_BASE}/mixed_people/api_search"
PEOPLE_ENRICH_URL = f"{API_BASE}/people/bulk_match"

# Apollo limits, not configurable choices.
MAX_PER_PAGE = 100
BULK_MATCH_LIMIT = 10

# Apollo tag IDs are 24-character hexadecimal strings (ObjectId format).
_TAG_ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)

# Apollo returns locked emails as `email_not_unlocked@domain.com`.
# Match only the identifier, not `@domain.com`; some companies use that domain.
_LOCKED_EMAIL_RE = re.compile(r"email_not_unlocked", re.IGNORECASE)

# Search only says whether an email exists. These values indicate one is available.
_WORTH_ENRICHING = {"verified", "likely", "guessed", "extrapolated"}


def _industry_filters(industries: list[str]) -> dict:
    """Separate free-form industry names from Apollo tag IDs.

    Apollo has two industry filters, and they are not interchangeable:
    `organization_industry_tag_ids` requires an internal tag ID, while
    `q_organization_keyword_tags` matches keywords in company descriptions.

    User-entered industry names must use the second filter. Putting a name in the
    tag ID field silently disables the filter. Users with a real tag ID can enter
    it in the same field, and the code will recognize it.
    """
    tag_ids = [i for i in industries if _TAG_ID_RE.match(i.strip())]
    keywords = [i for i in industries if not _TAG_ID_RE.match(i.strip())]

    filters: dict = {}
    if tag_ids:
        filters["organization_industry_tag_ids"] = tag_ids
    if keywords:
        filters["keyword_tags"] = keywords
    return filters


def _is_usable_email(email: str | None) -> bool:
    return bool(email) and not _LOCKED_EMAIL_RE.search(email or "")


def _worth_enriching(person: dict) -> bool:
    """Is this person worth spending one credit to look up an email for?

    Apollo indicates availability through `has_email`/`email_status`. Skipping this
    check would charge for records that are certain to have no email.
    """
    if _is_usable_email(person.get("email")):
        return False  # Already available; no lookup needed.
    if person.get("has_email") is True:
        return True
    return str(person.get("email_status") or "").lower() in _WORTH_ENRICHING


def _person_name(person: dict) -> str:
    """Build a displayable name from an Apollo person record.

    Observed on the current plan (2026-09-04): before reveal, Apollo hides the last
    name; `name` is `None`, leaving only `first_name` and `last_name_obfuscated`
    ("S***"). Reading only `name` left every contact nameless, even though Apollo
    provides the first name at no cost.

    Deliberately ignore `last_name_obfuscated`: "Phi S***" is not a usable form of
    address and could be mistaken for a real name and included in a message.
    """
    name = (person.get("name") or "").strip()
    if name:
        return name

    parts = [(person.get("first_name") or "").strip(), (person.get("last_name") or "").strip()]
    return " ".join(part for part in parts if part)


class ApolloProvider(CompanyContactProvider):
    name = "apollo"

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        reveal_emails: bool = True,
        reveal_personal_emails: bool = False,
    ):
        """`reveal_emails`: call People Enrichment to retrieve work emails.

        Enabled by default because a contact list without email addresses is nearly
        useless. **This step costs credits**, so set `reveal_emails=False` to only
        estimate how many companies and people match the criteria.

        `reveal_personal_emails` is **disabled** by default: personal emails cost
        extra credits, and Apollo does not return them for people in GDPR regions.
        Work emails are appropriate for B2B outreach.
        """
        if not api_key:
            raise ValueError("Apollo API key is missing (APOLLO_API_KEY)")
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=timeout)
        self.reveal_emails = reveal_emails
        self.reveal_personal_emails = reveal_personal_emails

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    def _post(self, url: str, payload: dict) -> dict:
        resp = self._client.post(url, json=payload, headers=self._headers())
        if resp.status_code == 403:
            raise RuntimeError(
                "Apollo returned 403 — the API key does not have access to this endpoint. "
                "Check the subscription plan and whether API access is enabled for the key."
            )
        resp.raise_for_status()
        return resp.json()

    # -- Companies ---------------------------------------------------------

    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        """Fetch up to `max_companies`, **using pagination**.

        Apollo returns up to 100 records per page. Previously, only page 1 was
        fetched, so a request for 250 companies silently returned just 100.
        """
        keyword_tags = list(criteria.keywords)
        industry = _industry_filters(criteria.industries)
        keyword_tags += industry.pop("keyword_tags", [])

        base_payload: dict = dict(industry)
        if keyword_tags:
            base_payload["q_organization_keyword_tags"] = keyword_tags
        if criteria.locations:
            base_payload["organization_locations"] = criteria.locations
        if criteria.company_size_min is not None or criteria.company_size_max is not None:
            base_payload["organization_num_employees_ranges"] = [
                f"{criteria.company_size_min or 1},{criteria.company_size_max or ''}"
            ]

        companies: list[Company] = []
        page = 1
        # Keep page size fixed so the offset remains correct on the last page.
        per_page = min(criteria.max_companies, MAX_PER_PAGE)
        while len(companies) < criteria.max_companies:
            payload = {**base_payload, "page": page, "per_page": per_page}
            data = self._post(ORGANIZATION_SEARCH_URL, payload)

            organizations = data.get("organizations") or []
            if not organizations:
                break

            companies.extend(
                Company(
                    name=org.get("name", ""),
                    description=org.get("short_description") or org.get("description"),
                    founded_year=org.get("founded_year"),
                    phone=org.get("phone") or (org.get("primary_phone") or {}).get("number"),
                    address=org.get("raw_address"),
                    annual_revenue=str(org["annual_revenue_printed"] if org.get("annual_revenue_printed") is not None else org["annual_revenue"]) if org.get("annual_revenue_printed") is not None or org.get("annual_revenue") is not None else None,
                    total_funding=str(org["total_funding_printed"] if org.get("total_funding_printed") is not None else org["total_funding"]) if org.get("total_funding_printed") is not None or org.get("total_funding") is not None else None,
                    technologies=[t["name"] for t in (org.get("current_technologies") or []) if isinstance(t, dict) and isinstance(t.get("name"), str)],
                    keywords=[k for k in (org.get("keywords") or []) if isinstance(k, str)],
                    linkedin_url=org.get("linkedin_url"),
                    domain=org.get("primary_domain") or org.get("website_url"),
                    industry=org.get("industry"),
                    location=", ".join(str(v) for v in [org.get("city"), org.get("state"), org.get("country")] if v) or None,
                    employee_count=org.get("estimated_num_employees"),
                    provider_id=org.get("id"),
                )
                for org in organizations
            )

            # Apollo reports the total page count; stop at the end instead of making an extra request.
            total_pages = (data.get("pagination") or {}).get("total_pages")
            if total_pages is not None and page >= total_pages:
                break
            page += 1

        return companies[: criteria.max_companies]

    # -- Contacts ----------------------------------------------------------

    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        if not company.provider_id:
            return []

        payload: dict = {
            "page": 1,
            "per_page": min(criteria.max_contacts_per_company, MAX_PER_PAGE),
            "organization_ids": [company.provider_id],
        }
        if criteria.seniority_levels:
            payload["person_seniorities"] = criteria.seniority_levels
        if criteria.target_titles:
            payload["person_titles"] = criteria.target_titles

        data = self._post(PEOPLE_SEARCH_URL, payload)
        people = (data.get("people") or [])[: criteria.max_contacts_per_company]

        if self.reveal_emails:
            people = self._reveal_emails(people)

        return [
            Contact(
                provider_id=person.get("id"),
                full_name=_person_name(person),
                title=person.get("title"),
                seniority=person.get("seniority"),
                linkedin_url=person.get("linkedin_url"),
                email=person.get("email") if _is_usable_email(person.get("email")) else None,
                company_name=company.name,
            )
            for person in people
        ]

    def _reveal_emails(self, people: list[dict]) -> list[dict]:
        """Look up actual email addresses for people whose search result says one is available.

        Errors at this step do **not** fail the entire search: contacts without
        email addresses are still useful (they retain their LinkedIn URLs), while
        losing the whole list is not.
        """
        # Keep original indices so results are matched to the correct people.
        targets = [(i, p) for i, p in enumerate(people) if _worth_enriching(p)]
        if not targets:
            return people

        revealed: dict[int, str] = {}
        for start in range(0, len(targets), BULK_MATCH_LIMIT):
            chunk = targets[start : start + BULK_MATCH_LIMIT]
            batch = [person for _, person in chunk]
            payload = {
                "reveal_personal_emails": self.reveal_personal_emails,
                "details": [
                    {
                        k: v
                        for k, v in (
                            ("id", person.get("id")),
                            ("first_name", person.get("first_name")),
                            ("last_name", person.get("last_name")),
                            ("name", person.get("name")),
                            ("organization_name", (person.get("organization") or {}).get("name")),
                            ("linkedin_url", person.get("linkedin_url")),
                        )
                        if v
                    }
                    for person in batch
                ],
            }

            try:
                data = self._post(PEOPLE_ENRICH_URL, payload)
            except (httpx.HTTPError, RuntimeError) as exc:
                logger.warning("Apollo enrichment failed; skipping email: %s", exc)
                return people

            # Apollo returns `matches` in request order, including null entries.
            # strict=False is intentional: Apollo sometimes returns fewer items than requested.
            matches = data.get("matches") or []
            for (index, _), match in zip(chunk, matches, strict=False):
                if match and _is_usable_email(match.get("email")):
                    revealed[index] = match["email"]

        return [
            {**person, "email": revealed[i]} if i in revealed else person
            for i, person in enumerate(people)
        ]
