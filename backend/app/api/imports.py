from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from ..db.repositories import import_repo, project_repo
from ..services import import_service

router = APIRouter(prefix="/api", tags=["imports"])


def _worker(request: Request):
    return request.app.state.import_worker


def _ensure_project(project_id: int) -> None:
    if not project_repo.get_project(project_id):
        raise HTTPException(404, "project not found")


class SingleTableIn(BaseModel):
    ddl: str
    etl_sql: str = ""
    conflict_strategy: str = "replace"
    confirmed_relation_index: int | None = None


@router.post("/imports/preflight")
async def preflight_import(request: Request) -> dict:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/zip":
        raise HTTPException(415, "content type must be application/zip")
    return import_service.preflight_zip(await request.body())


@router.get("/projects/{project_id}/imports")
def list_imports(project_id: int) -> dict:
    _ensure_project(project_id)
    return {"project_id": project_id, "imports": import_repo.list_imports(project_id)}


@router.post("/projects/{project_id}/imports", status_code=202)
async def create_import(project_id: int, request: Request, filename: str = Query("project.zip")) -> dict:
    _ensure_project(project_id)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/zip":
        raise HTTPException(415, "content type must be application/zip")
    blob = await request.body()
    item = import_service.enqueue_zip_import(project_id, filename, blob, _worker(request).enqueue)
    return {
        "id": item["id"],
        "project_id": item["project_id"],
        "version": item["version"],
        "status": item["status"],
        "run_id": item.get("run_id"),
        "files": item["files"],
    }


@router.post("/projects/{project_id}/tables/preview")
def preview_single_table(project_id: int, payload: SingleTableIn) -> dict:
    _ensure_project(project_id)
    if not payload.ddl.strip():
        raise HTTPException(400, "DDL is required")
    return import_service.preview_single_table(project_id, payload.ddl, payload.etl_sql)


@router.post("/projects/{project_id}/tables/import", status_code=201)
def import_single_table(project_id: int, payload: SingleTableIn) -> dict:
    _ensure_project(project_id)
    if not payload.ddl.strip():
        raise HTTPException(400, "DDL is required")
    return import_service.import_single_table_version(
        project_id,
        payload.ddl,
        payload.etl_sql,
        payload.conflict_strategy,
        payload.confirmed_relation_index,
    )


@router.get("/imports/{import_id}")
def get_import(import_id: int) -> dict:
    item = import_repo.get_import(import_id)
    if not item:
        raise HTTPException(404, "import not found")
    item["files"] = import_repo.list_import_files(import_id)
    item["run"] = import_repo.latest_run_for_import(import_id)
    return item


@router.get("/imports/{import_id}/files")
def list_import_files(import_id: int) -> dict:
    item = import_repo.get_import(import_id)
    if not item:
        raise HTTPException(404, "import not found")
    return {"import_id": import_id, "files": import_repo.list_import_files(import_id)}


def _safe_import_file(import_id: int, relative_path: str) -> Path:
    item = import_repo.get_import(import_id)
    if not item:
        raise HTTPException(404, "import not found")
    normalized = Path(relative_path.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise HTTPException(400, "unsafe path")
    file_path = import_service.import_version_dir(item["project_id"], item["version"]) / normalized
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "import file not found")
    return file_path


@router.get("/imports/{import_id}/files/content")
def get_import_file_content(import_id: int, path: str) -> Response:
    file_path = _safe_import_file(import_id, path)
    return Response(content=file_path.read_bytes(), media_type="text/plain; charset=utf-8")


@router.get("/imports/{import_id}/files/export")
def export_import_files(import_id: int, path: str | None = None):
    if path:
        file_path = _safe_import_file(import_id, path)
        return Response(
            content=file_path.read_bytes(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'},
        )
    item = import_repo.get_import(import_id)
    if not item:
        raise HTTPException(404, "import not found")
    files = import_repo.list_import_files(import_id)
    if not files:
        raise HTTPException(404, "no import files found")
    import io
    import zipfile

    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            file_path = _safe_import_file(import_id, file["relative_path"])
            archive.writestr(file["relative_path"], file_path.read_bytes())
    blob.seek(0)
    return StreamingResponse(
        blob,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="import-{item["project_id"]}-v{item["version"]}.zip"'},
    )
