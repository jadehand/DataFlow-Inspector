"""
SQL 解析器 — 基于 SQLGlot AST。

解析 INSERT/CTAS/DELETE 等 DML 语句，提取：
- 表级血缘（target → sources）
- 字段级血缘（target.col → source.col 映射，支持 CTE 穿透）
- 指标识别（聚合函数）
- GROUP BY 维度
- WHERE 过滤条件
- CTE 展开

输出格式与旧版 parse_sql 完全兼容，新增置信度和证据字段。
"""

from __future__ import annotations

import logging
import re
from typing import Any

import sqlglot
from sqlglot import exp

from .dialect_dws import get_dialect, preprocess_dml
from .regex_fallback import line_number, parse_sql as regex_parse_sql

logger = logging.getLogger(__name__)


# --- 公共入口 ---

def parse_sql(text: str, path: str, catalog: dict[str, dict]) -> list[dict[str, Any]]:
    """
    解析 SQL 文本，返回操作列表。

    先用 SQLGlot AST 解析，失败时降级到正则解析。
    """
    processed = preprocess_dml(text)
    dialect = get_dialect()

    operations: list[dict[str, Any]] = []

    try:
        statements = sqlglot.parse(processed, dialect=dialect)
    except Exception as e:
        logger.debug(f"SQLGlot 整段解析失败 ({path}): {e}，降级正则")
        ops = regex_parse_sql(text, path, catalog)
        for op in ops:
            op["parse_source"] = "regex_fallback"
        return ops

    for idx, stmt in enumerate(statements):
        if stmt is None:
            continue
        try:
            op = _parse_statement(stmt, path, text, catalog)
            if op:
                operations.append(op)
        except Exception as e:
            logger.debug(f"SQLGlot 单条解析失败 ({path}, stmt {idx}): {e}，降级正则")
            ops = regex_parse_sql(text, path, catalog)
            for op in ops:
                op["parse_source"] = "regex_fallback"
            return ops

    if not operations and text.strip():
        ops = regex_parse_sql(text, path, catalog)
        for op in ops:
            op["parse_source"] = "regex_fallback"
        return ops

    operations.sort(key=lambda op: op.get("line", 0))
    return operations


# --- 语句分发 ---

