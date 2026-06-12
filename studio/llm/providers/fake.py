# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""Fake provider: 仅用于测试 provider registry; 角色 fake 输出仍在 roles 层."""

from __future__ import annotations

from ...cost import Usage
from .base import BaseProvider, JsonModePolicy, ProviderResponse


class FakeProvider(BaseProvider):
    name = "fake"

    def complete(self, system: str, user: str,
                 json_policy: JsonModePolicy, stream: bool = False,
                 on_delta=None) -> ProviderResponse:
        return ProviderResponse(text="{}", usage=Usage(cached=False,
                                                       provider=self.name,
                                                       model=self.slot.model))
