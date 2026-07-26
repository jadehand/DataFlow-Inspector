from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import compare_service, impact_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["compare"])


class ChangeIn(BaseModel):
    object: str
    change_type: str


@router.get("/compare")
def compare_versions(project_id: int, left: int, right: int) -> dict:
    try:
        return compare_service.compare_project_versions(project_id, left, right)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/tables/{table_name}/compare")
def compare_table(project_id: int, table_name: str, left: int, right: int) -> dict:
    try:
        return compare_service.compare_single_table(project_id, table_name, left, right)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/impact-analysis")
def impact_analysis(project_id: int, payload: ChangeIn, version: int | None = None) -> dict:
    return impact_service.analyze_impact(project_id, payload.object, payload.change_type, version)
