# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""卡片解析与无损回写.

协议来源: topis/football-docs/00-design-card-spec.md。
设计要点: 文件被切成 [前导段, 卡片段, 间隔段...] 的行区间; 修订只替换
目标卡片的行区间, 其余字节原样保留 → round-trip 无损是单测硬指标。
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HEADING_RE = re.compile(r"^### ([A-Z]+-\d{2}) (.+?)\s*$")
META_RE = re.compile(
    r"^状态:\s*(\S+)\s*·\s*优先级:\s*(P[0-2])\s*·\s*依赖:\s*(.+?)\s*$")
FIELD_NAMES = ["目的", "设计理念", "如何设计", "验收标准", "评估钩子"]
FIELD_RE = re.compile(r"^\*\*(目的|设计理念|如何设计|验收标准|评估钩子)\*\*：")
ID_REF_RE = re.compile(r"\b([A-Z]{2,6}-\d{2})\b")
VALID_STATUSES = {"draft", "refined", "reviewed", "locked"}


class CardParseError(Exception):
    """卡片结构不符合 00 协议."""


@dataclass
class Card:
    """一张设计卡片(含其在文件中的行区间)."""

    id: str
    title: str
    status: str
    priority: str
    deps: list[str]
    file: Path
    start: int                      # 行区间 [start, end) , 0-based
    end: int
    fields: dict[str, str] = field(default_factory=dict)  # 字段名->正文(不含标记行)
    raw: str = ""                   # 卡片块原文(含标题行)

    @property
    def body_chars(self) -> int:
        return len(self.raw)


@dataclass
class CardFile:
    """一个卡片文件: 原始行 + 卡片区间索引."""

    path: Path
    lines: list[str]
    cards: list[Card]

    def text(self) -> str:
        return "".join(self.lines)

    def get(self, card_id: str) -> Card:
        for c in self.cards:
            if c.id == card_id:
                return c
        raise KeyError(f"{self.path}: 无卡片 {card_id}")


def _parse_deps(raw: str) -> list[str]:
    raw = raw.strip()
    if raw in {"无", "-", ""}:
        return []
    return [d for d in ID_REF_RE.findall(raw)]


def _extract_fields(block_lines: list[str], card_id: str) -> dict[str, str]:
    """按五字段标记行切分卡片正文; 缺字段/乱序由 gates 判定, 这里只提取."""
    marks: list[tuple[int, str]] = []
    for i, line in enumerate(block_lines):
        m = FIELD_RE.match(line)
        if m:
            marks.append((i, m.group(1)))
    fields: dict[str, str] = {}
    for j, (idx, name) in enumerate(marks):
        stop = marks[j + 1][0] if j + 1 < len(marks) else len(block_lines)
        head = FIELD_RE.sub("", block_lines[idx], count=1)
        content = ([head] if head.strip() else []) + block_lines[idx + 1:stop]
        fields[name] = "".join(content).strip("\n")
    return fields


def parse_block(block: str, file: Path = Path("<memory>"),
                start: int = 0) -> Card:
    """解析单个卡片块(用于解析 LLM 产出的修订稿)."""
    lines = block.splitlines(keepends=True)
    if not lines:
        raise CardParseError("空卡片块")
    m = HEADING_RE.match(lines[0].rstrip("\n"))
    if not m:
        raise CardParseError(f"首行不是卡片标题: {lines[0]!r}")
    card_id, title = m.group(1), m.group(2)
    meta = None
    for line in lines[1:6]:                 # 状态行须在标题后 5 行内
        mm = META_RE.match(line.rstrip("\n"))
        if mm:
            meta = mm
            break
    if meta is None:
        raise CardParseError(f"{card_id}: 缺少合法状态行(状态/优先级/依赖)")
    status, priority, deps_raw = meta.group(1), meta.group(2), meta.group(3)
    return Card(id=card_id, title=title, status=status, priority=priority,
                deps=_parse_deps(deps_raw), file=file, start=start,
                end=start + len(lines),
                fields=_extract_fields(lines, card_id), raw=block)


def parse_file(path: Path) -> CardFile:
    """解析整个文件; 卡片块 = '### ID' 起, 至下一个 '### '/'## ' 或 EOF."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    heads = [i for i, ln in enumerate(lines) if HEADING_RE.match(ln.rstrip("\n"))]
    cards: list[Card] = []
    for n, start in enumerate(heads):
        end = len(lines)
        for j in range(start + 1, len(lines)):
            s = lines[j]
            if s.startswith("### ") or s.startswith("## "):
                end = j
                break
        if n + 1 < len(heads):
            end = min(end, heads[n + 1])
        block = "".join(lines[start:end])
        card = parse_block(block, file=path, start=start)
        card.end = end
        cards.append(card)
    ids = [c.id for c in cards]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise CardParseError(f"{path}: 重复卡片 ID {sorted(dup)}")
    return CardFile(path=path, lines=lines, cards=cards)


def atomic_write(path: Path, content: str) -> None:
    """原子写: 同目录临时文件 + rename, 崩溃不留半成品."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def replace_card(cf: CardFile, card_id: str, new_block: str) -> str:
    """在内存中替换卡片块, 返回新文件全文(写盘由调用方决定时机)."""
    card = cf.get(card_id)
    if not new_block.endswith("\n"):
        new_block += "\n"
    new_lines = (cf.lines[:card.start]
                 + new_block.splitlines(keepends=True)
                 + cf.lines[card.end:])
    return "".join(new_lines)


@dataclass
class RepoIndex:
    """卡片库全量索引: 跨文件引用检查与依赖检索的依据."""

    files: dict[Path, CardFile]
    by_id: dict[str, Card]

    @classmethod
    def build(cls, docs_root: Path, patterns: list[str]) -> "RepoIndex":
        files: dict[Path, CardFile] = {}
        by_id: dict[str, Card] = {}
        paths: list[Path] = []
        for pat in patterns:
            paths.extend(sorted(docs_root.glob(pat)))
        for p in paths:
            cf = parse_file(p)
            files[p] = cf
            for c in cf.cards:
                if c.id in by_id:
                    raise CardParseError(
                        f"跨文件重复 ID {c.id}: {by_id[c.id].file} 与 {p}")
                by_id[c.id] = c
        return cls(files=files, by_id=by_id)

    def siblings(self, card: Card) -> list[Card]:
        return [c for c in self.files[card.file].cards if c.id != card.id]
