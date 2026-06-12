# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""技能模型: markdown + YAML front-matter(与 agentskills 风格对齐).

技能 = 你审过的方法论压缩, 供角色按需装载。格式约定:
---
id: systems-balance          # 小写连字符, 全局唯一
name: 系统平衡分析
version: 1
applies_to_roles: [critic]   # 角色 kind 或角色名; 空 = 全角色可用
triggers: [数值, 平衡]        # 目标卡正文/任务目标命中即候选自动装载
---
正文(检查清单/锚定样例/反模式, 批判 issue 须引用清单编号)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


class SkillParseError(Exception):
    """技能文件结构非法(显式失败, 不静默跳过坏技能)."""


@dataclass(frozen=True)
class Skill:
    """一个已解析技能(不可变)."""

    id: str
    name: str
    version: int
    applies_to_roles: tuple[str, ...]   # 空 = 全角色
    triggers: tuple[str, ...]
    body: str
    path: Path

    @property
    def chars(self) -> int:
        return len(self.body)

    def index_line(self) -> str:
        """渐进披露索引行: 常驻 prompt 只放这一行, 不放正文."""
        when = self.body.strip().splitlines()[0] if self.body.strip() else ""
        return f"- {self.id} | {self.name} | {when[:80]}"

    def render(self) -> str:
        return f"[技能 {self.id} · {self.name} v{self.version}]\n{self.body.strip()}"

    def usable_by(self, role_kind: str, role_name: str) -> bool:
        if not self.applies_to_roles:
            return True
        return role_kind in self.applies_to_roles or role_name in self.applies_to_roles

    def matches(self, text: str) -> bool:
        return any(t and t in text for t in self.triggers)


def parse_skill_file(path: Path) -> Skill:
    """解析单个技能文件; 任何字段非法都抛 SkillParseError."""
    if not path.is_file():
        raise SkillParseError(f"技能文件不存在: {path}")
    text = path.read_text(encoding="utf-8")
    m = _FRONT_RE.match(text)
    if not m:
        raise SkillParseError(f"{path}: 缺少 YAML front-matter(--- 包围)")
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise SkillParseError(f"{path}: front-matter 解析失败: {e}") from e
    if not isinstance(meta, dict):
        raise SkillParseError(f"{path}: front-matter 必须是映射")

    sid = str(meta.get("id", "")).strip()
    if not SKILL_ID_RE.match(sid):
        raise SkillParseError(f"{path}: 非法技能 id: {sid!r}")
    name = str(meta.get("name", "")).strip()
    if not name:
        raise SkillParseError(f"{path}: 缺少 name")
    body = text[m.end():].strip()
    if not body:
        raise SkillParseError(f"{path}: 技能正文为空")
    try:
        version = int(meta.get("version", 1))
    except (TypeError, ValueError) as e:
        raise SkillParseError(f"{path}: version 必须是整数") from e

    roles = meta.get("applies_to_roles") or []
    triggers = meta.get("triggers") or []
    if not isinstance(roles, list) or not isinstance(triggers, list):
        raise SkillParseError(f"{path}: applies_to_roles/triggers 必须是列表")
    return Skill(id=sid, name=name, version=version,
                 applies_to_roles=tuple(str(r) for r in roles),
                 triggers=tuple(str(t) for t in triggers),
                 body=body, path=path)
