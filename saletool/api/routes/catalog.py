"""/api/catalog — CRUD for your company's service catalog.

This is input for matching: description quality directly affects ranking quality,
because the LLM only sees what is written here.

Scope: system-wide (like Settings), so the sales team shares one service list.
Any logged-in user can view and edit it; `updated_by` records the last editor.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from saletool.api.deps import get_current_user
from saletool.db.factory import get_service_repository
from saletool.models import Service, ServiceInput

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _validated(payload: ServiceInput) -> ServiceInput:
    """Normalize input by trimming whitespace and removing empty list items."""
    cleaned = payload.model_copy(deep=True)
    cleaned.name = cleaned.name.strip()
    if not cleaned.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Service name is required."
        )

    cleaned.category = (cleaned.category or "").strip() or None
    cleaned.description = cleaned.description.strip()
    cleaned.value_proposition = (cleaned.value_proposition or "").strip() or None
    cleaned.target_company_size = (cleaned.target_company_size or "").strip() or None
    cleaned.target_industries = [i.strip() for i in cleaned.target_industries if i.strip()]
    cleaned.keywords = [k.strip() for k in cleaned.keywords if k.strip()]
    return cleaned


@router.get("")
def list_services(_: str = Depends(get_current_user)) -> list[dict]:
    return [service.model_dump() for service in get_service_repository().list_services()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceInput, user: str = Depends(get_current_user)) -> dict:
    service: Service = get_service_repository().create_service(_validated(payload), updated_by=user)
    return service.model_dump()


@router.put("/{service_id}")
def update_service(
    service_id: str, payload: ServiceInput, user: str = Depends(get_current_user)
) -> dict:
    try:
        service = get_service_repository().update_service(
            service_id, _validated(payload), updated_by=user
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return service.model_dump()


# Do not annotate the return type as `-> None`: with `from __future__ import
# annotations`, FastAPI interprets it as `NoneType` and treats it as a response
# model. A 204 response cannot have a body, so the app would fail when registering
# the route (AssertionError during import).
@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: str, _: str = Depends(get_current_user)):
    if not get_service_repository().delete_service(service_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
