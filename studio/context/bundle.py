# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""上下文数据结构: 有序段落 + 渲染 + 统计."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Section:
    """一个上下文段落; trimmable=False 的段(宪法/目标)永不裁剪."""

    name: str
    text: str
    trimmable: bool


@dataclass
class ContextBundle:
    """组装结果: 有序段落; render() 产出最终 user prompt 主体."""

    sections: list[Section]

    def render(self) -> str:
        parts = []
        for s in self.sections:
            if s.text.strip():
                parts.append(f"<<<{s.name}>>>\n{s.text.strip()}\n<<<END:{s.name}>>>")
        return "\n\n".join(parts)

    @property
    def total_chars(self) -> int:
        return sum(len(s.text) for s in self.sections)

    def section(self, name: str) -> Section:
        for s in self.sections:
            if s.name == name:
                return s
        raise KeyError(f"上下文无此段落: {name}")


def clip(text: str, limit: int) -> str:
    """硬截断并标注(确定性; 用于裁剪兜底, 优先用语义压缩)."""
    if limit < 0:
        raise ValueError("截断上限不能为负")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[截断, 原文 {len(text)} 字符]"
