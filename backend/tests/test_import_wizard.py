from __future__ import annotations

import io
import time
import zipfile


def make_zip(entries: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buf.getvalue()


def create_project(client, name: str = "Import contract") -> int:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def wait_for_import(client, import_id: int, attempts: int = 40, sleep_s: float = 0.05) -> dict:
    last = None
    for _ in range(attempts):
        response = client.get(f"/api/imports/{import_id}")
        assert response.status_code == 200, response.text
        last = response.json()
        if last.get("status") in {"completed", "failed"}:
            return last
        time.sleep(sleep_s)
    raise AssertionError(f"导入任务未在预期时间内结束: {last}")


def test_import_rejects_wrong_content_type(client):
    project_id = create_project(client, "Wrong content type")
    response = client.post(
        f"/api/projects/{project_id}/imports",
        content=b"plain text",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415
    assert "application/zip" in response.text


def test_import_rejects_zip_slip(client):
    project_id = create_project(client, "Unsafe zip")
    response = client.post(
        f"/api/projects/{project_id}/imports?filename=unsafe.zip",
        content=make_zip({"../bad.sql": "SELECT 1;"}),
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 400
    assert "unsafe path" in response.text


def test_import_accepts_async_zip_and_exposes_analysis_chain(client):
    project_id = create_project(client, "Async import")
    payload = make_zip(
        {
            "ddl/tables.ddl": """
            CREATE TABLE ods.source_orders (
              order_id BIGINT,
              amount DECIMAL(18,2)
            );
            CREATE TABLE dwd.fact_orders (
              order_id BIGINT,
              amount DECIMAL(18,2)
            );
            CREATE TABLE dws.order_summary (
              order_count BIGINT
            );
            """,
            "sql/job.sql": """
            INSERT INTO dwd.fact_orders
            SELECT order_id, amount
            FROM ods.source_orders;

            INSERT INTO dws.order_summary
            SELECT COUNT(*) AS order_count
            FROM dwd.fact_orders;
            """,
        }
    )
    response = client.post(
        f"/api/projects/{project_id}/imports?filename=demo.zip",
        content=payload,
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] in {"queued", "running", "completed"}
    assert body["run_id"]
    assert body["files"]

    listed = client.get(f"/api/projects/{project_id}/imports")
    assert listed.status_code == 200, listed.text
    assert listed.json()["imports"]

    completed = wait_for_import(client, int(body["id"]))
    assert completed["status"] == "completed", completed
    assert completed["run"]["status"] == "completed"
    assert completed["summary"].get("tables", 0) >= 3

    catalog = client.get(f"/api/projects/{project_id}/catalog")
    assert catalog.status_code == 200, catalog.text
    table_names = {item["name"] for item in catalog.json()["tables"]}
    assert {"ods.source_orders", "dwd.fact_orders", "dws.order_summary"} <= table_names

    lineage = client.get(f"/api/projects/{project_id}/lineage", params={"level": "table"})
    assert lineage.status_code == 200, lineage.text
    edges = {(item["source"], item["target"]) for item in lineage.json()["edges"]}
    assert ("ods.source_orders", "dwd.fact_orders") in edges
    assert ("dwd.fact_orders", "dws.order_summary") in edges

    metrics = client.get(f"/api/projects/{project_id}/metrics")
    assert metrics.status_code == 200, metrics.text
    metric_names = {item["name"] for item in metrics.json()["metrics"]}
    assert "order_count" in metric_names

    impact = client.post(
        f"/api/projects/{project_id}/impact-analysis",
        json={"object": "ods.source_orders", "change_type": "schema_change"},
    )
    assert impact.status_code == 200, impact.text
    impact_body = impact.json()
    impacted_targets = {item["target"] for item in impact_body["transitive_impacts"]}
    assert {"dwd.fact_orders", "dws.order_summary"} <= impacted_targets
    assert impact_body["summary"]["direct"] >= 1
    assert impact_body["summary"]["transitive"] >= 2
    assert impact_body["paths"]
    assert impact_body["evidence"]
    assert impact_body["risk"]["score"] > 0
    assert impact_body["recommendations"]

    missing = client.post(
        f"/api/projects/{project_id}/impact-analysis",
        json={"object": "missing.table", "change_type": "drop"},
    )
    assert missing.status_code == 404, missing.text


def test_import_file_endpoints_work_after_async_run(client):
    project_id = create_project(client, "Import files")
    payload = make_zip(
        {
            "ddl/tables.ddl": "CREATE TABLE ods.source_orders (order_id BIGINT);",
            "sql/job.sql": "INSERT INTO ods.source_orders SELECT 1 AS order_id;",
        }
    )
    created = client.post(
        f"/api/projects/{project_id}/imports?filename=files.zip",
        content=payload,
        headers={"Content-Type": "application/zip"},
    )
    assert created.status_code == 202, created.text
    import_id = int(created.json()["id"])

    completed = wait_for_import(client, import_id)
    assert completed["status"] == "completed", completed

    listed = client.get(f"/api/imports/{import_id}/files")
    assert listed.status_code == 200, listed.text
    files = listed.json()["files"]
    assert len(files) == 2
    rel_paths = {item["relative_path"] for item in files}
    assert "ddl/tables.ddl" in rel_paths
    assert "sql/job.sql" in rel_paths

    content = client.get(f"/api/imports/{import_id}/files/content", params={"path": "ddl/tables.ddl"})
    assert content.status_code == 200, content.text
    assert "CREATE TABLE" in content.text

    exported_file = client.get(f"/api/imports/{import_id}/files/export", params={"path": "sql/job.sql"})
    assert exported_file.status_code == 200
    assert exported_file.headers["content-disposition"].endswith('"job.sql"')

    exported_bundle = client.get(f"/api/imports/{import_id}/files/export")
    assert exported_bundle.status_code == 200
    assert "import-" in exported_bundle.headers["content-disposition"]
