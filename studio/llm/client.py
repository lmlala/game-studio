# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM 管理 facade: provider 路由 + JSON 解析/修复 + 缓存 + 成本计量.

设计要点:
- 模型只做"prompt 进、JSON 出"的纯函数; 无会话状态, 无工具调用;
- 响应按 prompt 哈希落盘缓存 → 重跑幂等且省钱;
- provider/model 差异放 providers/ 与 models/ registry, 不写死在通用 client。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from ..core.cards import atomic_write
from ..core.config import ModelsCfg, SettingsCfg, SlotCfg
from ..cost import CostMeter, Usage
from .errors import JSONParseError
from .models import ProviderRegistry
from .providers import JsonModePolicy, ProviderResponse

T = TypeVar("T", bound=BaseModel)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


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
    """带缓存与预算的同步客户端; provider 差异由 registry 隔离."""

    def __init__(self, models: ModelsCfg, settings: SettingsCfg,
                 cache_dir: Path, meter: Optional[CostMeter] = None):
        self.models = models
        self.cache_dir = cache_dir
        self.meter = meter or CostMeter(settings.max_run_usd,
                                        settings.max_run_tokens)
        self._providers: dict[str, object] = {}

    # ---------- 内部 ----------

    def _provider(self, slot_name: str, slot: SlotCfg):
        if slot_name not in self._providers:
            self._providers[slot_name] = ProviderRegistry.create(slot)
        return self._providers[slot_name]

    def _cache_path(self, slot: SlotCfg, system: str, user: str,
                    json_policy: JsonModePolicy) -> Path:
        h = hashlib.sha256(
            f"{slot.provider}\x00{slot.model}\x00{json_policy}\x00"
            f"{system}\x00{user}".encode()).hexdigest()
        return self.cache_dir / f"{h}.json"

    def _raw_call(self, slot_name: str, slot: SlotCfg, system: str, user: str,
                  json_policy: JsonModePolicy) -> ProviderResponse:
        cache = self._cache_path(slot, system, user, json_policy)
        if cache.is_file():
            data = json.loads(cache.read_text(encoding="utf-8"))
            usage = Usage(in_tokens=data.get("in", 0),
                          out_tokens=data.get("out", 0),
                          cached=True, provider=data.get("provider", ""),
                          model=data.get("model", slot.model))
            return ProviderResponse(text=data["text"], usage=usage)
        provider = self._provider(slot_name, slot)
        response = provider.complete(system, user, json_policy)
        atomic_write(cache, json.dumps({
            "text": response.text,
            "in": response.usage.in_tokens,
            "out": response.usage.out_tokens,
            "provider": response.usage.provider,
            "model": response.usage.model,
        }, ensure_ascii=False))
        return response

    # ---------- 对外 ----------

    def complete_json(self, slot_name: str, system: str, user: str,
                      schema: Type[T], purpose: str) -> T:
        """调用并解析为 schema; 按 slot/provider 策略做 JSON 修复重试."""
        slot = self.models.slot(slot_name)
        provider = self._provider(slot_name, slot)
        json_policy = provider.default_json_policy()
        system, user = self._ensure_json_prompt(system, user, schema, json_policy)
        attempts = max(slot.json_repair_attempts, 0) + 1
        text = ""
        last_error: Exception | None = None
        for attempt in range(attempts):
            response = self._raw_call(slot_name, slot, system, user, json_policy)
            text = response.text
            self.meter.add(slot_name, _purpose_name(purpose, attempt),
                           response.usage)
            try:
                return schema.model_validate_json(extract_json(text))
            except (ValueError, ValidationError) as e:
                last_error = e
                if attempt == attempts - 1:
                    break
                user = self._repair_prompt(user, schema, text, e)
        summary = text[:1000].replace("\n", "\\n")
        raise JSONParseError(
            f"{purpose}: JSON {attempts} 次解析失败: {last_error}; "
            f"last_output={summary}",
            purpose=purpose, attempts=attempts, last_output=text)

    # ---------- JSON prompt discipline ----------

    def _ensure_json_prompt(self, system: str, user: str, schema: Type[T],
                            policy: JsonModePolicy) -> tuple[str, str]:
        if not policy.enabled:
            return system, user
        instruction = _json_instruction(schema)
        combined = f"{system}\n{user}".lower()
        if policy.require_json_prompt and "json" not in combined:
            system = (system + "\n\n" if system else "") + instruction
        elif "json" not in instruction.lower():
            system = (system + "\n\n" if system else "") + instruction
        else:
            user = user + "\n\n" + instruction
        return system, user

    def _repair_prompt(self, user: str, schema: Type[T], last_text: str,
                       error: Exception) -> str:
        return (
            f"{user}\n\n"
            "[JSON 修复请求]\n"
            "上一轮输出不是合法 JSON object 或不符合 schema。"
            "请只输出一个合法 JSON object, 不要 Markdown、代码块、解释文字。\n"
            f"错误: {error}\n"
            f"上一轮输出摘要: {last_text[:2000]}\n\n"
            + _json_instruction(schema)
        )


def _purpose_name(purpose: str, attempt: int) -> str:
    return purpose if attempt == 0 else f"{purpose}.repair{attempt}"


def _json_instruction(schema: Type[BaseModel]) -> str:
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    if len(schema_text) > 2500:
        schema_text = schema_text[:2500] + "..."
    return (
        "You must output valid json. The response must be exactly one JSON object, "
        "with no Markdown fences, no prose, and no code. JSON schema summary:\n"
        f"{schema_text}"
    )
