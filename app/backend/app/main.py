from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
try:
    import sqlite3
except ModuleNotFoundError:  # Some minimal Python images omit stdlib _sqlite3.
    import pysqlite3 as sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DFI_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("DFI_DB_PATH", DATA_DIR / "dataflow.db"))
IMPORT_DIR = Path(os.getenv("DFI_IMPORT_DIR", DATA_DIR / "imports"))
MAX_ZIP = int(os.getenv("DFI_MAX_ZIP_BYTES", 50 * 1024 * 1024))
MAX_ZIP_FILES = int(os.getenv("DFI_MAX_ZIP_FILES", 2000))
MAX_ENTRY_BYTES = int(os.getenv("DFI_MAX_ENTRY_BYTES", 50 * 1024 * 1024))
MAX_EXPANDED_BYTES = int(os.getenv("DFI_MAX_EXPANDED_BYTES", MAX_ZIP * 5))
MAX_ARCHIVE_PATH = int(os.getenv("DFI_MAX_ARCHIVE_PATH", 512))
logger = logging.getLogger("dataflow-inspector")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS projects(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          dialect TEXT NOT NULL DEFAULT 'gaussdb_dws', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS imports(
          id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          version INTEGER NOT NULL, sha256 TEXT NOT NULL, filename TEXT NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          completed_at TEXT, error TEXT, error_detail TEXT,
          attempts INTEGER NOT NULL DEFAULT 1,
          source_import_id INTEGER REFERENCES imports(id) ON DELETE SET NULL,
          analysis TEXT NOT NULL DEFAULT '{}',
          UNIQUE(project_id, version));
        """)
        columns = {row["name"] for row in c.execute("PRAGMA table_info(imports)")}
        migrations = {
            "updated_at": "ALTER TABLE imports ADD COLUMN updated_at TEXT",
            "completed_at": "ALTER TABLE imports ADD COLUMN completed_at TEXT",
            "error": "ALTER TABLE imports ADD COLUMN error TEXT",
            "error_detail": "ALTER TABLE imports ADD COLUMN error_detail TEXT",
            "attempts": "ALTER TABLE imports ADD COLUMN attempts INTEGER NOT NULL DEFAULT 1",
            "source_import_id": "ALTER TABLE imports ADD COLUMN source_import_id INTEGER REFERENCES imports(id) ON DELETE SET NULL",
        }
        for name, statement in migrations.items():
            if name not in columns:
                c.execute(statement)
        c.execute("UPDATE imports SET updated_at=COALESCE(updated_at,created_at)")


app = FastAPI(title="DataFlow Inspector API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    # Development UI may use any available local port, except Loomi's
    # production backend on 8080.  Do not allow LAN names/IPs or arbitrary
    # web origins.
    allow_origin_regex=r"^https?://(?:127\.0\.0\.1|localhost):(?!8080$)\d{1,5}$",
    allow_methods=["*"], allow_headers=["*"],
)


def error_payload(code: str, message: str, details: Any = None) -> dict:
    payload = {
        "error": {"code": code, "message": message},
        "detail": message,
        "message": message,
    }
    if details is not None:
        payload["error"]["details"] = details
        if isinstance(details, dict) and details.get("error_id"):
            payload["error_detail"] = details
    return payload


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "request_error"))
        message = str(exc.detail.get("message", "request failed"))
        details = exc.detail.get("details")
    else:
        code = {
            400: "invalid_request", 404: "not_found", 409: "conflict",
            413: "payload_too_large", 415: "unsupported_media_type",
            422: "validation_error",
        }.get(exc.status_code, "request_error")
        message, details = str(exc.detail), None
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, message, details),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            "validation_error",
            "request validation failed",
            jsonable_encoder(exc.errors()),
        ),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled API error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_payload("internal_error", "unexpected server error"),
    )


@app.on_event("startup")
def startup() -> None:
    init_db()


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    dialect: str = Field(default="gaussdb_dws", min_length=1, max_length=64)

    @field_validator("name", "dialect")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ChangeIn(BaseModel):
    object: str = Field(min_length=1, max_length=512)
    change_type: str = Field(min_length=1, max_length=64)
    before: str | None = Field(default=None, max_length=4000)
    after: str | None = Field(default=None, max_length=4000)


def project_or_404(pid: int) -> dict:
    with db() as c:
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not r:
        raise HTTPException(404, "project not found")
    return dict(r)


def import_or_404(iid: int) -> dict:
    with db() as c:
        r = c.execute("SELECT * FROM imports WHERE id=?", (iid,)).fetchone()
    if not r:
        raise HTTPException(404, "import not found")
    d = dict(r)
    d["error_detail"] = decode_error_detail(d.get("error_detail"))
    try:
        d["analysis"] = json.loads(d["analysis"])
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(500, {
            "code": "analysis_data_corrupt",
            "message": f"stored analysis for import {iid} is invalid",
        })
    return d


def decode_error_detail(value: Any) -> dict | None:
    """Decode a persisted public diagnostic, tolerating pre-1.0 databases."""
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def new_error_detail(
    *,
    stage: str,
    code: str,
    safe_message: str,
    exception_type: str,
    suggestion: str,
    file: str | None = None,
) -> dict:
    """Create the only error shape allowed to cross the API boundary.

    Callers must provide controlled text rather than an exception message.
    This prevents SQL, absolute paths, credentials and sample values from
    leaking into the browser or the database.
    """
    error_id = f"DFI-{uuid.uuid4().hex[:12].upper()}"
    detail = {
        "error_id": error_id,
        "stage": stage,
        "code": code,
        "exception_type": exception_type,
        "safe_message": re.sub(r"\s+", " ", safe_message).strip()[:500],
        "suggestion": re.sub(r"\s+", " ", suggestion).strip()[:1000],
        "log_path": "logs/app.log",
        "log_hint": f"在应用日志中搜索错误编号 {error_id}",
    }
    if file:
        relative = Path(file.replace("\\", "/"))
        if not relative.is_absolute() and ".." not in relative.parts:
            detail["file"] = relative.as_posix()[:512]
    return detail


def preflight_error_detail(exc: HTTPException, *, validation: dict | None = None) -> dict:
    """Map archive/validation failures to non-sensitive public diagnostics."""
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    original_code = str(detail.get("code", ""))
    if original_code == "import_preflight_failed" or validation is not None:
        file = None
        errors = (validation or {}).get("errors", [])
        if errors:
            candidate = str(errors[0]).split(":", 1)[0]
            relative = Path(candidate.replace("\\", "/"))
            if not relative.is_absolute() and ".." not in relative.parts:
                file = relative.as_posix()
        return new_error_detail(
            stage="preflight",
            code="import_preflight_failed",
            exception_type="ValidationError",
            safe_message="导入包未通过上传前检查",
            file=file,
            suggestion="根据预检错误修正文件编码或补充至少一个加工 SQL，然后重新上传。",
        )
    if exc.status_code == 413:
        return new_error_detail(
            stage="preflight",
            code="import_package_too_large",
            exception_type="ArchiveLimitError",
            safe_message="导入包或解压后的文件超出系统限制",
            suggestion="删除无关文件、拆分项目，或联系管理员调整导入大小限制。",
        )
    if exc.status_code == 415:
        return new_error_detail(
            stage="preflight",
            code="unsupported_archive_type",
            exception_type="MediaTypeError",
            safe_message="上传内容不是受支持的 ZIP 文件",
            suggestion="将项目目录重新压缩为标准 ZIP 后上传。",
        )
    return new_error_detail(
        stage="preflight",
        code="invalid_import_package",
        exception_type="ArchiveValidationError",
        safe_message="导入包格式不合法或包含不安全的文件路径（unsafe zip entry）",
        suggestion="重新生成 ZIP，确保所有文件都位于项目目录内且未加密。",
    )


def unexpected_error_detail(stage: str, exc: Exception) -> dict:
    messages = {
        "analysis": (
            "SQL/DDL 分析未完成，分析器遇到未兼容的输入或内部错误",
            "点击查看导入错误详情并记录错误编号；如可提供脱敏项目包，可据此定位具体语法。",
        ),
        "persistence": (
            "分析结果保存失败",
            "检查本机磁盘空间和数据目录写入权限后重试。",
        ),
        "extraction": (
            "导入包解压失败",
            "重新生成 ZIP，确保压缩包未损坏且文件名有效。",
        ),
        "reanalysis": (
            "重新分析未完成",
            "确认原始导入文件仍然存在，或重新上传项目包。",
        ),
    }
    message, suggestion = messages.get(stage, (
        "导入处理未完成",
        "使用错误编号查询应用日志后重试。",
    ))
    return new_error_detail(
        stage=stage,
        code="analysis_failed" if stage in {"analysis", "reanalysis"} else "import_failed",
        exception_type=type(exc).__name__[:120],
        safe_message=message,
        suggestion=suggestion,
    )


def latest_analysis(pid: int, version: int | None = None) -> tuple[dict, dict]:
    project_or_404(pid)
    if version is not None:
        sql = "SELECT * FROM imports WHERE project_id=? AND version=?"
        args: list[Any] = [pid, version]
    else:
        sql = "SELECT * FROM imports WHERE project_id=? AND status='completed' ORDER BY version DESC LIMIT 1"
        args = [pid]
    with db() as c:
        r = c.execute(sql, args).fetchone()
    if not r:
        raise HTTPException(404, "project has no analyzed import")
    if r["status"] != "completed":
        raise HTTPException(409, {
            "code": "analysis_not_completed",
            "message": f"import version {r['version']} is {r['status']}",
        })
    meta = dict(r)
    try:
        analysis = json.loads(meta.pop("analysis"))
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(500, {
            "code": "analysis_data_corrupt",
            "message": f"stored analysis for version {r['version']} is invalid",
        })
    return analysis, meta


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/ready")
def ready() -> dict:
    with db() as c:
        c.execute("SELECT 1").fetchone()
    try:
        with tempfile.NamedTemporaryFile(prefix=".ready-", dir=IMPORT_DIR):
            pass
    except OSError as exc:
        logger.error("readiness check failed: %s", exc)
        raise HTTPException(503, {
            "code": "storage_not_ready",
            "message": "import storage is not writable",
        })
    return {"status": "ready", "database": "ok", "storage": "ok", "version": app.version}


@app.post("/api/projects", status_code=201)
def create_project(p: ProjectIn) -> dict:
    ts = now()
    with db() as c:
        cur = c.execute("INSERT INTO projects(name,description,dialect,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (p.name, p.description, p.dialect, ts, ts))
        pid = cur.lastrowid
    return project_or_404(pid)


@app.get("/api/projects")
def list_projects() -> list[dict]:
    with db() as c:
        rows = c.execute("""SELECT p.*,COUNT(i.id) import_count,
                                  MAX(CASE WHEN i.status='completed' THEN i.version END) latest_version,
                                  SUM(CASE WHEN i.status='failed' THEN 1 ELSE 0 END) failed_import_count
                           FROM projects p LEFT JOIN imports i ON i.project_id=p.id
                           GROUP BY p.id ORDER BY p.id""").fetchall()
    return [dict(x) for x in rows]


@app.get("/api/projects/{pid}")
def get_project(pid: int) -> dict:
    return project_or_404(pid)


@app.patch("/api/projects/{pid}")
def update_project(pid: int, p: ProjectIn) -> dict:
    project_or_404(pid)
    with db() as c:
        c.execute("UPDATE projects SET name=?,description=?,dialect=?,updated_at=? WHERE id=?",
                  (p.name, p.description, p.dialect, now(), pid))
    return project_or_404(pid)


@app.delete("/api/projects/{pid}", status_code=204)
def delete_project(pid: int) -> Response:
    project_or_404(pid)
    project_dir = IMPORT_DIR / str(pid)
    staged = IMPORT_DIR / f".deleted-{pid}-{uuid.uuid4().hex}"
    if project_dir.exists():
        os.replace(project_dir, staged)
    try:
        with db() as c:
            c.execute("DELETE FROM projects WHERE id=?", (pid,))
    except Exception:
        if staged.exists():
            os.replace(staged, project_dir)
        raise
    shutil.rmtree(staged, ignore_errors=True)
    return Response(status_code=204)


IDENT = r'(?:"[^"]+"|[A-Za-z_][\w$]*)(?:\.(?:"[^"]+"|[A-Za-z_][\w$]*)){0,2}'


def clean_ident(s: str) -> str:
    return ".".join(x.strip('"').lower() for x in s.strip().split("."))


def split_top(text: str) -> list[str]:
    out, start, depth, quote = [], 0, 0, None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            out.append(text[start:i].strip()); start = i + 1
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


def parse_ddl(text: str, path: str) -> list[dict]:
    tables = []
    pat = re.compile(rf"CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({IDENT})\s*\(",
                     re.I)
    for m in pat.finditer(text):
        depth, end = 1, m.end()
        while end < len(text) and depth:
            depth += (text[end] == "(") - (text[end] == ")"); end += 1
        cols = []
        for part in split_top(text[m.end():end - 1]):
            cm = re.match(r'\s*"?([\w$]+)"?\s+([A-Za-z][\w]*(?:\s*\([^)]*\))?)', part)
            if not cm or cm.group(1).upper() in {"PRIMARY", "UNIQUE", "CONSTRAINT", "DISTRIBUTE", "PARTITION"}:
                continue
            name, typ = cm.group(1).lower(), re.sub(r"\s+", " ", cm.group(2)).upper()
            role = classify_column(name, typ)
            cols.append({"name": name, "type": typ, **role})
        tables.append({"name": clean_ident(m.group(1)), "columns": cols, "ddl_file": path,
                       "layer": layer_of(clean_ident(m.group(1)))})
    return tables


def layer_of(name: str) -> str:
    base = name.split(".")[-1].lower()
    for layer in ("ods", "dwd", "dws", "ads"):
        if base.startswith(layer + "_") or name.startswith(layer + "."):
            return layer.upper()
    return "SOURCE" if name.startswith("rds.") else "DIM" if name.startswith("dim.") else "OTHER"


def classify_column(name: str, typ: str) -> dict:
    n = name.lower()
    if n in {"dt", "biz_date", "partition_date"}:
        return {"role": "partition_time", "semantic_type": "partition_time", "confidence": .95}
    if any(x in n for x in ("event_time", "request_time")):
        return {"role": "event_time", "semantic_type": "event_time", "confidence": .9}
    if any(x in n for x in ("ingestion_time", "load_time", "create_time")):
        return {"role": "ingestion_time", "semantic_type": "ingestion_time", "confidence": .85}
    if ("TIME" in typ or "DATE" in typ) and (
        n.startswith("ts_") or n.endswith(("_time", "_date", "_timestamp"))
    ):
        return {"role": "stat_time", "semantic_type": "statistical_time", "confidence": .75}
    if any(x in n for x in ("stat_", "_hour", "_minute")) and ("TIME" in typ or "DATE" in typ):
        return {"role": "stat_time", "semantic_type": "statistical_time", "confidence": .9}
    if n.endswith(("_cnt", "_count", "_amount", "_rate", "_ms", "_tokens")):
        return {"role": "measure", "semantic_type": "metric", "confidence": .85}
    if n.endswith(("_id", "_code", "_name", "_type", "_status", "_tier")):
        return {"role": "dimension", "semantic_type": "dimension", "confidence": .8}
    return {"role": "unknown", "semantic_type": "unknown", "confidence": .35}


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def matching_paren(text: str, opening: int) -> int | None:
    """Return the matching ')' while respecting SQL strings."""
    depth, quote, i = 0, None, opening
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def cte_definitions(stmt: str) -> dict[str, str]:
    """Extract balanced CTE bodies; regex cannot handle nested subqueries."""
    match = re.search(r"\bWITH\b", stmt, re.I)
    if not match:
        return {}
    out: dict[str, str] = {}
    pos = match.end()
    while pos < len(stmt):
        name_match = re.match(r'\s*,?\s*"?([A-Za-z_]\w*)"?\s+AS\s*\(', stmt[pos:], re.I)
        if not name_match:
            break
        name = name_match.group(1).lower()
        opening = pos + name_match.end() - 1
        closing = matching_paren(stmt, opening)
        if closing is None:
            break
        out[name] = stmt[opening + 1:closing]
        pos = closing + 1
        if not re.match(r"\s*,", stmt[pos:]):
            break
    return out


def top_level_select(text: str) -> re.Match | None:
    """Find SELECT outside parentheses, used to avoid selecting inside a CTE."""
    depth, quote, i = 0, None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            match = re.match(r"\bSELECT\b", text[i:], re.I)
            if match:
                return re.match(r"\bSELECT\b", text[i:], re.I)
        i += 1
    return None


def parse_sql(text: str, path: str, catalog: dict[str, dict]) -> list[dict]:
    operations = []
    # Strip comments but preserve line count.
    sql = re.sub(r"--[^\n]*", "", text)
    target_matches = list(re.finditer(rf"\bINSERT\s+INTO\s+({IDENT})", sql, re.I))
    target_matches += list(re.finditer(rf"\bCREATE\s+TABLE\s+({IDENT})\s+AS\b", sql, re.I))
    for tm in sorted(target_matches, key=lambda x: x.start()):
        target = clean_ident(tm.group(1))
        stmt_start = sql.rfind(";", 0, tm.start()) + 1
        stmt_end = sql.find(";", tm.end())
        stmt_end = len(sql) if stmt_end < 0 else stmt_end
        stmt = sql[stmt_start:stmt_end]
        local_target_end = tm.end() - stmt_start
        cte_bodies = cte_definitions(stmt)
        ctes = {name: [clean_ident(x) for x in re.findall(
            rf"\b(?:FROM|JOIN)\s+({IDENT})", body, re.I)]
                for name, body in cte_bodies.items()}

        def expand_cte(name: str, stack: set[str] | None = None) -> list[str]:
            stack = set() if stack is None else stack
            if name not in ctes or name in stack:
                return [name]
            resolved: list[str] = []
            for child in ctes[name]:
                for source in expand_cte(child, stack | {name}):
                    if source not in resolved:
                        resolved.append(source)
            return resolved

        sources, aliases = [], {}
        for sm in re.finditer(rf"\b(?:FROM|JOIN)\s+({IDENT})(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?", stmt[local_target_end:], re.I):
            src = clean_ident(sm.group(1))
            if src.upper() in {"SELECT"} or src == target:
                continue
            expanded = expand_cte(src)
            for actual in expanded:
                if actual not in sources:
                    sources.append(actual)
            alias = sm.group(2)
            if alias and alias.upper() not in {"ON", "WHERE", "LEFT", "RIGHT", "FULL", "INNER", "JOIN", "GROUP"}:
                aliases[alias.lower()] = expanded[0] if expanded else src
        select_region = stmt[local_target_end:]
        # The final SELECT follows all balanced CTE definitions. Searching from
        # the end of the last CTE avoids mistaking nested SELECTs for the writer.
        if cte_bodies:
            last_body = list(cte_bodies.values())[-1]
            body_pos = select_region.find(last_body)
            if body_pos >= 0:
                select_region = select_region[body_pos + len(last_body) + 1:]
        sel = re.search(r"\bSELECT\b(.*?)(?=\bFROM\b)", select_region, re.I | re.S)
        projections = split_top(sel.group(1)) if sel else []
        # Aggregates are often computed inside CTEs and merely projected by
        # name in the final SELECT. Keep those expressions for the metric
        # catalog while leaving final-output column lineage unchanged.
        metric_projections = list(projections)
        for body in cte_bodies.values():
            for cte_select in re.finditer(r"\bSELECT\b(.*?)(?=\bFROM\b)", body, re.I | re.S):
                for expr in split_top(cte_select.group(1)):
                    if expr not in metric_projections:
                        metric_projections.append(expr)
        tcols = [c["name"] for c in catalog.get(target, {}).get("columns", [])]
        # INSERT INTO table(col_a, col_b) must map projections to the explicit
        # writer column list instead of the physical DDL order.
        target_tail = stmt[local_target_end:]
        explicit_cols = re.match(r'\s*\(([^)]*)\)\s*(?=\bSELECT\b|\bWITH\b)', target_tail, re.I | re.S)
        if explicit_cols:
            tcols = [clean_ident(x).split(".")[-1] for x in split_top(explicit_cols.group(1))]
        col_edges = []
        for idx, expr in enumerate(projections):
            aliasm = re.search(r'\s+AS\s+"?([\w$]+)"?\s*$', expr, re.I)
            target_col = aliasm.group(1).lower() if aliasm else (tcols[idx] if idx < len(tcols) else None)
            if not target_col:
                continue
            refs = re.findall(r'\b([A-Za-z_]\w*)\.("?[\w$]+"?)\b', expr)
            resolved: set[tuple[str, str]] = set()
            for a, col in refs:
                src = aliases.get(a.lower())
                if src:
                    resolved.add((src, col.strip(chr(34)).lower()))
                    col_edges.append({"source": f"{src}.{col.strip(chr(34)).lower()}",
                                      "target": f"{target}.{target_col}", "expression": expr.strip(),
                                      "file": path, "line": line_number(sql, tm.start()), "confidence": .9})
            # SQL commonly omits a qualifier when there is a single input
            # relation (especially aggregate layers). Resolve only catalogued
            # columns in that unambiguous case; never guess across JOINs.
            if len(sources) == 1:
                src = sources[0]
                source_cols = [c["name"] for c in catalog.get(src, {}).get("columns", [])]
                expression_body = re.sub(r'\s+AS\s+"?[\w$]+"?\s*$', "", expr, flags=re.I)
                for col in source_cols:
                    if (src, col) not in resolved and re.search(rf'(?<![\w$])"?{re.escape(col)}"?(?![\w$])',
                                                               expression_body, re.I):
                        col_edges.append({"source": f"{src}.{col}", "target": f"{target}.{target_col}",
                                          "expression": expr.strip(), "file": path,
                                          "line": line_number(sql, tm.start()), "confidence": .85})
        group = re.search(r"\bGROUP\s+BY\b(.*?)(?=\bHAVING\b|\bORDER\s+BY\b|;|$)", stmt[local_target_end:], re.I | re.S)
        where = re.search(r"\bWHERE\b(.*?)(?=\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|;|$)", stmt[local_target_end:], re.I | re.S)
        operations.append({"type": "insert_select" if sql[tm.start():tm.start()+12].upper().startswith("INSERT") else "ctas",
                           "target": target, "sources": sources, "columns": col_edges,
                           "projections": projections, "metric_projections": metric_projections,
                           "group_by": split_top(group.group(1)) if group else [],
                           "where": where.group(1).strip() if where else None, "file": path,
                           "line": line_number(sql, tm.start())})
    # DELETE is a material operation in the common idempotent DELETE+INSERT
    # pattern. It has no source lineage, but retaining its predicate is
    # important for explaining replay windows and change impact.
    for dm in re.finditer(rf"\bDELETE\s+FROM\s+({IDENT})(?:\s+WHERE\s+(.*?))?(?=;|$)", sql, re.I | re.S):
        operations.append({"type": "delete", "target": clean_ident(dm.group(1)), "sources": [],
                           "columns": [], "projections": [], "metric_projections": [], "group_by": [],
                           "where": dm.group(2).strip() if dm.group(2) else None,
                           "file": path, "line": line_number(sql, dm.start())})
    operations.sort(key=lambda op: op["line"])
    return operations


def safe_extract(blob: bytes, dest: Path) -> list[dict]:
    if not blob or len(blob) > MAX_ZIP:
        raise HTTPException(413, "empty or oversized zip")
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        raise HTTPException(400, "invalid zip archive")
    files = []
    total = 0
    seen_paths: set[str] = set()
    entries = [info for info in zf.infolist() if not info.is_dir()]
    if len(entries) > MAX_ZIP_FILES:
        raise HTTPException(413, f"zip contains more than {MAX_ZIP_FILES} files")
    for info in entries:
        # ZIP names are specified with '/', but reject backslash paths too so
        # an archive cannot become unsafe when moved between operating systems.
        portable_name = info.filename.replace("\\", "/")
        rel = Path(portable_name)
        normalized = rel.as_posix()
        if (len(portable_name) > MAX_ARCHIVE_PATH or "\x00" in info.filename
                or rel.is_absolute() or ".." in rel.parts
                or re.match(r"^[A-Za-z]:", portable_name)
                or info.external_attr >> 16 & 0o170000 == 0o120000):
            raise HTTPException(400, f"unsafe zip entry: {info.filename}")
        if info.flag_bits & 0x1:
            raise HTTPException(400, f"encrypted zip entry is not supported: {info.filename}")
        if normalized in seen_paths:
            raise HTTPException(400, f"duplicate zip entry: {info.filename}")
        seen_paths.add(normalized)
        if info.file_size > MAX_ENTRY_BYTES:
            raise HTTPException(413, f"zip entry is too large: {info.filename}")
        total += info.file_size
        if total > MAX_EXPANDED_BYTES:
            raise HTTPException(413, "expanded archive too large")
        raw = zf.read(info)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append({"path": rel.as_posix(), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    if not files:
        raise HTTPException(400, "zip contains no files")
    return files


async def read_zip_body(request: Request) -> bytes:
    if "application/zip" not in request.headers.get("content-type", "").lower():
        raise HTTPException(415, "send ZIP bytes with Content-Type: application/zip")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_ZIP:
                raise HTTPException(413, "zip exceeds configured upload limit")
        except ValueError:
            raise HTTPException(400, "invalid Content-Length header")
    blob = await request.body()
    if not blob:
        raise HTTPException(413, "empty zip")
    if len(blob) > MAX_ZIP:
        raise HTTPException(413, "zip exceeds configured upload limit")
    return blob


def clean_filename(filename: str) -> str:
    value = filename.strip()
    if not value or len(value) > 255 or any(ord(ch) < 32 for ch in value):
        raise HTTPException(422, "filename must be 1-255 printable characters")
    # Only metadata is stored; dropping client paths also prevents leaking a
    # workstation directory into the import history.
    return Path(value.replace("\\", "/")).name


def classify_import_files(dest: Path, files: list[dict]) -> dict:
    """Classify an extracted package without persisting or analyzing a project."""
    classified: dict[str, list[str]] = {
        "sql": [], "ddl": [], "manifest": [], "jobs": [], "samples": [], "other": [],
    }
    errors: list[str] = []
    warnings: list[str] = []
    text_suffixes = {".sql", ".ddl", ".csv", ".yaml", ".yml", ".json"}
    for item in files:
        path = item["path"]
        rel = Path(path)
        suffix = rel.suffix.lower()
        lowered = path.lower()
        # Teams commonly use the .sql suffix for DDL. Directory placement is
        # the clearest signal in an import package and keeps the wizard counts
        # intuitive without treating DDL-only files as processing jobs.
        if suffix == ".sql" and "ddl" in {part.lower() for part in rel.parts[:-1]}:
            classified["ddl"].append(path)
        elif suffix == ".sql":
            classified["sql"].append(path)
        elif suffix == ".ddl":
            classified["ddl"].append(path)
        elif rel.name.lower() in {"manifest.yaml", "manifest.yml"}:
            classified["manifest"].append(path)
        elif rel.name.lower() == "jobs.csv":
            classified["jobs"].append(path)
        elif suffix == ".csv" and ("samples/" in f"/{lowered}" or "sample" in rel.stem.lower()):
            classified["samples"].append(path)
        else:
            classified["other"].append(path)
        if suffix in text_suffixes:
            try:
                (dest / rel).read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                errors.append(f"{path}: file is not UTF-8")

    # Some teams keep CREATE TABLE statements in .sql files. Count those as
    # both processing SQL and DDL evidence while preserving the file category.
    ddl_evidence = list(classified["ddl"])
    for path in classified["sql"]:
        try:
            text = (dest / path).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        if re.search(r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\b|\bALTER\s+TABLE\b", text, re.I):
            ddl_evidence.append(path)

    has_sql = bool(classified["sql"])
    has_ddl = bool(ddl_evidence)
    if not has_sql:
        errors.append("加工 SQL 是必需的；请在 ZIP 中加入至少一个 .sql 文件")
    if not has_ddl:
        warnings.append("未发现 DDL；仍可导入，但字段级血缘、SELECT * 展开和类型影响分析会不完整")
    if not classified["manifest"]:
        warnings.append("未提供 manifest.yaml（可选）；将使用默认 DWS 方言、时区和分层规则")
    if not classified["jobs"]:
        warnings.append("未提供 metadata/jobs.csv（可选）；作业顺序将根据 SQL 读写依赖推断")
    if not classified["samples"]:
        warnings.append("未提供 samples/*.csv（可选）；不会进行样例数据辅助分析")
    return {
        "files": classified,
        "counts": {key: len(value) for key, value in classified.items()},
        "has_sql": has_sql,
        "has_ddl": has_ddl,
        "has_manifest": bool(classified["manifest"]),
        "has_jobs": bool(classified["jobs"]),
        "has_samples": bool(classified["samples"]),
        "warnings": warnings,
        "errors": errors,
        "ready": not errors,
    }


def zip_response(blob: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(blob),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def blank_template_zip() -> bytes:
    buf = io.BytesIO()
    manifest = """project: my_data_pipeline
sql_dialect: gaussdb_dws
timezone: Asia/Shanghai
layer_rules:
  ods: "^ods_"
  dwd: "^dwd_"
  dws: "^dws_"
  ads: "^ads_"
"""
    jobs = "job_name,script_path,schedule,upstream_jobs,relation_status\n"
    readme = """DataFlow Inspector 导入模板

必需：sql/ 下至少一个加工 SQL。
强烈推荐：ddl/ 下提供涉及表的完整 DDL。
可选：manifest.yaml、metadata/jobs.csv、samples/*.csv。
请替换示例内容后，将整个目录重新压缩为 ZIP 上传。
"""
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dataflow-template/README.txt", readme)
        zf.writestr("dataflow-template/manifest.yaml", manifest)
        zf.writestr("dataflow-template/ddl/01_tables.ddl",
                    "CREATE TABLE ods.example_source (id BIGINT, event_time TIMESTAMP);\n")
        zf.writestr("dataflow-template/sql/01_example_job.sql",
                    "INSERT INTO dwd.example_target (id, event_time)\n"
                    "SELECT id, event_time FROM ods.example_source;\n")
        zf.writestr("dataflow-template/metadata/jobs.csv", jobs)
        zf.writestr("dataflow-template/samples/example_source.csv", "id,event_time\n")
    return buf.getvalue()


def analyze(dest: Path, files: list[dict]) -> dict:
    texts: dict[str, str] = {}
    diagnostics = []
    for f in files:
        if Path(f["path"]).suffix.lower() in {".sql", ".ddl", ".csv", ".yaml", ".yml"}:
            try:
                texts[f["path"]] = (dest / f["path"]).read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                diagnostics.append({"file": f["path"], "severity": "error", "message": "file is not UTF-8"})
    tables: list[dict] = []
    for path, text in texts.items():
        if Path(path).suffix.lower() in {".sql", ".ddl"}:
            tables.extend(parse_ddl(text, path))
    catalog = {t["name"]: t for t in tables}
    operations = []
    for path, text in texts.items():
        if Path(path).suffix.lower() == ".sql":
            operations.extend(parse_sql(text, path, catalog))
            if re.search(r"(?<!\.)\.\.\.(?!\.)", text):
                diagnostics.append({
                    "file": path, "severity": "warning", "code": "INCOMPLETE_SQL",
                    "message": "SQL contains an ellipsis placeholder; table lineage is retained, "
                               "but omitted columns are not guessed",
                })
    edges, column_edges = [], []
    for op in operations:
        for src in op["sources"]:
            edges.append({"source": src, "target": op["target"], "file": op["file"], "line": op["line"],
                          "operation": op["type"], "confidence": .95})
        column_edges.extend(op["columns"])
    jobs, job_edges = [], []
    for path, text in texts.items():
        if path.endswith("jobs.csv"):
            try:
                jobs = list(csv.DictReader(io.StringIO(text)))
                for j in jobs:
                    j["source"] = "declared"
                    j["script_path"] = j.get("script_path") or ""
                    j["targets"] = []
                    j["sources"] = []
                    for upstream in (j.get("upstream_jobs") or "").split("|"):
                        if upstream.strip():
                            job_edges.append({"source": upstream.strip(), "target": j.get("job_name"),
                                              "status": j.get("relation_status", "inferred")})
            except Exception as e:
                diagnostics.append({"file": path, "severity": "error", "message": f"jobs.csv: {e}"})
    metrics = []
    for op in operations:
        for i, expr in enumerate(op.get("metric_projections", op["projections"])):
            if re.search(r"\b(COUNT|SUM|AVG|MIN|MAX|PERCENTILE_DISC)\s*\(", expr, re.I):
                am = re.search(r"\s+AS\s+([\w$]+)\s*$", expr, re.I)
                name = am.group(1).lower() if am else f"metric_{i+1}"
                metrics.append({"name": name, "table": op["target"], "formula": expr.strip(),
                                "grain": op["group_by"], "filter": op["where"], "file": op["file"], "line": op["line"]})
    risks = []
    for path, text in texts.items():
        if re.search(r"\bSELECT\s+\*", text, re.I):
            risks.append({"code": "SELECT_STAR", "severity": "high", "file": path,
                          "message": "SELECT * may break when upstream columns change"})
    time_usage = []
    for op in operations:
        body = " ".join(op["projections"] + op["group_by"])
        fields = sorted(set(re.findall(r"\b([\w]*?(?:event|ingestion|stat|request)[\w]*time|stat_(?:minute|hour)|dt)\b", body, re.I)))
        if fields:
            time_usage.append({"target": op["target"], "fields": [x.lower() for x in fields], "file": op["file"]})
    minute = {x for u in time_usage if "minute" in u["target"] for x in u["fields"]}
    hour = {x for u in time_usage if "hour" in u["target"] for x in u["fields"]}
    if minute and hour and minute != hour:
        risks.append({"code": "TIME_SEMANTIC_DRIFT", "severity": "high",
                      "message": f"minute/hour aggregations use different time fields: {sorted(minute)} vs {sorted(hour)}"})
    filters_by_metric: dict[str, set[str]] = {}
    for m in metrics:
        filters_by_metric.setdefault(m["name"], set()).add(m["filter"] or "")
    for name, filters in filters_by_metric.items():
        if len(filters) > 1:
            risks.append({"code": "METRIC_FILTER_DRIFT", "severity": "medium",
                          "message": f"metric {name} has inconsistent filters"})
    # Missing catalog sources are retained as inferred external assets.
    known = set(catalog)
    for e in edges:
        for n in (e["source"], e["target"]):
            if n not in known:
                tables.append({"name": n, "columns": [], "ddl_file": None, "layer": layer_of(n), "inferred": True})
                known.add(n)
    # Make the stored analysis directly consumable by the product.  These
    # derived fields intentionally stay in the versioned analysis document so
    # every screen observes the same snapshot.
    upstreams: dict[str, set[str]] = {}
    downstreams: dict[str, set[str]] = {}
    for edge in edges:
        upstreams.setdefault(edge["target"], set()).add(edge["source"])
        downstreams.setdefault(edge["source"], set()).add(edge["target"])
    usage_by_target = {item["target"]: item for item in time_usage}
    writers: dict[str, list[dict]] = {}
    readers: dict[str, list[dict]] = {}
    for op in operations:
        evidence = {
            "operation": op["type"], "file": op["file"], "line": op["line"],
            "sources": op["sources"], "group_by": op["group_by"],
            "filter": op["where"],
        }
        writers.setdefault(op["target"], []).append(evidence)
        for source in op["sources"]:
            readers.setdefault(source, []).append({
                **evidence, "target": op["target"],
            })
    for table in tables:
        name = table["name"]
        table["upstreams"] = sorted(upstreams.get(name, set()))
        table["downstreams"] = sorted(downstreams.get(name, set()))
        table["upstream_count"] = len(table["upstreams"])
        table["downstream_count"] = len(table["downstreams"])
        table["write_evidence"] = writers.get(name, [])
        table["read_evidence"] = readers.get(name, [])
        write = table["write_evidence"][-1] if table["write_evidence"] else {}
        table["grain"] = write.get("group_by", [])
        fields = usage_by_target.get(name, {}).get("fields", [])
        column_names = {column["name"] for column in table.get("columns", [])}
        preferred = [
            column["name"] for column in table.get("columns", [])
            if column.get("role") in {
                "event_time", "stat_time", "partition_time", "ingestion_time"
            }
        ]
        table["time_fields"] = sorted(set(fields) | set(preferred))
        table["core_time_field"] = next(
            (field for field in fields if field in column_names),
            preferred[0] if preferred else (fields[0] if fields else None),
        )
        # Compatibility alias used by the asset-list UI.
        table["time_field"] = table["core_time_field"]

    lineage_nodes = [{
        "id": table["name"], "label": table["name"].split(".")[-1],
        "layer": table["layer"], "inferred": bool(table.get("inferred")),
        "upstream_count": table["upstream_count"],
        "downstream_count": table["downstream_count"],
    } for table in tables]

    # A jobs.csv is optional.  Without it, each writer operation is a useful
    # schedulable step and SQL read/write dependencies define its order.
    inferred_jobs = []
    writer_for_target: dict[str, str] = {}
    for index, op in enumerate(
        (op for op in operations if op["type"] != "delete"), 1
    ):
        job_name = f"sql_{index:03d}_{op['target'].replace('.', '_')}"
        inferred_jobs.append({
            "job_name": job_name, "script_path": op["file"], "schedule": "",
            "upstream_jobs": "", "relation_status": "inferred",
            "source": "inferred", "targets": [op["target"]],
            "sources": op["sources"], "line": op["line"],
        })
        writer_for_target[op["target"]] = job_name
    inferred_edges = []
    for job in inferred_jobs:
        for source in job["sources"]:
            upstream_job = writer_for_target.get(source)
            if upstream_job and upstream_job != job["job_name"]:
                inferred_edges.append({
                    "source": upstream_job, "target": job["job_name"],
                    "status": "inferred", "via_table": source,
                })
    if not jobs:
        jobs, job_edges = inferred_jobs, inferred_edges

    # The execution order is table-oriented, which is meaningful even when a
    # single SQL file contains multiple writers or jobs.csv is incomplete.
    targets = {op["target"] for op in operations if op["type"] != "delete"}
    indegree = {target: 0 for target in targets}
    target_adjacency: dict[str, set[str]] = {}
    operation_by_target = {
        op["target"]: op for op in operations if op["type"] != "delete"
    }
    for edge in edges:
        if edge["source"] in targets and edge["target"] in targets:
            if edge["target"] not in target_adjacency.setdefault(edge["source"], set()):
                target_adjacency[edge["source"]].add(edge["target"])
                indegree[edge["target"]] += 1
    ready_targets = sorted(target for target, degree in indegree.items() if degree == 0)
    ordered_targets: list[str] = []
    while ready_targets:
        target = ready_targets.pop(0)
        ordered_targets.append(target)
        for child in sorted(target_adjacency.get(target, set())):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready_targets.append(child)
                ready_targets.sort()
    ordered_targets.extend(sorted(targets - set(ordered_targets)))
    execution_order = [{
        "sequence": index, "target": target,
        "file": operation_by_target[target]["file"],
        "line": operation_by_target[target]["line"],
        "sources": operation_by_target[target]["sources"],
    } for index, target in enumerate(ordered_targets, 1)]
    return {"summary": {"tables": len(tables), "columns": sum(len(t["columns"]) for t in tables),
                        "table_edges": len(edges), "column_edges": len(column_edges),
                        "metrics": len(metrics), "risks": len(risks), "jobs": len(jobs)},
            "files": files, "tables": tables, "operations": operations, "table_lineage": edges,
            "column_lineage": column_edges, "lineage_nodes": lineage_nodes,
            "jobs": jobs, "job_lineage": job_edges, "execution_order": execution_order,
            "metrics": metrics, "time_usage": time_usage, "risks": risks, "diagnostics": diagnostics}


def reserve_import(project_id: int, sha256: str, filename: str,
                   source_import_id: int | None = None, attempts: int = 1) -> dict:
    """Allocate a version and persist processing state under one write lock."""
    ts = now()
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        exists = c.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone()
        if not exists:
            raise HTTPException(404, "project not found")
        version = c.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM imports WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
        cur = c.execute(
            """INSERT INTO imports(
                 project_id,version,sha256,filename,status,created_at,updated_at,
                 completed_at,error,attempts,source_import_id,analysis
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, version, sha256, filename, "processing", ts, ts,
             None, None, attempts, source_import_id, "{}"),
        )
        return {"id": cur.lastrowid, "project_id": project_id, "version": version}


def complete_import(iid: int, project_id: int, result: dict) -> dict:
    ts = now()
    with db() as c:
        c.execute(
            """UPDATE imports
               SET status='completed',analysis=?,error=NULL,error_detail=NULL,
                   updated_at=?,completed_at=?
               WHERE id=?""",
            (json.dumps(result, ensure_ascii=False), ts, ts, iid),
        )
        c.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, project_id))
        row = c.execute("SELECT * FROM imports WHERE id=?", (iid,)).fetchone()
    return dict(row)


def fail_import(iid: int, detail: dict, *, legacy_message: str | None = None) -> None:
    """Persist a public diagnostic; the full exception remains log-only."""
    safe_message = str(detail.get("safe_message") or "导入处理未完成")
    error_summary = legacy_message or safe_message
    with db() as c:
        c.execute(
            """UPDATE imports
               SET status='failed',error=?,error_detail=?,updated_at=?
               WHERE id=?""",
            (error_summary[:2000], json.dumps(detail, ensure_ascii=False), now(), iid),
        )


def import_result(row: dict, result: dict) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "version": row["version"],
        "status": row["status"],
        "sha256": row["sha256"],
        "filename": row["filename"],
        "summary": result["summary"],
        "diagnostics": result["diagnostics"],
        "attempts": row.get("attempts", 1),
        "completed_at": row.get("completed_at"),
    }


@app.post("/api/imports/preflight")
async def preflight_import(request: Request) -> dict:
    try:
        blob = await read_zip_body(request)
        with tempfile.TemporaryDirectory(prefix="dfi-preflight-") as temp:
            dest = Path(temp)
            files = safe_extract(blob, dest)
            result = classify_import_files(dest, files)
            if result["errors"]:
                result["error_details"] = [
                    {
                        **preflight_error_detail(
                            HTTPException(422, {
                                "code": "import_preflight_failed",
                                "message": "import package failed validation",
                            }),
                            validation={"errors": [message]},
                        ),
                        "validation_message": message,
                    }
                    for message in result["errors"]
                ]
            return result
    except HTTPException as exc:
        detail = preflight_error_detail(exc)
        logger.warning(
            "preflight rejected error_id=%s code=%s",
            detail["error_id"], detail["code"],
        )
        raise HTTPException(
            exc.status_code,
            {
                "code": detail["code"],
                "message": detail["safe_message"],
                "details": detail,
            },
        ) from exc


@app.get("/api/templates/blank")
def download_blank_template() -> StreamingResponse:
    return zip_response(blank_template_zip(), "dataflow-inspector-blank-template.zip")


@app.post("/api/projects/{pid}/imports", status_code=201)
async def upload_import(pid: int, request: Request, filename: str = Query("project.zip")) -> dict:
    project_or_404(pid)
    blob = await read_zip_body(request)
    filename = clean_filename(filename)
    digest = hashlib.sha256(blob).hexdigest()
    reserved = reserve_import(pid, digest, filename)
    iid, version = reserved["id"], reserved["version"]
    project_dir = IMPORT_DIR / str(pid)
    project_dir.mkdir(parents=True, exist_ok=True)
    dest = project_dir / str(version)
    staging = project_dir / f".{version}-{iid}.tmp"
    staging.mkdir()
    stage = "extraction"
    preflight: dict | None = None
    try:
        files = safe_extract(blob, staging)
        stage = "preflight"
        preflight = classify_import_files(staging, files)
        if not preflight["ready"]:
            raise HTTPException(422, {
                "code": "import_preflight_failed",
                "message": "import package failed validation",
                "details": preflight,
            })
        stage = "analysis"
        result = analyze(staging, files)
        stage = "persistence"
        (staging / "_source.zip").write_bytes(blob)
        os.replace(staging, dest)
        row = complete_import(iid, pid, result)
    except HTTPException as exc:
        shutil.rmtree(staging, ignore_errors=True)
        detail = preflight_error_detail(
            exc,
            validation=preflight if stage == "preflight" else None,
        )
        if preflight is not None and stage == "preflight":
            detail["validation"] = preflight
        legacy_message = (
            "import package failed validation"
            if detail["code"] == "import_preflight_failed"
            else None
        )
        fail_import(iid, detail, legacy_message=legacy_message)
        logger.warning(
            "import %s rejected error_id=%s stage=%s code=%s",
            iid, detail["error_id"], detail["stage"], detail["code"],
        )
        raise HTTPException(
            exc.status_code,
            {
                "code": detail["code"],
                "message": detail["safe_message"],
                "details": detail,
            },
        ) from exc
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        detail = unexpected_error_detail(stage, exc)
        fail_import(iid, detail)
        logger.exception(
            "import %s failed error_id=%s stage=%s",
            iid, detail["error_id"], stage,
        )
        raise HTTPException(500, {
            "code": detail["code"],
            "message": detail["safe_message"],
            "details": detail,
        }) from exc
    return import_result(row, result)


@app.post("/api/imports/{iid}/reanalyze")
def reanalyze_import(iid: int) -> dict:
    source = import_or_404(iid)
    if source["status"] != "completed":
        raise HTTPException(409, {
            "code": "source_import_not_completed",
            "message": "only a completed import can be reanalyzed",
        })
    source_dir = IMPORT_DIR / str(source["project_id"]) / str(source["version"])
    files = source["analysis"].get("files", [])
    if not source_dir.is_dir() or not files:
        raise HTTPException(409, {
            "code": "source_files_missing",
            "message": "stored source files are unavailable; upload the package again",
        })

    reserved = reserve_import(
        source["project_id"], source["sha256"], source["filename"],
        source_import_id=iid, attempts=int(source.get("attempts") or 1) + 1,
    )
    new_iid, version = reserved["id"], reserved["version"]
    project_dir = IMPORT_DIR / str(source["project_id"])
    dest = project_dir / str(version)
    staging = project_dir / f".{version}-{new_iid}.tmp"
    stage = "reanalysis"
    try:
        shutil.copytree(source_dir, staging)
        for item in files:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts or not (staging / relative).is_file():
                raise HTTPException(409, {
                    "code": "source_files_missing",
                    "message": f"stored source file is unavailable: {item['path']}",
                })
        stage = "analysis"
        result = analyze(staging, files)
        stage = "persistence"
        os.replace(staging, dest)
        row = complete_import(new_iid, source["project_id"], result)
    except HTTPException as exc:
        shutil.rmtree(staging, ignore_errors=True)
        detail = new_error_detail(
            stage="reanalysis",
            code="source_files_missing",
            exception_type="SourceValidationError",
            safe_message="重新分析所需的源文件不可用",
            suggestion="重新上传原始项目 ZIP 后再执行分析。",
        )
        fail_import(new_iid, detail)
        logger.warning(
            "reanalysis %s rejected error_id=%s code=%s",
            new_iid, detail["error_id"], detail["code"],
        )
        raise HTTPException(
            exc.status_code,
            {
                "code": detail["code"],
                "message": detail["safe_message"],
                "details": detail,
            },
        ) from exc
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        detail = unexpected_error_detail(stage, exc)
        fail_import(new_iid, detail)
        logger.exception(
            "reanalysis %s from import %s failed error_id=%s stage=%s",
            new_iid, iid, detail["error_id"], stage,
        )
        raise HTTPException(500, {
            "code": detail["code"],
            "message": detail["safe_message"],
            "details": detail,
        }) from exc
    return import_result(row, result)


@app.get("/api/projects/{pid}/imports")
def list_imports(pid: int) -> list[dict]:
    project_or_404(pid)
    with db() as c:
        rows = c.execute(
            """SELECT id,project_id,version,sha256,filename,status,created_at,
                      updated_at,completed_at,error,error_detail,attempts,source_import_id
               FROM imports WHERE project_id=? ORDER BY version DESC""",
            (pid,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["error_detail"] = decode_error_detail(item.get("error_detail"))
        result.append(item)
    return result


@app.get("/api/imports/{iid}")
def get_import(iid: int) -> dict:
    r = import_or_404(iid)
    a = r.pop("analysis")
    r["summary"] = a.get("summary")
    r["diagnostics"] = a.get("diagnostics", [])
    return r


@app.get("/api/projects/{pid}/catalog")
def catalog(pid: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    tables = a["tables"]
    if layer:
        tables = [t for t in tables if t["layer"].lower() == layer.lower()]
    if search:
        q = search.lower()
        tables = [t for t in tables if q in t["name"] or any(q in c["name"] for c in t["columns"])]
    return {"version": meta["version"], "tables": tables}


@app.get("/api/projects/{pid}/tables")
def tables_alias(pid: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    """Frontend-friendly alias for the catalog endpoint."""
    return catalog(pid, version, layer, search)


@app.get("/api/projects/{pid}/tables/{table_name:path}")
def table_detail(pid: int, table_name: str, version: int | None = None) -> dict:
    """Return one navigable asset with schema and traceable SQL evidence."""
    a, meta = latest_analysis(pid, version)
    normalized = clean_ident(table_name)
    table = next((item for item in a["tables"] if item["name"] == normalized), None)
    if not table:
        raise HTTPException(404, "table not found")
    table_edges = [
        edge for edge in a["table_lineage"]
        if edge["source"] == normalized or edge["target"] == normalized
    ]
    column_edges = [
        edge for edge in a["column_lineage"]
        if edge["source"].startswith(normalized + ".")
        or edge["target"].startswith(normalized + ".")
    ]
    produced_metrics = [metric for metric in a["metrics"] if metric["table"] == normalized]
    return {
        "version": meta["version"],
        "table": table,
        "columns": table.get("columns", []),
        "ddl_evidence": ({
            "file": table["ddl_file"], "object": normalized,
            "column_count": len(table.get("columns", [])),
        } if table.get("ddl_file") else None),
        "sql_evidence": table.get("write_evidence", []),
        "upstreams": table.get("upstreams", []),
        "downstreams": table.get("downstreams", []),
        "table_lineage": table_edges,
        "column_lineage": column_edges,
        "metrics": produced_metrics,
    }


@app.get("/api/projects/{pid}/lineage")
def lineage(pid: int, version: int | None = None, level: str = "table") -> dict:
    a, meta = latest_analysis(pid, version)
    if level not in {"table", "column"}:
        raise HTTPException(422, "level must be table or column")
    return {"version": meta["version"], "level": level,
            "nodes": a.get("lineage_nodes", []),
            "edges": a["table_lineage" if level == "table" else "column_lineage"]}


@app.get("/api/projects/{pid}/workflows")
def workflows(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "jobs": a["jobs"], "edges": a["job_lineage"],
            "execution_order": a.get("execution_order", [])}


@app.get("/api/projects/{pid}/metrics")
def metrics(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "metrics": a["metrics"], "time_usage": a["time_usage"],
            "risks": a["risks"]}


@app.get("/api/projects/{pid}/quality-findings")
def quality_findings(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "findings": a["risks"], "risks": a["risks"]}


@app.post("/api/projects/{pid}/impact-analysis")
def impact(pid: int, change: ChangeIn, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    obj = change.object.lower()
    table_names = {item["name"] for item in a["tables"]}
    table = next(
        (name for name in sorted(table_names, key=len, reverse=True)
         if obj == name or obj.startswith(name + ".")),
        obj,
    )
    changed_column = obj[len(table) + 1:] if obj.startswith(table + ".") else None
    adjacency: dict[str, list[str]] = {}
    for e in a["table_lineage"]:
        adjacency.setdefault(e["source"], []).append(e["target"])
    queue, seen, paths = [(table, 0)], {table}, []
    distance = {table: 0}
    while queue:
        cur, current_distance = queue.pop(0)
        for nxt in sorted(set(adjacency.get(cur, []))):
            edge = next((item for item in a["table_lineage"]
                         if item["source"] == cur and item["target"] == nxt), {})
            paths.append({
                "source": cur, "target": nxt, "file": edge.get("file"),
                "line": edge.get("line"), "distance": current_distance + 1,
            })
            if nxt not in seen:
                seen.add(nxt)
                distance[nxt] = current_distance + 1
                queue.append((nxt, current_distance + 1))
    direct = sorted(set(adjacency.get(table, [])))
    scripts = sorted({e["file"] for e in a["table_lineage"]
                      if e["source"] in seen or e["target"] in seen})
    metric_names = sorted({m["name"] for m in a["metrics"] if m["table"] in seen})
    ads = sorted(x for x in seen if layer_of(x) == "ADS")
    severity = "high" if change.change_type in {"delete_column", "rename_column", "group_by_change", "filter_change"} or len(seen) > 5 else "medium" if direct else "low"
    warnings = [r for r in a["risks"] if not r.get("file") or r.get("file") in scripts]
    affected = []
    for name in sorted(seen - {table}, key=lambda item: (distance.get(item, 999), item)):
        evidence = [{
            "file": edge.get("file"), "line": edge.get("line"),
            "source": edge["source"], "target": edge["target"],
        } for edge in a["table_lineage"]
            if edge["target"] == name and edge["source"] in seen]
        affected.append({
            "object": name, "type": "table", "layer": layer_of(name),
            "distance": distance.get(name), "direct": distance.get(name) == 1,
            "evidence": evidence,
        })

    # For a column change, follow only proven field mappings.  Table impacts
    # remain in the response because SELECT *, filters and joins can still
    # make an unproven field dependency relevant.
    affected_columns = []
    if changed_column:
        column_queue = [f"{table}.{changed_column}"]
        column_seen = set(column_queue)
        column_adjacency: dict[str, list[dict]] = {}
        for edge in a["column_lineage"]:
            column_adjacency.setdefault(edge["source"], []).append(edge)
        while column_queue:
            current = column_queue.pop(0)
            for edge in column_adjacency.get(current, []):
                target = edge["target"]
                if target not in column_seen:
                    column_seen.add(target)
                    column_queue.append(target)
                    affected_columns.append({
                        "object": target, "type": "column",
                        "layer": layer_of(target.rsplit(".", 1)[0]),
                        "direct": current == f"{table}.{changed_column}",
                        "evidence": [{
                            "file": edge.get("file"), "line": edge.get("line"),
                            "expression": edge.get("expression"),
                        }],
                    })
    modification_order = [{
        "sequence": index, "object": item["object"], "type": item["type"],
        "action": "先更新DDL与写入SQL，再按血缘顺序更新下游加工",
        "evidence": item["evidence"],
    } for index, item in enumerate(affected_columns + affected, 1)]
    return {"version": meta["version"], "change": change.model_dump(), "risk": severity,
            "direct_impacts": direct, "transitive_impacts": sorted(seen - {table}),
            "paths": paths, "scripts": scripts, "metrics": metric_names, "ads_tables": ads,
            "affected": affected_columns + affected,
            "modification_order": modification_order,
            "warnings": warnings, "recommendations": [
                "update target DDL and writer SQL first", "update downstream transformations in topological order",
                "run schema and metric regression checks", "backfill affected partitions when historical semantics change"]}


@app.get("/api/projects/{pid}/compare")
def compare(pid: int, left: int, right: int) -> dict:
    a, lm = latest_analysis(pid, left)
    b, rm = latest_analysis(pid, right)
    at, bt = {x["name"]: x for x in a["tables"]}, {x["name"]: x for x in b["tables"]}
    changed = []
    for n in sorted(set(at) & set(bt)):
        ac = {(c["name"], c["type"]) for c in at[n]["columns"]}
        bc = {(c["name"], c["type"]) for c in bt[n]["columns"]}
        if ac != bc:
            changed.append({"table": n, "added_columns": sorted(bc - ac), "removed_columns": sorted(ac - bc)})
    edgekey = lambda x: (x["source"], x["target"])
    ae, be = {edgekey(x) for x in a["table_lineage"]}, {edgekey(x) for x in b["table_lineage"]}
    columnkey = lambda x: (x["source"], x["target"], x.get("expression", ""))
    ace, bce = {columnkey(x) for x in a["column_lineage"]}, {columnkey(x) for x in b["column_lineage"]}
    metric_key = lambda x: (x["table"], x["name"], x["formula"], tuple(x.get("grain", [])), x.get("filter") or "")
    am, bm = {metric_key(x) for x in a["metrics"]}, {metric_key(x) for x in b["metrics"]}
    operation_key = lambda x: (x["target"], tuple(x["sources"]), x["type"], tuple(x.get("group_by", [])), x.get("where") or "")
    ao, bo = {operation_key(x) for x in a["operations"]}, {operation_key(x) for x in b["operations"]}
    result = {"left": lm["version"], "right": rm["version"], "tables": {
        "added": sorted(set(bt) - set(at)), "removed": sorted(set(at) - set(bt)), "changed": changed},
        "lineage": {"added": sorted(be - ae), "removed": sorted(ae - be)},
        "column_lineage": {"added": sorted(bce - ace), "removed": sorted(ace - bce)},
        "metrics": {"added": sorted(bm - am), "removed": sorted(am - bm)},
        "operations": {"added": sorted(bo - ao), "removed": sorted(ao - bo)},
        "risks": {
            "left": a["risks"], "right": b["risks"],
            "added_codes": sorted({x["code"] for x in b["risks"]} - {x["code"] for x in a["risks"]}),
            "removed_codes": sorted({x["code"] for x in a["risks"]} - {x["code"] for x in b["risks"]}),
        }}
    result["summary"] = {
        "table_changes": len(result["tables"]["added"]) + len(result["tables"]["removed"]) + len(changed),
        "table_lineage_changes": len(result["lineage"]["added"]) + len(result["lineage"]["removed"]),
        "column_lineage_changes": len(result["column_lineage"]["added"]) + len(result["column_lineage"]["removed"]),
        "metric_changes": len(result["metrics"]["added"]) + len(result["metrics"]["removed"]),
        "operation_changes": len(result["operations"]["added"]) + len(result["operations"]["removed"]),
    }
    return result


@app.post("/api/projects/{pid}/assistant/query")
def assistant(pid: int, payload: dict = Body(...), version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(422, "question is required")
    q = question.lower()
    evidence, lines = [], []
    for m in a["metrics"]:
        if m["name"].lower() in q:
            lines.append(f"{m['name']} 在 {m['table']} 中计算，公式为 {m['formula']}。")
            lines.append(f"聚合粒度：{', '.join(m['grain']) or '未识别'}；过滤：{m['filter'] or '无'}。")
            evidence.append({"file": m["file"], "line": m["line"], "object": f"{m['table']}.{m['name']}"})
    for t in a["tables"]:
        if t["name"] in q:
            ups = [e["source"] for e in a["table_lineage"] if e["target"] == t["name"]]
            downs = [e["target"] for e in a["table_lineage"] if e["source"] == t["name"]]
            lines.append(f"{t['name']} 属于 {t['layer']} 层；直接上游：{', '.join(ups) or '无'}；直接下游：{', '.join(downs) or '无'}。")
            evidence.extend({"file": e["file"], "line": e["line"], "object": t["name"]}
                            for e in a["table_lineage"] if e["target"] == t["name"] or e["source"] == t["name"])
    if any(x in q for x in ("时间字段", "时间关系", "时间口径", "核心时间")):
        time_tables = [table for table in a["tables"] if table.get("time_fields")]
        for table in time_tables:
            fields = table["time_fields"]
            lines.append(
                f"{table['name']} 的时间字段：{', '.join(fields)}；"
                f"核心时间字段：{table.get('core_time_field') or '待确认'}。"
            )
            write = (table.get("write_evidence") or [{}])[0]
            evidence.append({
                "file": write.get("file") or table.get("ddl_file"),
                "line": write.get("line"),
                "object": table["name"],
                "fields": fields,
            })
        for usage in a.get("time_usage", []):
            lines.append(
                f"{usage['target']} 的加工表达式使用时间字段："
                f"{', '.join(usage['fields'])}。"
            )
        if not time_tables:
            lines.append("当前版本未从 DDL 或加工表达式中识别到时间字段。")
    if any(x in q for x in ("风险", "问题", "异常")):
        lines.extend(f"[{r['severity']}] {r['message']}" for r in a["risks"])
        evidence.extend({"file": r.get("file"), "line": None, "object": r["code"]} for r in a["risks"])
    if not lines:
        lines.append("未找到足够的结构化证据。可询问具体表名、指标名或“有哪些风险”。")
    return {"version": meta["version"], "question": question, "answer": "\n".join(lines),
            "evidence": evidence[:20], "confidence": "high" if evidence else "low"}
