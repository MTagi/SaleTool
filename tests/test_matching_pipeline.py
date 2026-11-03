"""Test matching logic that does NOT depend on an LLM.

Rankings and service-label mapping are determined by code, so they must be
testable without real API calls.
"""

import asyncio

from saletool.llm_api import LLMError
from saletool.matching.llm import (
    MatchScoring,
    _ServiceFitOut,
    format_catalog,
    resolve_fits,
)
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
    EnrichmentSource,
    Executive,
    Service,
    ServiceFit,
)


def _service(name: str, service_id: str | None = None, **overrides) -> Service:
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


def _match(name: str, score: int, fits: list[int] | None = None, **overrides) -> CompanyMatch:
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


# --- Ranking ----------------------------------------------------------------


def test_ranks_by_score_descending():
    ranked = rank_matches([_match("Low", 20), _match("High", 90), _match("Mid", 55)])

    assert [m.company_name for m in ranked] == ["High", "Mid", "Low"]
    assert [m.rank for m in ranked] == [1, 2, 3]


def test_ties_go_to_the_company_that_fits_more_services():
    """When the best service score ties, rank the company matching more services first."""
    broad = _match("Broad", 80, fits=[80, 75, 70])
    narrow = _match("Narrow", 80, fits=[80, 10, 5])

    ranked = rank_matches([narrow, broad])

    assert [m.company_name for m in ranked] == ["Broad", "Narrow"]


def test_failed_companies_sink_below_genuinely_low_scores():
    """A scoring error differs from a low score and must not be conflated."""
    ranked = rank_matches([_match("Broken", 0, fits=[], error="LLM timed out"), _match("Weak", 5)])

    assert [m.company_name for m in ranked] == ["Weak", "Broken"]
    assert ranked[-1].error


def test_ranking_an_empty_list_is_fine():
    assert rank_matches([]) == []


# --- Service label mapping --------------------------------------------------


def test_resolves_short_labels_back_to_service_ids():
    services = [_service("ERP", "svc-1"), _service("Data platform", "svc-2")]
    scoring = MatchScoring(
        service_fits=[
            _ServiceFitOut(service_ref="S2", score=80, rationale="uses spreadsheets"),
            _ServiceFitOut(service_ref="S1", score=30, rationale="no signal"),
        ]
    )

    fits = resolve_fits(scoring, services)

    assert [f.service_id for f in fits] == ["svc-1", "svc-2"]  # Catalog order.
    assert {f.service_id: f.score for f in fits} == {"svc-1": 30, "svc-2": 80}


def test_accepts_the_service_name_instead_of_the_label():
    """Models sometimes ignore formatting instructions; do not discard the whole result."""
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
    assert "svc-1" not in text  # Real IDs must not appear in the prompt.


# --- Company profile --------------------------------------------------------


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
    """Search-provider data is structured; enrichment is inferred from a website
    and should only fill missing fields."""
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


def test_factory_evidence_and_sources_reach_the_scoring_request(monkeypatch):
    report = (
        "## Overview\n" + "General company information. " * 40
        + "\n## Facilities\nWangnoi Beverage operates a plant in Ayutthaya. "
        "Source: https://plant.example/facilities\n"
        "## Gaps\nCCTV infrastructure and buying intent are not established."
    )
    enrichment = CompanyEnrichment(
        company_name="Acme", description="Beverage manufacturer.",
        summary_markdown=report, report_status="completed",
        sources=[EnrichmentSource(
            url="https://plant.example/facilities", fetched_at="2026-11-03",
            fetch_method="http", extractor="json_ld+meta+regex", ok=True,
        )],
    )

    async def score(settings, payload):
        prompt = payload["messages"][1]["content"]
        assert report in prompt
        assert "Wangnoi Beverage" in prompt
        assert "https://plant.example/facilities" in prompt
        assert "CCTV infrastructure and buying intent are not established" in prompt
        return {"summary": "Facilities verified; camera infrastructure still unknown.",
                "service_fits": [{"service_ref": "S1", "score": 45, "rationale": "Factory"}]}

    monkeypatch.setattr("saletool.matching.llm.request_json", score)
    settings = AppSettings()
    settings.llm.api_key = "test-key"
    match = asyncio.run(match_company(_result("Acme"), [_service("VMS")], settings,
                                     enrichment=enrichment))
    assert match.error is None
    assert match.used_enrichment
    assert match.overall_score == 45


def test_failed_report_falls_back_to_balanced_source_excerpts():
    enrichment = CompanyEnrichment(
        company_name="Acme", report_status="failed", summary_markdown="Stale report",
        raw_markdown=("SOURCE URL: https://one.example\n" + "x" * 20000
                      + "\n\nSOURCE URL: https://two.example\nVerified warehouse in Hanoi."),
    )
    profile = build_company_profile(_result("Acme"), enrichment)
    assert "Stale report" not in profile
    assert "Verified warehouse in Hanoi" in profile
    assert "https://one.example" in profile
    assert "https://two.example" in profile
    assert "[truncated]" in profile
    assert len(profile) < 17000


def test_large_research_report_is_bounded_without_losing_source_urls():
    enrichment = CompanyEnrichment(
        company_name="Acme", summary_markdown="x" * 30000, report_status="completed",
        sources=[EnrichmentSource(
            url=url, fetched_at="2026-11-03", fetch_method="http", extractor="none", ok=ok,
        ) for url, ok in [("https://verified.example", True), ("https://failed.example", False)]],
    )
    profile = build_company_profile(_result("Acme"), enrichment)
    assert len(profile) < 17000
    assert "[truncated]" in profile
    assert "https://verified.example" in profile
    assert "https://failed.example" not in profile


# --- Join enrichment results -----------------------------------------------


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


def test_enrichment_rejects_conflicting_domains_and_ambiguous_names():
    first = CompanyEnrichment(company_name="Acme", domain="one.example")
    second = CompanyEnrichment(company_name="Acme", domain="two.example")
    index = build_enrichment_index([first])
    assert lookup_enrichment(index, "Acme", "two.example") is None
    assert lookup_enrichment(index, "Acme", None) is first
    index = build_enrichment_index([first, second])
    assert lookup_enrichment(index, "Acme", None) is None
    assert lookup_enrichment(index, "Acme", "two.example") is second


def test_company_name_cannot_collide_with_an_unrelated_domain():
    unrelated = CompanyEnrichment(company_name="Unrelated", domain="acme.example")
    index = build_enrichment_index([unrelated])
    assert lookup_enrichment(index, "acme.example", None) is None


# --- match_company: LLM errors must not fail the whole table ----------------


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
    # Put the best-matching service first so the UI can display it immediately.
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
