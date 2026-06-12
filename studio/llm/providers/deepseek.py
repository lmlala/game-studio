# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""DeepSeek provider.

DeepSeek JSON Output 文档要求:
- request 设置 response_format={"type": "json_object"};
- system 或 user prompt 必须包含 json 字样并给 JSON 格式样例;
- max_tokens 足够, 避免 JSON 被截断;
- JSON Output 仍可能返回空 content, 需要重试。
"""

from __future__ import annotations

from .base import JsonModePolicy
from .openai_compat import OpenAICompatProvider


class DeepSeekProvider(OpenAICompatProvider):
    """DeepSeek OpenAI-compatible adapter with JSON Mode defaults."""

    name = "deepseek"

    def default_json_policy(self) -> JsonModePolicy:
        return JsonModePolicy(
            enabled=self.slot.json_mode,
            response_format_supported=self.slot.response_format_supported,
            require_json_prompt=self.slot.require_json_prompt,
            allow_empty_content_retry=self.slot.allow_empty_content_retry,
        )
