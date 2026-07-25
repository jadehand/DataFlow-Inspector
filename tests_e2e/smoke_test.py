#!/usr/bin/env python3
"""DataFlow Inspector 黑盒验收：健康检查、演示项目导入及关键查询。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("DATAFLOW_API_URL", "http://127.0.0.1:18080").rstrip("/")
DEMO_ZIP = ROOT / "examples" / "token-traffic-demo.zip"


def request(method: str, path: str, body: bytes | None = None, headers=None):
    req = urllib.request.Request(
        BASE_URL + path, data=body, method=method, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"{path}: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{path}: HTTP {exc.code}: {detail}") from exc
    parsed = json.loads(raw) if raw else {}
    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"{path}: {parsed['error']}")
    return parsed


def pick_id(value, keys=("id", "project_id", "import_id")):
    if isinstance(value, dict):
        for key in keys:
            if value.get(key) is not None:
                return value[key]
        for key in ("project", "data", "result"):
            if key in value:
                found = pick_id(value[key], keys)
                if found is not None:
                    return found
    return None


def main():
    if not DEMO_ZIP.is_file() or DEMO_ZIP.stat().st_size == 0:
        raise RuntimeError(f"演示包不存在或为空: {DEMO_ZIP}")

    health = request("GET", "/api/health")
    print("✓ 健康检查", health)

    project_body = json.dumps(
        {"name": "Token 流量黑盒验收", "description": "自动化演示导入"}
    ).encode()
    project = request(
        "POST",
        "/api/projects",
        project_body,
        {"Content-Type": "application/json"},
    )
    project_id = pick_id(project, ("id", "project_id"))
    if project_id is None:
        raise RuntimeError(f"创建项目响应缺少 ID: {project}")
    print("✓ 创建项目", project_id)

    payload = DEMO_ZIP.read_bytes()
    headers = {"Content-Type": "application/zip"}
    imported = request(
        "POST",
        f"/api/projects/{project_id}/imports?filename={DEMO_ZIP.name}",
        payload,
        headers,
    )
    import_id = pick_id(imported, ("id", "import_id"))
    print("✓ 导入演示包", import_id if import_id is not None else "accepted")

    checks = {
        "资产目录": f"/api/projects/{project_id}/catalog",
        "表级血缘": f"/api/projects/{project_id}/lineage",
        "指标目录": f"/api/projects/{project_id}/metrics",
        "作业流": f"/api/projects/{project_id}/workflows",
    }
    for label, path in checks.items():
        result = request("GET", path)
        print(f"✓ {label}", type(result).__name__)

    impact = request(
        "POST",
        f"/api/projects/{project_id}/impact-analysis",
        json.dumps(
            {
                "object": "dwd.dwd_token_request.region_code",
                "change_type": "type_change",
                "before": "VARCHAR(16)",
                "after": "VARCHAR(32)",
            }
        ).encode(),
        {"Content-Type": "application/json"},
    )
    if "risk" not in impact or "transitive_impacts" not in impact:
        raise RuntimeError(f"影响分析响应不完整: {impact}")
    print("✓ 变更影响分析", impact["risk"])

    answer = request(
        "POST",
        f"/api/projects/{project_id}/assistant/query",
        json.dumps({"question": "有哪些风险？"}).encode(),
        {"Content-Type": "application/json"},
    )
    if not answer.get("answer"):
        raise RuntimeError(f"助手响应缺少答案: {answer}")
    print("✓ 证据化问答", answer.get("confidence"))

    print("黑盒验收通过")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"黑盒验收失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
