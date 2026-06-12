# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""主题记忆: 以议题文件(topic)为粒度的跨运行知识沉淀.

topic = 卡片所在文件名(如 05-event-system) —— 同一主题下的卡片共享
记忆: 升级(escalate)原因、defer 的开放问题、人工方向的历史、收敛结论。
价值: 下次运行同主题时, 角色不必从零理解"这个主题上次卡在哪"。
"""

from __future__ import annotations

from pathlib import Path

from .store import JsonlMemory

EVENT_KINDS = {"converged", "escalated", "deferred", "steered", "note"}


class TopicMemory(JsonlMemory):
    """单个主题的记忆; 由 for_card 工厂按卡片定位."""

    def __init__(self, memory_root: Path, topic: str, keep_last: int = 100):
        if not topic or not topic.strip():
            raise ValueError("topic 不能为空")
        self.topic = topic.strip()
        super().__init__(memory_root / "topics" / f"{self.topic}.jsonl",
                         keep_last=keep_last)

    @classmethod
    def for_card_file(cls, memory_root: Path, card_file: Path) -> "TopicMemory":
        """topic 键 = 卡片文件 stem(如 05-event-system)."""
        return cls(memory_root, card_file.stem)

    def record(self, kind: str, card_id: str, note: str) -> None:
        """业务入口: 校验事件类型后写入."""
        if kind not in EVENT_KINDS:
            raise ValueError(f"未知主题事件类型: {kind}")
        if not card_id or not note.strip():
            raise ValueError("主题事件必须含 card_id 与非空 note")
        self.append({"kind": kind, "card": card_id, "note": note.strip()})

    def _format_event(self, event: dict) -> str:
        kind = event.get("kind", "?")
        card = event.get("card", "?")
        note = str(event.get("note", ""))[:160]
        return f"- [{kind}] {card}: {note}"
