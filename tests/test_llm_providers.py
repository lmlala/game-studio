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
from studio.logging.llm_log import LLMCallLogger
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
        if kwargs.get("stream"):
            return _stream_chunks(content)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=usage)


class _FakeSDK:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def _stream_chunks(text: str):
    for part in [text[: len(text) // 2], text[len(text) // 2:]]:
        delta = SimpleNamespace(content=part)
        choice = SimpleNamespace(delta=delta)
        yield SimpleNamespace(choices=[choice], usage=None)


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


def test_deepseek_provider_streams_chunks(monkeypatch):
    slot = SlotCfg(provider="deepseek", base_url="https://api.deepseek.com",
                   model="deepseek-chat", api_key_env="X")
    provider = DeepSeekProvider(slot)
    completions = _FakeCompletions(['{"ok": true}'])
    monkeypatch.setattr(provider, "_sdk", lambda: _FakeSDK(completions))
    deltas: list[str] = []
    resp = provider.complete("system json", "user",
                             provider.default_json_policy(),
                             stream=True, on_delta=deltas.append)
    assert resp.text == '{"ok": true}'
    assert "".join(deltas) == resp.text
    assert completions.calls[0]["stream"] is True


def test_llm_client_logs_conversation(tmp_path, monkeypatch):
    slot = SlotCfg(provider="deepseek", base_url="https://api.deepseek.com",
                   model="deepseek-chat", api_key_env="X")
    models = ModelsCfg(slots={"workhorse": slot})
    llm_logger = LLMCallLogger(tmp_path)
    client = LLMClient(models, settings=SimpleNamespace(max_run_usd=1,
                                                       max_run_tokens=1000),
                       cache_dir=tmp_path / "cache",
                       llm_logger=llm_logger)
    provider = DeepSeekProvider(slot)
    completions = _FakeCompletions([
        '{"scores":{},"issues":[],"praise":[],"skill_requests":[]}'
    ])
    monkeypatch.setattr(provider, "_sdk", lambda: _FakeSDK(completions))
    client._providers["workhorse"] = provider
    client.complete_json("workhorse", "system json", "user",
                         Critique, "test-role", stream=False)
    assert (tmp_path / "llm.log").is_file()
    assert "test-role" in (tmp_path / "llm.log").read_text(encoding="utf-8")


def test_llm_client_stream_delta_and_cache_no_replay(tmp_path, monkeypatch):
    slot = SlotCfg(provider="deepseek", base_url="https://api.deepseek.com",
                   model="deepseek-chat", api_key_env="X", stream=True)
    models = ModelsCfg(slots={"workhorse": slot})
    client = LLMClient(models, settings=SimpleNamespace(max_run_usd=1,
                                                       max_run_tokens=1000),
                       cache_dir=tmp_path)
    provider = DeepSeekProvider(slot)
    completions = _FakeCompletions([
        '{"scores":{},"issues":[],"praise":[],"skill_requests":[]}'
    ])
    monkeypatch.setattr(provider, "_sdk", lambda: _FakeSDK(completions))
    client._providers["workhorse"] = provider
    deltas: list[str] = []
    result = client.complete_json("workhorse", "system json", "user",
                                  Critique, "test",
                                  on_delta=deltas.append, stream=True)
    assert result.issues == []
    assert deltas
    deltas.clear()
    result = client.complete_json("workhorse", "system json", "user",
                                  Critique, "test",
                                  on_delta=deltas.append, stream=True)
    assert result.issues == []
    assert deltas == [], "cache 命中不应重放 token delta"
