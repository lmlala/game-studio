# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""成本计量与预算守卫.

LLM provider 只报告 token 使用量和缓存状态; 本模块负责把 usage 转成
账本条目并执行 run 级预算封顶。这样不同 provider/model 的价格差异
不会污染调用层。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """单次 run 的 token/费用封顶触发."""


@dataclass
class Usage:
    """一次模型调用的用量."""

    in_tokens: int = 0
    out_tokens: int = 0
    usd: float = 0.0
    cached: bool = False
    provider: str = ""
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.in_tokens + self.out_tokens


@dataclass
class CostMeter:
    """run 级累计与预算守卫."""

    max_usd: float
    max_tokens: int
    total_usd: float = 0.0
    total_tokens: int = 0
    calls: int = 0
    cache_hits: int = 0
    entries: list[dict] = field(default_factory=list)

    def add(self, slot: str, purpose: str, usage: Usage) -> None:
        self.calls += 1
        if usage.cached:
            self.cache_hits += 1
        self.total_usd += usage.usd
        self.total_tokens += usage.total_tokens
        self.entries.append({
            "ts": time.time(),
            "slot": slot,
            "purpose": purpose,
            "provider": usage.provider,
            "model": usage.model,
            "in": usage.in_tokens,
            "out": usage.out_tokens,
            "usd": round(usage.usd, 6),
            "cached": usage.cached,
        })
        if self.total_usd > self.max_usd or self.total_tokens > self.max_tokens:
            raise BudgetExceeded(
                f"预算触顶: ${self.total_usd:.3f}/{self.max_usd} "
                f"或 {self.total_tokens}/{self.max_tokens} tokens")
