"""/api/search, /api/download/{fmt} — chạy pipeline tìm công ty + liên hệ cấp cao."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from saletool.models import CompanyResult, DEFAULT_SENIOR_LEVELS, SearchCriteria
from saletool.output import write_csv, write_json
from saletool.pipeline import run_search
from saletool.providers import get_provider
from saletool.api.deps import get_current_user

router = APIRouter(prefix="/api", tags=["search"])

# Kết quả tìm kiếm gần nhất của mỗi user, lưu tạm trong bộ nhớ tiến trình
# (mất khi restart server — đủ dùng cho 1 phiên làm việc; nâng cấp lên lưu
# trong DB nếu cần giữ lịch sử nhiều phiên).
_results_store: dict[str, list[CompanyResult]] = {}


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

    _results_store[user] = results
    total_contacts = sum(len(r.contacts) for r in results)
    return {
        "companies": [r.model_dump() for r in results],
        "total_companies": len(results),
        "total_contacts": total_contacts,
    }


@router.get("/download/{fmt}")
def download(fmt: str, user: str = Depends(get_current_user)) -> Response:
    results = _results_store.get(user)
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có kết quả tìm kiếm nào để tải.")
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng không hỗ trợ (dùng csv hoặc json).")

    fd, tmp_path_str = tempfile.mkstemp(suffix=f".{fmt}")
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        if fmt == "json":
            write_json(results, tmp_path)
            media_type = "application/json"
        else:
            write_csv(results, tmp_path)
            media_type = "text/csv"
        data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=saletool_results.{fmt}"},
    )
