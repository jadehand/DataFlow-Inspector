from __future__ import annotations

from ..db.repositories import analysis_repo
from .query_service import latest_import_or_404


def answer_question(project_id: int, question: str, version: int | None = None) -> dict:
    current = latest_import_or_404(project_id, version)
    needle = question.lower().strip()
    metrics = analysis_repo.list_metrics(current["id"])
    findings = analysis_repo.list_findings(current["id"])
    tables = analysis_repo.list_tables(current["id"])
    evidence = []
    answer = "没有找到直接匹配的证据。"
    confidence = "low"
    for metric in metrics:
        if needle and (needle in metric.get("name", "").lower() or needle in metric.get("formula", "").lower()):
            answer = f"{metric.get('name', '指标')} 来自 {metric.get('table', '未知表')}，公式为 {metric.get('formula', '—')}"
            evidence.append(
                {
                    "type": "metric",
                    "table": metric.get("table"),
                    "file": metric.get("file"),
                    "line": metric.get("line"),
                }
            )
            confidence = "high"
            break
    if confidence == "low":
        for finding in findings:
            if needle and needle in (finding.get("message", "") + finding.get("code", "")).lower():
                answer = finding.get("message", "命中风险证据")
                evidence.append(
                    {
                        "type": "risk",
                        "code": finding.get("code"),
                        "file": finding.get("file"),
                    }
                )
                confidence = "medium"
                break
    if confidence == "low":
        for table in tables:
            if needle and needle in table.get("name", "").lower():
                answer = f"{table['name']} 属于 {table.get('layer', 'OTHER')} 层。"
                evidence.append({"type": "table", "table": table["name"], "ddl_file": table.get("ddl_file")})
                confidence = "medium"
                break
    return {
        "project_id": project_id,
        "question": question,
        "answer": answer,
        "confidence": confidence,
        "evidence": evidence,
    }
