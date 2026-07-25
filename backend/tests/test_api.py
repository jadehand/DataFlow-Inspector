import os
from pathlib import Path

os.environ["DFI_DATA_DIR"] = "/tmp/dataflow-inspector-tests"
os.environ["DFI_DB_PATH"] = "/tmp/dataflow-inspector-tests/test.db"
os.environ["DFI_IMPORT_DIR"] = "/tmp/dataflow-inspector-tests/imports"

from fastapi.testclient import TestClient
from app.main import app, init_db


def test_demo_end_to_end():
    import shutil
    shutil.rmtree("/tmp/dataflow-inspector-tests", ignore_errors=True)
    init_db()
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        p = client.post("/api/projects", json={"name": "Token traffic"}).json()
        zip_path = Path(__file__).parents[2] / "examples" / "token-traffic-demo.zip"
        r = client.post(f"/api/projects/{p['id']}/imports?filename=demo.zip",
                        content=zip_path.read_bytes(), headers={"Content-Type": "application/zip"})
        assert r.status_code == 201, r.text
        assert r.json()["summary"]["tables"] >= 10
        catalog = client.get(f"/api/projects/{p['id']}/catalog").json()
        assert any(t["name"] == "dws.dws_token_minute" for t in catalog["tables"])
        lineage = client.get(f"/api/projects/{p['id']}/lineage").json()
        assert any(e["target"] == "dws.dws_token_minute" for e in lineage["edges"])
        metrics = client.get(f"/api/projects/{p['id']}/metrics").json()
        assert metrics["metrics"]
        impact = client.post(f"/api/projects/{p['id']}/impact-analysis",
                             json={"object": "dwd.dwd_token_request_wide.region_code",
                                   "change_type": "rename_column"}).json()
        assert impact["transitive_impacts"]
        answer = client.post(f"/api/projects/{p['id']}/assistant/query",
                             json={"question": "有哪些风险"}).json()
        assert answer["evidence"]


def test_reject_path_traversal():
    import io, shutil, zipfile
    shutil.rmtree("/tmp/dataflow-inspector-tests", ignore_errors=True)
    init_db()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../bad.sql", "select 1")
    with TestClient(app) as client:
        p = client.post("/api/projects", json={"name": "Unsafe"}).json()
        r = client.post(f"/api/projects/{p['id']}/imports", content=buf.getvalue(),
                        headers={"Content-Type": "application/zip"})
        assert r.status_code == 400


def test_all_product_endpoints_cors_and_version_compare():
    import shutil
    shutil.rmtree("/tmp/dataflow-inspector-tests", ignore_errors=True)
    init_db()
    zip_path = Path(__file__).parents[2] / "examples" / "token-traffic-demo.zip"
    blob = zip_path.read_bytes()
    with TestClient(app) as client:
        cors = client.options("/api/projects", headers={
            "Origin": "http://127.0.0.1:15173",
            "Access-Control-Request-Method": "GET",
        })
        assert cors.status_code == 200
        assert cors.headers["access-control-allow-origin"] == "http://127.0.0.1:15173"

        project = client.post("/api/projects", json={"name": "Endpoint audit"}).json()
        pid = project["id"]
        first = client.post(f"/api/projects/{pid}/imports?filename=v1.zip", content=blob,
                            headers={"Content-Type": "application/zip"})
        second = client.post(f"/api/projects/{pid}/imports?filename=v2.zip", content=blob,
                             headers={"Content-Type": "application/zip"})
        assert first.status_code == second.status_code == 201
        assert client.get(f"/api/projects/{pid}/imports").status_code == 200
        assert client.get(f"/api/imports/{first.json()['id']}").status_code == 200
        assert client.get(f"/api/projects/{pid}/tables?layer=DWS").json()["tables"]

        table_edges = client.get(f"/api/projects/{pid}/lineage?level=table").json()["edges"]
        column_edges = client.get(f"/api/projects/{pid}/lineage?level=column").json()["edges"]
        assert table_edges
        assert any(e["target"].endswith("dws_token_minute.stat_minute") for e in column_edges)
        assert client.get(f"/api/projects/{pid}/workflows").json()["jobs"]
        assert client.get(f"/api/projects/{pid}/metrics").json()["metrics"]
        assert client.get(f"/api/projects/{pid}/quality-findings").json()["findings"]
        assert client.post(f"/api/projects/{pid}/impact-analysis", json={
            "object": "dwd.dwd_token_request_wide.region_code",
            "change_type": "rename_column",
        }).json()["transitive_impacts"]
        compared = client.get(f"/api/projects/{pid}/compare?left=1&right=2")
        assert compared.status_code == 200
        assert compared.json()["lineage"] == {"added": [], "removed": []}
        answer = client.post(f"/api/projects/{pid}/assistant/query",
                             json={"question": "request_cnt"}).json()
        assert answer["confidence"] == "high"


def test_reject_backslash_traversal_and_wrong_content_type():
    import io, shutil, zipfile
    shutil.rmtree("/tmp/dataflow-inspector-tests", ignore_errors=True)
    init_db()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(r"..\bad.sql", "select 1")
    with TestClient(app) as client:
        pid = client.post("/api/projects", json={"name": "ZIP audit"}).json()["id"]
        unsafe = client.post(f"/api/projects/{pid}/imports", content=buf.getvalue(),
                             headers={"Content-Type": "application/zip"})
        assert unsafe.status_code == 400
        wrong_type = client.post(f"/api/projects/{pid}/imports", content=b"not a zip",
                                 headers={"Content-Type": "text/plain"})
        assert wrong_type.status_code == 415
