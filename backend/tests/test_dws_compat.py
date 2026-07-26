from app.parser import analyze, parse_ddl, parse_sql


DDL = """
CREATE TABLE schema.ods_source_a (
  entity_id VARCHAR(255), mq_timestamp TIMESTAMP, val_input FLOAT8,
  val_output FLOAT8, ext_attr_1 VARCHAR(255), updated_at TIMESTAMP
);
CREATE TABLE schema.dwd_fact_request (
  entity_id VARCHAR(255), ts_event TIMESTAMP, val_total FLOAT8,
  latest_rank BIGINT
);
CREATE TABLE schema.dws_agg_minute (
  entity_id VARCHAR(255), val_p90 FLOAT8
);
"""


def _catalog():
    return {t["name"]: t for t in parse_ddl(DDL, "schema.ddl")}


def test_delete_insert_macro_balanced_ctes_union_cast_case_and_window():
    sql = """
    DELETE FROM schema.dwd_fact_request WHERE ts_event = '${data_time}';
    INSERT INTO schema.dwd_fact_request
    WITH a AS (
      SELECT entity_id, val_input, val_output, ext_attr_1, updated_at
      FROM schema.ods_source_a
      WHERE mq_timestamp >= '${data_time}'
        AND mq_timestamp < DATE_ADD('${data_time}', INTERVAL '1' HOUR)
    ), ranked AS (
      SELECT *, ROW_NUMBER() OVER (
        PARTITION BY entity_id ORDER BY updated_at DESC
      ) AS rn FROM a
      UNION ALL
      SELECT *, 2 AS rn FROM schema.ods_source_b
    )
    SELECT entity_id, DATE_FORMAT('${data_time}', '%Y-%m-%d %H:00:00'),
      CASE WHEN ext_attr_1 NOT LIKE '%None%'
        THEN SPLIT_PART(ext_attr_1, 'x', 1)::BIGINT + val_output
        ELSE val_input + val_output END AS val_total,
      rn AS latest_rank
    FROM ranked WHERE rn = 1;
    """
    ops = parse_sql(sql, "dwd.sql", _catalog())
    assert [op["type"] for op in ops] == ["delete", "insert_select"]
    insert = ops[1]
    assert insert["target"] == "schema.dwd_fact_request"
    assert set(insert["sources"]) == {"schema.ods_source_a", "schema.ods_source_b"}
    assert "${data_time}" in ops[0]["where"]
    assert any("::BIGINT" in p for p in insert["projections"])
    assert any("CASE WHEN" in p for p in insert["projections"])


def test_percentile_disc_within_group_is_metric_and_ellipsis_is_diagnostic(tmp_path):
    (tmp_path / "flow.sql").write_text("""
    INSERT INTO schema.dws_agg_minute
    SELECT entity_id,
      PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY val_total) AS val_p90
    FROM schema.dwd_fact_request
    GROUP BY entity_id;
    SELECT entity_id, ... FROM schema.ods_source_a;
    """, encoding="utf-8")
    files = [{"path": "flow.sql", "size": (tmp_path / "flow.sql").stat().st_size,
              "sha256": "test"}]
    result = analyze(tmp_path, files)
    assert any(m["name"] == "val_p90" for m in result["metrics"])
    assert any(d.get("code") == "INCOMPLETE_SQL" for d in result["diagnostics"])
    assert not any("..." in edge["source"] or "..." in edge["target"]
                   for edge in result["column_lineage"])


def test_aggregate_metrics_inside_ctes_are_catalogued(tmp_path):
    (tmp_path / "flow.sql").write_text("""
    INSERT INTO schema.dws_agg_minute
    WITH summary AS (
      SELECT entity_id,
        SUM(val_total) AS tpm,
        AVG(val_total) AS val_avg,
        PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY val_total) AS val_p90
      FROM schema.dwd_fact_request
      GROUP BY entity_id
    )
    SELECT entity_id, tpm, val_avg, val_p90 FROM summary;
    """, encoding="utf-8")
    files = [{"path": "flow.sql", "size": (tmp_path / "flow.sql").stat().st_size,
              "sha256": "test"}]
    result = analyze(tmp_path, files)
    names = {m["name"] for m in result["metrics"]}
    assert {"tpm", "val_avg", "val_p90"} <= names


def test_cors_allows_only_local_non_8080_development_origins(client):
    for origin in ("http://127.0.0.1:15173", "http://localhost:18080", "https://localhost:4173"):
        response = client.options("/api/projects", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET",
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin

    for origin in ("http://127.0.0.1:8080", "http://localhost:8080",
                   "http://192.168.1.2:15173", "https://example.com:15173"):
        response = client.options("/api/projects", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET",
        })
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
