# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM 层错误类型."""

from __future__ import annotations


class LLMError(RuntimeError):
    """LLM 调用或结构化解析失败."""


class ProviderCallError(LLMError):
    """provider 网络/限流/服务端错误在重试后仍失败."""


class EmptyContentError(LLMError):
    """provider 返回空 content."""


class JSONParseError(LLMError):
    """模型输出无法解析或无法通过 schema 校验."""

    def __init__(self, message: str, *, purpose: str = "", attempts: int = 0,
                 last_output: str = ""):
        super().__init__(message)
        self.purpose = purpose
        self.attempts = attempts
        self.last_output = last_output
