# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""上下文压缩: 轮次记录 -> 紧凑摘要(确定性提取式, 零 LLM 成本).

压缩策略说明: 中档模型管线里, 用 LLM 做摘要会引入二次幻觉与额外成本,
因此压缩一律是提取式 —— 取裁决结论、被采纳指令、最高严重度 issue,
丢弃原始长文。需要完整现场时去 reviews/<卡>/round-N.json 查档。
"""

from __future__ import annotations


def summarize_round(record: dict, max_chars: int) -> str:
    """单轮记录 -> 一段摘要: 裁决 + 采纳指令 + 高严重度 issue."""
    if max_chars <= 0:
        raise ValueError("摘要预算必须为正")
    verdict = record.get("verdict", {}) or {}
    round_no = record.get("round", "?")
    decision = verdict.get("decision", "?")
    score = record.get("score")
    head = (f"[第{round_no}轮] 裁决={decision}"
            + (f" 均分={score:.2f}" if isinstance(score, (int, float)) else ""))

    accepted = [d.get("instruction", "")[:80]
                for d in verdict.get("directives", [])
                if d.get("action") == "accept" and d.get("instruction")]
    severe = [i.get("claim", "")[:60]
              for i in record.get("open_issues", [])
              if i.get("severity") in {"blocking", "major"}]

    lines = [head]
    if accepted:
        lines.append("采纳指令: " + "; ".join(accepted[:3]))
    if severe:
        lines.append("高严重度问题: " + "; ".join(severe[:3]))
    rationale = str(verdict.get("rationale", "")).strip()
    if rationale:
        lines.append("理由: " + rationale[:120])

    out = "\n".join(lines)
    return out if len(out) <= max_chars else out[:max_chars] + "…"


def compress_history(records: list[dict], per_round_chars: int) -> str:
    """多轮记录 -> 摘要序列(旧轮在前); 空记录返回空串."""
    return "\n".join(summarize_round(r, per_round_chars)
                     for r in records if isinstance(r, dict))
