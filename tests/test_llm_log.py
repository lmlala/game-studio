# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM 对话日志测试."""

from __future__ import annotations

from studio.logging.llm_log import LLMCallLogger


def test_llm_call_logger_writes_text_and_jsonl(tmp_path):
    logger = LLMCallLogger(tmp_path, max_chars=100)
    logger.record(
        slot="workhorse",
        provider="deepseek",
        model="deepseek-chat",
        purpose="提案者",
        attempt=0,
        system="sys",
        user="user",
        response='{"ok": true}',
        in_tokens=10,
        out_tokens=5,
    )
    text = (tmp_path / "llm.log").read_text(encoding="utf-8")
    jsonl = (tmp_path / "llm.jsonl").read_text(encoding="utf-8")
    assert "提案者" in text
    assert "[response]" in text
    assert '{"ok": true}' in text
    assert '"purpose": "提案者"' in jsonl
