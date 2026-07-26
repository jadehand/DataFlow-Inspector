from __future__ import annotations

from fastapi import APIRouter, Body

from ..services import assistant_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["assistant"])


@router.post("/assistant/query")
def ask(project_id: int, payload: dict = Body(...), version: int | None = None) -> dict:
    return assistant_service.answer_question(project_id, payload.get("question", ""), version)
