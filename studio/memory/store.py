# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""记忆存储基类: jsonl 追加 + 确定性摘要的公共实现.

topic 记忆与 agent 记忆共享同一存储形态: 事件 jsonl(append-only,
可审计) + digest(提取式压缩, 带字符预算)。LLM 不参与摘要 —— 记忆是
事实档案, 不是模型的二次创作。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.interfaces import BaseMemory


class JsonlMemory(BaseMemory):
    """jsonl 事件记忆: 子类只需实现 _format_event 一行化规则."""

    def __init__(self, path: Path, keep_last: int = 200):
        if keep_last <= 0:
            raise ValueError("keep_last 必须为正")
        self.path = path
        self.keep_last = keep_last

    # ---------- 写 ----------

    def append(self, event: dict) -> None:
        if not isinstance(event, dict) or not event.get("kind"):
            raise ValueError("记忆事件必须是含 kind 字段的 dict")
        rec = {"ts": time.time(), **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------- 读 ----------

    def load(self, last_n: int | None = None) -> list[dict]:
        if not self.path.is_file():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue                    # 损坏行跳过, 不阻塞运行
        return events[-(last_n or self.keep_last):]

    def digest(self, max_chars: int) -> str:
        """新事件在后; 超预算从最旧开始丢(最近的经验最值钱)."""
        if max_chars <= 0:
            return ""
        lines = [self._format_event(e) for e in self.load()]
        lines = [ln for ln in lines if ln]
        out: list[str] = []
        used = 0
        for ln in reversed(lines):          # 从最新往回装
            if used + len(ln) + 1 > max_chars:
                break
            out.append(ln)
            used += len(ln) + 1
        return "\n".join(reversed(out))

    def _format_event(self, event: dict) -> str:
        """默认一行化; 子类按事件类型定制."""
        kind = event.get("kind", "?")
        note = str(event.get("note", ""))[:160]
        return f"- [{kind}] {note}" if note else ""
