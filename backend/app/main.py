from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
try:
    import sqlite3
except ModuleNotFoundError:  # Some minimal Python images omit stdlib _sqlite3.
    import pysqlite3 as sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DFI_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("DFI_DB_PATH", DATA_DIR / "dataflow.db"))
IMPORT_DIR = Path(os.getenv("DFI_IMPORT_DIR", DATA_DIR / "imports"))
MAX_ZIP = int(os.getenv("DFI_MAX_ZIP_BYTES", 50 * 1024 * 1024))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS projects(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          dialect TEXT NOT NULL DEFAULT 'gaussdb_dws', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS imports(
          id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          version INTEGER NOT NULL, sha256 TEXT NOT NULL, filename TEXT NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL, analysis TEXT NOT NULL,
          UNIQUE(project_id, version));
        """)


app = FastAPI(title="DataFlow Inspector API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    # Development UI may use any available local port, except Loomi's
    # production backend on 8080.  Do not allow LAN names/IPs or arbitrary
    # web origins.
    allow_origin_regex=r"^https?://(?:127\.0\.0\.1|localhost):(?!8080$)\d{1,5}$",
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    dialect: str = "gaussdb_dws"


class ChangeIn(BaseModel):
    object: str
    change_type: str
    before: str | None = None
    after: str | None = None


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
    d["analysis"] = json.loads(d["analysis"])
    return d


def latest_analysis(pid: int, version: int | None = None) -> tuple[dict, dict]:
    project_or_404(pid)
    sql = "SELECT * FROM imports WHERE project_id=?"
    args: list[Any] = [pid]
    if version is not None:
        sql += " AND version=?"
        args.append(version)
    sql += " ORDER BY version DESC LIMIT 1"
    with db() as c:
        r = c.execute(sql, args).fetchone()
    if not r:
        raise HTTPException(404, "project has no analyzed import")
    meta = dict(r)
    return json.loads(meta.pop("analysis")), meta


@app.get("/api/health")
def health() -> dict:
    with db() as c:
        c.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "ok", "version": app.version}


@app.post("/api/projects", status_code=201)
def create_project(p: ProjectIn) -> dict:
    if not p.name.strip():
        raise HTTPException(422, "name is required")
    ts = now()
    with db() as c:
        cur = c.execute("INSERT INTO projects(name,description,dialect,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (p.name.strip(), p.description, p.dialect, ts, ts))
        pid = cur.lastrowid
    return project_or_404(pid)


@app.get("/api/projects")
def list_projects() -> list[dict]:
    with db() as c:
        rows = c.execute("""SELECT p.*,COUNT(i.id) import_count,MAX(i.version) latest_version
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
    with db() as c:
        c.execute("DELETE FROM projects WHERE id=?", (pid,))
    shutil.rmtree(IMPORT_DIR / str(pid), ignore_errors=True)
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
                aliases[alias.lower()] = expanded[0]
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
    for info in zf.infolist():
        # ZIP names are specified with '/', but reject backslash paths too so
        # an archive cannot become unsafe when moved between operating systems.
        portable_name = info.filename.replace("\\", "/")
        rel = Path(portable_name)
        if info.is_dir():
            continue
        normalized = rel.as_posix()
        if ("\x00" in info.filename or rel.is_absolute() or ".." in rel.parts
                or re.match(r"^[A-Za-z]:", portable_name)
                or info.external_attr >> 16 & 0o170000 == 0o120000):
            raise HTTPException(400, f"unsafe zip entry: {info.filename}")
        if normalized in seen_paths:
            raise HTTPException(400, f"duplicate zip entry: {info.filename}")
        seen_paths.add(normalized)
        total += info.file_size
        if total > MAX_ZIP * 5:
            raise HTTPException(413, "expanded archive too large")
        raw = zf.read(info)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append({"path": rel.as_posix(), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    if not files:
        raise HTTPException(400, "zip contains no files")
    return files


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
    return {"summary": {"tables": len(tables), "columns": sum(len(t["columns"]) for t in tables),
                        "table_edges": len(edges), "column_edges": len(column_edges),
                        "metrics": len(metrics), "risks": len(risks), "jobs": len(jobs)},
            "files": files, "tables": tables, "operations": operations, "table_lineage": edges,
            "column_lineage": column_edges, "jobs": jobs, "job_lineage": job_edges,
            "metrics": metrics, "time_usage": time_usage, "risks": risks, "diagnostics": diagnostics}


@app.post("/api/imports/preflight")
async def preflight_import(request: Request) -> dict:
    if "application/zip" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "send ZIP bytes with Content-Type: application/zip")
    blob = await request.body()
    with tempfile.TemporaryDirectory(prefix="dfi-preflight-") as temp:
        dest = Path(temp)
        files = safe_extract(blob, dest)
        return classify_import_files(dest, files)


@app.get("/api/templates/blank")
def download_blank_template() -> StreamingResponse:
    return zip_response(blank_template_zip(), "dataflow-inspector-blank-template.zip")


@app.get("/api/templates/demo")
def download_demo_template() -> StreamingResponse:
    # Resolve relative to this module, never the server's current directory.
    candidates = [
        ROOT.parent / "examples" / "token-traffic-demo.zip",
        ROOT.parent / "examples" / "desensitized-pipeline-project.zip",
    ]
    demo = next((path for path in candidates if path.is_file() and path.stat().st_size), None)
    if demo is None:
        # A deployable backend package may intentionally omit repository
        # examples. Return the safe built-in package instead of a cwd-dependent
        # 404 so the import wizard remains useful.
        return zip_response(blank_template_zip(), "dataflow-inspector-demo.zip")
    return zip_response(demo.read_bytes(), "dataflow-inspector-demo.zip")


@app.post("/api/projects/{pid}/imports", status_code=201)
async def upload_import(pid: int, request: Request, filename: str = Query("project.zip")) -> dict:
    project_or_404(pid)
    if "application/zip" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "send ZIP bytes with Content-Type: application/zip")
    blob = await request.body()
    digest = hashlib.sha256(blob).hexdigest()
    with db() as c:
        version = c.execute("SELECT COALESCE(MAX(version),0)+1 FROM imports WHERE project_id=?", (pid,)).fetchone()[0]
    dest = IMPORT_DIR / str(pid) / str(version)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    try:
        files = safe_extract(blob, dest)
        result = analyze(dest, files)
        with db() as c:
            cur = c.execute("""INSERT INTO imports(project_id,version,sha256,filename,status,created_at,analysis)
                             VALUES(?,?,?,?,?,?,?)""",
                            (pid, version, digest, filename, "completed", now(), json.dumps(result, ensure_ascii=False)))
            iid = cur.lastrowid
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return {"id": iid, "project_id": pid, "version": version, "status": "completed",
            "sha256": digest, "summary": result["summary"]}


@app.get("/api/projects/{pid}/imports")
def list_imports(pid: int) -> list[dict]:
    project_or_404(pid)
    with db() as c:
        rows = c.execute("SELECT id,project_id,version,sha256,filename,status,created_at FROM imports WHERE project_id=? ORDER BY version DESC", (pid,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/imports/{iid}")
def get_import(iid: int) -> dict:
    r = import_or_404(iid)
    a = r.pop("analysis")
    r["summary"], r["diagnostics"] = a["summary"], a["diagnostics"]
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


@app.get("/api/projects/{pid}/lineage")
def lineage(pid: int, version: int | None = None, level: str = "table") -> dict:
    a, meta = latest_analysis(pid, version)
    if level not in {"table", "column"}:
        raise HTTPException(422, "level must be table or column")
    return {"version": meta["version"], "level": level,
            "edges": a["table_lineage" if level == "table" else "column_lineage"]}


@app.get("/api/projects/{pid}/workflows")
def workflows(pid: int, version: int | None = None) -> dict:
    a, meta = latest_analysis(pid, version)
    return {"version": meta["version"], "jobs": a["jobs"], "edges": a["job_lineage"]}


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
    table = obj.rsplit(".", 1)[0] if obj.count(".") >= 2 else obj
    adjacency: dict[str, list[str]] = {}
    for e in a["table_lineage"]:
        adjacency.setdefault(e["source"], []).append(e["target"])
    queue, seen, paths = [table], {table}, []
    while queue:
        cur = queue.pop(0)
        for nxt in adjacency.get(cur, []):
            paths.append({"source": cur, "target": nxt})
            if nxt not in seen:
                seen.add(nxt); queue.append(nxt)
    direct = adjacency.get(table, [])
    scripts = sorted({e["file"] for e in a["table_lineage"] if e["source"] in seen or e["target"] in seen})
    metric_names = sorted({m["name"] for m in a["metrics"] if m["table"] in seen})
    ads = sorted(x for x in seen if layer_of(x) == "ADS")
    severity = "high" if change.change_type in {"delete_column", "rename_column", "group_by_change", "filter_change"} or len(seen) > 5 else "medium" if direct else "low"
    warnings = [r for r in a["risks"] if not r.get("file") or r.get("file") in scripts]
    return {"version": meta["version"], "change": change.model_dump(), "risk": severity,
            "direct_impacts": direct, "transitive_impacts": sorted(seen - {table}),
            "paths": paths, "scripts": scripts, "metrics": metric_names, "ads_tables": ads,
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
    return {"left": lm["version"], "right": rm["version"], "tables": {
        "added": sorted(set(bt) - set(at)), "removed": sorted(set(at) - set(bt)), "changed": changed},
        "lineage": {"added": sorted(be - ae), "removed": sorted(ae - be)}}


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
    if any(x in q for x in ("风险", "问题", "异常")):
        lines.extend(f"[{r['severity']}] {r['message']}" for r in a["risks"])
        evidence.extend({"file": r.get("file"), "line": None, "object": r["code"]} for r in a["risks"])
    if not lines:
        lines.append("未找到足够的结构化证据。可询问具体表名、指标名或“有哪些风险”。")
    return {"version": meta["version"], "question": question, "answer": "\n".join(lines),
            "evidence": evidence[:20], "confidence": "high" if evidence else "low"}


# ============================================================
#  单表导入 + 冲突检测 + 自动融合
# ============================================================

from app.parser.single_table import (
    import_single_table,
    merge_table_into_analysis,
    infer_relationships,
    SingleTableImportResult,
)


class SingleTableImportRequest(BaseModel):
    ddl: str
    etl_sql: str = ""                  # 可选：加工 SQL，提供时精准解析血缘
    conflict_strategy: str = "check"   # "check" | "replace" | "keep" | "merge"


@app.post("/api/projects/{pid}/tables/import")
def import_single_table_endpoint(pid: int, req: SingleTableImportRequest) -> dict:
    """
    导入单条 CREATE TABLE DDL + 可选 ETL SQL。

    三级模式：
    - DDL + ETL  → 精准解析入库 (action: imported_precise)
    - 仅 DDL      → 返回推断供用户判断 (action: orphan_pending)，或直接作为孤立表入库 (conflict_strategy != "check")
    - 冲突        → 返回冲突详情让用户选择策略 (action: conflict)
    """
    project_or_404(pid)

    # 获取最新分析数据
    existing = None
    latest_version = 0
    with db() as c:
        row = c.execute(
            "SELECT * FROM imports WHERE project_id=? ORDER BY version DESC LIMIT 1",
            (pid,),
        ).fetchone()
    if row:
        existing = json.loads(dict(row)["analysis"])
        latest_version = row["version"]

    result = import_single_table(
        ddl_text=req.ddl,
        project_id=pid,
        existing_analysis=existing,
        conflict_strategy=req.conflict_strategy,
        etl_sql=req.etl_sql if req.etl_sql else None,
    )

    # 推断结果格式化
    def _relations_out():
        return [
            {
                "index": i,
                "source_table": r.source_table,
                "target_table": r.target_table,
                "matched_columns_count": len(r.matched_columns),
                "matched_columns": r.matched_columns[:20],
                "confidence": r.confidence,
                "inference_method": r.inference_method,
            }
            for i, r in enumerate(result.inferred_relations)
        ]

    # ↓ 三种不需要写库的返回场景 ↓

    # A. 冲突
    if result.action == "conflict":
        return {
            "table_name": result.table_name,
            "action": result.action,
            "conflict": result.conflict.__dict__ if result.conflict else None,
            "table_lineage": result.table_lineage,
            "column_lineage": result.column_lineage,
            "inferred_relations": _relations_out(),
            "message": result.message,
            "requires_decision": True,
            "available_strategies": ["replace", "keep", "merge"],
        }

    # B. 仅 DDL、check 模式 → 返回推断给用户判断
    if result.action == "orphan_pending":
        return {
            "table_name": result.table_name,
            "action": result.action,
            "table": {
                "name": result.table_name,
                "layer": result.table_info["layer"] if result.table_info else "?",
                "columns": [{"name": c["name"], "type": c["type"]} for c in (result.table_info["columns"] if result.table_info else [])],
            },
            "inferred_relations": _relations_out(),
            "message": result.message,
            "requires_decision": True,
            "options": [
                "accept_orphan: 作为孤立表接受（无血缘）",
                "confirm_inference: 选定一个推断关系确认入库",
                "provide_etl: 补充 ETL SQL 后重新导入",
            ],
        }

    # C. DDL + ETL check 模式 → 解析完成预览，等用户确认
    if result.action == "ready_to_import_precise":
        # 检查上游表是否已在数据字典中
        existing_cat = {}
        if existing:
            for t in existing.get("tables", []):
                existing_cat[t["name"]] = t
        etl_sources = {e["source"] for e in result.table_lineage}
        missing_upstream = sorted(s for s in etl_sources
                                if s not in existing_cat and s != result.table_name)
        return {
            "table_name": result.table_name,
            "action": result.action,
            "table": {
                "name": result.table_name,
                "layer": result.table_info["layer"] if result.table_info else "?",
                "columns": len(result.table_info["columns"]) if result.table_info else 0,
            },
            "table_lineage": result.table_lineage,
            "column_lineage_count": len(result.column_lineage),
            "column_lineage": result.column_lineage[:20],
            "missing_upstream_tables": missing_upstream,
            "message": result.message,
            "requires_decision": True,
        }

    # ↓ 入库场景 ↓

    # 构建或更新分析数据
    if existing is None:
        new_analysis = {
            "summary": {
                "tables": 1,
                "columns": len(result.table_info["columns"]) if result.table_info else 0,
                "table_edges": len(result.table_lineage),
                "column_edges": len(result.column_lineage),
                "metrics": 0, "risks": 0, "jobs": 0,
            },
            "files": [],
            "tables": [result.table_info] if result.table_info else [],
            "operations": result.operations,
            "table_lineage": result.table_lineage,
            "column_lineage": result.column_lineage,
            "jobs": [], "job_lineage": [],
            "metrics": [], "time_usage": [], "risks": [], "diagnostics": [],
        }
    else:
        new_analysis = merge_table_into_analysis(
            existing, result.table_info,
            result.table_lineage, result.column_lineage,
            result.inferred_relations, result.operations)

    # 写回
    seed = (req.ddl + (req.etl_sql or "")).encode()
    digest = hashlib.sha256(seed).hexdigest()
    new_version = latest_version + 1
    ts = now()
    with db() as c:
        c.execute(
            """INSERT INTO imports(project_id,version,sha256,filename,status,created_at,analysis)
               VALUES(?,?,?,?,?,?,?)""",
            (pid, new_version, digest, f"single-import:{result.table_name}", "completed",
             ts, json.dumps(new_analysis, ensure_ascii=False)),
        )

    lineage_sources = {e.get("parse_source", "?") for e in
                      (result.table_lineage + result.column_lineage)}
    return {
        "table_name": result.table_name,
        "action": result.action,
        "conflict": result.conflict.__dict__ if result.conflict else None,
        "lineage_source": "parsed_from_sql" if "sqlglot_ast" in lineage_sources else
                         "inferred" if "inferred" in lineage_sources else
                         "none",
        "table_lineage": result.table_lineage,
        "column_lineage": result.column_lineage,
        "inferred_relations": _relations_out(),
        "version": new_version,
        "summary": new_analysis["summary"],
        "message": result.message,
    }


@app.get("/api/projects/{pid}/tables/{table_name:path}/relationships")
def get_table_relationships(pid: int, table_name: str, version: int | None = None) -> dict:
    """查询指定表在现有数据字典中的上游/下游关系和同名字段匹配。"""
    a, meta = latest_analysis(pid, version)

    # 找到目标表
    target_table = None
    for t in a["tables"]:
        if t["name"].lower() == table_name.lower():
            target_table = t
            break

    if not target_table:
        raise HTTPException(404, f"table {table_name} not found in project {pid}")

    # 上游表
    upstream = [e["source"] for e in a["table_lineage"] if e["target"].lower() == table_name.lower()]

    # 下游表
    downstream = [e["target"] for e in a["table_lineage"] if e["source"].lower() == table_name.lower()]

    # 同名字段匹配（JOIN 键）
    target_cols = {c["name"].lower(): c for c in target_table.get("columns", [])}
    join_matches = []
    for t in a["tables"]:
        if t["name"] == table_name:
            continue
        for c in t.get("columns", []):
            cname = c["name"].lower()
            if cname in target_cols and cname.endswith("_id"):
                join_matches.append({
                    "table": t["name"],
                    "column": cname,
                    "type": c.get("type", ""),
                })

    return {
        "version": meta["version"],
        "table": table_name,
        "layer": target_table.get("layer"),
        "columns": len(target_table.get("columns", [])),
        "upstream_tables": upstream,
        "downstream_tables": downstream,
        "join_key_matches": join_matches,
    }


@app.post("/api/projects/{pid}/tables/preview")
def preview_table_ddl(pid: int, payload: dict = Body(...)) -> dict:
    """预处理单条 DDL，返回解析结果和冲突/关系预览（不写库）。"""
    ddl_text = str(payload.get("ddl", "")).strip()
    if not ddl_text:
        raise HTTPException(422, "ddl is required")

    from app.parser.ddl_parser import parse_ddl as ast_parse_ddl

    tables = ast_parse_ddl(ddl_text, "__preview__")
    if not tables:
        raise HTTPException(400, "DDL 解析失败：未识别到有效的 CREATE TABLE 语句")

    table_info = tables[0]

    # 获取现有 catalog
    existing_catalog = {}
    with db() as c:
        row = c.execute(
            "SELECT * FROM imports WHERE project_id=? ORDER BY version DESC LIMIT 1",
            (pid,),
        ).fetchone()
    if row:
        analysis = json.loads(dict(row)["analysis"])
        for t in analysis.get("tables", []):
            existing_catalog[t["name"]] = t

    # 冲突检测
    from app.parser.single_table import check_conflict
    conflict = check_conflict(table_info["name"], table_info["columns"], existing_catalog)

    # 关系推断
    relations = infer_relationships(
        table_info["name"], table_info["columns"], existing_catalog)

    return {
        "table": {
            "name": table_info["name"],
            "layer": table_info["layer"],
            "columns": [{"name": c["name"], "type": c["type"],
                        "role": c.get("role", "unknown")}
                       for c in table_info["columns"]],
        },
        "conflict": conflict.__dict__ if conflict else None,
        "inferred_relations": [
            {
                "source_table": r.source_table,
                "target_table": r.target_table,
                "matched_columns_count": len(r.matched_columns),
                "confidence": r.confidence,
                "inference_method": r.inference_method,
            }
            for r in relations
        ],
        "total_relations_found": len(relations),
    }
