# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""终端展示格式化工具."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


def event_prefix(event: str) -> str:
    return event.replace(".", ":")


def format_event_line(event: str, message: str = "",
                      fields: dict[str, Any] | None = None) -> str:
    fields = fields or {}
    bits = [f"[{event_prefix(event)}]"]
    if message:
        bits.append(str(message))
    for key in ("card", "round", "role", "result", "decision",
                "score", "attempts", "cards", "remaining", "failure_reason",
                "error"):
        if key in fields and fields[key] not in (None, ""):
            bits.append(f"{key}={fields[key]}")
    return " ".join(bits)


def plan_counts(plan) -> dict[str, int]:
    counts: dict[str, int] = {}
    for todo in plan.todos:
        counts[todo.status] = counts.get(todo.status, 0) + 1
    return counts


def format_plan_summary(plan) -> str:
    counts = plan_counts(plan)
    body = " ".join(f"{key}={counts.get(key, 0)}"
                    for key in ("done", "failed", "in_progress",
                                "pending", "skipped"))
    return f"[plan:updated] {body}"


def todos_as_dicts(plan) -> list[dict]:
    return [asdict(todo) for todo in plan.todos]
