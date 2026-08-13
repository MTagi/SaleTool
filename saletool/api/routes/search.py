"""/api/search, /api/search/runs, /api/download/{fmt} — chạy pipeline tìm
công ty + liên hệ cấp cao, và lịch sử các lần chạy trước đó."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from saletool.api.deps import get_current_user
from saletool.db.factory import get_search_run_repository
from saletool.models import DEFAULT_SENIOR_LEVELS, SearchCriteria
from saletool.output import write_csv, write_json
from saletool.pipeline import run_search
from saletool.providers import get_provider

router = APIRouter(prefix="/api", tags=["search"])


def _split_csv_field(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


async def _save_upload(upload) -> Path:
    suffix = Path(upload.filename or "upload.csv").suffix or ".csv"
    fd, path_str = tempfile.mkstemp(suffix=suffix)
    path = Path(path_str)
    content = await upload.read()
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


@router.post("/search")
async def search(request: Request, user: str = Depends(get_current_user)) -> dict:
    form = await request.form()

    def field(name: str, default: str = "") -> str:
        value = form.get(name, default)
        return value if isinstance(value, str) else default

    seniority_levels = [v for v in form.getlist("seniority_levels") if isinstance(v, str)]

    try:
        criteria = SearchCriteria(
            industries=_split_csv_field(field("industries")),
            keywords=_split_csv_field(field("keywords")),
            locations=_split_csv_field(field("locations")),
            company_size_min=_parse_optional_int(field("company_size_min")),
            company_size_max=_parse_optional_int(field("company_size_max")),
            target_titles=_split_csv_field(field("target_titles")),
            seniority_levels=seniority_levels or list(DEFAULT_SENIOR_LEVELS),
            max_companies=int(field("max_companies", "20") or 20),
            max_contacts_per_company=int(field("max_contacts_per_company", "5") or 5),
        )
    except Exception as exc:  # noqa: BLE001 - trả lỗi input rõ ràng cho client
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tiêu chí không hợp lệ: {exc}")

    provider_name = field("provider", "mock")
    tmp_paths: list[Path] = []
    try:
        provider_kwargs: dict = {}
        if provider_name == "apollo":
            api_key = field("apollo_api_key")
            if not api_key:
                raise ValueError("Provider apollo cần API key.")
            provider_kwargs["api_key"] = api_key
        elif provider_name == "csv_import":
            companies_upload = form.get("companies_csv")
            if not companies_upload or not getattr(companies_upload, "filename", None):
                raise ValueError("Provider csv_import cần file CSV danh sách công ty.")
            companies_path = await _save_upload(companies_upload)
            tmp_paths.append(companies_path)
            provider_kwargs["companies_csv"] = str(companies_path)

            contacts_upload = form.get("contacts_csv")
            if contacts_upload and getattr(contacts_upload, "filename", None):
                contacts_path = await _save_upload(contacts_upload)
                tmp_paths.append(contacts_path)
                provider_kwargs["contacts_csv"] = str(contacts_path)

        provider_instance = get_provider(provider_name, **provider_kwargs)
        results = run_search(criteria, provider_instance)
    except Exception as exc:  # noqa: BLE001 - trả lỗi rõ ràng thay vì 500 trắng
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Không chạy được tìm kiếm: {exc}")
    finally:
        for p in tmp_paths:
            p.unlink(missing_ok=True)

    # api_key không nằm trong `criteria` nên không bao giờ bị lưu vào lịch sử.
    run = get_search_run_repository().save_run(
        username=user, provider=provider_name, criteria=criteria, results=results
    )

    return {
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lần tìm kiếm này.")
    return run.model_dump()


@router.get("/download/{fmt}")
def download(fmt: str, run_id: str | None = None, user: str = Depends(get_current_user)) -> Response:
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng không hỗ trợ (dùng csv hoặc json).")

    repo = get_search_run_repository()
    run = repo.get_run(user, run_id) if run_id else repo.get_latest_run(user)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có kết quả tìm kiếm nào để tải.")

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
