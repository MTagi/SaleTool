"""Điều phối enrich 1 công ty.

Thứ tự chạy được thiết kế để **giảm dần độ tin cậy và tăng dần chi phí**:

  1. structured  — JSON-LD / meta / mailto / regex   (rẻ nhất, chính xác nhất)
  2. website     — sitemap + crawl nông website công ty
  3. search      — trang bên ngoài (chỉ khi bật)
  4. LLM         — chỉ cho phần các bước trên KHÔNG lấy được

Mọi thứ lấy được ở bước sớm sẽ không bị bước sau ghi đè.
"""

from __future__ import annotations

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
    """Thêm phần tử mới, giữ thứ tự, không trùng.

    `key_fn` cho phép so trùng theo dạng chuẩn hoá thay vì so chuỗi thô — cần cho
    số điện thoại, vì cùng 1 số hay xuất hiện ở nhiều định dạng trên các trang
    khác nhau.
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
    """Ghi provenance cho 1 lần bóc dữ liệu (URL nào, lúc nào, bằng cách gì)."""
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
    """Enrich 1 công ty. Không raise — lỗi từng trang được ghi vào `sources`."""
    enrichment_cfg = settings.enrichment
    domain = normalize_domain(target.domain) if target.domain else None

    result = CompanyEnrichment(company_name=target.company_name, domain=domain)
    fetcher = _build_fetcher(settings)

    # ---- Bước 1+2: thu thập URL cần đọc ----
    urls: list[str] = []

    if enrichment_cfg.use_company_website and domain:
        try:
            urls.extend(
                await discover_company_site_urls(
                    domain,
                    enrichment_cfg.user_agent,
                    max_pages=enrichment_cfg.max_pages_per_company,
                    timeout=enrichment_cfg.request_timeout_seconds,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Không lấy được URL từ website %s: %s", domain, exc)

    if enrichment_cfg.use_web_search and settings.search.provider != "none":
        remaining = max(enrichment_cfg.max_pages_per_company - len(urls), 0)
        if remaining:
            try:
                provider = get_search_provider(settings.search)
                urls.extend(
                    await discover_external_urls(
                        provider,
                        target.company_name,
                        domain,
                        target.extra_context,
                        max_results=min(remaining, settings.search.max_results),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Web search lỗi cho '%s': %s", target.company_name, exc)

    urls = list(dict.fromkeys(urls))[: enrichment_cfg.max_pages_per_company]

    if not urls:
        result.enriched_at = datetime.now(timezone.utc).isoformat()
        return result

    # ---- Bước 3: tải + bóc từng trang ----
    llm_client = None
    if enrichment_cfg.use_llm and settings.llm.enabled and settings.llm.api_key:
        try:
            llm_client = LLMClient(settings.llm)
        except LLMError as exc:
            logger.warning("Không khởi tạo được LLM client: %s", exc)

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

        # --- Tầng 0: dữ liệu có cấu trúc (luôn chạy, gần như miễn phí) ---
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

        # --- Tầng 3: LLM, chỉ cho phần còn thiếu ---
        needs_llm = llm_client and text and (not result.description or not result.executives)
        if needs_llm:
            try:
                extracted = await llm_client.extract_company_info(
                    target.company_name, truncate_for_llm(text), source_url=url
                )
            except LLMError as exc:
                logger.warning("LLM lỗi ở %s: %s", url, exc)
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

    # Dọn lần cuối: mã số thuế có thể được tìm thấy ở trang khác với trang chứa
    # số điện thoại, nên bộ lọc trong từng trang chưa đủ để loại nó khỏi phones.
    if result.tax_code:
        tax_key = normalize_phone(result.tax_code)
        result.phones = [p for p in result.phones if normalize_phone(p) != tax_key]

    result.enriched_at = datetime.now(timezone.utc).isoformat()
    return result
