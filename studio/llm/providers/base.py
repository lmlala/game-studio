# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""Provider 抽象: 各模型供应商差异在这里隔离."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ...cost import Usage
from ...core.config import SlotCfg


@dataclass(frozen=True)
class JsonModePolicy:
    """JSON 输出能力策略."""

    enabled: bool = False
    response_format_supported: bool = False
    require_json_prompt: bool = False
    allow_empty_content_retry: bool = False


@dataclass
class ProviderResponse:
    text: str
    usage: Usage


class BaseProvider(ABC):
    """同步 provider adapter."""

    name = "base"

    def __init__(self, slot: SlotCfg):
        self.slot = slot

    @abstractmethod
    def complete(self, system: str, user: str,
                 json_policy: JsonModePolicy) -> ProviderResponse:
        """执行一次模型调用."""

    def default_json_policy(self) -> JsonModePolicy:
        return JsonModePolicy()
