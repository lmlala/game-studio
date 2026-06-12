# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""通用 OpenAI-compatible provider."""

from __future__ import annotations

import os
import time

from ...cost import Usage, apply_slot_pricing
from ..errors import EmptyContentError, ProviderCallError
from .base import BaseProvider, JsonModePolicy, ProviderResponse


class OpenAICompatProvider(BaseProvider):
    """只使用 OpenAI chat.completions 兼容参数."""

    name = "openai_compat"

    def __init__(self, slot):
        super().__init__(slot)
        self._client = None

    def _sdk(self):
        if self._client is None:
            from openai import OpenAI
            api_key = os.environ.get(self.slot.api_key_env, "")
            if not api_key:
                raise ProviderCallError(f"环境变量 {self.slot.api_key_env} 未设置")
            self._client = OpenAI(base_url=self.slot.base_url, api_key=api_key)
        return self._client

    def complete(self, system: str, user: str,
                 json_policy: JsonModePolicy) -> ProviderResponse:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                kwargs = self._request_kwargs(system, user, json_policy)
                resp = self._sdk().chat.completions.create(**kwargs)
                text = resp.choices[0].message.content or ""
                if not text and json_policy.allow_empty_content_retry:
                    raise EmptyContentError("provider 返回空 content")
                pu = getattr(resp, "usage", None)
                usage = Usage(
                    in_tokens=getattr(pu, "prompt_tokens", 0) or 0,
                    out_tokens=getattr(pu, "completion_tokens", 0) or 0,
                    provider=self.name,
                    model=self.slot.model,
                )
                return ProviderResponse(text=text,
                                        usage=apply_slot_pricing(self.slot, usage))
            except EmptyContentError:
                last_err = EmptyContentError("provider 返回空 content")
                time.sleep(2 ** attempt)
            except Exception as exc:
                last_err = exc
                time.sleep(2 ** attempt)
        raise ProviderCallError(f"{self.name} 调用失败(3 次重试后): {last_err}")

    def _request_kwargs(self, system: str, user: str,
                        json_policy: JsonModePolicy) -> dict:
        kwargs = {
            "model": self.slot.model,
            "temperature": self.slot.temperature,
            "max_tokens": self.slot.max_output_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        if json_policy.enabled and json_policy.response_format_supported:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs
