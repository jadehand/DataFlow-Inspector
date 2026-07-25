"""
SQL 解析器包 — 基于 SQLGlot 的 AST 解析引擎。

对外提供与旧版 main.py 中同名函数一致的接口：
- parse_ddl(text, path) -> list[dict]
- parse_sql(text, path, catalog) -> list[dict]
- analyze(dest, files) -> dict

解析失败时自动降级到正则解析（regex_fallback），
确保兼容性的同时逐步升级解析深度。
"""

from __future__ import annotations

from .ddl_parser import parse_ddl
from .sql_parser import parse_sql
from .analyzer import analyze
from .evidence import Confidence, Evidence

__all__ = ["parse_ddl", "parse_sql", "analyze", "Confidence", "Evidence"]
