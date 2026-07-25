import io
import os
import zipfile

os.environ["DFI_DATA_DIR"] = "/tmp/dataflow-inspector-tests"
os.environ["DFI_DB_PATH"] = "/tmp/dataflow-inspector-tests/test.db"
os.environ["DFI_IMPORT_DIR"] = "/tmp/dataflow-inspector-tests/imports"

from fastapi.testclient import TestClient

from app.main import app


def make_zip(entries: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buf.getvalue()


def preflight(client: TestClient, blob: bytes):
    return client.post(
        "/api/imports/preflight",
        content=blob,
        headers={"Content-Type": "application/zip"},
    )


def test_preflight_rejects_zip_slip():
    with TestClient(app) as client:
        response = preflight(client, make_zip({"../bad.sql": "SELECT 1;"}))
    assert response.status_code == 400
    assert "unsafe zip entry" in response.text


def test_preflight_requires_processing_sql():
    with TestClient(app) as client:
        response = preflight(client, make_zip({
            "project/ddl/tables.ddl": "CREATE TABLE ods.a (id BIGINT);",
            "project/manifest.yaml": "project: demo\n",
        }))
    assert response.status_code == 200
    body = response.json()
    assert body["has_ddl"] is True
    assert body["has_sql"] is False
    assert body["ready"] is False
    assert any("SQL" in error for error in body["errors"])


def test_preflight_complete_package_and_template_downloads():
    blob = make_zip({
        "project/manifest.yaml": "project: demo\n",
        "project/ddl/tables.ddl": "CREATE TABLE ods.a (id BIGINT);",
        "project/sql/job.sql": "INSERT INTO dwd.b SELECT id FROM ods.a;",
        "project/metadata/jobs.csv": "job_name,script_path\njob,sql/job.sql\n",
        "project/samples/a.csv": "id\n1\n",
    })
    with TestClient(app) as client:
        response = preflight(client, blob)
        blank = client.get("/api/templates/blank")
        demo = client.get("/api/templates/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["errors"] == []
    assert all(body[key] for key in (
        "has_sql", "has_ddl", "has_manifest", "has_jobs", "has_samples"
    ))
    for download in (blank, demo):
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            assert archive.testzip() is None
            assert archive.namelist()


def test_preflight_counts_sql_suffixed_files_in_ddl_directory_as_ddl():
    blob = make_zip({
        "project/ddl/tables.sql": "CREATE TABLE ods.a (id BIGINT);",
        "project/sql/job.sql": "INSERT INTO dwd.b SELECT id FROM ods.a;",
    })
    with TestClient(app) as client:
        response = preflight(client, blob)
    body = response.json()
    assert body["ready"] is True
    assert body["counts"]["ddl"] == 1
    assert body["counts"]["sql"] == 1


def test_preflight_non_utf8_is_error():
    with TestClient(app) as client:
        response = preflight(client, make_zip({"sql/job.sql": b"\xff\xfe\xfa"}))
    assert response.status_code == 200
    body = response.json()
    assert body["has_sql"] is True
    assert body["ready"] is False
    assert any("UTF-8" in error for error in body["errors"])
