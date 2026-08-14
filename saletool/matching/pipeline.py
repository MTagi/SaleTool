"""Ghép kết quả search + catalog dịch vụ -> danh sách công ty đã xếp hạng.

Luồng cho mỗi công ty:

  1. dựng hồ sơ công ty từ kết quả search, và **nếu từng enrich thì trộn thêm**
     dữ liệu enrich vào (mô tả, ngành, công nghệ, ban lãnh đạo);
  2. LLM chấm điểm công ty đó với từng dịch vụ được chọn;
  3. code tính điểm tổng và xếp hạng.

Bước 3 cố tình **không** giao cho LLM. Nếu để model tự nói "công ty này xếp thứ
3" thì thứ tự sẽ đổi giữa hai lần chạy trên cùng dữ liệu và không giải thích
được cho người bán. Ở đây điểm tổng = điểm của dịch vụ khớp nhất, vì trong thực
tế bán hàng chỉ cần một dịch vụ đủ hợp là đã có lý do để tiếp cận.
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

logger = logging.getLogger(__name__)

# Giới hạn độ dài các phần tự do trong hồ sơ — hồ sơ dài không làm điểm chính
# xác hơn, chỉ làm tốn token.
MAX_DESCRIPTION_CHARS = 800
MAX_LIST_ITEMS = 12


def _clip(text: str | None, limit: int = MAX_DESCRIPTION_CHARS) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def enrichment_key(name: str | None, domain: str | None) -> tuple[str, str]:
    """Khoá ghép công ty giữa kết quả search và kết quả enrich.

    Ghép theo cả tên lẫn domain vì hai luồng nhập liệu khác nhau: search trả tên
    theo nhà cung cấp, còn enrich thường được chạy theo domain.
    """
    return (name or "").strip().lower(), normalize_domain(domain or "")


def build_enrichment_index(jobs_results: list[CompanyEnrichment]) -> dict[str, CompanyEnrichment]:
    """Dựng bảng tra enrich theo tên và theo domain.

    `jobs_results` xếp theo thứ tự mới nhất trước — bản ghi đầu tiên gặp sẽ
    thắng, để dữ liệu enrich mới không bị bản cũ đè.
    """
    index: dict[str, CompanyEnrichment] = {}
    for result in jobs_results:
        name_key, domain_key = enrichment_key(result.company_name, result.domain)
        for key in (name_key, domain_key):
            if key and key not in index:
                index[key] = result
    return index


def lookup_enrichment(
    index: dict[str, CompanyEnrichment], name: str | None, domain: str | None
) -> CompanyEnrichment | None:
    name_key, domain_key = enrichment_key(name, domain)
    # Domain trước: trùng domain là bằng chứng mạnh hơn trùng tên.
    return index.get(domain_key) or index.get(name_key)


def build_company_profile(
    result: CompanyResult, enrichment: CompanyEnrichment | None = None
) -> str:
    """Gộp mọi thứ biết về 1 công ty thành khối text cho LLM đọc."""
    company = result.company
    lines = [f"Name: {company.name}"]

    def add(label: str, value: str | None) -> None:
        if value:
            lines.append(f"{label}: {value}")

    add("Website", company.domain or (enrichment.domain if enrichment else None))
    add("LinkedIn", company.linkedin_url)
    add("Industry", company.industry or (enrichment.industry if enrichment else None))
    add("Location", company.location or (enrichment.headquarters if enrichment else None))

    if company.employee_count:
        add("Employees", str(company.employee_count))
    elif enrichment and enrichment.employee_count_text:
        add("Employees", enrichment.employee_count_text)

    if enrichment:
        add("Description", _clip(enrichment.description))
        if enrichment.founded_year:
            add("Founded", str(enrichment.founded_year))
        if enrichment.technologies:
            add("Technologies", ", ".join(enrichment.technologies[:MAX_LIST_ITEMS]))
        if enrichment.addresses:
            add("Address", _clip(enrichment.addresses[0], 200))

    # Chức danh của người liên hệ là tín hiệu mua hàng thật: có CTO nghĩa là có
    # đội kỹ thuật, có Head of Growth nghĩa là đang đẩy tăng trưởng.
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
    """Chấm 1 công ty. Lỗi LLM được ghi vào `error` chứ không raise ra ngoài,
    để một công ty hỏng không làm mất cả bảng xếp hạng."""
    company = result.company
    match = CompanyMatch(
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
        logger.warning("Chấm điểm thất bại cho '%s': %s", company.name, exc)
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
    """Sắp xếp và đánh số thứ hạng. Trả về chính danh sách đã sắp (sửa tại chỗ `rank`).

    Thứ tự ưu tiên khi bằng điểm: công ty hợp với **nhiều** dịch vụ hơn (điểm
    trung bình cao hơn) đứng trước — bán được nhiều thứ cho một khách thì đáng
    theo đuổi hơn. Công ty chấm lỗi luôn xuống cuối, không lẫn với công ty điểm
    thấp thật.
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