def _parse_statement(stmt: exp.Expression, path: str, original_text: str,
                     catalog: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(stmt, exp.Insert):
        return _parse_insert(stmt, path, original_text, catalog)
    if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":
        if isinstance(stmt.expression, exp.Subquery):
            return _parse_ctas(stmt, path, original_text, catalog)
    if isinstance(stmt, exp.Delete):
        return _parse_delete(stmt, path, original_text)
    return None


def _parse_insert(stmt: exp.Insert, path: str, original_text: str,
                  catalog: dict[str, Any]) -> dict[str, Any]:
    target = _table_name(stmt.this)

    explicit_cols: list[str] = []
    if hasattr(stmt, "expressions") and stmt.expressions:
        explicit_cols = [str(c).lower().strip('"') for c in stmt.expressions]

    select_stmt = stmt.expression
    if isinstance(select_stmt, exp.Subquery):
        select_stmt = select_stmt.this

    # WITH 子句可能在 Insert 上，也可能在 Select 上
    ctes = _collect_ctes(stmt)
    ctes.update(_collect_ctes(select_stmt))

    return _build_operation(
        op_type="insert_select",
        target=target,
        select_stmt=select_stmt,
        explicit_cols=explicit_cols,
        ctes=ctes,
        path=path,
        original_text=original_text,
        catalog=catalog,
    )


def _parse_ctas(stmt: exp.Create, path: str, original_text: str,
                catalog: dict[str, Any]) -> dict[str, Any]:
    target = _table_name(stmt.this) if hasattr(stmt.this, "name") else str(stmt.this).lower()
    select_stmt = stmt.expression
    if isinstance(select_stmt, exp.Subquery):
        select_stmt = select_stmt.this

    ctes = _collect_ctes(select_stmt)

    return _build_operation(
        op_type="ctas",
        target=target,
        select_stmt=select_stmt,
        explicit_cols=[],
        ctes=ctes,
        path=path,
        original_text=original_text,
        catalog=catalog,
    )


def _parse_delete(stmt: exp.Delete, path: str, original_text: str) -> dict[str, Any]:
    target = _table_name(stmt.this)
    where_exp = stmt.args.get("where")
    where_clause = str(where_exp.this) if where_exp else None
    line = _find_line_number(stmt, original_text)

    return {
        "type": "delete",
        "target": target,
        "sources": [],
        "columns": [],
        "projections": [],
        "metric_projections": [],
        "group_by": [],
        "where": where_clause.strip() if where_clause else None,
        "file": path,
        "line": line,
        "confidence": 0.95,
        "parse_source": "sqlglot_ast",
    }


# --- 操作构建 ---

def _build_operation(
    op_type: str,
    target: str,
    select_stmt: exp.Select,
    explicit_cols: list[str],
    ctes: dict[str, exp.CTE],
    path: str,
    original_text: str,
    catalog: dict[str, Any],
) -> dict[str, Any]:

    if not isinstance(select_stmt, exp.Select):
        line = _find_line_number(select_stmt, original_text)
        return {
            "type": op_type,
            "target": target,
            "sources": [],
            "columns": [],
            "projections": [],
            "metric_projections": [],
            "group_by": [],
            "where": None,
            "file": path,
            "line": line,
            "confidence": 0.5,
            "parse_source": "regex_fallback",
        }

    # 表级源
    source_tables = _collect_source_tables(select_stmt, ctes, target)

    # 字段级血缘（穿透 CTE）
    col_edges, projections = _build_column_lineage(
        select_stmt=select_stmt,
        target=target,
        explicit_cols=explicit_cols,
        ctes=ctes,
        source_tables=source_tables,
        path=path,
        original_text=original_text,
        catalog=catalog,
    )

    # 收集所有投影（包括 CTE 中的聚合，用于指标识别）
    metric_projections = list(projections)
    for cte in ctes.values():
        cte_sel = cte.this
        if isinstance(cte_sel, exp.Subquery):
            cte_sel = cte_sel.this
        if isinstance(cte_sel, exp.Select):
            for proj in cte_sel.expressions:
                s = str(proj)
                if s not in metric_projections:
                    metric_projections.append(s)

    # GROUP BY
    group_by = []
    group_exp = select_stmt.args.get("group")
    if group_exp:
        for ge in group_exp.expressions:
            group_by.append(str(ge))

    # WHERE
    where_exp = select_stmt.args.get("where")
    where_clause = str(where_exp.this) if where_exp else None

    line = _find_line_number(select_stmt, original_text)

    return {
        "type": op_type,
        "target": target,
        "sources": source_tables,
        "columns": col_edges,
        "projections": projections,
        "metric_projections": metric_projections,
        "group_by": group_by,
        "where": where_clause.strip() if where_clause else None,
        "file": path,
        "line": line,
        "confidence": 0.95,
        "parse_source": "sqlglot_ast",
    }


# --- CTE 收集 ---

def _collect_ctes(stmt: exp.Expression) -> dict[str, exp.CTE]:
    """从语句中收集所有 CTE（处理 with_ / with 两种属性名）。"""
    ctes: dict[str, exp.CTE] = {}
    if stmt is None:
        return ctes

    current = stmt
    while True:
        with_clause = None
        if isinstance(current, exp.Select):
            with_clause = current.args.get("with_") or current.args.get("with")
        else:
            with_clause = current.args.get("with_") or current.args.get("with")

        if not isinstance(with_clause, exp.With):
            break

        for cte in with_clause.expressions:
            if isinstance(cte, exp.CTE):
                name = cte.alias.lower()
                if name not in ctes:
                    ctes[name] = cte

        current = with_clause.this
        if not isinstance(current, (exp.Select, exp.Query)):
            break

    return ctes


# --- 表级血缘 ---

def _collect_source_tables(select_stmt: exp.Select, ctes: dict[str, exp.CTE],
                           target: str) -> list[str]:
    """收集所有物理源表（穿透 CTE、UNION）。"""
    tables: list[str] = []
    seen: set[str] = set()

    def add_table(name: str):
        key = name.lower()
        if key not in seen and key != target.lower():
            seen.add(key)
            tables.append(name.lower())

    def collect_from_select(sel: exp.Select, cte_stack: set[str]):
        from_key = "from_" if "from_" in sel.args else "from"
        from_exp = sel.args.get(from_key)
        if from_exp:
            collect_from_node(from_exp.this, cte_stack)

        for join in sel.args.get("joins", []):
            collect_from_node(join.this, cte_stack)

    def collect_from_node(node: exp.Expression, cte_stack: set[str]):
        if isinstance(node, exp.Table):
            name = _table_name(node)
            key = name.lower()
            if key in ctes:
                if key in cte_stack:
                    return
                cte = ctes[key]
                cte_sel = cte.this
                if isinstance(cte_sel, exp.Subquery):
                    cte_sel = cte_sel.this
                if isinstance(cte_sel, exp.Select):
                    collect_from_select(cte_sel, cte_stack | {key})
                # 处理 UNION
                for union in cte_sel.find_all(exp.Union) if hasattr(cte_sel, "find_all") else []:
                    if isinstance(union, exp.Union):
                        if hasattr(union, "left") and isinstance(union.left, exp.Select):
                            collect_from_select(union.left, cte_stack | {key})
                        if hasattr(union, "right") and isinstance(union.right, exp.Select):
                            collect_from_select(union.right, cte_stack | {key})
            else:
                add_table(name)
        elif isinstance(node, exp.Subquery):
            alias = node.alias
            sel = node.this
            if isinstance(sel, exp.Select):
                collect_from_select(sel, cte_stack)
        elif isinstance(node, exp.Alias):
            collect_from_node(node.this, cte_stack)
        elif isinstance(node, exp.Lateral):
            collect_from_node(node.this, cte_stack)
        elif isinstance(node, exp.Union):
            if hasattr(node, "left") and isinstance(node.left, exp.Select):
                collect_from_select(node.left, cte_stack)
            if hasattr(node, "right") and isinstance(node.right, exp.Select):
                collect_from_select(node.right, cte_stack)
        else:
            for child in node.args.values():
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, exp.Expression):
                            collect_from_node(item, cte_stack)
                elif isinstance(child, exp.Expression):
                    collect_from_node(child, cte_stack)

    # 还要处理 Select 本身是 UNION 的情况
    if isinstance(select_stmt, exp.Union):
        if hasattr(select_stmt, "left") and isinstance(select_stmt.left, exp.Select):
            collect_from_select(select_stmt.left, set())
        if hasattr(select_stmt, "right") and isinstance(select_stmt.right, exp.Select):
            collect_from_select(select_stmt.right, set())
    else:
        collect_from_select(select_stmt, set())

    return tables


