"""
单表导入 & 自动融合引擎。

支持：
1. DDL + 可选 ETL SQL 一起提交，精确解析血缘关系
2. 冲突检测：同名表已存在时，返回冲突详情让用户选择策略
3. 无 ETL SQL 时：基于字段名/类型/命名规范兜底推测血缘
4. 有 ETL SQL 时：直接从 SQL 解析表级血缘和字段级血缘（无需推断）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .ddl_parser import parse_ddl


# --- 冲突检测 ---

@dataclass
class TableConflict:
    """表冲突详情。"""

    existing_name: str            # 已存在的表全名
    existing_layer: str           # 已有的分层
    existing_column_count: int    # 已存在的列数
    new_column_count: int         # 新表的列数
    common_columns: list[str]     # 同名列
    added_columns: list[str]      # 新表有、旧表没有的列
    removed_columns: list[str]    # 旧表有、新表没有的列
    type_mismatches: list[dict]   # 同名但类型不同的列
    duplicate_source: str         # 来源文件（zip 导入 or 单表导入）
    severity: str = "conflict"    # conflict / similar / new


def check_conflict(table_name: str, columns: list[dict], existing_catalog: dict[str, dict]) -> TableConflict | None:
    """
    检查导入的表是否与现有数据字典冲突。

    匹配规则：
    1. 精确同名 → conflict
    2. 短名相同（schema.table 中 table 部分相同）→ conflict
    3. 完全不冲突 → None
    """
    # 精确匹配
    exact_match = existing_catalog.get(table_name)
    if exact_match:
        return _build_conflict(table_name, exact_match, columns, "exact_match")

    # 短名匹配（去掉 schema 前缀）
    short_name = table_name.split(".")[-1].lower()
    for existing_name, existing_table in existing_catalog.items():
        existing_short = existing_name.split(".")[-1].lower()
        if existing_short == short_name:
            # schema 不同但表名相同——这是不同环境下同名表的场景
            return _build_conflict(existing_name, existing_table, columns, f"same_name_diff_schema({table_name} vs {existing_name})")

    return None


def _build_conflict(
    existing_name: str,
    existing_table: dict,
    new_columns: list[dict],
    match_type: str,
) -> TableConflict:
    """构建冲突详情对象。"""
    existing_cols = {c["name"].lower(): c for c in existing_table.get("columns", [])}
    new_cols = {c["name"].lower(): c for c in new_columns}

    common = sorted(set(existing_cols) & set(new_cols))
    added = sorted(set(new_cols) - set(existing_cols))
    removed = sorted(set(existing_cols) - set(new_cols))

    type_mismatches = []
    for col_name in common:
        old_type = existing_cols[col_name].get("type", "").upper()
        new_type = new_cols[col_name].get("type", "").upper()
        if old_type != new_type:
            type_mismatches.append({
                "column": col_name,
                "old_type": old_type,
                "new_type": new_type,
            })

    return TableConflict(
        existing_name=existing_name,
        existing_layer=existing_table.get("layer", "OTHER"),
        existing_column_count=len(existing_cols),
        new_column_count=len(new_cols),
        common_columns=common,
        added_columns=added,
        removed_columns=removed,
        type_mismatches=type_mismatches,
        duplicate_source=match_type,
        severity="conflict" if common else "similar",
    )


# --- 关系推断 ---

@dataclass
class InferredRelationship:
    """推断的表间关系。"""

    source_table: str
    target_table: str
    matched_columns: list[dict]   # [{source_col, target_col, match_type}]
    confidence: float
    inference_method: str         # "column_name_match" | "naming_convention" | "data_type_compat"


def infer_relationships(
    new_table_name: str,
    new_columns: list[dict],
    existing_catalog: dict[str, dict],
    min_confidence: float = 0.5,
) -> list[InferredRelationship]:
    """
    基于字段名和类型，推断新表与现有表之间可能的关系。

    推断策略（按置信度排序）：
    1. 命名层级关系：ODS -> DWD -> DWS -> ADS 的同名前缀
    2. 字段名强匹配：大量同名字段（>= 50% 匹配）
    3. 主键/外键匹配：_id 后缀字段匹配
    4. 类型兼容性：TIMESTAMP ↔ DATE 等
    """
    from .regex_fallback import layer_of

    relationships: list[InferredRelationship] = []

    new_layer = layer_of(new_table_name)
    new_col_names = {c["name"].lower() for c in new_columns}
    new_col_types = {c["name"].lower(): c.get("type", "") for c in new_columns}

    for existing_name, existing_table in existing_catalog.items():
        if existing_name == new_table_name:
            continue

        existing_layer = existing_table.get("layer", "OTHER")
        existing_columns = existing_table.get("columns", [])
        existing_col_names = {c["name"].lower() for c in existing_columns}
        existing_col_types = {c["name"].lower(): c.get("type", "") for c in existing_columns}

        matched_cols: list[dict] = []
        match_reasons: list[str] = []

        # 策略 1：同名字段匹配
        common = new_col_names & existing_col_names
        for col_name in common:
            reason = "name_match"
            new_type = new_col_types.get(col_name, "")
            old_type = existing_col_types.get(col_name, "")
            if new_type and old_type and new_type.upper() == old_type.upper():
                reason = "name_and_type_match"
            matched_cols.append({
                "source_col": f"{existing_name}.{col_name}",
                "target_col": f"{new_table_name}.{col_name}",
                "match_type": reason,
            })
            match_reasons.append("column_name_match")

        # 策略 2：_id 后缀匹配（JOIN 键关系）
        id_cols_new = {c for c in new_col_names if c.endswith("_id")}
        id_cols_existing = {c for c in existing_col_names if c.endswith("_id")}
        id_common = id_cols_new & id_cols_existing
        for col_name in id_common:
            if not any(m["target_col"] == f"{new_table_name}.{col_name}" for m in matched_cols):
                matched_cols.append({
                    "source_col": f"{existing_name}.{col_name}",
                    "target_col": f"{new_table_name}.{col_name}",
                    "match_type": "join_key_match",
                })
        if id_common:
            match_reasons.append("join_key_match")

        # 策略 3：命名层级关系（同名不同层）
        new_short = new_table_name.split(".")[-1].lower()
        existing_short = existing_name.split(".")[-1].lower()
        shared_stem = _common_stem(new_short, existing_short)
        if shared_stem and shared_stem not in new_col_names and len(shared_stem) >= 5:
            match_reasons.append("naming_convention")
            if not matched_cols:
                # 即使没有具体列匹配，也标记为可能相关
                for col_name in list(new_col_names)[:3]:
                    matched_cols.append({
                        "source_col": f"{existing_name}.{col_name}" if col_name in existing_col_names else None,
                        "target_col": f"{new_table_name}.{col_name}",
                        "match_type": "inferred_from_naming",
                    })

        # 策略 4：明显的父子层级关系
        if new_layer in ("DWD", "DWS", "ADS") and existing_layer in ("ODS", "DWD", "DWS"):
            # 同字根 + 合理分层
            if shared_stem and len(shared_stem) >= 5:
                match_reasons.append("hierarchy")

        if not matched_cols:
            continue

        # 计算置信度
        match_ratio = len(common) / max(len(new_col_names), 1)
        if "naming_convention" in match_reasons:
            confidence = min(0.85, 0.4 + match_ratio * 0.4)
        elif "join_key_match" in match_reasons:
            confidence = min(0.9, 0.5 + match_ratio * 0.3)
        elif match_ratio >= 0.5:
            confidence = min(0.95, 0.6 + match_ratio * 0.3)
        else:
            confidence = min(0.7, 0.3 + match_ratio * 0.4)

        if confidence >= min_confidence:
            relationships.append(InferredRelationship(
                source_table=existing_name,
                target_table=new_table_name,
                matched_columns=matched_cols,
                confidence=round(confidence, 2),
                inference_method="+".join(sorted(set(match_reasons))),
            ))

    # 按置信度排序
    relationships.sort(key=lambda r: -r.confidence)
    return relationships


def _common_stem(a: str, b: str) -> str | None:
    """提取两个表名的共同词干。"""
    # 去掉前后缀（ods_/dwd_/dws_/ads_/dim_）
    def strip_prefix(name: str) -> str:
        for prefix in ("dim_", "ads_", "dws_", "dwd_", "ods_"):
            if name.startswith(prefix):
                return name[len(prefix):]
        return name

    a_strip = strip_prefix(a)
    b_strip = strip_prefix(b)

    # 找最大公共子串
    from difflib import SequenceMatcher
    sm = SequenceMatcher(None, a_strip, b_strip)
    match = sm.find_longest_match(0, len(a_strip), 0, len(b_strip))
    if match.size >= 3:
        return a_strip[match.a:match.a + match.size]
    return None


# --- 单表导入主逻辑 ---

@dataclass
class SingleTableImportResult:
    """单表导入的完整结果。"""

    success: bool
    table_name: str
    action: str                          # "imported" | "replaced" | "merged" | "skipped" | "conflict"
    table_info: dict[str, Any] | None    # 解析后的表信息
    conflict: TableConflict | None       # 冲突详情（如果有）
    table_lineage: list[dict]            # 精确表级血缘（从 ETL SQL 解析）
    column_lineage: list[dict]           # 精确字段血缘（从 ETL SQL 解析）
    inferred_relations: list[InferredRelationship]  # 推断的关系（无 ETL SQL 时作为兜底）
    operations: list[dict]              # 解析出的 DML 操作
    message: str


def import_single_table(
    ddl_text: str,
    project_id: int,
    existing_analysis: dict[str, Any] | None,
    conflict_strategy: str = "check",   # "replace" | "keep" | "merge" | "check"
    etl_sql: str | None = None,
) -> SingleTableImportResult:
    """
    导入单条 CREATE TABLE DDL（及可选的 ETL SQL），融合进现有分析结果。

    三级语义：

    A. DDL + ETL SQL  →  精确：AST 解析血缘，直接入库
    B. 仅 DDL          →  预设"孤立表"：没有来源的叶子节点，等用户后续补充 ETL
    C. 推断            →  仅返回待验证建议（unconfirmed_suggestions），
                          用户确认后传入 strategy="merge_inferred" 才入库

    参数：
        ddl_text:          CREATE TABLE DDL
        project_id:        项目 ID
        existing_analysis: 现有分析数据
        conflict_strategy: 冲突策略
            - "check": 检测冲突 + 返回推断供用户判断；无冲突且无 ETL → 存孤立表
            - "replace" / "keep" / "merge" / "merge_inferred": 执行入库动作
        etl_sql: 加工 SQL（如果有）
    """
    # 1. 解析 DDL
    tables = parse_ddl(ddl_text, "__single_import__")
    if not tables:
        return SingleTableImportResult(
            success=False, table_name="", action="failed",
            table_info=None, conflict=None,
            table_lineage=[], column_lineage=[], inferred_relations=[],
            operations=[],
            message="DDL 解析失败：未识别到有效的 CREATE TABLE 语句。",
        )

    table_info = tables[0]
    table_name = table_info["name"]
    new_columns = table_info["columns"]

    # 2. 构建现有 catalog
    existing_catalog: dict[str, dict] = {}
    if existing_analysis:
        for t in existing_analysis.get("tables", []):
            existing_catalog[t["name"]] = t

    # 2.5 解析 ETL SQL（如果提供了）→ 精确血缘
    parsed_table_edges: list[dict] = []
    parsed_column_edges: list[dict] = []
    parsed_operations: list[dict] = []
    has_etl = bool(etl_sql and etl_sql.strip())
    if has_etl:
        from .sql_parser import parse_sql
        try:
            ddl_catalog = {t["name"]: t for t in tables}
            full_catalog = {**existing_catalog, **ddl_catalog}
            ops = parse_sql(etl_sql, "__single_import_etl__", full_catalog)
            for op in ops:
                parsed_operations.append(op)
                for src in op.get("sources", []):
                    parsed_table_edges.append({
                        "source": src, "target": op["target"],
                        "file": "__single_import_etl__", "line": op.get("line", 0),
                        "operation": op.get("type", "insert_select"),
                        "confidence": op.get("confidence", 0.95),
                        "parse_source": op.get("parse_source", "sqlglot_ast"),
                    })
                for ce in op.get("columns", []):
                    parsed_column_edges.append(ce)
        except Exception:
            pass  # SQL 解析失败不影响 DDL 导入

    # 3. 冲突检测
    conflict = check_conflict(table_name, new_columns, existing_catalog)

    # 4. ==================== check 模式（预检 + 推断供判断） ====================
    if conflict_strategy == "check":
        # 4a. 有冲突 → 返回冲突详情
        if conflict is not None:
            inferred = infer_relationships(table_name, new_columns, existing_catalog)
            return SingleTableImportResult(
                success=False, table_name=table_name, action="conflict",
                table_info=table_info, conflict=conflict,
                table_lineage=parsed_table_edges,
                column_lineage=parsed_column_edges,
                inferred_relations=inferred,
                operations=parsed_operations,
                message=f"表 {table_name} 已存在。请选择处理策略。",
            )

        # 4b. 有 ETL SQL → 精确，可直接导入（但 check 模式不写库，返回给前端确认）
        if has_etl:
            return SingleTableImportResult(
                success=True, table_name=table_name, action="ready_to_import_precise",
                table_info=table_info, conflict=None,
                table_lineage=parsed_table_edges,
                column_lineage=parsed_column_edges,
                inferred_relations=[],
                operations=parsed_operations,
                message=(f"DDL + ETL 已解析：{table_name} ({len(new_columns)} 列)，"
                         f"上游表 {len({e['source'] for e in parsed_table_edges})} 个，"
                         f"字段血缘 {len(parsed_column_edges)} 条。确认后入库。"),
            )

        # 4c. 没有 ETL → 返回推断建议，让用户判断，暂不存孤立表
        inferred = infer_relationships(table_name, new_columns, existing_catalog)
        return SingleTableImportResult(
            success=True, table_name=table_name, action="orphan_pending",
            table_info=table_info, conflict=None,
            table_lineage=[],
            column_lineage=[],
            inferred_relations=inferred,
            operations=[],
            message=(f"表 {table_name} 已解析 ({len(new_columns)} 列)，但未提供 ETL SQL。"
                     f"推断出 {len(inferred)} 条可能关系（待验证）。"
                     f"请选择：1) 确认某个推断关系 2) 补充 ETL SQL 3) 作为孤立表接受"),
        )

    # 5. ==================== 入库动作 ====================

    # 5a. 有 ETL → 精确入库
    # 5b. 无 ETL → 孤立表入库（table_lineage/column_lineage 为空）
    if not conflict:
        # 无 ETL → 孤立表
        if not has_etl:
            # 如果策略是 merge_inferred，使用推断结果
            if conflict_strategy == "merge_inferred":
                inferred = infer_relationships(table_name, new_columns, existing_catalog)
                return SingleTableImportResult(
                    success=True, table_name=table_name, action="imported_inferred",
                    table_info=table_info, conflict=None,
                    table_lineage=[], column_lineage=[], inferred_relations=inferred,
                    operations=[],
                    message=f"表 {table_name} 已作为孤立表导入（{len(new_columns)} 列）。"
                            f"推断关系 {len(inferred)} 条待后续 ETL 验证。",
                )
            # 纯孤立表
            return SingleTableImportResult(
                success=True, table_name=table_name, action="imported_orphan",
                table_info=table_info, conflict=None,
                table_lineage=[], column_lineage=[],
                inferred_relations=[],
                operations=[],
                message=(f"表 {table_name} 已作为孤立表导入（{len(new_columns)} 列）。"
                         f"尚未关联上下游，请补充 ETL SQL 以建立血缘。"),
            )
        # 有 ETL → 精准入库
        return SingleTableImportResult(
            success=True, table_name=table_name, action="imported_precise",
            table_info=table_info, conflict=None,
            table_lineage=parsed_table_edges,
            column_lineage=parsed_column_edges,
            inferred_relations=[],
            operations=parsed_operations,
            message=(f"表 {table_name} ({len(new_columns)} 列) 及其 ETL 已入库。"
                     f"{len(parsed_table_edges)} 条表血缘、{len(parsed_column_edges)} 条字段血缘。"),
        )

    # 6. ==================== 冲突处理策略 ====================
    existing = existing_catalog[conflict.existing_name]

    if conflict_strategy == "replace":
        return SingleTableImportResult(
            success=True, table_name=table_name, action="replaced",
            table_info=table_info, conflict=conflict,
            table_lineage=parsed_table_edges,
            column_lineage=parsed_column_edges,
            inferred_relations=[], operations=parsed_operations,
            message=f"表 {table_name} 已被新定义替换（{conflict.new_column_count} 列）。",
        )

    elif conflict_strategy == "keep":
        return SingleTableImportResult(
            success=True, table_name=table_name, action="skipped",
            table_info=existing, conflict=conflict,
            table_lineage=[], column_lineage=[],
            inferred_relations=[], operations=[],
            message=f"已保留表 {table_name} 的现有定义。",
        )

    elif conflict_strategy == "merge":
        existing_col_names = {c["name"].lower() for c in existing["columns"]}
        merged_columns = list(existing["columns"])
        for col in new_columns:
            if col["name"].lower() not in existing_col_names:
                merged_columns.append(col)
        merged_table = {
            **existing, "columns": merged_columns,
            "confidence": max(existing.get("confidence", 0.5), 0.85),
            "parse_source": "merged_single_import",
        }
        return SingleTableImportResult(
            success=True, table_name=table_name, action="merged",
            table_info=merged_table, conflict=conflict,
            table_lineage=parsed_table_edges,
            column_lineage=parsed_column_edges,
            inferred_relations=[], operations=parsed_operations,
            message=f"表 {table_name} 已合并：新增 {len(merged_columns) - len(existing['columns'])} 列。",
        )

    return SingleTableImportResult(
        success=False, table_name=table_name, action="error",
        table_info=None, conflict=conflict,
        table_lineage=[], column_lineage=[], inferred_relations=[],
        operations=[], message=f"未知的冲突策略: {conflict_strategy}",
    )


# --- 辅助 ---

def merge_table_into_analysis(
    analysis: dict[str, Any],
    table_info: dict[str, Any],
    table_lineage: list[dict],
    column_lineage: list[dict],
    inferred_relations: list[InferredRelationship],
    operations: list[dict],
) -> dict[str, Any]:
    """
    将单表导入结果融合进现有 analysis dict。

    优先级：ETL SQL 解析出的精确血缘 > 推断血缘
    """
    import copy
    result = {k: copy.deepcopy(v) if isinstance(v, list) else v
              for k, v in analysis.items()}

    table_name = table_info["name"]

    # 更新或追加表
    existing_idx = None
    for i, t in enumerate(result["tables"]):
        if t["name"] == table_name:
            existing_idx = i
            break
    if existing_idx is not None:
        result["tables"][existing_idx] = table_info
    else:
        result["tables"].append(table_info)

    # 追加从 ETL SQL 解析出的精确血缘（优先级最高）
    existing_edges = {(e["source"], e["target"]) for e in result.get("table_lineage", [])}
    for edge in table_lineage:
        key = (edge["source"], edge["target"])
        if key not in existing_edges:
            result.setdefault("table_lineage", []).append(edge)
            existing_edges.add(key)

    existing_col_keys = {(e["source"], e["target"]) for e in result.get("column_lineage", [])}
    for ce in column_lineage:
        key = (ce["source"], ce["target"])
        if key not in existing_col_keys:
            result.setdefault("column_lineage", []).append(ce)
            existing_col_keys.add(key)

    # 追加推断的血缘（作为兜底，置信度低于精确解析）
    for rel in inferred_relations:
        key = (rel.source_table, rel.target_table)
        if key not in existing_edges and rel.confidence >= 0.6:
            result.setdefault("table_lineage", []).append({
                "source": rel.source_table,
                "target": rel.target_table,
                "file": "__inferred__",
                "line": 0,
                "operation": "inferred",
                "confidence": rel.confidence,
                "parse_source": "inferred",
                "inference_method": rel.inference_method,
            })
            existing_edges.add(key)
    for rel in inferred_relations:
        for mc in rel.matched_columns:
            key = (mc["source_col"], mc["target_col"])
            if key not in existing_col_keys and mc.get("source_col"):
                result.setdefault("column_lineage", []).append({
                    "source": mc["source_col"],
                    "target": mc["target_col"],
                    "expression": f"inferred from {mc['match_type']}",
                    "file": "__inferred__",
                    "line": 0,
                    "confidence": rel.confidence,
                    "transform_type": "inferred",
                    "parse_source": "inferred",
                })
                existing_col_keys.add(key)

    # 追加 ETL 操作
    existing_ops_signatures = {
        (op.get("type"), op.get("target"), op.get("file"))
        for op in result.get("operations", [])
    }
    for op in operations:
        sig = (op.get("type"), op.get("target"), op.get("file"))
        if sig not in existing_ops_signatures:
            result.setdefault("operations", []).append(op)
            existing_ops_signatures.add(sig)

    # 重算 summary
    result["summary"] = {
        "tables": len(result.get("tables", [])),
        "columns": sum(len(t.get("columns", [])) for t in result.get("tables", [])),
        "table_edges": len(result.get("table_lineage", [])),
        "column_edges": len(result.get("column_lineage", [])),
        "metrics": len(result.get("metrics", [])),
        "risks": len(result.get("risks", [])),
        "jobs": len(result.get("jobs", [])),
    }

    return result
