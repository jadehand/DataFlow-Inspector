"""
MAAS demo project - parser verification script.
Tests ODS->DWD->DWS->ADS 5-table pipeline with DWS dialect features.
"""

import json
import tempfile
import zipfile
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.parser.analyzer import analyze
from app.main import safe_extract


def test_llm_demo():
    demo_dir = Path(__file__).parents[1] / "examples" / "llm-demo"
    if not demo_dir.is_dir():
        print("llm-demo dir not found, skipping")
        return False

    # Package ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(demo_dir.rglob("*")):
            if f.is_file() and "__pycache__" not in str(f):
                arcname = f.relative_to(demo_dir).as_posix()
                zf.write(f, arcname)
    blob = buf.getvalue()
    print(f"ZIP size: {len(blob) / 1024:.1f} KB")

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        files = safe_extract(blob, dest)
        print(f"Extracted files: {len(files)}")

        result = analyze(dest, files)
        summary = result["summary"]

        print()
        print("=" * 60)
        print("MAAS Demo Parse Results")
        print("=" * 60)
        print(f"  Tables:           {summary['tables']}")
        print(f"  Columns:          {summary['columns']}")
        print(f"  Table edges:      {summary['table_edges']}")
        print(f"  Column edges:     {summary['column_edges']}")
        print(f"  Metrics:          {summary['metrics']}")
        print(f"  Risks:            {summary['risks']}")
        print(f"  Jobs:             {summary['jobs']}")
        print(f"  Diagnostics:      {len(result['diagnostics'])}")

        # Layer breakdown
        print()
        print("=" * 60)
        print("Layer Breakdown")
        print("=" * 60)
        layers = {}
        for t in result["tables"]:
            layer = t.get("layer", "OTHER")
            layers.setdefault(layer, []).append(t)
        for layer, tables in sorted(layers.items()):
            print(f"  {layer}: {len(tables)} table(s)")
            for t in tables:
                dws_info = t.get("dws", {})
                dist = dws_info.get("distribute_type", "")
                part_info = ""
                if dws_info.get("distribute_columns"):
                    part_info += f" dist={dist}({dws_info['distribute_columns']})"
                if dws_info.get("partition_columns"):
                    part_info += f" part={dws_info['partition_type']}({dws_info['partition_columns']})"
                if dws_info.get("storage_params"):
                    part_info += f" storage={dws_info['storage_params']}"
                cols_count = len(t["columns"])
                flag = " [inferred]" if t.get("inferred") else ""
                print(f"    {t['name']} ({cols_count} cols){flag}{part_info}")

        # Table lineage
        print()
        print("=" * 60)
        print("Table Lineage (Processing Chain)")
        print("=" * 60)
        for e in result["table_lineage"]:
            print(f"  {e['source']} -> {e['target']} ({e['operation']}, {e['file']})")

        # Column lineage sample
        print()
        print("=" * 60)
        print(f"Column Lineage ({summary['column_edges']} total, showing first 25)")
        print("=" * 60)
        for e in result["column_lineage"][:25]:
            ttype = e.get("transform_type", "?")
            conf = e.get("confidence", "?")
            srcp = e.get("parse_source", "?")
            print(f"  {e['source']:45s} -> {e['target']:50s} [{ttype}, conf={conf}, {srcp}]")
        if len(result["column_lineage"]) > 25:
            print(f"  ... {summary['column_edges']} total")

        # Metrics
        print()
        print("=" * 60)
        print(f"Metrics ({summary['metrics']} total)")
        print("=" * 60)
        for m in result["metrics"]:
            print(f"  {m['name']:20s} | {m['table']:40s} | {m['formula'][:70]}")

        # Job DAG
        print()
        print("=" * 60)
        print("Job DAG")
        print("=" * 60)
        for j in result["jobs"]:
            upstreams = j.get("upstream_jobs", "")
            print(f"  {j['job_name']} [{j.get('schedule', '')}] <- {upstreams}")

        # Risks
        if result["risks"]:
            print()
            print("=" * 60)
            print(f"Risks ({len(result['risks'])} total)")
            print("=" * 60)
            for r in result["risks"]:
                print(f"  [{r['severity']}] {r['code']}: {r['message'][:100]}")

        # VERIFICATION
        print()
        print("=" * 60)
        print("Verification")
        print("=" * 60)
        errors = []

        # 1. 5 tables
        expected_tables = {
            "ods.ods_llm_api_request_log",
            "dwd.dwd_llm_api_request_detail",
            "dim.dim_llm_model_info",
            "dws.dws_llm_api_model_minute_stat",
            "ads.ads_llm_customer_model_daily_stat",
        }
        actual_names = {t["name"] for t in result["tables"]}
        if expected_tables.issubset(actual_names):
            print("[PASS] 5 core tables all recognized")
        else:
            missing = expected_tables - actual_names
            errors.append(f"[FAIL] Missing tables: {missing}")

        # 2. Table lineage (including DIM JOIN)
        lineage_pairs = {f"{e['source']}->{e['target']}" for e in result["table_lineage"]}
        expected_lineage = {
            "ods.ods_llm_api_request_log->dwd.dwd_llm_api_request_detail",
            "dwd.dwd_llm_api_request_detail->dws.dws_llm_api_model_minute_stat",
            "dim.dim_llm_model_info->dws.dws_llm_api_model_minute_stat",
            "dws.dws_llm_api_model_minute_stat->ads.ads_llm_customer_model_daily_stat",
        }
        if expected_lineage.issubset(lineage_pairs):
            print("[PASS] 4 core table lineage edges (incl. DIM JOIN)")
        else:
            missing_le = expected_lineage - lineage_pairs
            errors.append(f"[FAIL] Missing lineage: {missing_le}")

        # 3. Column lineage
        if summary["column_edges"] >= 30:
            print(f"[PASS] Column lineage: {summary['column_edges']} edges (>=30)")
        elif summary["column_edges"] >= 5:
            print(f"[OK] Column lineage: {summary['column_edges']} edges (>=5)")
        else:
            errors.append(f"[FAIL] Column lineage too few: {summary['column_edges']}")

        # 4. Metrics
        expected_metrics = {"request_cnt", "success_cnt", "fail_cnt",
                           "input_tokens_sum", "output_tokens_sum", "total_tokens_sum",
                           "avg_latency_ms", "p95_latency_ms",
                           "cost_input", "cost_output", "total_cost"}
        actual_metrics = {m["name"] for m in result["metrics"]}
        if expected_metrics.issubset(actual_metrics):
            print(f"[PASS] All {len(expected_metrics)} core metrics identified")
        else:
            missing_m = expected_metrics - actual_metrics
            print(f"[WARN] Missing metrics: {missing_m} (total: {len(actual_metrics)})")

        # 5. DWS dialect info
        dws_tables = [t for t in result["tables"] if t.get("dws")]
        if dws_tables:
            print(f"[PASS] DWS dialect info: {len(dws_tables)} tables")
        else:
            errors.append("[FAIL] No DWS dialect info extracted")

        # 6. Job DAG
        if len(result["jobs"]) >= 3:
            print(f"[PASS] Job DAG: {len(result['jobs'])} jobs")
        else:
            print(f"[WARN] Job count: {len(result['jobs'])} (expected >=3)")

        # 7. Layer classification
        layer_map = {t["name"]: t.get("layer", "?") for t in result["tables"]}
        expected_layers = {
            "ods.ods_llm_api_request_log": "ODS",
            "dwd.dwd_llm_api_request_detail": "DWD",
            "dim.dim_llm_model_info": "DIM",
            "dws.dws_llm_api_model_minute_stat": "DWS",
            "ads.ads_llm_customer_model_daily_stat": "ADS",
        }
        layer_ok = all(layer_map.get(n) == l for n, l in expected_layers.items())
        if layer_ok:
            print("[PASS] Layer classification (ODS/DWD/DIM/DWS/ADS) correct")
        else:
            for n, l in expected_layers.items():
                if layer_map.get(n) != l:
                    print(f"  [FAIL] {n}: expected {l}, got {layer_map.get(n)}")

        # 8. No errors in diagnostics
        if not result["diagnostics"]:
            print("[PASS] No parse errors/diagnostics")
        else:
            print(f"[WARN] {len(result['diagnostics'])} diagnostics found")

        if errors:
            print()
            print("FAILURES:")
            for e in errors:
                print(f"  {e}")
            return False
        else:
            print()
            print("=" * 60)
            print("ALL CORE VERIFICATIONS PASSED!")
            print("=" * 60)
            return True


if __name__ == "__main__":
    ok = test_llm_demo()
    if not ok:
        sys.exit(1)
