# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""阿里云百炼 Qwen provider (OpenAI 兼容模式).

深度思考 (enable_thinking):
- 混合思考模型 (qwen3.6-max / qwen-plus / qwen-flash 等) 可通过 extra_body 开关;
- enable_thinking=true 时多数模型要求 stream=true, 且与 JSON Mode 互斥;
- 本 agent 默认 JSON 输出, 因此 json_policy.enabled 时强制 enable_thinking=false。
参考: https://help.aliyun.com/zh/model-studio/deep-thinking
"""

from __future__ import annotations

from .base import JsonModePolicy
from .openai_compat import OpenAICompatProvider


class QwenProvider(OpenAICompatProvider):
    """DashScope compatible-mode adapter with Qwen-specific extras."""

    name = "qwen"

    def default_json_policy(self) -> JsonModePolicy:
        return JsonModePolicy(
            enabled=self.slot.json_mode,
            response_format_supported=self.slot.response_format_supported,
            require_json_prompt=self.slot.require_json_prompt,
            allow_empty_content_retry=self.slot.allow_empty_content_retry,
        )

    def _request_kwargs(self, system: str, user: str,
                        json_policy: JsonModePolicy,
                        stream: bool = False) -> dict:
        kwargs = super()._request_kwargs(system, user, json_policy, stream)
        extra = self._thinking_extra(json_policy)
        if extra:
            kwargs["extra_body"] = extra
        if extra.get("enable_thinking"):
            kwargs["stream"] = True
            kwargs.pop("response_format", None)
        return kwargs

    def _thinking_extra(self, json_policy: JsonModePolicy) -> dict:
        """JSON 模式与思考模式互斥; 结构化输出场景必须关闭思考."""
        if json_policy.enabled:
            return {"enable_thinking": False}
        extra: dict = {}
        if self.slot.enable_thinking:
            extra["enable_thinking"] = True
            if self.slot.thinking_budget is not None:
                extra["thinking_budget"] = self.slot.thinking_budget
        elif self.slot.enable_thinking is False:
            extra["enable_thinking"] = False
        return extra
