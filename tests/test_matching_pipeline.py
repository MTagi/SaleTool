"""Test phần logic của matching — chỗ KHÔNG phụ thuộc LLM.

Thứ hạng và việc map nhãn dịch vụ đều do code quyết định, nên chúng phải kiểm
được mà không cần gọi API thật.
"""

import asyncio

from saletool.llm_api import LLMError
from saletool.matching.llm import MatchScoring, _ServiceFitOut, format_catalog, resolve_fits
from saletool.matching.pipeline import (
    build_company_profile,
    build_enrichment_index,
    lookup_enrichment,
    match_company,
    rank_matches,
)
from saletool.models import (
    AppSettings,
    Company,
    CompanyEnrichment,
    CompanyMatch,
    CompanyResult,
    Contact,
    Executive,
    Service,
    ServiceFit,
)


def _service(name: str, service_id: str = None, **overrides) -> Service:
    payload = {
        "id": service_id or f"id-{name.lower().replace(' ', '-')}",
        "name": name,
        "description": f"{name} description",
        "created_at": "2026-08-14T00:00:00+00:00",
        "updated_at": "2026-08-14T00:00:00+00:00",
    }
    payload.update(overrides)
    return Service(**payload)


def _result(name="Acme Fintech", **company_fields) -> CompanyResult:
    return CompanyResult(company=Company(name=name, **company_fields))


def _match(name: str, score: int, fits: list[int] = None, **overrides) -> CompanyMatch:
    fits = fits if fits is not None else [score]
    return CompanyMatch(
        company_name=name,
        overall_score=score,
        service_fits=[
            ServiceFit(service_id=f"s{i}", service_name=f"S{i}", score=s)
            for i, s in enumerate(fits)
        ],
        **overrides,
    )


# --- Xếp hạng ---------------------------------------------------------------


def test_ranks_by_score_descending():
    ranked = rank_matches([_match("Low", 20), _match("High", 90), _match("Mid", 55)])

    assert [m.company_name for m in ranked] == ["High", "Mid", "Low"]
    assert [m.rank for m in ranked] == [1, 2, 3]


def test_ties_go_to_the_company_that_fits_more_services():
    """Cùng điểm dịch vụ tốt nhất thì công ty bán được nhiều thứ hơn đứng trước."""
    broad = _match("Broad", 80, fits=[80, 75, 70])
    narrow = _match("Narrow", 80, fits=[80, 10, 5])

    ranked = rank_matches([narrow, broad])

    assert [m.company_name for m in ranked] == ["Broad", "Narrow"]


def test_failed_companies_sink_below_genuinely_low_scores():
    """Chấm lỗi khác với chấm được điểm thấp — không được lẫn vào nhau."""
    ranked = rank_matches([_match("Broken", 0, fits=[], error="LLM timed out"), _match("Weak", 5)])

    assert [m.company_name for m in ranked] == ["Weak", "Broken"]
    assert ranked[-1].error


def test_ranking_an_empty_list_is_fine():
    assert rank_matches([]) == []


# --- Map nhãn dịch vụ -------------------------------------------------------


def test_resolves_short_labels_back_to_service_ids():
    services = [_service("ERP", "svc-1"), _service("Data platform", "svc-2")]
    scoring = MatchScoring(
        service_fits=[
            _ServiceFitOut(service_ref="S2", score=80, rationale="uses spreadsheets"),
            _ServiceFitOut(service_ref="S1", score=30, rationale="no signal"),
        ]
    )

    fits = resolve_fits(scoring, services)

    assert [f.service_id for f in fits] == ["svc-1", "svc-2"]  # theo thứ tự catalog
    assert {f.service_id: f.score for f in fits} == {"svc-1": 30, "svc-2": 80}


def test_accepts_the_service_name_instead_of_the_label():
    """Model nào cũng có lúc bỏ qua hướng dẫn định dạng — đừng vứt cả kết quả."""
    services = [_service("ERP", "svc-1")]
    scoring = MatchScoring(service_fits=[_ServiceFitOut(service_ref="erp", score=70)])

    assert resolve_fits(scoring, services)[0].score == 70


def test_unscored_services_still_appear_with_zero():
    services = [_service("ERP", "svc-1"), _service("Audit", "svc-2")]
    scoring = MatchScoring(service_fits=[_ServiceFitOut(service_ref="S1", score=60)])

    fits = resolve_fits(scoring, services)

    assert len(fits) == 2
    assert fits[1].score == 0
    assert "did not score" in fits[1].rationale


def test_unknown_labels_are_dropped_not_crashed():
    services = [_service("ERP", "svc-1")]
    scoring = MatchScoring(
        service_fits=[
            _ServiceFitOut(service_ref="S9", score=99),
            _ServiceFitOut(service_ref="S1", score=40),
        ]
    )

    fits = resolve_fits(scoring, services)

    assert len(fits) == 1
    assert fits[0].score == 40


def test_duplicate_labels_keep_the_highest_score():
    services = [_service("ERP", "svc-1")]
    scoring = MatchScoring(
        service_fits=[
            _ServiceFitOut(service_ref="S1", score=20),
            _ServiceFitOut(service_ref="S1", score=75),
        ]
    )

    assert resolve_fits(scoring, services)[0].score == 75


