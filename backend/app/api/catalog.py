from __future__ import annotations

from fastapi import APIRouter

from ..services import query_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["catalog"])


@router.get("/catalog")
def catalog(project_id: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    return query_service.catalog(project_id, version, layer, search)


@router.get("/tables")
def list_tables(project_id: int, version: int | None = None, layer: str | None = None, search: str | None = None) -> dict:
    return query_service.catalog(project_id, version, layer, search)


@router.get("/tables/{table_name}/detail")
def table_detail(project_id: int, table_name: str, version: int | None = None) -> dict:
    return query_service.table_detail(project_id, table_name, version)


@router.get("/lineage")
def lineage(project_id: int, version: int | None = None, level: str = "table") -> dict:
    return query_service.lineage(project_id, version, level)


@router.get("/workflows")
def workflows(project_id: int, version: int | None = None) -> dict:
    return query_service.workflows(project_id, version)


@router.get("/metrics")
def metrics(project_id: int, version: int | None = None) -> dict:
    return query_service.metrics(project_id, version)


@router.get("/quality-findings")
def quality_findings(project_id: int, version: int | None = None) -> dict:
    return query_service.quality_findings(project_id, version)
