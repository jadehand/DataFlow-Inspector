#!/usr/bin/env python3
"""P2 black-box acceptance test against an already running API server."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile


BASE_URL = os.getenv("DATAFLOW_API_URL", "http://127.0.0.1:18080").rstrip("/")
API_BASE = f"{BASE_URL}/api"
ROOT = Path(__file__).resolve().parents[1]
DEMO_ZIP = ROOT / "examples" / "token-traffic-demo.zip"
POLL_TIMEOUT = float(os.getenv("DATAFLOW_ACCEPTANCE_TIMEOUT", "120"))


class AcceptanceFailure(AssertionError):
    pass


def require(condition: object, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


def http_request(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expected: int | set[int] = 200,
    json_response: bool = True,
) -> tuple[int, dict[str, str], object]:
    request_id = f"p2-{uuid.uuid4().hex[:12]}"
    request_headers = {"X-Request-ID": request_id, **(headers or {})}
    request = urllib.request.Request(
        API_BASE + path,
        data=body,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
    except Exception as exc:
        raise AcceptanceFailure(f"{method} {path}: request failed: {exc}") from exc

    allowed = expected if isinstance(expected, set) else {expected}
    require(
        status in allowed,
        f"{method} {path}: expected HTTP {sorted(allowed)}, got {status}: "
        f"{raw.decode('utf-8', 'replace')[:1000]}",
    )
    require(response_headers.get("x-request-id") == request_id, f"{method} {path}: missing or changed x-request-id")

    if not json_response:
        return status, response_headers, raw
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceFailure(f"{method} {path}: response is not valid JSON") from exc
    return status, response_headers, payload


def json_request(
    method: str,
    path: str,
    payload: object,
    *,
    expected: int | set[int] = 200,
) -> tuple[int, dict[str, str], object]:
    return http_request(
        method,
        path,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        expected=expected,
    )


def error_request(method: str, path: str, **kwargs) -> dict:
    _, headers, payload = http_request(method, path, **kwargs)
    require(isinstance(payload, dict), f"{method} {path}: error response must be an object")
    required = {"error", "detail", "status_code", "request_id"}
    require(required <= payload.keys(), f"{method} {path}: incomplete error envelope: {payload}")
    require(payload["request_id"] == headers["x-request-id"], f"{method} {path}: error request IDs differ")
    return payload


def zip_blob(files: dict[str, bytes | str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode() if isinstance(content, str) else content)
    return output.getvalue()


def changed_demo_blob(blob: bytes) -> bytes:
    """Create a deterministic second version without maintaining another fixture."""
    source = io.BytesIO(blob)
    output = io.BytesIO()
    changed = False
    with zipfile.ZipFile(source) as current, zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as updated:
        for info in current.infolist():
            content = current.read(info.filename)
            if info.filename.endswith("/ddl/03_dwd.sql"):
                replacement = content.replace(b"region_code      VARCHAR(16),", b"region_code      VARCHAR(32),")
                changed = changed or replacement != content
                content = replacement
            updated.writestr(info, content)
    require(changed, "could not build deterministic V2 fixture")
    return output.getvalue()


def upload(project_id: int, blob: bytes, filename: str) -> dict:
    encoded_name = urllib.parse.quote(filename)
    _, _, payload = http_request(
        "POST",
        f"/projects/{project_id}/imports?filename={encoded_name}",
        body=blob,
        headers={"Content-Type": "application/zip"},
        expected=202,
    )
    require(isinstance(payload, dict), "upload response must be an object")
    for key in ("id", "project_id", "version", "status", "run_id", "files"):
        require(payload.get(key) is not None, f"upload response missing {key}: {payload}")
    require(payload["project_id"] == project_id, "upload response has wrong project")
    return payload


def wait_for_import(import_id: int) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT
    last: dict = {}
    while time.monotonic() < deadline:
        _, _, payload = http_request("GET", f"/imports/{import_id}")
        require(isinstance(payload, dict), "import status response must be an object")
        last = payload
        status = payload.get("status")
        if status == "completed":
            require(payload.get("run", {}).get("status") == "completed", f"run did not complete: {payload}")
            return payload
        if status == "failed":
            raise AcceptanceFailure(f"import {import_id} failed: {payload.get('run') or payload}")
        time.sleep(0.25)
    raise AcceptanceFailure(f"import {import_id} timed out after {POLL_TIMEOUT}s: {last}")


def assert_error_packages(project_id: int) -> None:
    error_request(
        "POST",
        "/imports/preflight",
        body=b"not-a-zip",
        headers={"Content-Type": "application/zip"},
        expected=400,
    )
    error_request(
        "POST",
        f"/projects/{project_id}/imports?filename=invalid.zip",
        body=b"not-a-zip",
        headers={"Content-Type": "application/zip"},
        expected=400,
    )
    _, _, empty = http_request(
        "POST",
        "/imports/preflight",
        body=zip_blob({}),
        headers={"Content-Type": "application/zip"},
    )
    require(any(item.get("code") == "EMPTY_ARCHIVE" for item in empty.get("errors", [])), "empty ZIP was not rejected")
    error_request(
        "POST",
        "/imports/preflight",
        body=zip_blob({"../escape.sql": "SELECT 1;"}),
        headers={"Content-Type": "application/zip"},
        expected=400,
    )


def run_acceptance() -> list[str]:
    failures: list[str] = []
    require(DEMO_ZIP.is_file() and DEMO_ZIP.stat().st_size > 0, f"fixture missing or empty: {DEMO_ZIP}")
    demo_blob = DEMO_ZIP.read_bytes()

    _, _, health = http_request("GET", "/health")
    require(isinstance(health, dict) and health.get("status") in {"ok", "healthy", "up"}, f"unhealthy API: {health}")

    project_name = f"P2 acceptance {uuid.uuid4().hex[:10]}"
    _, _, project = json_request(
        "POST",
        "/projects",
        {"name": project_name, "description": "automated P2 black-box acceptance"},
        expected=201,
    )
    require(isinstance(project, dict) and project.get("id"), f"project creation missing id: {project}")
    project_id = int(project["id"])

    _, _, preflight = http_request(
        "POST",
        "/imports/preflight",
        body=demo_blob,
        headers={"Content-Type": "application/zip"},
    )
    require(isinstance(preflight, dict), "preflight response must be an object")
    expected_counts = {"ddl": 6, "sql": 8, "manifest": 1, "jobs": 1, "samples": 2}
    actual_counts = {key: preflight.get(key) for key in expected_counts}
    if actual_counts != expected_counts:
        failures.append(f"preflight counts: expected {expected_counts}, got {actual_counts}")
    if preflight.get("errors"):
        failures.append(f"preflight returned errors: {preflight['errors']}")

    first = upload(project_id, demo_blob, "token-traffic-demo-v1.zip")
    first_done = wait_for_import(int(first["id"]))
    require(first_done.get("sha256"), "completed import has no archive hash")
    version_1 = int(first_done["version"])

    _, _, catalog = http_request("GET", f"/projects/{project_id}/catalog?version={version_1}")
    tables = catalog.get("tables", [])
    table_names = {item.get("name") for item in tables}
    required_tables = {
        "rds.token_request",
        "ods.ods_token_request",
        "dwd.dwd_token_request",
        "dwd.dwd_token_request_wide",
        "dws.dws_token_minute",
        "ads.ads_token_realtime",
    }
    require(required_tables <= table_names, f"catalog missing tables: {sorted(required_tables - table_names)}")

    detail_name = "dws.dws_token_minute"
    detail_path = urllib.parse.quote(detail_name, safe="")
    _, _, detail = http_request(
        "GET",
        f"/projects/{project_id}/tables/{detail_path}/detail?version={version_1}",
    )
    require(detail.get("table", {}).get("name") == detail_name, f"wrong table detail: {detail}")
    require(detail.get("fields"), "table detail has no fields")
    require(detail.get("evidence"), "table detail has no evidence")

    _, _, table_lineage = http_request(
        "GET",
        f"/projects/{project_id}/lineage?version={version_1}&level=table",
    )
    table_edges = {(item.get("source"), item.get("target")) for item in table_lineage.get("edges", [])}
    expected_chain = {
        ("rds.token_request", "ods.ods_token_request"),
        ("ods.ods_token_request", "dwd.dwd_token_request"),
        ("dwd.dwd_token_request", "dwd.dwd_token_request_wide"),
        ("dwd.dwd_token_request_wide", "dws.dws_token_minute"),
        ("dws.dws_token_minute", "ads.ads_token_realtime"),
    }
    require(expected_chain <= table_edges, f"table lineage missing: {sorted(expected_chain - table_edges)}")

    _, _, column_lineage = http_request(
        "GET",
        f"/projects/{project_id}/lineage?version={version_1}&level=column",
    )
    require(column_lineage.get("edges"), "column lineage is empty")

    _, _, workflows = http_request("GET", f"/projects/{project_id}/workflows?version={version_1}")
    require(len(workflows.get("jobs", [])) == 8, f"expected 8 workflows, got {len(workflows.get('jobs', []))}")
    require(isinstance(workflows.get("edges"), list), "workflow edges missing")

    _, _, metrics = http_request("GET", f"/projects/{project_id}/metrics?version={version_1}")
    require(metrics.get("metrics"), "metrics are empty")

    _, _, findings = http_request("GET", f"/projects/{project_id}/quality-findings?version={version_1}")
    finding_text = json.dumps(findings.get("findings", []), ensure_ascii=False).lower()
    for marker in ("time", "select_star", "filter"):
        if marker not in finding_text:
            failures.append(f"quality findings missing marker: {marker}")

    _, _, assistant = json_request(
        "POST",
        f"/projects/{project_id}/assistant/query?version={version_1}",
        {"question": "dws_token_minute"},
    )
    require(assistant.get("confidence") in {"medium", "high"}, f"assistant did not find project evidence: {assistant}")
    require(assistant.get("evidence"), "assistant response has no evidence")

    _, _, file_list = http_request("GET", f"/imports/{first['id']}/files")
    files = file_list.get("files", [])
    require(files, "import file list is empty")
    selected_path = next((item["relative_path"] for item in files if item["relative_path"].endswith(".sql")), None)
    require(selected_path, "import has no readable SQL file")
    encoded_path = urllib.parse.quote(selected_path, safe="")
    _, content_headers, content = http_request(
        "GET",
        f"/imports/{first['id']}/files/content?path={encoded_path}",
        json_response=False,
    )
    require(content.strip(), "import file content is empty")
    require(content_headers.get("content-type", "").startswith("text/plain"), "file content has wrong media type")
    _, export_headers, exported = http_request(
        "GET",
        f"/imports/{first['id']}/files/export?path={encoded_path}",
        json_response=False,
    )
    require(exported == content, "single-file export differs from file content")
    require("attachment" in export_headers.get("content-disposition", ""), "single-file export is not an attachment")
    _, bundle_headers, bundle = http_request(
        "GET",
        f"/imports/{first['id']}/files/export",
        json_response=False,
    )
    require(bundle_headers.get("content-type") == "application/zip", "bundle export has wrong media type")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        require(selected_path in archive.namelist(), "bundle export is missing the selected file")

    second = upload(project_id, changed_demo_blob(demo_blob), "token-traffic-demo-v2.zip")
    second_done = wait_for_import(int(second["id"]))
    version_2 = int(second_done["version"])
    require(version_2 > version_1, f"second import did not create a new version: {version_1}, {version_2}")

    _, _, comparison = http_request(
        "GET",
        f"/projects/{project_id}/compare?left={version_1}&right={version_2}",
    )
    require(comparison.get("left_version") == version_1, f"compare has wrong left version: {comparison}")
    require(comparison.get("right_version") == version_2, f"compare has wrong right version: {comparison}")
    for key in ("tables", "columns", "lineage", "metrics", "risks", "summary"):
        require(isinstance(comparison.get(key), dict), f"compare missing {key}: {comparison}")
    modified_columns = set(comparison["columns"].get("modified", []))
    require(
        "dwd.dwd_token_request.region_code" in modified_columns,
        f"compare did not detect V2 field type change: {comparison}",
    )
    require(
        comparison["summary"].get("columns_changed", 0) >= 1,
        f"compare summary did not count changed columns: {comparison['summary']}",
    )

    _, _, impact = json_request(
        "POST",
        f"/projects/{project_id}/impact-analysis?version={version_2}",
        {"object": "dwd.dwd_token_request.region_code", "change_type": "type_change"},
    )
    require(impact.get("object") == "dwd.dwd_token_request.region_code", f"impact object mismatch: {impact}")
    require(isinstance(impact.get("transitive_impacts"), list), "impact result has no transitive impacts")
    if not impact.get("transitive_impacts"):
        failures.append("column impact returned no downstream objects")

    try:
        assert_error_packages(project_id)
    except AcceptanceFailure as exc:
        failures.append(f"error package checks: {exc}")
    return failures


def main() -> int:
    print(f"P2 API: {BASE_URL}", flush=True)
    try:
        failures = run_acceptance()
    except AcceptanceFailure as exc:
        print(f"P2 acceptance blocked: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("P2 acceptance completed with contract failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("P2 full acceptance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
