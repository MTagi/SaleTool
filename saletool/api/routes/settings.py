"""/api/settings — configure the LLM, search tools, and enrichment pipeline.

Scope: configuration is system-wide (not per-user), suitable for a small internal
tool. Any logged-in user can view and edit it.

API key handling principle: **never return the real key to the client**. The
client receives a masked value for display; on save, if it sends back the
MASKED_SECRET sentinel, the backend preserves the existing key.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from saletool.api.deps import get_current_user
from saletool.crypto import mask
from saletool.db.factory import get_settings_repository
from saletool.enrichment.search import get_search_provider
from saletool.models import (
    APOLLO_SEARCH_FIELDS,
    DATA_PROVIDERS,
    DATA_PROVIDERS_REQUIRING_KEY,
    LLM_PROVIDERS,
    MASKED_SECRET,
    SEARCH_PROVIDERS,
    SEARCH_PROVIDERS_REQUIRING_KEY,
    AppSettings,
    SearchCriteria,
)
from saletool.providers import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class TestConnectionRequest(BaseModel):
    target: str  # "llm" | "search" | "data_source"


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str
    detail: str | None = None


def _to_client_view(settings: AppSettings) -> dict:
    """Convert values to a safe format for the frontend: real keys become masked values."""
    payload = settings.model_dump(mode="json")
    payload["llm"]["api_key"] = mask(settings.llm.api_key)
    payload["search"]["api_key"] = mask(settings.search.api_key)
    payload["data_source"]["api_key"] = mask(settings.data_source.api_key)
    payload["llm"]["api_key_set"] = bool(settings.llm.api_key)
    payload["search"]["api_key_set"] = bool(settings.search.api_key)
    payload["data_source"]["api_key_set"] = bool(settings.data_source.api_key)
    return payload


def _merge_secret(incoming: str | None, existing: str | None) -> str | None:
    """Keep the existing key if the client did not change it (sentinel or masked value)."""
    if incoming is None:
        return existing
    if incoming == MASKED_SECRET:
        return existing
    if incoming.startswith("•"):
        # If the client sends back the same mask, treat it as unchanged.
        return existing
    stripped = incoming.strip()
    return stripped or None


@router.get("")
def read_settings(_: str = Depends(get_current_user)) -> dict:
    settings = get_settings_repository().get_settings()
    return {
        "settings": _to_client_view(settings),
        "options": {
            "apollo_search_fields": APOLLO_SEARCH_FIELDS,
            "data_providers": DATA_PROVIDERS,
            "data_providers_requiring_key": DATA_PROVIDERS_REQUIRING_KEY,
            "llm_providers": LLM_PROVIDERS,
            "search_providers": SEARCH_PROVIDERS,
            "search_providers_requiring_key": SEARCH_PROVIDERS_REQUIRING_KEY,
        },
    }


@router.put("")
def write_settings(payload: AppSettings, user: str = Depends(get_current_user)) -> dict:
    repo = get_settings_repository()
    current = repo.get_settings()

    if payload.data_source.provider not in DATA_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported data provider: {payload.data_source.provider}",
        )
    if payload.llm.provider not in LLM_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported LLM provider: {payload.llm.provider}",
        )
    if payload.search.provider not in SEARCH_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported search provider: {payload.search.provider}",
        )

    payload.llm.api_key = _merge_secret(payload.llm.api_key, current.llm.api_key)
    payload.search.api_key = _merge_secret(payload.search.api_key, current.search.api_key)
    payload.data_source.api_key = _merge_secret(
        payload.data_source.api_key, current.data_source.api_key
    )

    # Deliberately do NOT require data_source.api_key here: users must be able to
    # save Settings before they have a key (e.g. a new installation without an
    # Apollo subscription). /api/status reports a missing key, Search disables
    # submit, and /api/search returns 400 — block where needed without locking
    # the Settings page.

    # Reject impossible configurations here instead of letting enrichment fail at runtime.
    if payload.search.provider in SEARCH_PROVIDERS_REQUIRING_KEY and not payload.search.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Search provider '{payload.search.provider}' requires an API key.",
        )
    if payload.enrichment.use_web_search and payload.search.provider == "none":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Web search is enabled for enrichment but no search provider is selected.",
        )
    if payload.enrichment.use_llm and not payload.llm.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM extraction is enabled but no LLM API key is configured.",
        )

    try:
        saved = repo.save_settings(payload, updated_by=user)
    except RuntimeError as exc:
        # Without SALETOOL_SECRET_KEY, API keys cannot be encrypted. The
        # exception includes key-generation instructions; do not return a blank 500.
        logger.error("Could not save settings: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return {"settings": _to_client_view(saved)}


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(
    payload: TestConnectionRequest, _: str = Depends(get_current_user)
) -> TestConnectionResponse:
    """Make a real LLM/search call with saved settings so users know whether it works."""
    settings = get_settings_repository().get_settings()

    if payload.target == "llm":
        return await _test_llm(settings)
    if payload.target == "search":
        return await _test_search(settings)
    if payload.target == "data_source":
        return _test_data_source(settings)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="target must be 'llm', 'search' or 'data_source'",
    )


def _test_data_source(settings: AppSettings) -> TestConnectionResponse:
    """Try a real company search to check whether the key works.

    Only run company search with `reveal_emails=False`: Apollo charges credits for
    email lookups, and a test must not spend the user's credits.
    """
    if not settings.data_source.api_key:
        return TestConnectionResponse(ok=False, message="No API key configured.")

    try:
        provider = get_provider(
            settings.data_source.provider,
            api_key=settings.data_source.api_key,
            reveal_emails=False,
        )
        companies = provider.search_companies(
            SearchCriteria(keywords=["technology"], locations=["Vietnam"], max_companies=1)
        )
    except Exception as exc:  # noqa: BLE001 - Show the actual error so users can fix the key or permissions.
        return TestConnectionResponse(
            ok=False,
            message=f"Data provider '{settings.data_source.provider}' failed.",
            detail=str(exc)[:500],
        )

    if not companies:
        return TestConnectionResponse(
            ok=True,
            message="Connected, but the test query matched no companies.",
            detail="The key works; try different criteria on the Search page.",
        )

    return TestConnectionResponse(
        ok=True,
        message=f"Connected. Found {len(companies)} company.",
        detail=companies[0].name,
    )


async def _test_llm(settings: AppSettings) -> TestConnectionResponse:
    if not settings.llm.api_key:
        return TestConnectionResponse(ok=False, message="No API key configured.")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{settings.llm.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm.api_key}"},
                json={
                    "model": settings.llm.model,
                    "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                    "max_tokens": 5,
                },
            )
    except httpx.HTTPError as exc:
        return TestConnectionResponse(ok=False, message="Could not reach the LLM API.", detail=str(exc))

    if resp.status_code != 200:
        return TestConnectionResponse(
            ok=False,
            message=f"LLM API returned {resp.status_code}.",
            detail=resp.text[:500],
        )

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        return TestConnectionResponse(
            ok=False, message="Unexpected response shape from the LLM API.", detail=str(exc)
        )

    return TestConnectionResponse(
        ok=True, message=f"Connected. Model '{settings.llm.model}' replied.", detail=str(content)[:200]
    )


async def _test_search(settings: AppSettings) -> TestConnectionResponse:
    if settings.search.provider == "none":
        return TestConnectionResponse(
            ok=False, message="No search provider selected (set to 'none')."
        )

    try:
        provider = get_search_provider(settings.search)
        results = await provider.search("Vietnam technology company", max_results=3)
    except Exception as exc:  # noqa: BLE001 - Show the actual error so users can fix the configuration.
        return TestConnectionResponse(
            ok=False, message=f"Search provider '{settings.search.provider}' failed.", detail=str(exc)[:500]
        )

    if not results:
        return TestConnectionResponse(
            ok=False,
            message="Search ran but returned no results — check the instance/API key.",
        )

    return TestConnectionResponse(
        ok=True,
        message=f"Connected. Got {len(results)} result(s).",
        detail=results[0].url,
    )
