# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM JSON 提取测试."""

from __future__ import annotations

import pytest

from studio.llm.client import extract_json


def test_extract_json_from_json_fence():
    assert extract_json('```json\n{"ok": true}\n```') == '{"ok": true}'


def test_extract_json_skips_rust_fence():
    text = '```rust\npub struct X { field: String }\n```\n后面 {"ok": true}'
    assert extract_json(text) == '{"ok": true}'


def test_extract_json_skips_invalid_braces_until_valid_json():
    text = "pub struct X { field: String }\n然后输出 {\"ok\": true}"
    assert extract_json(text) == '{"ok": true}'


def test_extract_json_raises_when_no_valid_json():
    with pytest.raises(ValueError, match="无合法 JSON|无 JSON"):
        extract_json("```rust\npub trait X { fn judge(&self); }\n```")
