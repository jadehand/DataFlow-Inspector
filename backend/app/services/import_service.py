from __future__ import annotations

from dataclasses import asdict
import hashlib
import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..core.config import get_settings
from ..db.repositories import analysis_repo, import_repo
from ..parser import analyze as parser_analyze
from ..parser.single_table import import_single_table, merge_table_into_analysis
from .common import file_category, logical_name, sha256_bytes


def import_version_dir(project_id: int, version: int) -> Path:
    return get_settings().imports_dir / str(project_id) / str(version)


def _validated_archive(blob: bytes) -> tuple[zipfile.ZipFile, list[zipfile.ZipInfo]]:
    settings = get_settings()
    if len(blob) > settings.max_zip_bytes:
        raise HTTPException(413, "zip too large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "invalid zip file") from exc
    infos = [info for info in archive.infolist() if not info.is_dir()]
    if len(infos) > settings.max_zip_files:
        archive.close()
        raise HTTPException(413, "zip contains too many files")
    total_size = 0
    for info in infos:
        relative_path = Path(info.filename.replace("\\", "/"))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            archive.close()
            raise HTTPException(400, "unsafe path in zip")
        if info.file_size > settings.max_zip_file_bytes:
            archive.close()
            raise HTTPException(413, "zip member too large")
        total_size += info.file_size
        if total_size > settings.max_zip_uncompressed_bytes:
            archive.close()
            raise HTTPException(413, "zip expands beyond allowed size")
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > settings.max_zip_compression_ratio:
            archive.close()
            raise HTTPException(413, "zip compression ratio too high")
    return archive, infos


def _extract_archive(
    archive: zipfile.ZipFile, infos: list[zipfile.ZipInfo], dest: Path
) -> list[dict]:
    dest.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for info in infos:
        relative_path = Path(info.filename.replace("\\", "/"))
        target = dest / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with archive.open(info) as source, target.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        files.append(
            {
                "path": relative_path.as_posix(),
                "size": size,
                "sha256": digest.hexdigest(),
                "category": file_category(relative_path.as_posix()),
                "logical_name": logical_name(relative_path.as_posix()),
            }
        )
    return files


def preflight_zip(blob: bytes) -> dict:
    archive, infos = _validated_archive(blob)

    counts = {"ddl": 0, "sql": 0, "manifest": 0, "jobs": 0, "samples": 0}
    errors: list[dict] = []
    warnings: list[dict] = []
    files: list[dict] = []
    for info in infos:
        relative_path = Path(info.filename.replace("\\", "/"))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise HTTPException(400, "unsafe path in zip")
        path = relative_path.as_posix()
        category = file_category(path)
        if category == "ddl":
            counts["ddl"] += 1
        elif category == "sql":
            counts["sql"] += 1
        if relative_path.name.lower() in {"manifest.json", "manifest.yaml", "manifest.yml"}:
            counts["manifest"] += 1
        if relative_path.name.lower() == "jobs.csv":
            counts["jobs"] += 1
        if category == "samples":
            counts["samples"] += 1
        files.append({"path": path, "size": info.file_size, "category": category})

    if not files:
        errors.append({"code": "EMPTY_ARCHIVE", "message": "ZIP project package is empty"})
    if counts["sql"] == 0:
        warnings.append({"code": "MISSING_SQL", "message": "no transformation SQL found"})
    if counts["ddl"] == 0:
        warnings.append({"code": "MISSING_DDL", "message": "no DDL found; field analysis will be incomplete"})
    archive.close()
    return {**counts, "errors": errors, "warnings": warnings, "files": files}


def enqueue_zip_import(project_id: int, filename: str, blob: bytes, queue_run) -> dict:
    archive, infos = _validated_archive(blob)
    if not infos:
        archive.close()
        raise HTTPException(400, "ZIP project package is empty")
    settings = get_settings()
    settings.imports_dir.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".staged-import-", dir=settings.imports_dir))
    try:
        files = _extract_archive(archive, infos, staged)
        created = import_repo.create_import(project_id, filename, sha256_bytes(blob), "zip")
        dest = import_version_dir(project_id, created["version"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(dest)
        import_repo.record_import_files(created["id"], files, "zip_upload")
        run = import_repo.latest_run_for_import(created["id"])
        queue_run(run["id"])
        item = import_repo.get_import(created["id"])
        item["files"] = import_repo.list_import_files(created["id"])
        return item
    finally:
        archive.close()
        if staged.exists():
            shutil.rmtree(staged)


def _structured_analysis(import_id: int | None) -> dict:
    if import_id is None:
        return {
            "summary": {},
            "files": [],
            "tables": [],
            "operations": [],
            "table_lineage": [],
            "column_lineage": [],
            "jobs": [],
            "job_lineage": [],
            "metrics": [],
            "time_usage": [],
            "risks": [],
            "diagnostics": [],
        }
    tables = analysis_repo.list_tables(import_id)
    for table in tables:
        table["columns"] = analysis_repo.list_columns(import_id, table["name"])
    return {
        "summary": {},
        "files": import_repo.list_import_files(import_id),
        "tables": tables,
        "operations": [],
        "table_lineage": analysis_repo.list_table_edges(import_id),
        "column_lineage": analysis_repo.list_column_edges(import_id),
        "jobs": analysis_repo.list_jobs(import_id),
        "job_lineage": analysis_repo.list_job_edges(import_id),
        "metrics": analysis_repo.list_metrics(import_id),
        "time_usage": [],
        "risks": analysis_repo.list_findings(import_id),
        "diagnostics": [],
    }


def _serialize_single_result(result) -> dict:
    payload = asdict(result)
    payload["table"] = payload.pop("table_info")
    conflict = payload.get("conflict")
    if conflict:
        conflict["shared_columns"] = conflict.pop("common_columns")
        conflict["changed_types"] = conflict.pop("type_mismatches")
    relations = payload.get("inferred_relations", [])
    for index, relation in enumerate(relations):
        relation["index"] = index
        relation["matched_columns_count"] = len(relation.get("matched_columns", []))
    return payload


def _single_table_result(
    project_id: int,
    ddl: str,
    etl_sql: str,
    conflict_strategy: str,
):
    current = import_repo.latest_completed_import(project_id)
    analysis = _structured_analysis(current["id"] if current else None)
    result = import_single_table(
        ddl,
        project_id,
        analysis,
        conflict_strategy=conflict_strategy,
        etl_sql=etl_sql or None,
    )
    if etl_sql.strip():
        if not result.operations:
            raise HTTPException(400, "ETL SQL could not be parsed")
        wrong_targets = sorted(
            {
                operation.get("target", "")
                for operation in result.operations
                if operation.get("target", "").lower() != result.table_name.lower()
            }
        )
        if wrong_targets:
            raise HTTPException(
                400,
                f"ETL target must match DDL table {result.table_name}; got {', '.join(wrong_targets)}",
            )
    return current, analysis, result


def preview_single_table(project_id: int, ddl: str, etl_sql: str = "") -> dict:
    _, analysis, result = _single_table_result(project_id, ddl, etl_sql, "check")
    payload = _serialize_single_result(result)
    conflict = payload.get("conflict")
    if conflict:
        payload["available_strategies"] = ["replace", "merge", "keep"]
        payload["recommended_strategy"] = "replace"
        payload["requires_decision"] = True
    elif etl_sql.strip():
        payload["available_strategies"] = ["replace"]
        payload["recommended_strategy"] = "replace"
        payload["requires_decision"] = False
    else:
        payload["available_strategies"] = ["replace", "merge_inferred"]
        payload["recommended_strategy"] = "replace"
        payload["requires_decision"] = False
    known_tables = {table["name"].lower() for table in analysis["tables"]}
    payload["missing_upstream_tables"] = sorted(
        {
            edge["source"]
            for edge in payload.get("table_lineage", [])
            if edge.get("source", "").lower() not in known_tables
        }
    )
    payload["lineage_source"] = "parsed_from_sql" if etl_sql.strip() else "none"
    return payload


def _copy_previous_files(previous: dict | None, created: dict) -> list[dict]:
    if not previous:
        return []
    source_dir = import_version_dir(previous["project_id"], previous["version"])
    target_dir = import_version_dir(created["project_id"], created["version"])
    copied = []
    for item in import_repo.list_import_files(previous["id"]):
        source = source_dir / item["relative_path"]
        if not source.is_file():
            continue
        target = target_dir / item["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(
            {
                "path": item["relative_path"],
                "size": item["size_bytes"],
                "sha256": item["content_sha256"],
                "category": item["category"],
                "logical_name": item["logical_name"],
            }
        )
    return copied


def import_single_table_version(
    project_id: int,
    ddl: str,
    etl_sql: str = "",
    conflict_strategy: str = "replace",
    confirmed_relation_index: int | None = None,
) -> dict:
    allowed = {"replace", "merge", "keep", "merge_inferred"}
    if conflict_strategy not in allowed:
        raise HTTPException(400, f"unsupported conflict strategy: {conflict_strategy}")
    previous, analysis, result = _single_table_result(
        project_id, ddl, etl_sql, conflict_strategy
    )
    payload = _serialize_single_result(result)
    if not result.success:
        payload["requires_decision"] = True
        return payload
    if result.action == "skipped":
        payload.update({"requires_decision": False, "navigation": {"page": "assets"}})
        return payload

    inferred = result.inferred_relations
    if conflict_strategy == "merge_inferred":
        if confirmed_relation_index is None or not 0 <= confirmed_relation_index < len(inferred):
            raise HTTPException(400, "confirmed_relation_index is required for merge_inferred")
        inferred = [inferred[confirmed_relation_index]]
    if conflict_strategy == "replace":
        table_name = result.table_name.lower()
        analysis["table_lineage"] = [
            edge
            for edge in analysis["table_lineage"]
            if edge.get("target", "").lower() != table_name
        ]
        analysis["column_lineage"] = [
            edge
            for edge in analysis["column_lineage"]
            if not edge.get("target", "").lower().startswith(f"{table_name}.")
        ]
    safe_name = (
        result.table_name.replace(".", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )
    ddl_path = f"ddl/{safe_name}.ddl"
    result.table_info["ddl_file"] = ddl_path
    merged = merge_table_into_analysis(
        analysis,
        result.table_info,
        result.table_lineage,
        result.column_lineage,
        inferred,
        result.operations,
    )

    combined = ddl.encode("utf-8") + b"\0" + etl_sql.encode("utf-8")
    created = import_repo.create_import(
        project_id,
        f"single-table-{safe_name}.sql",
        sha256_bytes(combined),
        "single_table",
    )
    target_dir = import_version_dir(project_id, created["version"])
    target_dir.mkdir(parents=True, exist_ok=True)
    files = _copy_previous_files(previous, created)
    (target_dir / "ddl").mkdir(parents=True, exist_ok=True)
    (target_dir / ddl_path).write_text(ddl, encoding="utf-8")
    files = [item for item in files if item["path"] != ddl_path]
    files.append(
        {
            "path": ddl_path,
            "size": len(ddl.encode("utf-8")),
            "sha256": sha256_bytes(ddl.encode("utf-8")),
            "category": "ddl",
            "logical_name": safe_name,
        }
    )
    if etl_sql.strip():
        etl_path = f"sql/{safe_name}.sql"
        (target_dir / "sql").mkdir(parents=True, exist_ok=True)
        (target_dir / etl_path).write_text(etl_sql, encoding="utf-8")
        files = [item for item in files if item["path"] != etl_path]
        files.append(
            {
                "path": etl_path,
                "size": len(etl_sql.encode("utf-8")),
                "sha256": sha256_bytes(etl_sql.encode("utf-8")),
                "category": "sql",
                "logical_name": safe_name,
            }
        )
        for edge in merged["table_lineage"]:
            if edge.get("file") == "__single_import_etl__":
                edge["file"] = etl_path
        for edge in merged["column_lineage"]:
            if edge.get("file") == "__single_import_etl__":
                edge["file"] = etl_path
    import_repo.record_import_files(created["id"], files, "single_table")
    analysis_repo.replace_import_analysis(
        project_id, created["id"], created["version"], merged
    )
    run = import_repo.latest_run_for_import(created["id"])
    import_repo.mark_run_completed(run["id"], merged, merged["summary"])
    payload["table"]["ddl_file"] = ddl_path
    payload.update(
        {
            "id": created["id"],
            "import_id": created["id"],
            "project_id": project_id,
            "version": created["version"],
            "status": "completed",
            "requires_decision": False,
            "lineage_source": "parsed_from_sql" if etl_sql.strip() else "none",
            "navigation": {"page": "lineage" if etl_sql.strip() else "assets"},
            "files": import_repo.list_import_files(created["id"]),
        }
    )
    return payload


def process_run(run_id: int) -> dict:
    if not import_repo.claim_run(run_id):
        return {}
    run = import_repo.get_run(run_id)
    if not run:
        raise RuntimeError(f"run {run_id} not found")
    current_import = import_repo.get_import(run["import_id"])
    dest = import_version_dir(current_import["project_id"], current_import["version"])
    files = [
        {
            "path": item["relative_path"],
            "size": item["size_bytes"],
            "sha256": item["content_sha256"],
            "category": item["category"],
            "logical_name": item["logical_name"],
        }
        for item in import_repo.list_import_files(current_import["id"])
    ]
    analysis = parser_analyze(dest, files)
    analysis_repo.replace_import_analysis(
        current_import["project_id"],
        current_import["id"],
        current_import["version"],
        analysis,
    )
    import_repo.mark_run_completed(run_id, analysis, analysis.get("summary", {}))
    return import_repo.get_import(current_import["id"])
