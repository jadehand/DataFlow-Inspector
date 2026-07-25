"""
置信度 & 证据链模型。

每条解析结论都带置信度和证据来源，便于前端展示和用户判断可信度。

置信度分级（从高到低）：
- confirmed (1.0)      人工确认
- ast_proven (0.95)    AST 直接证明（列级直接映射、表级清晰读写）
- ast_expression (0.85) AST 解析成功，但结果来自表达式转换
- inferred (0.65)      命名/规则推断（如 SELECT * 展开、分层识别）
- regex_fallback (0.5)  正则降级解析（SQLGlot 失败时）
- ai_suggested (0.3)   （预留）AI 建议
"""

from __future__ import annotations

from enum import Enum


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    AST_PROVEN = "ast_proven"
    AST_EXPRESSION = "ast_expression"
    INFERRED = "inferred"
    REGEX_FALLBACK = "regex_fallback"
    AI_SUGGESTED = "ai_suggested"

    @property
    def score(self) -> float:
        return _SCORES[self]

    def __float__(self) -> float:
        return self.score


_SCORES = {
    Confidence.CONFIRMED: 1.0,
    Confidence.AST_PROVEN: 0.95,
    Confidence.AST_EXPRESSION: 0.85,
    Confidence.INFERRED: 0.65,
    Confidence.REGEX_FALLBACK: 0.5,
    Confidence.AI_SUGGESTED: 0.3,
}


class Evidence:
    """证据对象：说明一条结论是怎么来的。"""

    __slots__ = ("source", "file", "line", "detail", "confidence")

    def __init__(
        self,
        source: str,
        file: str | None = None,
        line: int | None = None,
        detail: str | None = None,
        confidence: Confidence = Confidence.AST_PROVEN,
    ):
        self.source = source          # 证据来源："ast" / "regex" / "inference" / "manual"
        self.file = file              # 源文件路径
        self.line = line              # 源文件行号
        self.detail = detail          # 补充说明（SQL 片段、表达式等）
        self.confidence = confidence  # 置信度级别

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "file": self.file,
            "line": self.line,
            "detail": self.detail,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence.score,
        }
