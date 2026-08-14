"""/api/settings — cấu hình LLM, công cụ search và pipeline enrich.

Phạm vi: cấu hình dùng chung cho cả hệ thống (không per-user), phù hợp tool nội
bộ nhóm nhỏ. Mọi user đã đăng nhập đều xem/sửa được.

Nguyên tắc xử lý API key: **không bao giờ trả key thật về client**. Client nhận
bản mask để hiển thị; khi lưu, nếu client gửi lại đúng sentinel MASKED_SECRET
thì backend giữ nguyên key cũ.
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
    LLM_PROVIDERS,
    MASKED_SECRET,
    SEARCH_PROVIDERS,
    SEARCH_PROVIDERS_REQUIRING_KEY,
    AppSettings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class TestConnectionRequest(BaseModel):
    target: str  # "llm" | "search"


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str
    detail: str | None = None


def _to_client_view(settings: AppSettings) -> dict:
    """Chuyển sang dạng an toàn để gửi cho frontend: key thật -> bản mask."""
    payload = settings.model_dump(mode="json")
    payload["llm"]["api_key"] = mask(settings.llm.api_key)
    payload["search"]["api_key"] = mask(settings.search.api_key)
    payload["llm"]["api_key_set"] = bool(settings.llm.api_key)
    payload["search"]["api_key_set"] = bool(settings.search.api_key)
    return payload


def _merge_secret(incoming: str | None, existing: str | None) -> str | None:
    """Giữ key cũ nếu client không sửa (gửi lại sentinel hoặc bản mask)."""
    if incoming is None:
        return existing
    if incoming == MASKED_SECRET:
        return existing
    if incoming.startswith("•"):
        # Client gửi lại nguyên bản mask -> coi như không đổi.
        return existing
    stripped = incoming.strip()
    return stripped or None


@router.get("")
def read_settings(_: str = Depends(get_current_user)) -> dict:
    settings = get_settings_repository().get_settings()
    return {
        "settings": _to_client_view(settings),
        "options": {
            "llm_providers": LLM_PROVIDERS,
            "search_providers": SEARCH_PROVIDERS,
            "search_providers_requiring_key": SEARCH_PROVIDERS_REQUIRING_KEY,
        },
    }


@router.put("")
def write_settings(payload: AppSettings, user: str = Depends(get_current_user)) -> dict:
    repo = get_settings_repository()
    current = repo.get_settings()

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

    # Chặn cấu hình bất khả thi ngay tại đây thay vì để enrich fail lúc chạy.
    if payload.search.provider in SEARCH_PROVIDERS_REQUIRING_KEY and not payload.search.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Search provider '{payload.search.provider}' requires an API key.",
        )
    if payload.search.provider == "searxng" and not payload.search.searxng_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SearXNG requires an instance URL (e.g. http://localhost:8080).",
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
        # Thiếu SALETOOL_SECRET_KEY thì không mã hoá được API key. Bản thân
        # exception đã có hướng dẫn sinh khoá — đừng để nó thành 500 trống rỗng.
        logger.error("Không lưu được settings: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return {"settings": _to_client_view(saved)}


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(
    payload: TestConnectionRequest, _: str = Depends(get_current_user)
) -> TestConnectionResponse:
    """Gọi thật tới LLM/search bằng cấu hình đã lưu để người dùng biết nó có chạy không."""
    settings = get_settings_repository().get_settings()

    if payload.target == "llm":
        return await _test_llm(settings)
    if payload.target == "search":
        return await _test_search(settings)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="target must be 'llm' or 'search'"
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
    except Exception as exc:  # noqa: BLE001 - hiện lỗi thật cho người dùng sửa cấu hình
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
