from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ..db.repositories import project_repo

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    dialect: str = "gaussdb_dws"


@router.get("/projects")
def list_projects() -> dict:
    return {"projects": project_repo.list_projects()}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectIn) -> dict:
    if not payload.name.strip():
        raise HTTPException(400, "project name is required")
    return project_repo.create_project(payload.name.strip(), payload.description, payload.dialect)
