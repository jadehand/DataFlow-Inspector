#!/usr/bin/env python3
"""DataFlow Inspector 最小烟测：启动后验证核心 API 契约。"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request


BASE_URL = os.getenv("DATAFLOW_API_URL", "http://127.0.0.1:18080").rstrip("/")
API_BASE = f"{BASE_URL}/api"


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}/]+\}", "{param}", path)


def request(method: str, path: str, body: bytes | None = None, headers=None, expect_status=None, base_url: str = API_BASE):
    req = urllib.request.Request(
        base_url + path,
        data=body,
        method=method,
        headers=headers or {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            status = response.status
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
    except Exception as exc:  # pragma: no cover - surfaced to CLI
        raise RuntimeError(f"{path}: 请求失败: {exc}") from exc

    if expect_status is not None:
        allowed = expect_status if isinstance(expect_status, set) else {expect_status}
        if status not in allowed:
            decoded = raw.decode("utf-8", "replace")
            raise RuntimeError(f"{path}: 期望状态 {sorted(allowed)}，实际 {status}: {decoded}")

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw.decode("utf-8", "replace")}
    return status, response_headers, parsed


def pick_id(payload, keys=("id", "project_id", "import_id")):
    if isinstance(payload, dict):
        for key in keys:
            if payload.get(key) is not None:
                return payload[key]
        for key in ("project", "data", "result"):
            if key in payload:
                found = pick_id(payload[key], keys)
                if found is not None:
                    return found
    return None


def main():
    status, headers, health = request("GET", "/health", expect_status=200)
    if health.get("status") not in {"ok", "healthy", "up"}:
        raise RuntimeError(f"/health 返回异常: {health}")
    if not headers.get("x-request-id"):
        raise RuntimeError("健康检查缺少 x-request-id")
    print("✓ 健康检查")

    _, _, openapi = request("GET", "/openapi.json", expect_status=200, base_url=BASE_URL)
    paths = {normalize_path(path) for path in openapi.get("paths", {})}
    required_paths = {
        "/api/health",
        "/api/projects",
        "/api/projects/{param}/imports",
        "/api/imports/{param}",
        "/api/projects/{param}/catalog",
        "/api/projects/{param}/lineage",
        "/api/projects/{param}/compare",
        "/api/projects/{param}/impact-analysis",
    }
    missing = sorted(path for path in required_paths if path not in paths)
    if missing:
        raise RuntimeError(f"OpenAPI 缺少核心路径: {missing}")
    print("✓ OpenAPI 核心路由")

    _, cors_headers, _ = request(
        "OPTIONS",
        "/projects",
        headers={
            "Origin": "http://127.0.0.1:15173",
            "Access-Control-Request-Method": "GET",
        },
        expect_status=200,
    )
    if cors_headers.get("access-control-allow-origin") != "http://127.0.0.1:15173":
        raise RuntimeError(f"CORS 允许来源异常: {cors_headers}")
    status, _, _ = request(
        "OPTIONS",
        "/projects",
        headers={
            "Origin": "http://127.0.0.1:8080",
            "Access-Control-Request-Method": "GET",
        },
        expect_status={400, 403},
    )
    if status not in {400, 403}:
        raise RuntimeError("8080 来源未被拒绝")
    print("✓ CORS 端口边界")

    create_body = json.dumps({"name": "Smoke project", "description": "runtime check"}).encode()
    _, _, project = request(
        "POST",
        "/projects",
        create_body,
        {"Content-Type": "application/json"},
        expect_status={200, 201},
    )
    project_id = pick_id(project, ("id", "project_id"))
    if project_id is None:
        raise RuntimeError(f"创建项目响应缺少 ID: {project}")
    print("✓ 创建项目", project_id)

    _, _, project_list = request("GET", "/projects", expect_status=200)
    list_items = project_list if isinstance(project_list, list) else project_list.get("projects", [])
    if not any((item.get("id") or item.get("project_id")) == project_id for item in list_items):
        raise RuntimeError(f"项目列表缺少刚创建的项目: {project_list}")
    print("✓ 查询项目列表")

    _, _, import_list = request("GET", f"/projects/{project_id}/imports", expect_status=200)
    if import_list.get("project_id") != project_id:
        raise RuntimeError(f"项目导入列表不匹配: {import_list}")
    print("✓ 查询导入列表")

    invalid_payload_status, _, invalid_payload = request(
        "POST",
        f"/projects/{project_id}/imports",
        b"not a zip",
        {"Content-Type": "text/plain"},
        expect_status={400, 415, 422},
    )
    if invalid_payload_status == 404:
        raise RuntimeError("导入接口不存在")
    print("✓ 导入接口拒绝非法负载")

    missing_status, _, missing_import = request("GET", "/imports/999999999", expect_status=404)
    if missing_status != 404:
        raise RuntimeError("缺失导入资源未返回 404")
    required_error_keys = {"error", "detail", "status_code", "request_id"}
    if not required_error_keys <= set(missing_import):
        raise RuntimeError(f"错误返回结构不完整: {missing_import}")
    print("✓ 错误包结构")

    print("最小烟测通过")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"最小烟测失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
