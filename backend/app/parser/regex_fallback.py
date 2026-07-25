"""
正则解析降级方案 — 旧版 main.py 中的纯正则解析函数。

当 SQLGlot 解析失败时，回退到这些函数，保证：
1. 至少能提取表级血缘（低置信度）
2. 不会因为解析失败而中断导入

这些函数从 main.py 中原封不动搬过来，作为 baseline 参考和降级兜底。
"""

from __future__ import annotations

import re


IDENT = r'(?:"[^"]+"|[A-Za-z_][\w$]*)(?:\.(?:"[^"]+"|[A-Za-z_][\w$]*)){0,2}'


def clean_ident(s: str) -> str:
    return ".".join(x.strip('"').lower() for x in s.strip().split("."))


def split_top(text: str) -> list[str]:
    out, start, depth, quote = [], 0, 0, None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


def layer_of(name: str) -> str:
    base = name.split(".")[-1].lower()
    for layer in ("ods", "dwd", "dws", "ads"):
        if base.startswith(layer + "_") or name.startswith(layer + "."):
            return layer.upper()
    return "SOURCE" if name.startswith("rds.") else "DIM" if name.startswith("dim.") else "OTHER"


def classify_column(name: str, typ: str) -> dict:
    n = name.lower()
    if n in {"dt", "biz_date", "partition_date"}:
        return {"role": "partition_time", "semantic_type": "partition_time", "confidence": .95}
    if any(x in n for x in ("event_time", "request_time")):
        return {"role": "event_time", "semantic_type": "event_time", "confidence": .9}
    if any(x in n for x in ("ingestion_time", "load_time", "create_time")):
        return {"role": "ingestion_time", "semantic_type": "ingestion_time", "confidence": .85}
    if any(x in n for x in ("stat_", "_hour", "_minute")) and ("TIME" in typ or "DATE" in typ):
        return {"role": "stat_time", "semantic_type": "statistical_time", "confidence": .9}
    if n.endswith(("_cnt", "_count", "_amount", "_rate", "_ms", "_tokens")):
        return {"role": "measure", "semantic_type": "metric", "confidence": .85}
    if n.endswith(("_id", "_code", "_name", "_type", "_status", "_tier")):
        return {"role": "dimension", "semantic_type": "dimension", "confidence": .8}
    return {"role": "unknown", "semantic_type": "unknown", "confidence": .35}


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def parse_ddl(text: str, path: str) -> list[dict]:
    """纯正则 DDL 解析（降级用）。"""
    tables = []
    pat = re.compile(rf"CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({IDENT})\s*\(",
                     re.I)
    for m in pat.finditer(text):
        depth, end = 1, m.end()
        while end < len(text) and depth:
            depth += (text[end] == "(") - (text[end] == ")")
            end += 1
        cols = []
        for part in split_top(text[m.end():end - 1]):
            cm = re.match(r'\s*"?([\w$]+)"?\s+([A-Za-z][\w]*(?:\s*\([^)]*\))?)', part)
            if not cm or cm.group(1).upper() in {"PRIMARY", "UNIQUE", "CONSTRAINT", "DISTRIBUTE", "PARTITION"}:
                continue
            name, typ = cm.group(1).lower(), re.sub(r"\s+", " ", cm.group(2)).upper()
            role = classify_column(name, typ)
            cols.append({"name": name, "type": typ, **role})
        tables.append({"name": clean_ident(m.group(1)), "columns": cols, "ddl_file": path,
                       "layer": layer_of(clean_ident(m.group(1)))})
    return tables


def matching_paren(text: str, opening: int) -> int | None:
    depth, quote, i = 0, None, opening
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def cte_definitions(stmt: str) -> dict[str, str]:
    match = re.search(r"\bWITH\b", stmt, re.I)
    if not match:
        return {}
    out: dict[str, str] = {}
    pos = match.end()
    while pos < len(stmt):
        name_match = re.match(r'\s*,?\s*"?([A-Za-z_]\w*)"?\s+AS\s*\(', stmt[pos:], re.I)
        if not name_match:
            break
        name = name_match.group(1).lower()
        opening = pos + name_match.end() - 1
        closing = matching_paren(stmt, opening)
        if closing is None:
            break
        out[name] = stmt[opening + 1:closing]
        pos = closing + 1
        if not re.match(r"\s*,", stmt[pos:]):
            break
    return out


