# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""Provider registry."""

from __future__ import annotations

from typing import Type

from ...core.config import SlotCfg
from ..providers import (BaseProvider, DeepSeekProvider, FakeProvider,
                         OpenAICompatProvider)
from .capabilities import infer_provider


class ProviderRegistry:
    """SlotCfg -> provider adapter."""

    _PROVIDERS: dict[str, Type[BaseProvider]] = {
        "deepseek": DeepSeekProvider,
        "openai_compat": OpenAICompatProvider,
        "fake": FakeProvider,
    }

    @classmethod
    def create(cls, slot: SlotCfg) -> BaseProvider:
        provider_name = infer_provider(slot)
        if provider_name not in cls._PROVIDERS:
            raise ValueError(f"未知 provider: {provider_name}")
        return cls._PROVIDERS[provider_name](slot)
