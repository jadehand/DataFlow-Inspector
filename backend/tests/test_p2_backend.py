from __future__ import annotations

import io
import threading
import zipfile

import pytest


def make_zip(entries: dict[str, str], compression=zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def create_project(client, name: str) -> int:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_preflight_classifies_top_level_directory_package(client):
    payload = make_zip(
        {
            "token-demo/ddl/schema.sql": "CREATE TABLE ods.events(id BIGINT);",
            "token-demo/sql/load.sql": "INSERT INTO ods.events SELECT 1;",
            "token-demo/metadata/manifest.yaml": "name: token-demo",
            "token-demo/metadata/jobs.csv": "job_name,script_path\nload,sql/load.sql",
            "token-demo/samples/events.csv": "id\n1",
        }
    )
    response = client.post(
        "/api/imports/preflight",
        content=payload,
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert {
        "ddl": body["ddl"],
        "sql": body["sql"],
        "manifest": body["manifest"],
        "jobs": body["jobs"],
        "samples": body["samples"],
    } == {"ddl": 1, "sql": 1, "manifest": 1, "jobs": 1, "samples": 1}
    categories = {item["path"]: item["category"] for item in body["files"]}
    assert categories["token-demo/ddl/schema.sql"] == "ddl"
    assert categories["token-demo/sql/load.sql"] == "sql"
    assert categories["token-demo/metadata/manifest.yaml"] == "metadata"
    assert categories["token-demo/samples/events.csv"] == "samples"


@pytest.mark.parametrize(
    ("environment", "entries", "message"),
    [
        ("DFI_MAX_ZIP_FILES", {"a.sql": "x", "b.sql": "x"}, "too many files"),
        ("DFI_MAX_ZIP_FILE_BYTES", {"a.sql": "12345"}, "member too large"),
        ("DFI_MAX_ZIP_UNCOMPRESSED_BYTES", {"a.sql": "123", "b.sql": "456"}, "allowed size"),
        ("DFI_MAX_ZIP_COMPRESSION_RATIO", {"a.sql": "0" * 10000}, "compression ratio"),
    ],
)
def test_zip_limits_reject_before_creating_import(
    client, monkeypatch, environment, entries, message
):
    project_id = create_project(client, f"ZIP limit {environment}")
    monkeypatch.setenv(environment, "1")
    response = client.post(
        f"/api/projects/{project_id}/imports",
        content=make_zip(entries),
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 413, response.text
    assert message in response.text
    listed = client.get(f"/api/projects/{project_id}/imports")
    assert listed.json()["imports"] == []


def test_empty_zip_does_not_create_import(client):
    project_id = create_project(client, "Empty ZIP")
    response = client.post(
        f"/api/projects/{project_id}/imports",
        content=make_zip({}),
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 400, response.text
    assert client.get(f"/api/projects/{project_id}/imports").json()["imports"] == []


def test_recoverable_runs_reset_running_and_claim_once(client):
    from app.db.repositories import import_repo

    project_id = create_project(client, "Worker recovery")
    created = import_repo.create_import(project_id, "recover.zip", "hash", "zip")
    run = import_repo.latest_run_for_import(created["id"])
    assert import_repo.claim_run(run["id"]) is True
    assert import_repo.claim_run(run["id"]) is False

    recovered = import_repo.recoverable_run_ids()
    assert run["id"] in recovered
    reset = import_repo.get_run(run["id"])
    assert reset["status"] == "queued"
    assert reset["started_at"] is None
    assert import_repo.claim_run(run["id"]) is True


def test_worker_start_enqueues_database_recovery(monkeypatch):
    from app.tasks import worker as worker_module

    processed = []
    processed_event = threading.Event()
    monkeypatch.setattr(worker_module.import_repo, "recoverable_run_ids", lambda: [41])

    def process(run_id):
        processed.append(run_id)
        processed_event.set()

    monkeypatch.setattr(worker_module.import_service, "process_run", process)
    worker = worker_module.ImportWorker()
    worker.start()
    try:
        assert processed_event.wait(timeout=1)
        assert processed == [41]
    finally:
        worker.stop()


def test_compare_exposes_changed_details_and_impacted_ads(monkeypatch):
    from app.services import compare_service

    imports = {1: {"id": 11}, 2: {"id": 22}}
    tables = {
        11: [{"name": "dws.sales", "layer": "DWS", "description": "old"}],
        22: [
            {"name": "dws.sales", "layer": "DWS", "description": "new"},
            {"name": "ads.sales", "layer": "ADS"},
        ],
    }
    columns = {
        11: [{"name": "amount", "table_name": "dws.sales", "type": "BIGINT"}],
        22: [{"name": "amount", "table_name": "dws.sales", "type": "DECIMAL"}],
    }
    monkeypatch.setattr(
        compare_service.import_repo,
        "get_import_by_project_version",
        lambda project_id, version: imports.get(version),
    )
    monkeypatch.setattr(compare_service.analysis_repo, "list_tables", lambda import_id: tables[import_id])
    monkeypatch.setattr(
        compare_service.analysis_repo,
        "list_columns",
        lambda import_id, table_name: [
            item for item in columns[import_id] if item["table_name"] == table_name
        ],
    )
    monkeypatch.setattr(
        compare_service.analysis_repo,
        "list_table_edges",
        lambda import_id: [] if import_id == 11 else [{"source": "dws.sales", "target": "ads.sales"}],
    )
    monkeypatch.setattr(compare_service.analysis_repo, "list_metrics", lambda import_id: [])
    monkeypatch.setattr(compare_service.analysis_repo, "list_findings", lambda import_id: [])

    result = compare_service.compare_project_versions(7, 1, 2)

    assert result["tables"]["modified"] == ["dws.sales"]
    changed = {item["name"]: item for item in result["tables"]["changed"]}
    assert changed["dws.sales"]["before"]["description"] == "old"
    assert changed["dws.sales"]["after"]["description"] == "new"
    assert changed["dws.sales"]["columns"][0]["before"]["type"] == "BIGINT"
    assert changed["dws.sales"]["columns"][0]["after"]["type"] == "DECIMAL"
    assert result["summary"]["tables_added"] == 1
    assert result["summary"]["tables_changed"] == 1
    assert result["summary"]["columns_changed"] == 1
    assert result["summary"]["impacted_ads"] == ["ads.sales"]


def test_impact_exposes_evidence_and_rejects_unknown_object(monkeypatch):
    from app.services import impact_service

    monkeypatch.setattr(impact_service, "latest_import_or_404", lambda project_id, version: {"id": 9})
    monkeypatch.setattr(
        impact_service.analysis_repo,
        "list_tables",
        lambda import_id: [{"name": "dws.sales"}, {"name": "ads.sales"}],
    )
    monkeypatch.setattr(
        impact_service.analysis_repo,
        "list_columns",
        lambda import_id, table_name: [{"name": "amount"}],
    )
    monkeypatch.setattr(
        impact_service.analysis_repo,
        "list_table_edges",
        lambda import_id: [
            {
                "source": "dws.sales",
                "target": "ads.sales",
                "file": "sql/sales.sql",
                "line": 8,
                "operation": "INSERT",
                "confidence": 0.9,
                "parse_source": "ast",
            }
        ],
    )
    monkeypatch.setattr(impact_service.analysis_repo, "list_column_edges", lambda import_id: [])
    monkeypatch.setattr(
        impact_service.analysis_repo,
        "list_metrics",
        lambda import_id: [{"name": "sales", "table": "ads.sales"}],
    )
    monkeypatch.setattr(impact_service.analysis_repo, "list_findings", lambda import_id: [])

    result = impact_service.analyze_impact(1, "dws.sales", "type_change")
    assert result["ads_tables"] == ["ads.sales"]
    assert result["scripts"] == ["sql/sales.sql"]
    assert result["paths"][0]["nodes"] == ["dws.sales", "ads.sales"]
    assert result["evidence"][0]["line"] == 8
    assert result["metrics"][0]["name"] == "sales"
    assert result["risk"]["score"] > 0
    assert result["recommendations"]

    with pytest.raises(Exception) as error:
        impact_service.analyze_impact(1, "missing.table", "drop")
    assert getattr(error.value, "status_code", None) == 404
