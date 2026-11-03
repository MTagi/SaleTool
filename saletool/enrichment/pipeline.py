"""Orchestrate enrichment for one company.

The stages run in order of **decreasing reliability and increasing cost**:

  1. structured  — JSON-LD / meta / mailto / regex   (cheapest, most accurate)
  2. website     — sitemap + shallow crawl of the company website
  3. search      — external pages (only when enabled)
  4. LLM         — only for fields the previous stages could not find

Data found in an earlier stage is never overwritten by a later stage.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from saletool.enrichment.discovery import (
    discover_company_site_urls,
    discover_external_urls,
    normalize_domain,
)
from saletool.enrichment.extractor import extract_text, truncate_for_llm
from saletool.enrichment.fetcher import (
    DomainRateLimiter,
    FallbackFetcher,
    HttpFetcher,
    PlaywrightFetcher,
    RobotsCache,
)
from saletool.enrichment.llm import LLMClient, LLMError
from saletool.enrichment.query_planner import plan_queries
from saletool.enrichment.report import summarize_report
from saletool.enrichment.search import get_search_provider
from saletool.enrichment.structured import extract_structured, normalize_phone
from saletool.models import (
    AppSettings,
    CompanyEnrichment,
    EnrichmentSource,
    EnrichTarget,
    Executive,
)

logger = logging.getLogger(__name__)


def _merge_unique(target: list[str], new_items: list[str], limit: int = 20, key_fn=None) -> None:
    """Append a new item while preserving order and avoiding duplicates.

    `key_fn` allows deduplication using normalized values instead of raw strings.
    This is needed for phone numbers, which often appear in different formats
    across pages.
    """
    key_fn = key_fn or (lambda item: item.lower())
    seen = {key_fn(item) for item in target}

    for item in new_items:
        if not item:
            continue
        key = key_fn(item)
        if not key or key in seen:
            continue
        target.append(item)
        seen.add(key)
        if len(target) >= limit:
            return


def _merge_executives(target: list[Executive], new_items: list[Executive], source_url: str) -> None:
    existing = {e.full_name.strip().lower() for e in target}
    for exec_item in new_items:
        name = (exec_item.full_name or "").strip()
        if not name or name.lower() in existing:
            continue
        exec_item.source_url = exec_item.source_url or source_url
        target.append(exec_item)
        existing.add(name.lower())


def _source(
    url: str, fetched_at: str, method: str, extractor: str, ok: bool, note: str | None = None
) -> EnrichmentSource:
    """Record provenance for one extraction (URL, time, and method)."""
    return EnrichmentSource(
        url=url,
        fetched_at=fetched_at,
        fetch_method=method,
        extractor=extractor,
        ok=ok,
        note=note,
    )


def _build_fetcher(settings: AppSettings):
    enrichment = settings.enrichment
    robots = RobotsCache(enrichment.user_agent) if enrichment.respect_robots_txt else None
    limiter = DomainRateLimiter(enrichment.request_delay_seconds)

    http = HttpFetcher(
        user_agent=enrichment.user_agent,
        timeout=enrichment.request_timeout_seconds,
        robots=robots,
        limiter=limiter,
    )
    browser = (
        PlaywrightFetcher(
            user_agent=enrichment.user_agent,
            timeout=max(enrichment.request_timeout_seconds, 30.0),
            robots=robots,
            limiter=limiter,
        )
        if enrichment.use_browser_fallback
        else None
    )
    return FallbackFetcher(http, browser)


async def enrich_company(target: EnrichTarget, settings: AppSettings) -> CompanyEnrichment:
    """Enrich one company. Never raise; errors for individual pages go in `sources`."""
    enrichment_cfg = settings.enrichment
    domain = normalize_domain(target.domain) if target.domain else None

    result = CompanyEnrichment(company_name=target.company_name, domain=domain)
    raw_parts = []
    if target.company_profile:
        raw_parts.append("SOURCE: Apollo search snapshot\n" + json.dumps(target.company_profile.model_dump(exclude_none=True), ensure_ascii=False, indent=2))
    fetcher = _build_fetcher(settings)

    # ---- Stages 1+2: collect URLs to read ----
    urls: list[str] = []

    if enrichment_cfg.use_company_website and domain:
        try:
            primary = getattr(fetcher, "primary", fetcher)
            urls.extend(
                await discover_company_site_urls(
                    domain,
                    enrichment_cfg.user_agent,
                    max_pages=enrichment_cfg.max_pages_per_company,
                    timeout=enrichment_cfg.request_timeout_seconds,
                    robots=getattr(primary, "robots", None),
                    limiter=getattr(primary, "limiter", None),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not get URLs from website %s: %s", domain, exc)

    if enrichment_cfg.use_web_search and settings.search.provider != "none":
        # Reserve space for external research instead of allowing the website
        # sitemap to consume the entire budget before search is attempted.
        search_budget = min(
            settings.search.max_results,
            enrichment_cfg.web_search_reserved_pages,
            enrichment_cfg.max_pages_per_company,
        )
        website_urls = list(dict.fromkeys(urls))
        urls = website_urls[: enrichment_cfg.max_pages_per_company - search_budget]
        remaining = max(enrichment_cfg.max_pages_per_company - len(urls), 0)
        if remaining:
            try:
                provider = get_search_provider(settings.search)
                result.search_queries, result.query_planning_status = await plan_queries(target, settings)
                urls.extend(
                    await discover_external_urls(
                        provider,
                        target.company_name,
                        domain,
                        target.extra_context,
                        max_results=min(remaining, settings.search.max_results),
                        queries=result.search_queries,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Web search failed for '%s': %s", target.company_name, exc)
        # If search found fewer pages (or failed), fill unused space with the
        # remaining website pages. The overall page budget is unchanged.
        urls.extend(url for url in website_urls if url not in urls)

    urls = list(dict.fromkeys(urls))[: enrichment_cfg.max_pages_per_company]


    # ---- Stage 3: fetch and extract each page ----
    llm_client = None
    if enrichment_cfg.use_llm and settings.llm.enabled and settings.llm.api_key:
        try:
            llm_client = LLMClient(settings.llm)
        except LLMError as exc:
            logger.warning("Could not initialize LLM client: %s", exc)

    for url in urls:
        page = await fetcher.fetch(url)
        fetched_at = datetime.now(timezone.utc).isoformat()

        if not page.ok or not page.html:
            result.sources.append(
                _source(url, fetched_at, page.method, "none", ok=False, note=page.error)
            )
            continue

        result.pages_fetched += 1
        text = extract_text(page.html, url=url)
        raw_parts.append("SOURCE URL: " + url + "\nFETCHED AT: " + fetched_at + "\n\n" + text)

        # --- Stage 0: structured data (always runs, nearly free) ---
        if enrichment_cfg.use_structured_data:
            structured = extract_structured(page.html, text)

            result.description = result.description or structured.description
            result.founded_year = result.founded_year or structured.founded_year
            result.tax_code = result.tax_code or structured.tax_code

            _merge_unique(result.emails, structured.emails)
            _merge_unique(result.phones, structured.phones, key_fn=normalize_phone)
            _merge_unique(result.addresses, structured.addresses)
            for key, link in structured.social_links.items():
                result.social_links.setdefault(key, link)

            result.sources.append(
                _source(url, fetched_at, page.method, "json_ld+meta+regex", ok=True)
            )

        # --- Stage 3: LLM, only for missing fields ---
        needs_llm = llm_client and text and (not result.description or not result.executives)
        if needs_llm:
            try:
                extracted = await llm_client.extract_company_info(
                    target.company_name, truncate_for_llm(text), source_url=url
                )
            except LLMError as exc:
                logger.warning("LLM failed at %s: %s", url, exc)
                result.sources.append(
                    _source(url, fetched_at, page.method, "llm", ok=False, note=str(exc)[:200])
                )
            else:
                result.llm_calls += 1
                result.description = result.description or extracted.description
                result.industry = result.industry or extracted.industry
                result.founded_year = result.founded_year or extracted.founded_year
                result.headquarters = result.headquarters or extracted.headquarters
                result.employee_count_text = (
                    result.employee_count_text or extracted.employee_count_text
                )
                _merge_unique(result.technologies, extracted.technologies)
                _merge_executives(result.executives, extracted.executives, url)

                result.sources.append(_source(url, fetched_at, page.method, "llm", ok=True))

    # Final cleanup: a tax ID may appear on a different page from a phone number,
    # so per-page filtering is not enough to remove it from the phone list.
    if result.tax_code:
        tax_key = normalize_phone(result.tax_code)
        result.phones = [p for p in result.phones if normalize_phone(p) != tax_key]

    result.raw_markdown = "\n\n".join(raw_parts) or None
    await summarize_report(result, settings)
    result.enriched_at = datetime.now(timezone.utc).isoformat()
    return result
