from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def as_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def file_category(relative_path: str) -> str:
    normalized = str(relative_path).replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    suffix = Path(normalized).suffix.lower()
    for part in parts[:-1]:
        if part == "ddl":
            return "ddl"
        if part == "sql":
            return "sql"
        if part in {"metadata", "samples", "generated", "files"}:
            return part
    if suffix == ".ddl":
        return "ddl"
    if suffix == ".sql":
        return "sql"
    if suffix in {".csv", ".json", ".yaml", ".yml"}:
        return "metadata"
    return "other"


def logical_name(relative_path: str) -> str:
    return Path(str(relative_path).replace("\\", "/")).stem
