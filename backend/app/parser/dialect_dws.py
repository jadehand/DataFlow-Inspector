"""
GaussDB(DWS) 方言适配。

DWS 是 PostgreSQL 的衍生方言，大部分语法 SQLGlot 的 postgres 方言可以直接处理。
本模块负责预处理 DWS 专有语法，使其能被 SQLGlot 正确解析，
同时提取 DWS 特有的信息（分布键、分区策略、存储参数等）。

处理策略：
1. 预处理：把 DWS 特有语法转换/移除，生成 SQLGlot 可解析的形式
2. 解析：用 SQLGlot postgres 方言解析
3. 后处理：把提取的 DWS 信息回填到解析结果中
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DWSTableInfo:
    """从 DDL 中提取的 DWS 特有表信息。"""

    distribute_type: str | None = None   # HASH / REPLICATION / ROUNDROBIN
    distribute_columns: list[str] = field(default_factory=list)
    partition_type: str | None = None    # RANGE / LIST / HASH (DWS 主要用 RANGE)
    partition_columns: list[str] = field(default_factory=list)
    storage_params: dict[str, str] = field(default_factory=dict)  # orientation, compression 等
    on_commit: str | None = None         # PRESERVE ROWS / DELETE ROWS 等


# --- DDL 预处理 ---
#
# DWS 的 CREATE TABLE 尾部通常长这样（顺序不固定）：
#   CREATE TABLE t (...)
#     WITH (orientation=column, ...)
#     DISTRIBUTE BY HASH(col)
#     PARTITION BY RANGE (col) (START ... END ... EVERY ...)
#     TABLESPACE xxx;
#
# 我们用"语句尾部扫描"的方式：从最后一个右括号（字段列表结束）开始，
# 往分号方向扫描，逐个识别并移除 DWS 专有子句。


def _find_create_table_body_end(sql: str) -> int | None:
    """
    找到 CREATE TABLE 字段列表的最后一个右括号位置。
    即 CREATE TABLE name ( ... ) 的匹配闭合括号位置。
    """
    m = re.search(r'CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[^\s(]+\s*\(',
                  sql, re.IGNORECASE)
    if not m:
        return None
    pos = m.end() - 1  # 指向开括号
    depth = 0
    in_string = None
    i = pos
    while i < len(sql):
        ch = sql[i]
        if in_string:
            if ch == in_string:
                if i + 1 < len(sql) and sql[i + 1] == in_string:
                    i += 1
                else:
                    in_string = None
        elif ch in "'\"`":
            in_string = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _scan_trailing_clauses(sql: str, body_end: int) -> list[tuple[str, int, int]]:
    """
    从 body_end 开始扫描到语句结束或分号，识别 DWS 专有子句。
    返回 [(clause_type, start, end)] 列表。

    能识别的子句：
    - WITH (...)           → storage
    - DISTRIBUTE BY ...    → distribute
    - PARTITION BY ... (...)  → partition
    - ON COMMIT ...        → on_commit
    - TABLESPACE ...       → tablespace (忽略，SQLGlot 支持)
    """
    tail = sql[body_end + 1:]
    clauses = []
    pos = 0

    # 关键字列表，按字母排序便于维护
    keywords = [
        ("WITH", "storage"),
        ("DISTRIBUTE", "distribute"),
        ("PARTITION", "partition"),
        ("ON", "on_commit"),
        ("TABLESPACE", "tablespace"),
    ]

    while pos < len(tail):
        # 跳过空白
        if tail[pos] in ' \t\n\r':
            pos += 1
            continue
        # 遇到分号，结束
        if tail[pos] == ';':
            break

        matched = False
        # 尝试匹配各个关键字
        upper_tail = tail[pos:pos + 15].upper()
        for kw, ctype in keywords:
            if upper_tail.startswith(kw + ' ') or upper_tail.startswith(kw + '\n') or upper_tail.startswith(kw + '\t'):
                # 找到子句结束位置（下一个关键字或分号）
                clause_start = pos
                clause_end = _find_clause_end(tail, pos + len(kw))
                # 计算在原始 sql 中的位置
                abs_start = body_end + 1 + clause_start
                abs_end = body_end + 1 + clause_end
                clauses.append((ctype, abs_start, abs_end))
                pos = clause_end
                matched = True
                break

        if not matched:
            # 无法识别的内容，跳过一个字符继续
            pos += 1

    return clauses


def _find_clause_end(tail: str, start: int) -> int:
    """找到一个子句的结束位置（下一个顶级关键字或分号）。"""
    pos = start
    depth = 0
    in_string = None

    # 先跳过关键字后面的空格和 BY 等
    while pos < len(tail) and tail[pos] in ' \t\n\r':
        pos += 1
    if tail[pos:pos + 2].upper() == 'BY':
        pos += 2
    while pos < len(tail) and tail[pos] in ' \t\n\r':
        pos += 1

    # 然后一直扫描到下一个顶级关键字或分号
    while pos < len(tail):
        ch = tail[pos]

        if in_string:
            if ch == in_string:
                if pos + 1 < len(tail) and tail[pos + 1] == in_string:
                    pos += 1
                else:
                    in_string = None
            pos += 1
            continue

        if ch in "'\"`":
            in_string = ch
            pos += 1
            continue

        if ch == '(':
            depth += 1
            pos += 1
            continue
        if ch == ')':
            depth -= 1
            pos += 1
            continue

        if depth == 0:
            # 检查是否遇到分号
            if ch == ';':
                return pos
            # 检查是否遇到下一个关键字
            remaining = tail[pos:pos + 15]
            upper = remaining.upper()
            if any(upper.startswith(kw + ' ') or upper.startswith(kw + '\n') or upper.startswith(kw + '\t')
                   for kw in ('WITH', 'DISTRIBUTE', 'PARTITION', 'ON ', 'TABLESPACE')):
                # 注意：'ON ' 要带空格，避免匹配 ONE 之类
                return pos

        pos += 1

    return len(tail)


def extract_dws_info(sql: str) -> tuple[str, DWSTableInfo]:
    """
    从 DDL SQL 中提取 DWS 特有信息，并返回清理后的 SQL + 提取的信息。

    清理原则：
    - 移除 SQLGlot 无法解析的 DWS 专有语法
    - 保留表结构、字段、约束等核心内容
    - 提取的信息存入 DWSTableInfo

    注意：只处理单条 CREATE TABLE 语句。多条语句在外部循环调用。
    """
    info = DWSTableInfo()
    cleaned = sql

    body_end = _find_create_table_body_end(cleaned)
    if body_end is None:
        return cleaned, info

    clauses = _scan_trailing_clauses(cleaned, body_end)

    # 从后往前移除（避免位置偏移）
    for ctype, start, end in reversed(clauses):
        clause_text = cleaned[start:end]
        upper = clause_text.upper()

        if ctype == "distribute":
            if "HASH" in upper:
                info.distribute_type = "HASH"
                m = re.search(r'HASH\s*\(([^)]+)\)', clause_text, re.I)
                if m:
                    cols = [c.strip().strip('"').lower() for c in m.group(1).split(',') if c.strip()]
                    info.distribute_columns = cols
            elif "REPLICATION" in upper:
                info.distribute_type = "REPLICATION"
            elif "ROUNDROBIN" in upper:
                info.distribute_type = "ROUNDROBIN"

        elif ctype == "partition":
            if "RANGE" in upper:
                info.partition_type = "RANGE"
            elif "LIST" in upper:
                info.partition_type = "LIST"
            elif "HASH" in upper:
                info.partition_type = "HASH"
            else:
                info.partition_type = "RANGE"
            m = re.search(r'(?:BY\s+(?:RANGE|LIST|HASH)\s*)?\(([^)]+)\)', clause_text, re.I)
            if m:
                cols = [c.strip().strip('"').lower() for c in m.group(1).split(',') if c.strip()]
                info.partition_columns = cols

        elif ctype == "storage":
            m = re.search(r'WITH\s*\(\s*([^)]+?)\s*\)', clause_text, re.I | re.S)
            if m:
                params_raw = m.group(1)
                for pair in re.split(r',\s*', params_raw):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        info.storage_params[k.strip().lower()] = v.strip().strip("'\"")

        elif ctype == "on_commit":
            m = re.search(r'ON\s+COMMIT\s+(PRESERVE\s+ROWS|DELETE\s+ROWS|DROP)', clause_text, re.I)
            if m:
                info.on_commit = m.group(1).upper().replace(' ', '_')

        # TABLESPACE 子句：SQLGlot 支持，不移除

        # 移除子句（连同前面的空白）
        while start > 0 and cleaned[start - 1] in ' \t\n\r':
            start -= 1
        cleaned = cleaned[:start] + cleaned[end:]

    return cleaned, info


# --- SQL 预处理（DML 中的 DWS 特有语法） ---

# ::BIGINT 等 PostgreSQL 风格类型转换 SQLGlot 原生支持，不用处理
# DATE_ADD(...) SQLGlot 也支持
# SPLIT_PART(...) SQLGlot 支持
# PERCENTILE_DISC(...), WITHIN GROUP (...) SQLGlot 支持

# DWS 特有的一些函数可以在这里做别名映射
_DWS_FUNCTION_ALIASES = {
    # 目前 SQLGlot 已覆盖大部分常用 DWS 函数
    # 遇到解析失败的函数再在这里添加映射
}


def preprocess_dml(sql: str) -> str:
    """
    DML 语句预处理，把 DWS 特有的语法转换为 SQLGlot 可解析的形式。

    当前 DWS 的 DML 和 PostgreSQL 高度兼容，多数场景无需处理。
    这里预留扩展点。
    """
    return sql


def get_dialect() -> str:
    """返回 SQLGlot 使用的方言名。"""
    return "postgres"
