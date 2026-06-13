# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""LLM 对话日志: 每次调用落盘 llm.log + llm.jsonl.

与终端 SSE 解耦 — 运行时看 stage/plan 事件, 排查 JSON/门禁问题时 tail llm.log。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..core.cards import atomic_write


class LLMCallLogger:
    """单次 run 的 LLM 调用记录器."""

    def __init__(self, run_dir: Path, max_chars: int = 12000):
        if max_chars <= 0:
            raise ValueError("max_chars 必须为正")
        self.run_dir = run_dir
        self.max_chars = max_chars
        self.text_path = run_dir / "llm.log"
        self.jsonl_path = run_dir / "llm.jsonl"
        self._seq = 0
        run_dir.mkdir(parents=True, exist_ok=True)

    def record(self, *, slot: str, provider: str, model: str, purpose: str,
               attempt: int, system: str, user: str, response: str,
               in_tokens: int = 0, out_tokens: int = 0,
               cached: bool = False, stream: bool = False,
               extra: dict[str, Any] | None = None) -> None:
        self._seq += 1
        rec = {
            "ts": time.time(),
            "seq": self._seq,
            "slot": slot,
            "provider": provider,
            "model": model,
            "purpose": purpose,
            "attempt": attempt,
            "cached": cached,
            "stream": stream,
            "in_tokens": in_tokens,
            "out_tokens": out_tokens,
            "system": _clip(system, self.max_chars),
            "user": _clip(user, self.max_chars),
            "response": _clip(response, self.max_chars),
        }
        if extra:
            rec["extra"] = extra
        self._append_jsonl(rec)
        self._append_text(rec)

    def _append_jsonl(self, rec: dict) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _append_text(self, rec: dict) -> None:
        header = (
            f"--- #{rec['seq']} {rec['purpose']} "
            f"slot={rec['slot']} provider={rec['provider']} "
            f"model={rec['model']} attempt={rec['attempt']} "
            f"cached={rec['cached']} in={rec['in_tokens']} out={rec['out_tokens']} ---"
        )
        body = "\n".join([
            header,
            "[system]",
            rec["system"],
            "",
            "[user]",
            rec["user"],
            "",
            "[response]",
            rec["response"],
            "",
        ])
        with self.text_path.open("a", encoding="utf-8") as f:
            f.write(body)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, total {len(text)} chars]"
