from __future__ import annotations

import io
import re
import zipfile


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}/]+\}", "{param}", path)


def route_methods_map(app) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        if path:
            mapping.setdefault(normalize_path(path), set()).update(methods)
    return mapping


def make_zip(entries: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buf.getvalue()


def create_project(client, name: str = "Contract test") -> int:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code in {200, 201}, response.text
    body = response.json()
    project_id = body.get("id") or body.get("project_id")
    assert project_id is not None, body
    return int(project_id)


def test_app_exposes_minimum_route_surface(app):
    routes = route_methods_map(app)
    expected = {
        "/api/health": {"GET"},
        "/api/projects": {"GET", "POST"},
        "/api/projects/{param}/imports": {"GET", "POST"},
        "/api/imports/{param}": {"GET"},
        "/api/projects/{param}/catalog": {"GET"},
        "/api/projects/{param}/lineage": {"GET"},
        "/api/projects/{param}/compare": {"GET"},
        "/api/projects/{param}/impact-analysis": {"POST"},
        "/api/projects/{param}/dictionary/bulk/preview": {"POST"},
        "/api/projects/{param}/dictionary/bulk": {"PUT"},
        "/api/projects/{param}/metadata/revisions": {"GET"},
        "/api/projects/{param}/assistant/query": {"POST"},
    }
    for path, methods in expected.items():
        assert path in routes, f"缺少核心路由: {path}"
        assert methods <= routes[path], f"{path} 缺少方法: {methods - routes[path]}"


def test_app_exposes_frontend_p0_route_contract(app):
    routes = route_methods_map(app)
    expected = {
        "/api/projects/{param}/tables/preview": {"POST"},
        "/api/projects/{param}/tables/import": {"POST"},
        "/api/imports/preflight": {"POST"},
        "/api/projects/{param}/dictionary/export": {"GET"},
    }
    for path, methods in expected.items():
        assert path in routes, f"前端已调用但后端缺少路由: {path}"
        assert methods <= routes[path], f"{path} 缺少方法: {methods - routes[path]}"


def test_compare_ignores_storage_identity_fields(monkeypatch):
    from app.services import compare_service

    imports = {
        1: {"id": 101, "project_id": 7, "version": 1},
        2: {"id": 202, "project_id": 7, "version": 2},
    }
    tables = {
        101: [
            {
                "id": 1001,
                "import_id": 101,
                "version": 1,
                "name": "dws.order_summary",
                "layer": "DWS",
                "description": "订单汇总",
            }
        ],
        202: [
            {
                "id": 2001,
                "import_id": 202,
                "version": 2,
                "name": "dws.order_summary",
                "layer": "DWS",
                "description": "订单汇总",
            }
        ],
    }
    columns = {
        101: [
            {
                "id": 1101,
                "import_id": 101,
                "version": 1,
                "table_name": "dws.order_summary",
                "name": "order_count",
                "type": "BIGINT",
                "description": "订单数",
            }
        ],
        202: [
            {
                "id": 2101,
                "import_id": 202,
                "version": 2,
                "table_name": "dws.order_summary",
                "name": "order_count",
                "type": "BIGINT",
                "description": "订单数",
            }
        ],
    }

    monkeypatch.setattr(
        compare_service.import_repo,
        "get_import_by_project_version",
        lambda project_id, version: imports.get(version) if project_id == 7 else None,
    )
    monkeypatch.setattr(compare_service.analysis_repo, "list_tables", lambda import_id: tables[import_id])
    monkeypatch.setattr(
        compare_service.analysis_repo,
        "list_columns",
        lambda import_id, table_name: columns[import_id],
    )
    monkeypatch.setattr(compare_service.analysis_repo, "list_table_edges", lambda import_id: [])
    monkeypatch.setattr(compare_service.analysis_repo, "list_metrics", lambda import_id: [])
    monkeypatch.setattr(compare_service.analysis_repo, "list_findings", lambda import_id: [])

    result = compare_service.compare_project_versions(7, 1, 2)

    assert result["tables"]["modified"] == []
    assert result["columns"]["modified"] == []
    assert result["summary"]["modified"] == 0


def test_health_contract(client):
    response = client.get("/api/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    assert body.get("status") in {"ok", "healthy", "up"}, body
    assert response.headers.get("x-request-id")


def test_http_errors_use_json_envelope(client):
    response = client.get("/api/imports/999999999")
    assert response.status_code == 404, response.text
    body = response.json()
    assert body["status_code"] == 404
    assert body["error"]
    assert body["detail"]
    assert body["request_id"]


def test_cors_allows_local_ui_but_rejects_8080(client):
    allowed = client.options(
        "/api/projects",
        headers={
            "Origin": "http://127.0.0.1:15173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:15173"

    blocked = client.options(
        "/api/projects",
        headers={
            "Origin": "http://127.0.0.1:8080",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


def test_project_creation_and_listing_contract(client):
    project_id = create_project(client)
    listed = client.get("/api/projects")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    items = payload if isinstance(payload, list) else payload.get("projects", [])
    assert any((item.get("id") or item.get("project_id")) == project_id for item in items), payload

    imports = client.get(f"/api/projects/{project_id}/imports")
    assert imports.status_code == 200, imports.text
    assert imports.json()["project_id"] == project_id
    assert imports.json()["imports"] == []


def test_import_endpoint_rejects_invalid_payload_without_404(client):
    project_id = create_project(client, "Import contract")
    response = client.post(
        f"/api/projects/{project_id}/imports",
        content=b"not a zip file",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code in {400, 415, 422}, response.text
    assert response.status_code != 404


def test_import_preflight_rejects_zip_slip(client):
    project_id = create_project(client, "Unsafe zip contract")
    payload = make_zip({"../bad.sql": "SELECT 1;"})
    response = client.post(
        f"/api/projects/{project_id}/imports",
        content=payload,
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 400
    assert "unsafe path" in response.text
