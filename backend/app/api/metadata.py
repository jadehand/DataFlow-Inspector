from __future__ import annotations

from fastapi import APIRouter, Response

from ..services import metadata_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["metadata"])


@router.get("/dictionary/export")
def export_dictionary(project_id: int) -> Response:
    content = metadata_service.export_dictionary_csv(project_id)
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="data-dictionary-project-{project_id}.csv"'
        },
    )


@router.post("/dictionary/bulk/preview")
def preview_bulk(project_id: int, payload: dict) -> dict:
    return metadata_service.preview_bulk_update(project_id, payload)


@router.put("/dictionary/bulk")
def save_bulk(project_id: int, payload: dict) -> dict:
    return metadata_service.save_bulk_update(project_id, payload)


@router.get("/metadata/revisions")
def metadata_revisions(project_id: int) -> dict:
    return metadata_service.list_revisions(project_id)


@router.get("/metadata/compare")
def compare_revisions(project_id: int, left: int, right: int) -> dict:
    return metadata_service.compare_revisions(project_id, left, right)
