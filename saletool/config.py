"""Nạp input format (YAML/JSON) mô tả mục tiêu tìm kiếm công ty."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from saletool.models import SearchCriteria


def load_criteria(path: str | Path) -> SearchCriteria:
    """Đọc file cấu hình (.yaml/.yml/.json) và trả về SearchCriteria đã validate."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình: {file_path}")

    raw = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(raw) or {}
    elif file_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(f"Định dạng file không được hỗ trợ: {file_path.suffix} (dùng .yaml hoặc .json)")

    return SearchCriteria.model_validate(data)
