# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM 管理: OpenAI 兼容端点客户端 + 路由/重试/JSON 修复/缓存/预算.

设计要点:
- 模型只做"prompt 进、JSON 出"的纯函数; 无会话状态, 无工具调用;
- 响应按 prompt 哈希落盘缓存 → 重跑幂等且省钱;
- 成本记账到 (slot, purpose) 粒度, 超预算抛 BudgetExceeded 终止本次 run。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from ..core.cards import atomic_write
from ..core.config import ModelsCfg, SettingsCfg, SlotCfg

T = TypeVar("T", bound=BaseModel)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class BudgetExceeded(RuntimeError):
    """单次 run 的 token/费用封顶触发."""


class LLMError(RuntimeError):
    """重试与修复都失败后的最终错误."""


@dataclass
class Usage:
    in_tokens: int = 0
    out_tokens: int = 0
    usd: float = 0.0
    cached: bool = False


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

    def add(self, slot: str, purpose: str, u: Usage) -> None:
        self.calls += 1
        if u.cached:
            self.cache_hits += 1
        self.total_usd += u.usd
        self.total_tokens += u.in_tokens + u.out_tokens
        self.entries.append({"ts": time.time(), "slot": slot,
                             "purpose": purpose, "in": u.in_tokens,
                             "out": u.out_tokens, "usd": round(u.usd, 6),
                             "cached": u.cached})
        if self.total_usd > self.max_usd or self.total_tokens > self.max_tokens:
            raise BudgetExceeded(
                f"预算触顶: ${self.total_usd:.3f}/{self.max_usd} "
                f"或 {self.total_tokens}/{self.max_tokens} tokens")


def extract_json(text: str) -> str:
    """从模型输出提取 JSON: 优先代码围栏, 其次首个平衡花括号块."""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("输出中无 JSON 对象")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("JSON 花括号不平衡")


class LLMClient:
    """带缓存与预算的同步客户端. fake provider 由 roles 层处理, 不进此类."""

    def __init__(self, models: ModelsCfg, settings: SettingsCfg,
                 cache_dir: Path, meter: Optional[CostMeter] = None):
        self.models = models
        self.cache_dir = cache_dir
        self.meter = meter or CostMeter(settings.max_run_usd,
                                        settings.max_run_tokens)
        self._sdk_clients: dict[str, object] = {}

    # ---------- 内部 ----------

    def _sdk(self, slot: SlotCfg):
        if slot.provider == "fake":
            raise LLMError("provider=fake 的模型位只能配合 --fake 模式使用")
        key = f"{slot.base_url}|{slot.api_key_env}"
        if key not in self._sdk_clients:
            from openai import OpenAI  # 延迟导入: dry-run/测试不需要
            api_key = os.environ.get(slot.api_key_env, "")
            if not api_key:
                raise LLMError(f"环境变量 {slot.api_key_env} 未设置")
            self._sdk_clients[key] = OpenAI(base_url=slot.base_url,
                                            api_key=api_key)
        return self._sdk_clients[key]

    def _cache_path(self, slot: SlotCfg, system: str, user: str) -> Path:
        h = hashlib.sha256(
            f"{slot.model}\x00{system}\x00{user}".encode()).hexdigest()
        return self.cache_dir / f"{h}.json"

    def _raw_call(self, slot: SlotCfg, system: str, user: str) -> tuple[str, Usage]:
        cache = self._cache_path(slot, system, user)
        if cache.is_file():
            data = json.loads(cache.read_text(encoding="utf-8"))
            return data["text"], Usage(cached=True)
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._sdk(slot).chat.completions.create(
                    model=slot.model,
                    temperature=slot.temperature,
                    max_tokens=slot.max_output_tokens,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}])
                text = resp.choices[0].message.content or ""
                pu = getattr(resp, "usage", None)
                u = Usage(in_tokens=getattr(pu, "prompt_tokens", 0) or 0,
                          out_tokens=getattr(pu, "completion_tokens", 0) or 0)
                u.usd = (u.in_tokens * slot.price_in_per_m
                         + u.out_tokens * slot.price_out_per_m) / 1e6
                atomic_write(cache, json.dumps(
                    {"text": text, "in": u.in_tokens, "out": u.out_tokens},
                    ensure_ascii=False))
                return text, u
            except Exception as e:  # 网络/限流/5xx 指数退避重试
                last_err = e
                time.sleep(2 ** attempt)
        raise LLMError(f"调用失败(3 次重试后): {last_err}")

    # ---------- 对外 ----------

    def complete_json(self, slot_name: str, system: str, user: str,
                      schema: Type[T], purpose: str) -> T:
        """调用并解析为 schema; 解析失败追加错误信息修复重试一次."""
        slot = self.models.slot(slot_name)
        text, usage = self._raw_call(slot, system, user)
        self.meter.add(slot_name, purpose, usage)
        for attempt in (0, 1):
            try:
                return schema.model_validate_json(extract_json(text))
            except (ValueError, ValidationError) as e:
                if attempt == 1:
                    raise LLMError(f"{purpose}: JSON 两次解析失败: {e}")
                repair_user = (f"{user}\n\n你上一次的输出无法解析:\n{text[:2000]}\n"
                               f"错误: {e}\n请只输出符合要求的合法 JSON, 不要任何其他文字。")
                text, usage = self._raw_call(slot, system, repair_user)
                self.meter.add(slot_name, purpose + ".repair", usage)
        raise AssertionError("unreachable")
