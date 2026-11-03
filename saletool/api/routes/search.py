"""/api/search, /api/search/runs, /api/download/{fmt} — run company/senior-contact
search and retrieve previous run history."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from starlette.concurrency import run_in_threadpool

from saletool.api.deps import get_current_user
from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
    get_search_run_repository,
    get_settings_repository,
)
from saletool.history import read_workflow_history
from saletool.models import (
    DATA_PROVIDERS,
    DATA_PROVIDERS_REQUIRING_KEY,
    DEFAULT_SENIOR_LEVELS,
    SENIORITY_LEVELS,
    SearchCriteria,
)
from saletool.output import write_csv, write_json
from saletool.pipeline import run_search
from saletool.providers import get_provider
from saletool.title_expansion import expand_titles

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search/options")
def search_options(_: str = Depends(get_current_user)) -> dict:
    """Valid seniority levels for the search form.

    Return them from the backend instead of hardcoding them in the frontend: this
    list is defined in `saletool/seniority.py`, and duplicating it in JS would
    require keeping two copies in sync.
    """
    return {
        "enabled_search_fields": get_settings_repository().get_settings().data_source.enabled_search_fields,
        "seniority_levels": SENIORITY_LEVELS,
        "default_senior_levels": DEFAULT_SENIOR_LEVELS,
        "data_providers": DATA_PROVIDERS,
        # The frontend needs to know which providers require a key so it can
        # explain what is missing below the selector instead of assuming all do.
        "data_providers_requiring_key": DATA_PROVIDERS_REQUIRING_KEY,
    }


def _split_csv_field(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


@router.post("/search")
async def search(request: Request, user: str = Depends(get_current_user)) -> dict:
    form = await request.form()
    settings = get_settings_repository().get_settings()
    data_source = settings.data_source
    enabled_fields = set(data_source.enabled_search_fields)

    def field(name: str, default: str = "") -> str:
        value = form.get(name, default)
        return value if isinstance(value, str) else default

    seniority_levels = [v for v in form.getlist("seniority_levels") if isinstance(v, str)]
    if "seniority_levels" not in enabled_fields:
        selected_seniority_levels = []
    elif field("seniority_filter_present") == "true":
        selected_seniority_levels = seniority_levels
    else:
        selected_seniority_levels = seniority_levels or list(DEFAULT_SENIOR_LEVELS)

    try:
        criteria = SearchCriteria(
            industries=_split_csv_field(field("industries")) if "industries" in enabled_fields else [],
            keywords=_split_csv_field(field("keywords")) if "keywords" in enabled_fields else [],
            locations=_split_csv_field(field("locations")) if "locations" in enabled_fields else [],
            company_size_min=(
                _parse_optional_int(field("company_size_min"))
                if "company_size" in enabled_fields
                else None
            ),
            company_size_max=(
                _parse_optional_int(field("company_size_max"))
                if "company_size" in enabled_fields
                else None
            ),
            target_titles=(
                _split_csv_field(field("target_titles")) if "target_titles" in enabled_fields else []
            ),
            seniority_levels=selected_seniority_levels,
            max_companies=int(field("max_companies", "20") or 20),
            max_contacts_per_company=int(field("max_contacts_per_company", "5") or 5),
        )
    except Exception as exc:  # Broad catch to return a clear input error to the client.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid criteria: {exc}"
        ) from exc

    # Get the data source and API key from Settings, not the form: this is a
    # one-time team setting stored encrypted. The form only contains values that
    # change per run (criteria and whether to look up emails).
    provider_name = field("data_provider") or data_source.provider
    if provider_name not in DATA_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported data provider: {provider_name}",
        )
    if provider_name != data_source.provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{provider_name}' is not the configured data source "
                f"('{data_source.provider}'). Change it in Settings first."
            ),
        )
    if provider_name in DATA_PROVIDERS_REQUIRING_KEY and not data_source.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No API key configured for '{provider_name}'. Add it in Settings.",
        )

    try:
        provider_instance = get_provider(
            provider_name,
            api_key=data_source.api_key,
            # Email lookup costs Apollo credits, so it must be possible to disable it in the form.
            reveal_emails=field("apollo_reveal_emails", "true") != "false",
        )
        criteria.expanded_target_titles, criteria.title_expansion_status = await expand_titles(criteria.target_titles, settings.llm)
        results = await run_in_threadpool(run_search, criteria, provider_instance)
    except Exception as exc:  # Broad catch to return a clear error instead of a blank 500.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Search failed: {exc}"
        ) from exc

    # api_key is not part of `criteria`, so it is never saved in history.
    run = get_search_run_repository().save_run(
        username=user, provider=provider_name, criteria=criteria, results=results
    )

    return {
        "expanded_target_titles": criteria.expanded_target_titles,
        "title_expansion_status": criteria.title_expansion_status,
        "run_id": run.id,
        "created_at": run.created_at,
        "provider": run.provider,
        "companies": [r.model_dump() for r in results],
        "total_companies": run.total_companies,
        "total_contacts": run.total_contacts,
    }


@router.get("/search/runs")
def list_runs(user: str = Depends(get_current_user), limit: int = 20) -> list[dict]:
    runs = get_search_run_repository().list_runs(user, limit=limit)
    return [r.model_dump() for r in runs]


@router.get("/search/runs/{run_id}")
def get_run(run_id: str, user: str = Depends(get_current_user)) -> dict:
    run = get_search_run_repository().get_run(user, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found.")
    return run.model_dump()


@router.delete("/search/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run_id: str, user: str = Depends(get_current_user)):
    # Delete a search run and its enrichment/matching/messaging jobs. Keep older
    # jobs without run_id (manual/legacy) because they may belong to other history.
    repo = get_search_run_repository()
    if not repo.get_run(user, run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found.")
    for job_repo in (
        get_enrich_job_repository(),
        get_match_job_repository(),
        get_message_job_repository(),
    ):
        job_repo.delete_for_run(user, run_id)
    repo.delete_run(user, run_id)
@router.get("/search/runs/{run_id}/history")
def get_history(run_id: str, user: str = Depends(get_current_user)) -> dict:
    run = get_search_run_repository().get_run(user, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found.")
    return read_workflow_history(run)


@router.get("/download/{fmt}")
def download(fmt: str, run_id: str | None = None, user: str = Depends(get_current_user)) -> Response:
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported format (use csv or json).")

    repo = get_search_run_repository()
    run = repo.get_run(user, run_id) if run_id else repo.get_latest_run(user)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No search results to download yet.")

    fd, tmp_path_str = tempfile.mkstemp(suffix=f".{fmt}")
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        if fmt == "json":
            write_json(run.results, tmp_path)
            media_type = "application/json"
        else:
            write_csv(run.results, tmp_path)
            media_type = "text/csv"
        data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=saletool_results.{fmt}"},
    )
