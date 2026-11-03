"""Load YAML/JSON input describing company search criteria."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from saletool.models import SearchCriteria


def load_criteria(path: str | Path) -> SearchCriteria:
    """Read a config file (.yaml/.yml/.json) and return validated SearchCriteria."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    raw = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(raw) or {}
    elif file_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix} (use .yaml or .json)")

    return SearchCriteria.model_validate(data)