# --- 字段级血缘（CTE 穿透） ---

def _build_column_lineage(
    select_stmt: exp.Select,
    target: str,
    explicit_cols: list[str],
    ctes: dict[str, exp.CTE],
    source_tables: list[str],
    path: str,
    original_text: str,
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    构建字段级血缘边。支持穿透 CTE 追溯到物理表列。

    算法：对每个输出列，递归穿过 CTE 找到物理源列。
    """
    col_edges: list[dict[str, Any]] = []
    projections: list[str] = []
    line = _find_line_number(select_stmt, original_text)

    # 目标列名
    target_cols = explicit_cols if explicit_cols else [
        c["name"] for c in catalog.get(target, {}).get("columns", [])
    ]

    for idx, proj in enumerate(select_stmt.expressions):
        proj_str = str(proj)
        projections.append(proj_str)

        # 目标列名
        if isinstance(proj, exp.Alias):
            target_col = proj.alias.lower()
        elif idx < len(target_cols):
            target_col = target_cols[idx].lower()
        else:
            continue

        # 追溯源列（穿透 CTE）
        inner_expr = proj.this if isinstance(proj, exp.Alias) else proj
        source_cols = _trace_column(inner_expr, select_stmt, ctes, source_tables, catalog)

        for src_table, src_col, transform_type in source_cols:
            confidence = 0.95 if transform_type == "direct" else 0.85
            edge = {
                "source": f"{src_table}.{src_col}",
                "target": f"{target}.{target_col}",
                "expression": proj_str.strip(),
                "file": path,
                "line": line,
                "confidence": confidence,
                "transform_type": transform_type,
                "parse_source": "sqlglot_ast",
            }
            if not any(e["source"] == edge["source"] and e["target"] == edge["target"]
                       for e in col_edges):
                col_edges.append(edge)

    # SELECT * 展开
    if any(isinstance(p, exp.Star) for p in select_stmt.expressions):
        for src_table in source_tables:
            src_cols = [c["name"] for c in catalog.get(src_table, {}).get("columns", [])]
            for col_name in src_cols:
                edge = {
                    "source": f"{src_table}.{col_name}",
                    "target": f"{target}.{col_name}",
                    "expression": "SELECT *",
                    "file": path,
                    "line": line,
                    "confidence": 0.65,
                    "transform_type": "star_expansion",
                    "parse_source": "inferred",
                }
                if not any(e["source"] == edge["source"] and e["target"] == edge["target"]
                           for e in col_edges):
                    col_edges.append(edge)

    return col_edges, projections


def _trace_column(
    expr: exp.Expression,
    select_stmt: exp.Select,
    ctes: dict[str, exp.CTE],
    source_tables: list[str],
    catalog: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """
    追溯一个表达式依赖的物理源列。
    返回 [(table, column, transform_type)]
    transform_type: direct / expression / aggregate
    """
    # 检查表达式是否是聚合
    is_agg = _has_aggregate(expr)
    base_transform = "aggregate" if is_agg else None

    # 收集所有 Column 引用
    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for col in expr.find_all(exp.Column):
        col_name = col.name.lower().strip('"')
        table_part = col.table

        if table_part:
            # 有表前缀
            table_key = table_part.lower().strip('"')
            physical_cols = _resolve_table_column(
                table_key, col_name, select_stmt, ctes, source_tables, catalog)
        else:
            # 无表前缀，尝试从所有源中匹配
            physical_cols = _match_ambiguous_column(
                col_name, select_stmt, ctes, source_tables, catalog)

        for tbl, col_, src_transform in physical_cols:
            key = (tbl.lower(), col_.lower())
            if key in seen:
                continue
            seen.add(key)

            # 组合 transform 类型
            if base_transform == "aggregate":
                final_transform = "aggregate"
            elif base_transform is None and isinstance(expr, exp.Column) and src_transform == "direct":
                final_transform = "direct"
            else:
                final_transform = src_transform if src_transform != "direct" else "expression"

            results.append((tbl.lower(), col_.lower(), final_transform))

    return results


def _resolve_table_column(
    table_key: str,
    col_name: str,
    select_stmt: exp.Select,
    ctes: dict[str, exp.CTE],
    source_tables: list[str],
    catalog: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """
    解析 table.column 引用，穿透 CTE 找到物理源列。
    """
    # 1. 检查 FROM/JOIN 中的别名
    from_tables = _get_from_tables(select_stmt)
    for tname, talias in from_tables:
        if talias and talias.lower() == table_key:
            # 别名指向的是 CTE 还是物理表？
            return _resolve_source_column(tname, col_name, ctes, source_tables, catalog)
        if not talias and tname.lower() == table_key:
            return _resolve_source_column(tname, col_name, ctes, source_tables, catalog)

    # 2. 直接匹配物理表名
    for st in source_tables:
        if st.lower() == table_key or st.lower().endswith("." + table_key):
            cols = [c["name"] for c in catalog.get(st, {}).get("columns", [])]
            if col_name in cols:
                return [(st, col_name, "direct")]

    # 3. 可能是 CTE 名（当 FROM 中用了 CTE 但没别名）
    if table_key in ctes:
        return _resolve_cte_column(table_key, col_name, ctes, source_tables, catalog)

    return []


def _resolve_source_column(
    name: str,
    col_name: str,
    ctes: dict[str, exp.CTE],
    source_tables: list[str],
    catalog: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """
    解析一个源名（可能是物理表或 CTE）+ 列名，找到物理源列。
    """
    key = name.lower()
    if key in ctes:
        return _resolve_cte_column(key, col_name, ctes, source_tables, catalog)

    # 物理表
    for st in source_tables:
        if st.lower() == key or st.lower().endswith("." + key):
            cols = [c["name"] for c in catalog.get(st, {}).get("columns", [])]
            if col_name in cols:
                return [(st, col_name, "direct")]
            # 列不在 catalog 里（可能 catalog 不全），也返回一条
            return [(st, col_name, "direct")]

    return []


def _resolve_cte_column(
    cte_name: str,
    col_name: str,
    ctes: dict[str, exp.CTE],
    source_tables: list[str],
    catalog: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """
    穿透 CTE：找到 CTE 输出列对应的源表达式，再递归追溯。
    """
    cte = ctes.get(cte_name.lower())
    if not cte:
        return []

    cte_sel = cte.this
    if isinstance(cte_sel, exp.Subquery):
        cte_sel = cte_sel.this
    if not isinstance(cte_sel, exp.Select):
        return []

    # 在 CTE 的输出投影中找到对应列的表达式
    cte_inner_ctes = _collect_ctes(cte_sel)
    all_ctes = {**ctes, **cte_inner_ctes}

    for proj in cte_sel.expressions:
        proj_name = None
        proj_expr = proj

        if isinstance(proj, exp.Alias):
            proj_name = proj.alias.lower()
            proj_expr = proj.this
        elif isinstance(proj, exp.Column):
            proj_name = proj.name.lower()
        elif isinstance(proj, exp.Star):
            continue  # * 后面单独处理

        if proj_name == col_name.lower():
            # 找到了，递归追溯这个表达式
            return _trace_column(proj_expr, cte_sel, all_ctes, source_tables, catalog)

    # SELECT * 的 CTE，展开 *
    has_star = any(isinstance(p, exp.Star) for p in cte_sel.expressions)
    if has_star:
        cte_sources = _collect_source_tables(cte_sel, all_ctes, "")
        for st in cte_sources:
            cols = [c["name"] for c in catalog.get(st, {}).get("columns", [])]
            if col_name in cols:
                return [(st, col_name, "direct")]

    return []


def _match_ambiguous_column(
    col_name: str,
    select_stmt: exp.Select,
    ctes: dict[str, exp.CTE],
    source_tables: list[str],
    catalog: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """没有表前缀的列，尝试匹配唯一源。"""
    matches = []
    for st in source_tables:
        cols = [c["name"] for c in catalog.get(st, {}).get("columns", [])]
        if col_name in cols:
            matches.append((st, col_name, "direct"))

    # 只有一个匹配才返回（多源同名列不猜）
    if len(matches) == 1:
        return matches
    return []


def _get_from_tables(sel: exp.Select) -> list[tuple[str, str]]:
    """获取 FROM/JOIN 中的 (表名, 别名) 列表。"""
    result = []

    def collect(node):
        if isinstance(node, exp.Table):
            name = _table_name(node)
            alias = node.alias or ""
            result.append((name, alias))
        elif isinstance(node, exp.Subquery):
            alias = node.alias or ""
            result.append((f"<subquery:{alias}>", alias))
        elif isinstance(node, exp.Alias):
            collect(node.this)
        else:
            for child in node.args.values():
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, exp.Expression):
                            collect(item)
                elif isinstance(child, exp.Expression):
                    collect(child)

    from_key = "from_" if "from_" in sel.args else "from"
    from_exp = sel.args.get(from_key)
    if from_exp:
        collect(from_exp.this)

    for join in sel.args.get("joins", []):
        collect(join.this)

    return result


# --- 工具函数 ---

def _has_aggregate(expr: exp.Expression) -> bool:
    """检查表达式是否包含聚合函数。"""
    # 用 is_aggregate 属性（SQLGlot 所有聚合函数都标了这个）
    for node in expr.find_all(exp.Func):
        if getattr(node, "is_aggregate", False):
            return True
    # 显式检查常见类型作为兜底
    common_aggs = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max,
                   exp.PercentileDisc, exp.PercentileCont,
                   exp.Stddev, exp.Variance)
    for node in expr.find_all(exp.Expression):
        if isinstance(node, common_aggs):
            return True
    return False


def _table_name(node: exp.Table) -> str:
    """从 Table 节点提取标准化表名。"""
    parts: list[str] = []
    if hasattr(node, "catalog") and node.catalog:
        parts.append(str(node.catalog).lower())
    if hasattr(node, "db") and node.db:
        parts.append(str(node.db).lower())
    if hasattr(node, "name") and node.name:
        parts.append(str(node.name).lower())
    if not parts:
        return str(node).lower()
    return ".".join(parts)


def _find_line_number(stmt: exp.Expression, text: str) -> int:
    """估算语句在原文中的行号。"""
    sql_str = str(stmt).strip()
    # 取前 40 个非空白字符作为关键词
    chars = []
    for ch in sql_str:
        if not ch.isspace():
            chars.append(ch)
        if len(chars) >= 40:
            break
    keyword = "".join(chars)
    if not keyword:
        return 1
    # 搜索关键词（允许中间有空白）
    pattern = r"\s*".join(re.escape(c) for c in keyword)
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return line_number(text, m.start())
    return 1
