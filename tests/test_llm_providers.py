# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM provider 与 JSON prompt 策略测试."""

from __future__ import annotations

from types import SimpleNamespace

from studio.core.config import ModelsCfg, SlotCfg
from studio.llm.client import LLMClient
from studio.llm.providers import DeepSeekProvider, JsonModePolicy
from studio.roles.schemas import Critique


class _FakeCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=usage)


class _FakeSDK:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def test_deepseek_provider_passes_response_format(monkeypatch):
    slot = SlotCfg(provider="deepseek", base_url="https://api.deepseek.com",
                   model="deepseek-chat", api_key_env="X")
    provider = DeepSeekProvider(slot)
    completions = _FakeCompletions(['{"ok": true}'])
    monkeypatch.setattr(provider, "_sdk", lambda: _FakeSDK(completions))
    policy = provider.default_json_policy()
    resp = provider.complete("system json", "user", policy)
    assert resp.text == '{"ok": true}'
    assert completions.calls[0]["response_format"] == {"type": "json_object"}


def test_deepseek_provider_retries_empty_content(monkeypatch):
    slot = SlotCfg(provider="deepseek", base_url="https://api.deepseek.com",
                   model="deepseek-chat", api_key_env="X")
    provider = DeepSeekProvider(slot)
    completions = _FakeCompletions(["", '{"ok": true}'])
    monkeypatch.setattr(provider, "_sdk", lambda: _FakeSDK(completions))
    resp = provider.complete("system json", "user",
                             provider.default_json_policy())
    assert resp.text == '{"ok": true}'
    assert len(completions.calls) == 2


def test_llm_client_adds_json_instruction_for_json_mode(tmp_path):
    slot = SlotCfg(provider="deepseek", base_url="https://api.deepseek.com",
                   model="deepseek-chat", api_key_env="X")
    models = ModelsCfg(slots={"workhorse": slot})
    client = LLMClient(models, settings=SimpleNamespace(max_run_usd=1,
                                                       max_run_tokens=1000),
                       cache_dir=tmp_path)
    system, user = client._ensure_json_prompt(
        "你是批判者", "输出结果", Critique,
        JsonModePolicy(enabled=True, require_json_prompt=True,
                       response_format_supported=True))
    assert "json" in (system + user).lower()
    assert "JSON schema summary" in system + user
