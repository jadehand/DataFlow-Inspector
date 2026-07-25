"""
DDL 解析器 — 基于 SQLGlot AST。

解析 CREATE TABLE 语句，提取表名、字段、类型、约束等信息。
兼容 GaussDB(DWS) 专有语法（分布键、分区、存储参数等）。

输出格式与旧版 parse_ddl 完全兼容，同时新增 DWS 特有字段。
"""

from __future__ import annotations

import logging
import re
from typing import Any

try:
    import sqlglot
    from sqlglot import exp
except ModuleNotFoundError:  # Optional at runtime; parser falls back to regex.
    sqlglot = None
    exp = None

from .dialect_dws import DWSTableInfo, extract_dws_info, get_dialect
from .regex_fallback import classify_column, layer_of, parse_ddl as regex_parse_ddl

logger = logging.getLogger(__name__)


def parse_ddl(text: str, path: str) -> list[dict[str, Any]]:
    """
    解析 DDL 文本，返回表定义列表。

    先用 SQLGlot AST 解析，失败时降级到正则解析。
    输出格式兼容旧版，新增 dws_info 字段。
    """
    # 按语句拆分，逐个解析（单条失败不影响其他）
    if sqlglot is None or exp is None:
        tables = regex_parse_ddl(text, path)
        for t in tables:
            t["confidence"] = 0.5
            t["parse_source"] = "regex_fallback"
        return tables

    raw_statements = _split_statements(text)
    tables: list[dict[str, Any]] = []
    used_fallback = False

    for stmt_text in raw_statements:
        stripped = stmt_text.strip()
        if not stripped:
            continue
        # 去掉行首注释（DDL 文件常用 -- 注释分隔各层）
        uncommented = re.sub(r'^(?:\s*--[^\n]*\n)+', '', stripped)
        if not re.search(r'^\s*CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\b',
                         uncommented, re.IGNORECASE):
            continue
        # 传原始语句给 _parse_create_table（含注释，方便追踪原文）
        try:
            table = _parse_create_table(stripped, path)
            if table:
                tables.append(table)
        except Exception as e:
            # 单条失败，降级用正则解析这条
            logger.debug(f"SQLGlot DDL 解析失败 ({path}): {e}，降级正则")
            fallback_tables = regex_parse_ddl(stripped, path)
            for t in fallback_tables:
                t["confidence"] = 0.5
                t["parse_source"] = "regex_fallback"
                tables.append(t)
            used_fallback = True

    # 如果全部失败且一张表都没解析出来，全量降级正则
    if not tables and raw_statements:
        tables = regex_parse_ddl(text, path)
        for t in tables:
            t["confidence"] = 0.5
            t["parse_source"] = "regex_fallback"
        used_fallback = True

    return tables


def _split_statements(text: str) -> list[str]:
    """按分号拆分 SQL 语句，考虑字符串和括号内的分号。"""
    statements = []
    current = []
    depth = 0
    in_string = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            current.append(ch)
            if ch == in_string:
                # 检查转义（双引号/单引号的转义是两个相同字符）
                if i + 1 < len(text) and text[i + 1] == in_string:
                    current.append(text[i + 1])
                    i += 1
                else:
                    in_string = None
        elif ch in "'\"`":
            in_string = ch
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == ";" and depth == 0:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
        i += 1

    remaining = "".join(current).strip()
    if remaining:
        statements.append(remaining)
    return statements


def _parse_create_table(sql: str, path: str) -> dict[str, Any] | None:
    """解析单条 CREATE TABLE 语句。"""
    # 先做 DWS 预处理，提取专有信息
    cleaned_sql, dws_info = extract_dws_info(sql)

    dialect = get_dialect()
    parsed = sqlglot.parse_one(cleaned_sql, dialect=dialect)

    if not isinstance(parsed, exp.Create):
        return None
    if parsed.kind != "TABLE":
        return None

    # 表名：Create.this 是 Schema 节点
    # Schema.this 是 Table（表名），Schema.expressions 是字段定义
    schema_node = parsed.this
    if not isinstance(schema_node, exp.Schema):
        return None
    table_node = schema_node.this
    table_name = _table_name(table_node)

    # 字段
    columns: list[dict[str, Any]] = []
    if hasattr(schema_node, "expressions") and schema_node.expressions:
        for col_def in schema_node.expressions:
            if isinstance(col_def, exp.ColumnDef):
                col_name = col_def.name.lower()
                col_type = col_def.args.get("kind")
                col_type_str = str(col_type).upper() if col_type else "UNKNOWN"
                role_info = classify_column(col_name, col_type_str)
                col_info = {
                    "name": col_name,
                    "type": col_type_str,
                    **role_info,
                    "nullable": not col_def.args.get("not_null", False),
                }
                # 主键信息
                if col_def.args.get("primary_key"):
                    col_info["is_primary_key"] = True
                columns.append(col_info)
            elif isinstance(col_def, exp.PrimaryKey):
                # 表级主键约束，回写到对应字段
                pk_cols = [str(c).lower().strip('"') for c in col_def.expressions]
                for col in columns:
                    if col["name"] in pk_cols:
                        col["is_primary_key"] = True

    # 临时表
    is_temporary = bool(parsed.args.get("temporary"))
    is_unlogged = "UNLOGGED" in sql.upper()

    result = {
        "name": table_name,
        "columns": columns,
        "ddl_file": path,
        "layer": layer_of(table_name),
        "confidence": 0.95,
        "parse_source": "sqlglot_ast",
        "is_temporary": is_temporary,
        "is_unlogged": is_unlogged,
    }

    # DWS 特有信息
    if dws_info.distribute_type or dws_info.partition_type or dws_info.storage_params:
        result["dws"] = {
            "distribute_type": dws_info.distribute_type,
            "distribute_columns": dws_info.distribute_columns,
            "partition_type": dws_info.partition_type,
            "partition_columns": dws_info.partition_columns,
            "storage_params": dws_info.storage_params,
            "on_commit": dws_info.on_commit,
        }

    return result


def _table_name(table_node: exp.Table) -> str:
    """
    从 Create.this (Table 节点) 提取标准化表名。

    SQLGlot 的 CREATE TABLE 解析结果中：
    - Create.this 是 Table 节点
    - Table.db 是 schema 名（如果有）
    - Table.catalog 是 catalog 名（如果有）
    - Table.name 是表名
    """
    parts: list[str] = []

    # catalog（三级命名：catalog.schema.table）
    if hasattr(table_node, "catalog") and table_node.catalog:
        parts.append(str(table_node.catalog).lower())

    # db / schema
    if hasattr(table_node, "db") and table_node.db:
        parts.append(str(table_node.db).lower())

    # 表名
    name = table_node.name
    if name:
        parts.append(str(name).lower())

    if not parts:
        return str(table_node).lower()

    return ".".join(parts)
