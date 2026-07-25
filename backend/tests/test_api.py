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


def test_dictionary_bulk_compare_and_export():
    import shutil
    shutil.rmtree("/tmp/dataflow-inspector-tests", ignore_errors=True)
    init_db()
    zip_path = Path(__file__).parents[2] / "examples" / "token-traffic-demo.zip"
    blob = zip_path.read_bytes()
    with TestClient(app) as client:
        pid = client.post("/api/projects", json={"name": "Dictionary"}).json()["id"]
        first = client.post(
            f"/api/projects/{pid}/imports?filename=v1.zip",
            content=blob,
            headers={"Content-Type": "application/zip"},
        )
        second = client.post(
            f"/api/projects/{pid}/imports?filename=v2.zip",
            content=blob,
            headers={"Content-Type": "application/zip"},
        )
        assert first.status_code == second.status_code == 201

        payload = {
            "tables": [{
                "table_name": "dws.dws_token_minute",
                "display_name": "分钟汇总",
                "owner": "data-team",
                "update_frequency": "hourly",
                "retention": "90d",
                "note": "分钟聚合事实表",
            }],
            "columns": [{
                "table_name": "dws.dws_token_minute",
                "column_name": "request_cnt",
                "display_name": "请求数",
                "note": "分钟粒度请求次数",
                "business_tag": "metric",
            }],
            "revision_meta": {
                "source": "detail_editor",
                "operator": "tester",
                "reason": "初始化中文名和口径备注",
            },
        }
        preview = client.post(f"/api/projects/{pid}/dictionary/bulk/preview", json=payload)
        saved = client.put(f"/api/projects/{pid}/dictionary/bulk", json=payload)
        assert preview.status_code == 200, preview.text
        assert preview.json()["summary"]["table_updates"] == 1
        assert preview.json()["summary"]["column_updates"] == 1
        assert preview.json()["requires_confirmation"] is True
        assert preview.json()["next_metadata_revision"] == 1
        assert saved.status_code == 200, saved.text
        assert saved.json()["saved_tables"] == 1
        assert saved.json()["saved_columns"] == 1
        assert saved.json()["metadata_revision"]["revision"] == 1
        assert saved.json()["metadata_revision"]["source"] == "detail_editor"
        assert saved.json()["metadata_revision"]["operator"] == "tester"
        assert saved.json()["skipped"] == {"missing_tables": [], "missing_columns": []}
        assert saved.json()["preview"]["summary"]["table_updates"] == 1
        assert saved.json()["preview"]["summary"]["column_updates"] == 1

        payload_v2 = {
            "tables": [{
                "table_name": "dws.dws_token_minute",
                "display_name": "分钟汇总宽表",
                "owner": "data-team",
                "update_frequency": "hourly",
                "retention": "90d",
                "note": "分钟聚合事实表",
            }],
            "columns": [{
                "table_name": "dws.dws_token_minute",
                "column_name": "request_cnt",
                "display_name": "请求总数",
                "note": "分钟粒度请求次数",
                "business_tag": "metric",
            }],
            "revision_meta": {
                "source": "asset_bulk_edit",
                "operator": "reviewer",
                "reason": "统一表名和字段中文名",
            },
        }
        saved_v2 = client.put(f"/api/projects/{pid}/dictionary/bulk", json=payload_v2)
        assert saved_v2.status_code == 200, saved_v2.text
        assert saved_v2.json()["metadata_revision"]["revision"] == 2

        revisions = client.get(f"/api/projects/{pid}/metadata/revisions")
        assert revisions.status_code == 200
        assert revisions.json()["revisions"][0]["revision"] == 2
        assert revisions.json()["revisions"][0]["source"] == "asset_bulk_edit"
        metadata_compare = client.get(f"/api/projects/{pid}/metadata/compare?left=1&right=2")
        assert metadata_compare.status_code == 200
        assert metadata_compare.json()["compare_scope"] == "metadata_revision"
        assert metadata_compare.json()["summary"]["diff_items"] >= 1

        detail = client.get(f"/api/projects/{pid}/tables/dws.dws_token_minute/detail").json()
        assert detail["table"]["display_name"] == "分钟汇总宽表"
        assert detail["metadata_revision"]["revision"] == 2
        assert detail["metadata_revision"]["operator"] == "reviewer"
        request_cnt = next(field for field in detail["fields"] if field["name"] == "request_cnt")
        assert request_cnt["display_name"] == "请求总数"
        assert request_cnt["business_tag"] == "metric"

        impact = client.post(
            f"/api/projects/{pid}/impact-analysis",
            json={
                "object": "dws.dws_token_minute.request_cnt",
                "change_type": "加工逻辑变化",
                "compare_scope": "metadata_revision",
                "left_revision": 1,
                "right_revision": 2,
            },
        )
        assert impact.status_code == 200, impact.text
        assert impact.json()["evidence_scope"] == "metadata_revision"
        assert impact.json()["diff_evidence"]

        table_compare = client.get(
            f"/api/projects/{pid}/tables/dws.dws_token_minute/compare?left=1&right=2"
        )
        assert table_compare.status_code == 200
        assert "diff_items" in table_compare.json()
        assert table_compare.json()["compare_scope"] == "table"
        assert "table_metadata" in table_compare.json()

        project_compare = client.get(f"/api/projects/{pid}/compare?left=1&right=2")
        assert project_compare.status_code == 200
        assert "diff_items" in project_compare.json()
        assert project_compare.json()["compare_scope"] == "project"
        assert "table_names_in_scope" in project_compare.json()

        exported_json = client.get(f"/api/projects/{pid}/dictionary/export?format=json").json()
        assert exported_json["row_count"] > 0
        assert any(row["table_display_name"] == "分钟汇总宽表" for row in exported_json["rows"])

        exported_csv = client.get(f"/api/projects/{pid}/dictionary/export")
        assert exported_csv.status_code == 200
        assert "data-dictionary-project" in exported_csv.headers["content-disposition"]