def parse_sql(text: str, path: str, catalog: dict[str, dict]) -> list[dict]:
    """纯正则 SQL 解析（降级用）。"""
    operations = []
    sql = re.sub(r"--[^\n]*", "", text)
    target_matches = list(re.finditer(rf"\bINSERT\s+INTO\s+({IDENT})", sql, re.I))
    target_matches += list(re.finditer(rf"\bCREATE\s+TABLE\s+({IDENT})\s+AS\b", sql, re.I))
    for tm in sorted(target_matches, key=lambda x: x.start()):
        target = clean_ident(tm.group(1))
        stmt_start = sql.rfind(";", 0, tm.start()) + 1
        stmt_end = sql.find(";", tm.end())
        stmt_end = len(sql) if stmt_end < 0 else stmt_end
        stmt = sql[stmt_start:stmt_end]
        local_target_end = tm.end() - stmt_start
        cte_bodies = cte_definitions(stmt)
        ctes = {name: [clean_ident(x) for x in re.findall(
            rf"\b(?:FROM|JOIN)\s+({IDENT})", body, re.I)]
                for name, body in cte_bodies.items()}

        def expand_cte(name: str, stack: set[str] | None = None) -> list[str]:
            stack = set() if stack is None else stack
            if name not in ctes or name in stack:
                return [name]
            resolved: list[str] = []
            for child in ctes[name]:
                for source in expand_cte(child, stack | {name}):
                    if source not in resolved:
                        resolved.append(source)
            return resolved

        sources, aliases = [], {}
        for sm in re.finditer(rf"\b(?:FROM|JOIN)\s+({IDENT})(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?", stmt[local_target_end:], re.I):
            src = clean_ident(sm.group(1))
            if src.upper() in {"SELECT"} or src == target:
                continue
            expanded = expand_cte(src)
            for actual in expanded:
                if actual not in sources:
                    sources.append(actual)
            alias = sm.group(2)
            if alias and alias.upper() not in {"ON", "WHERE", "LEFT", "RIGHT", "FULL", "INNER", "JOIN", "GROUP"}:
                aliases[alias.lower()] = expanded[0]
        select_region = stmt[local_target_end:]
        if cte_bodies:
            last_body = list(cte_bodies.values())[-1]
            body_pos = select_region.find(last_body)
            if body_pos >= 0:
                select_region = select_region[body_pos + len(last_body) + 1:]
        sel = re.search(r"\bSELECT\b(.*?)(?=\bFROM\b)", select_region, re.I | re.S)
        projections = split_top(sel.group(1)) if sel else []
        metric_projections = list(projections)
        for body in cte_bodies.values():
            for cte_select in re.finditer(r"\bSELECT\b(.*?)(?=\bFROM\b)", body, re.I | re.S):
                for expr in split_top(cte_select.group(1)):
                    if expr not in metric_projections:
                        metric_projections.append(expr)
        tcols = [c["name"] for c in catalog.get(target, {}).get("columns", [])]
        target_tail = stmt[local_target_end:]
        explicit_cols = re.match(r'\s*\(([^)]*)\)\s*(?=\bSELECT\b|\bWITH\b)', target_tail, re.I | re.S)
        if explicit_cols:
            tcols = [clean_ident(x).split(".")[-1] for x in split_top(explicit_cols.group(1))]
        col_edges = []
        for idx, expr in enumerate(projections):
            aliasm = re.search(r'\s+AS\s+"?([\w$]+)"?\s*$', expr, re.I)
            target_col = aliasm.group(1).lower() if aliasm else (tcols[idx] if idx < len(tcols) else None)
            if not target_col:
                continue
            refs = re.findall(r'\b([A-Za-z_]\w*)\.("?[\w$]+"?)\b', expr)
            resolved: set[tuple[str, str]] = set()
            for a, col in refs:
                src = aliases.get(a.lower())
                if src:
                    resolved.add((src, col.strip(chr(34)).lower()))
                    col_edges.append({"source": f"{src}.{col.strip(chr(34)).lower()}",
                                      "target": f"{target}.{target_col}", "expression": expr.strip(),
                                      "file": path, "line": line_number(sql, tm.start()), "confidence": .9})
            if len(sources) == 1:
                src = sources[0]
                source_cols = [c["name"] for c in catalog.get(src, {}).get("columns", [])]
                expression_body = re.sub(r'\s+AS\s+"?[\w$]+"?\s*$', "", expr, flags=re.I)
                for col in source_cols:
                    if (src, col) not in resolved and re.search(rf'(?<![\w$])"?{re.escape(col)}"?(?![\w$])',
                                                               expression_body, re.I):
                        col_edges.append({"source": f"{src}.{col}", "target": f"{target}.{target_col}",
                                          "expression": expr.strip(), "file": path,
                                          "line": line_number(sql, tm.start()), "confidence": .85})
        group = re.search(r"\bGROUP\s+BY\b(.*?)(?=\bHAVING\b|\bORDER\s+BY\b|;|$)", stmt[local_target_end:], re.I | re.S)
        where = re.search(r"\bWHERE\b(.*?)(?=\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|;|$)", stmt[local_target_end:], re.I | re.S)
        operations.append({"type": "insert_select" if sql[tm.start():tm.start()+12].upper().startswith("INSERT") else "ctas",
                           "target": target, "sources": sources, "columns": col_edges,
                           "projections": projections, "metric_projections": metric_projections,
                           "group_by": split_top(group.group(1)) if group else [],
                           "where": where.group(1).strip() if where else None, "file": path,
                           "line": line_number(sql, tm.start())})
    for dm in re.finditer(rf"\bDELETE\s+FROM\s+({IDENT})(?:\s+WHERE\s+(.*?))?(?=;|$)", sql, re.I | re.S):
        operations.append({"type": "delete", "target": clean_ident(dm.group(1)), "sources": [],
                           "columns": [], "projections": [], "metric_projections": [], "group_by": [],
                           "where": dm.group(2).strip() if dm.group(2) else None,
                           "file": path, "line": line_number(sql, dm.start())})
    operations.sort(key=lambda op: op["line"])
    return operations