def test_out_of_range_scores_are_clamped():
    services = [_service("ERP", "svc-1")]
    scoring = MatchScoring(service_fits=[_ServiceFitOut(service_ref="S1", score=100)])

    assert resolve_fits(scoring, services)[0].score == 100


def test_catalog_is_rendered_with_short_labels():
    text = format_catalog([_service("ERP", "svc-1"), _service("Audit", "svc-2")])

    assert "[S1] ERP" in text
    assert "[S2] Audit" in text
    assert "svc-1" not in text  # id thật không lọt vào prompt


# --- Hồ sơ công ty ----------------------------------------------------------


def test_profile_flags_itself_when_there_is_nothing_to_judge():
    profile = build_company_profile(_result("Mystery Co"))

    assert "Mystery Co" in profile
    assert "thin" in profile


def test_profile_merges_enrichment_into_the_search_result():
    result = CompanyResult(
        company=Company(name="Acme", domain="acme.vn", location="Hanoi"),
        contacts=[Contact(full_name="Lan Nguyen", title="CFO")],
    )
    enrichment = CompanyEnrichment(
        company_name="Acme",
        description="Payments platform for SMEs.",
        industry="Fintech",
        technologies=["React", "AWS"],
        executives=[Executive(full_name="Minh Tran", title="CTO")],
    )

    profile = build_company_profile(result, enrichment)

    assert "acme.vn" in profile
    assert "Fintech" in profile
    assert "Payments platform" in profile
    assert "React, AWS" in profile
    assert "Lan Nguyen — CFO" in profile
    assert "Minh Tran — CTO" in profile


def test_search_result_wins_over_enrichment_for_the_same_field():
    """Dữ liệu từ nhà cung cấp search là dữ liệu có cấu trúc; enrich là suy luận
    từ website nên chỉ dùng để lấp chỗ trống."""
    result = _result("Acme", industry="Logistics")
    enrichment = CompanyEnrichment(company_name="Acme", industry="Fintech")

    profile = build_company_profile(result, enrichment)

    assert "Industry: Logistics" in profile
    assert "Industry: Fintech" not in profile


def test_long_descriptions_are_clipped():
    enrichment = CompanyEnrichment(company_name="Acme", description="x" * 5000)

    profile = build_company_profile(_result("Acme"), enrichment)

    assert len(profile) < 2000
    assert "…" in profile


# --- Ghép kết quả enrich ----------------------------------------------------


def test_enrichment_is_found_by_domain_and_by_name():
    index = build_enrichment_index(
        [CompanyEnrichment(company_name="Acme Fintech", domain="acmefintech.vn")]
    )

    assert lookup_enrichment(index, "Acme Fintech", None) is not None
    assert lookup_enrichment(index, "Different Name", "https://www.acmefintech.vn/") is not None
    assert lookup_enrichment(index, "Unrelated Co", None) is None


def test_the_newest_enrichment_wins():
    index = build_enrichment_index(
        [
            CompanyEnrichment(company_name="Acme", domain="acme.vn", description="new"),
            CompanyEnrichment(company_name="Acme", domain="acme.vn", description="old"),
        ]
    )

    assert lookup_enrichment(index, "Acme", "acme.vn").description == "new"


# --- match_company: lỗi LLM không được làm hỏng cả bảng ----------------------


def test_llm_failure_is_recorded_on_the_company_not_raised(monkeypatch):
    async def boom(*args, **kwargs):
        raise LLMError("provider is down")

    monkeypatch.setattr("saletool.matching.llm.request_json", boom)

    settings = AppSettings()
    settings.llm.api_key = "sk-test"

    match = asyncio.run(match_company(_result("Acme"), [_service("ERP")], settings))

    assert match.error == "provider is down"
    assert match.overall_score == 0
    assert match.company_name == "Acme"


def test_overall_score_is_the_best_fitting_service(monkeypatch):
    async def scored(*args, **kwargs):
        return {
            "summary": "Worth a call.",
            "signals": ["hiring finance staff"],
            "concerns": [],
            "service_fits": [
                {"service_ref": "S1", "score": 35, "rationale": "no signal"},
                {"service_ref": "S2", "score": 85, "rationale": "clear need"},
            ],
        }

    monkeypatch.setattr("saletool.matching.llm.request_json", scored)

    settings = AppSettings()
    settings.llm.api_key = "sk-test"
    services = [_service("ERP", "svc-1"), _service("Audit", "svc-2")]

    match = asyncio.run(match_company(_result("Acme"), services, settings))

    assert match.overall_score == 85
    assert match.best_service_name == "Audit"
    assert match.best_service_id == "svc-2"
    assert match.signals == ["hiring finance staff"]
    assert match.error is None
    # Dịch vụ khớp nhất phải nằm đầu để UI hiển thị ngay.
    assert match.service_fits[0].score == 85


def test_malformed_llm_output_is_salvaged(monkeypatch):
    async def messy(*args, **kwargs):
        return {
            "summary": "ok",
            "signals": "not-a-list",
            "service_fits": [
                {"service_ref": "S1", "score": 60, "rationale": "fine"},
                {"nonsense": True},
            ],
        }

    monkeypatch.setattr("saletool.matching.llm.request_json", messy)

    settings = AppSettings()
    settings.llm.api_key = "sk-test"

    match = asyncio.run(match_company(_result("Acme"), [_service("ERP", "svc-1")], settings))

    assert match.error is None
    assert match.overall_score == 60
    assert match.signals == []
