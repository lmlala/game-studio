# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""Qwen provider 测试."""

from __future__ import annotations

from types import SimpleNamespace

from studio.core.config import SlotCfg
from studio.llm.providers import JsonModePolicy, QwenProvider


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        msg = SimpleNamespace(content='{"ok": true}')
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=usage)


class _FakeSDK:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_qwen_json_mode_disables_thinking(monkeypatch):
    slot = SlotCfg(
        provider="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        api_key_env="X",
        enable_thinking=True,
    )
    provider = QwenProvider(slot)
    sdk = _FakeSDK()
    monkeypatch.setattr(provider, "_sdk", lambda: sdk)
    policy = provider.default_json_policy()
    provider.complete("system json", "user", policy)
    extra = sdk.chat.completions.calls[0]["extra_body"]
    assert extra["enable_thinking"] is False
    assert sdk.chat.completions.calls[0]["response_format"] == {
        "type": "json_object"}


def test_qwen_thinking_requires_stream(monkeypatch):
    slot = SlotCfg(
        provider="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen3.6-max",
        api_key_env="X",
        enable_thinking=True,
        json_mode=False,
        response_format_supported=False,
    )
    provider = QwenProvider(slot)
    policy = JsonModePolicy(enabled=False)
    kwargs = provider._request_kwargs("sys", "user", policy, stream=False)
    assert kwargs["extra_body"]["enable_thinking"] is True
    assert kwargs["stream"] is True


def test_infer_provider_routes_dashscope_to_qwen():
    from studio.llm.models.capabilities import infer_provider

    slot = SlotCfg(
        provider="openai_compat",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-flash",
        api_key_env="X",
    )
    assert infer_provider(slot) == "qwen"
