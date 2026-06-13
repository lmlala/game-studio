# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""技能注册表: 从内核与项目包目录聚合技能, 提供索引与查询.

来源优先级: 项目包技能 > 内核内置技能(同 id 时项目包覆盖内核 ——
领域知识允许专化通用方法论)。
"""

from __future__ import annotations

from pathlib import Path

from ..core.interfaces import BaseSkillSource
from .model import Skill, SkillParseError, parse_skill_file

BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills_builtin"


class DirSkillSource(BaseSkillSource):
    """目录来源: 目录内全部 *.md 都是技能文件."""

    def __init__(self, root: Path):
        if not isinstance(root, Path):
            raise TypeError("技能目录必须是 Path")
        self.root = root

    def load_all(self) -> list[Skill]:
        if not self.root.is_dir():
            return []
        return [parse_skill_file(p) for p in sorted(self.root.glob("*.md"))]


class SkillRegistry:
    """聚合多来源技能; 查询全部确定性(同输入同输出)."""

    def __init__(self, skills: dict[str, Skill]):
        self.by_id = skills

    @classmethod
    def build(cls, pack_skills_dirs: list[Path],
              include_builtin: bool = True) -> "SkillRegistry":
        """先装内核技能再装项目技能, 项目同 id 覆盖内核."""
        sources: list[BaseSkillSource] = []
        if include_builtin:
            sources.append(DirSkillSource(BUILTIN_SKILLS_DIR))
        sources.extend(DirSkillSource(d) for d in pack_skills_dirs)
        by_id: dict[str, Skill] = {}
        for src in sources:
            for sk in src.load_all():
                by_id[sk.id] = sk
        return cls(by_id)

    def get(self, skill_id: str) -> Skill:
        if skill_id not in self.by_id:
            raise KeyError(f"技能不存在: {skill_id}")
        return self.by_id[skill_id]

    def has(self, skill_id: str) -> bool:
        return skill_id in self.by_id

    def for_role(self, role_kind: str, role_name: str) -> list[Skill]:
        return [s for s in sorted(self.by_id.values(), key=lambda x: x.id)
                if s.usable_by(role_kind, role_name)]

    def index_text(self, role_kind: str, role_name: str) -> str:
        """渐进披露索引: id + 名称 + 何时使用, 供角色自主申请."""
        lines = [s.index_line() for s in self.for_role(role_kind, role_name)]
        return "\n".join(lines)

    def match_triggers(self, text: str, role_kind: str,
                       role_name: str) -> list[Skill]:
        """触发词命中的候选技能(确定性, 按 id 排序)."""
        if not text:
            return []
        return [s for s in self.for_role(role_kind, role_name)
                if s.matches(text)]
