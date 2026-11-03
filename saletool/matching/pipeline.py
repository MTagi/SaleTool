"""Combine search results with the service catalog to produce ranked companies.

Flow for each company:

  1. build a company profile from search results and **include enrichment data if
     available** (description, industry, technologies, leadership);
  2. ask the LLM to score the company against each selected service;
  3. calculate total scores and rankings in code.

Step 3 is deliberately **not** delegated to the LLM. If the model decides "this
company ranks third", rankings may change across runs on the same data and are
hard to explain to salespeople. The total score here is the best-fit service score,
since one suitable service is enough reason to contact a company.
"""

from __future__ import annotations

import logging

from saletool.enrichment.discovery import normalize_domain
from saletool.llm_api import LLMError
from saletool.matching.llm import MatchLLMClient
from saletool.models import (
    AppSettings,
    CompanyEnrichment,
    CompanyMatch,
    CompanyResult,
    Service,
)
from saletool.prompt_text import MAX_LIST_ITEMS, clip_text

logger = logging.getLogger(__name__)

MAX_RESEARCH_CHARS = 16000


def _research_evidence(enrichment: CompanyEnrichment) -> str | None:
    """Keep research and source URLs within a separate budget from the short description."""
    if enrichment.summary_markdown and enrichment.report_status in (None, "completed"):
        text = enrichment.summary_markdown.strip()
        label = "Enrichment research report (AI synthesis; verify against cited sources)"
    elif enrichment.raw_markdown:
        # Share the budget so a long first page does not crowd out later sources.
        sections = enrichment.raw_markdown.split("\n\nSOURCE URL: ")[:MAX_LIST_ITEMS]
        limit = max(1, (MAX_RESEARCH_CHARS - 32 * len(sections)) // len(sections))
        text = "\n\nSOURCE URL: ".join(
            section if len(section) <= limit else section[:limit] + "\n[truncated]"
            for section in sections
        )
        label = "Enrichment source excerpts (report unavailable)"
    else:
        return None

    if len(text) > MAX_RESEARCH_CHARS:
        text = text[:MAX_RESEARCH_CHARS] + "\n[truncated]"
    urls = list(dict.fromkeys(source.url for source in enrichment.sources if source.ok))
    sources = "\n".join(f"- {url}" for url in urls[:MAX_LIST_ITEMS])
    return f"{label}:\n{text}" + (f"\nSuccessfully read source URLs:\n{sources}" if sources else "")


def enrichment_key(name: str | None, domain: str | None) -> tuple[str, str]:
    """Company key for joining search and enrichment results.

    Join by both name and domain because the two input flows differ: search uses
    the provider's company name, while enrichment usually runs by domain.
    """
    return (name or "").strip().lower(), normalize_domain(domain or "")


def build_enrichment_index(jobs_results: list[CompanyEnrichment]) -> dict[str, CompanyEnrichment | None]:
    """Build enrichment lookups by name and domain.

    `jobs_results` are newest first; the first record wins so newer enrichment
    data is not overwritten by older data.
    """
    index: dict[str, CompanyEnrichment | None] = {}
    for result in jobs_results:
        name_key, domain_key = enrichment_key(result.company_name, result.domain)
        for key in (f"name:{name_key}" if name_key else "", f"domain:{domain_key}" if domain_key else ""):
            if key and key not in index:
                index[key] = result
            elif key.startswith("name:") and index.get(key) is not None:
                existing_domain = normalize_domain(index[key].domain or "")
                if existing_domain and domain_key and existing_domain != domain_key:
                    index[key] = None
    return index


def lookup_enrichment(
    index: dict[str, CompanyEnrichment | None], name: str | None, domain: str | None
) -> CompanyEnrichment | None:
    name_key, domain_key = enrichment_key(name, domain)
    # Check domain first: a domain match is stronger evidence than a name match.
    by_domain = index.get(f"domain:{domain_key}") if domain_key else None
    if by_domain is not None:
        return by_domain
    by_name = index.get(f"name:{name_key}") if name_key else None
    if by_name is not None:
        other_domain = normalize_domain(by_name.domain or "")
        if domain_key and other_domain and domain_key != other_domain:
            return None
    return by_name


def build_company_profile(
    result: CompanyResult, enrichment: CompanyEnrichment | None = None
) -> str:
    """Combine everything known about a company into a text block for the LLM."""
    company = result.company
    lines = [f"Name: {company.name}"]

    def add(label: str, value: str | None) -> None:
        if value:
            lines.append(f"{label}: {value}")

    add("Website", company.domain or (enrichment.domain if enrichment else None))
    add("LinkedIn", company.linkedin_url)
    add("Apollo description", (company.description or "")[:1000])
    add("Apollo founded year", str(company.founded_year) if company.founded_year else None)
    add("Apollo annual revenue (provider estimate)", company.annual_revenue)
    add("Apollo total funding", company.total_funding)
    add("Apollo technologies", ", ".join(company.technologies[:20]))
    add("Apollo keywords", ", ".join(company.keywords[:20]))
    add("Apollo address", company.address)
    add("Industry", company.industry or (enrichment.industry if enrichment else None))
    add("Location", company.location or (enrichment.headquarters if enrichment else None))

    if company.employee_count:
        add("Employees", str(company.employee_count))
    elif enrichment and enrichment.employee_count_text:
        add("Employees", enrichment.employee_count_text)

    if enrichment:
        add("Description", clip_text(enrichment.description))
        if enrichment.founded_year:
            add("Founded", str(enrichment.founded_year))
        if enrichment.technologies:
            add("Technologies", ", ".join(enrichment.technologies[:MAX_LIST_ITEMS]))
        if enrichment.addresses:
            add("Address", clip_text(enrichment.addresses[0], 200))
        research = _research_evidence(enrichment)
        if research:
            lines.append(research)

    # Contact titles are real buying signals: a CTO suggests a technical team,
    # while a Head of Growth suggests investment in growth.
    people = [
        f"{c.full_name} — {c.title}" if c.title else c.full_name
        for c in result.contacts[:MAX_LIST_ITEMS]
    ]
    if enrichment:
        people += [
            f"{e.full_name} — {e.title}" if e.title else e.full_name
            for e in enrichment.executives[:MAX_LIST_ITEMS]
        ]
    if people:
        lines.append("Known people: " + "; ".join(dict.fromkeys(people)))

    if len(lines) <= 2:
        lines.append("(No further information available — the profile is thin.)")

    return "\n".join(lines)


async def match_company(
    result: CompanyResult,
    services: list[Service],
    settings: AppSettings,
    objective: str | None = None,
    enrichment: CompanyEnrichment | None = None,
) -> CompanyMatch:
    """Score one company. Store LLM errors in `error` instead of raising so one
    failed company does not remove the entire ranking."""
    company = result.company
    match = CompanyMatch(
        company_id=company.id,
        company_name=company.name,
        domain=company.domain or (enrichment.domain if enrichment else None),
        linkedin_url=company.linkedin_url,
        industry=company.industry or (enrichment.industry if enrichment else None),
        location=company.location or (enrichment.headquarters if enrichment else None),
        employee_count=company.employee_count,
        used_enrichment=enrichment is not None,
    )

    profile = build_company_profile(result, enrichment)

    try:
        scoring, fits = await MatchLLMClient(settings.llm).score_company(
            profile, services, objective
        )
    except LLMError as exc:
        logger.warning("Scoring failed for '%s': %s", company.name, exc)
        match.error = str(exc)[:300]
        return match

    match.summary = scoring.summary.strip()
    match.signals = [s for s in scoring.signals if s][:MAX_LIST_ITEMS]
    match.concerns = [c for c in scoring.concerns if c][:MAX_LIST_ITEMS]
    match.service_fits = sorted(fits, key=lambda f: f.score, reverse=True)

    if match.service_fits:
        best = match.service_fits[0]
        match.overall_score = best.score
        match.best_service_id = best.service_id
        match.best_service_name = best.service_name

    return match


def rank_matches(matches: list[CompanyMatch]) -> list[CompanyMatch]:
    """Sort and assign ranks. Return the same sorted list (updating `rank` in place).

    Tie-breaker: companies matching **more** services (higher average score) rank
    first, since selling more to one customer is more valuable. Companies with
    scoring errors always go last, separate from companies with genuinely low scores.
    """

    def sort_key(match: CompanyMatch) -> tuple:
        mean = (
            sum(f.score for f in match.service_fits) / len(match.service_fits)
            if match.service_fits
            else 0.0
        )
        return (match.error is None, match.overall_score, mean, match.used_enrichment)

    ordered = sorted(matches, key=sort_key, reverse=True)
    for position, match in enumerate(ordered, start=1):
        match.rank = position
    return ordered
