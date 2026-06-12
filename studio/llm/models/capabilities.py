# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""模型能力推断.

配置优先, 推断兜底。不要在通用 client 中写死供应商行为。
"""

from __future__ import annotations

from ...core.config import SlotCfg


def infer_provider(slot: SlotCfg) -> str:
    """兼容旧配置: openai_compat + DeepSeek base_url 自动路由到 deepseek."""
    if slot.provider == "openai_compat" and "api.deepseek.com" in slot.base_url:
        return "deepseek"
    return slot.provider


def default_json_flags(provider: str) -> dict[str, bool]:
    if provider == "deepseek":
        return {
            "json_mode": True,
            "response_format_supported": True,
            "require_json_prompt": True,
            "allow_empty_content_retry": True,
        }
    return {
        "json_mode": False,
        "response_format_supported": False,
        "require_json_prompt": False,
        "allow_empty_content_retry": False,
    }
