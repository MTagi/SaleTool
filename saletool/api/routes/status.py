"""/api/status — configured settings and available data.

One call lets the UI know which steps can run in advance. Previously, users had
to fill the form and submit it before seeing a 400 "LLM API key missing" error;
the information was available from the start but was never requested.

The endpoint returns **facts**, not display text: the frontend decides what to
show, while the backend reports the system state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from saletool.api.deps import get_current_user
from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
    get_search_run_repository,
    get_service_repository,
    get_settings_repository,
)

router = APIRouter(prefix="/api/status", tags=["status"])

# Enough to know "whether" and "approximately how many" without fetching all history.
_PROBE_LIMIT = 50


@router.get("")
def read_status(user: str = Depends(get_current_user)) -> dict:
    settings = get_settings_repository().get_settings()
    services = get_service_repository().list_services()

    runs = get_search_run_repository().list_runs(user, limit=_PROBE_LIMIT)
    latest_run = runs[0] if runs else None

    return {
        # Step 1 cannot run without a data source key. The Search page uses this
        # flag to block early instead of returning 400 after the form is filled.
        "data_source_provider": settings.data_source.provider,
        "data_source_configured": bool(settings.data_source.api_key),
        "llm_configured": bool(settings.llm.api_key),
        "sender_configured": settings.sender.is_usable(),
        "search_provider": settings.search.provider,
        "auto_enrich_on_search": settings.enrichment.auto_enrich_on_search,
        "counts": {
            "services": len(services),
            "active_services": sum(1 for s in services if s.active),
            "runs": len(runs),
            "enrich_jobs": len(get_enrich_job_repository().list_jobs(user, limit=_PROBE_LIMIT)),
            "match_jobs": len(get_match_job_repository().list_jobs(user, limit=_PROBE_LIMIT)),
            "message_jobs": len(get_message_job_repository().list_jobs(user, limit=_PROBE_LIMIT)),
        },
        "latest_run": (
            {
                "id": latest_run.id,
                "created_at": latest_run.created_at,
                "total_companies": latest_run.total_companies,
                "total_contacts": latest_run.total_contacts,
            }
            if latest_run
            else None
        ),
    }
