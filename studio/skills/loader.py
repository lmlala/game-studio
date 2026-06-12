# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""技能装载裁决: 自主调用的"两级模型", 自主性放在便宜可控的位置.

装载来源(优先级从高到低, 超出上限先砍低优先级):
1. 角色显式绑定(cast.yaml roles[].skills) —— 人工指定, 永远装;
2. 角色上一轮申请(产出 JSON 的 skill_requests) —— 模型自主, 白名单校验;
3. 触发词命中(目标卡正文 + 任务目标) —— 确定性自动路由。
纪律: 单角色单轮 ≤ max_skills_per_role 个; 技能段总字符 ≤ skill_context_chars;
申请了不存在/不适用的技能 → 拒绝并记入 journal(不中断运行)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Skill
from .registry import SkillRegistry


@dataclass
class LoadDecision:
    """一次装载裁决结果(可审计)."""

    skills: list[Skill] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)   # 被拒申请(含原因)

    def render(self) -> str:
        if not self.skills:
            return ""
        return "\n\n".join(s.render() for s in self.skills)


class SkillLoader:
    """按角色裁决本轮技能装载; 无状态, 申请由调用方跨轮传递."""

    def __init__(self, registry: SkillRegistry, max_per_role: int,
                 chars_budget: int):
        if max_per_role < 0 or chars_budget < 0:
            raise ValueError("技能预算不能为负")
        self.registry = registry
        self.max_per_role = max_per_role
        self.chars_budget = chars_budget

    def decide(self, role_kind: str, role_name: str, bound_ids: list[str],
               requested_ids: list[str], trigger_text: str) -> LoadDecision:
        """裁决装载清单: 绑定 > 申请 > 触发, 去重后裁预算."""
        decision = LoadDecision()
        picked: dict[str, Skill] = {}

        for sid in bound_ids:                      # 1. 显式绑定: 配置错误即失败
            picked[sid] = self.registry.get(sid)

        for sid in requested_ids:                  # 2. 自主申请: 白名单校验
            sid = str(sid).strip()
            if not sid or sid in picked:
                continue
            if not self.registry.has(sid):
                decision.rejected.append(f"{sid}(不存在)")
                continue
            sk = self.registry.get(sid)
            if not sk.usable_by(role_kind, role_name):
                decision.rejected.append(f"{sid}(角色不适用)")
                continue
            picked[sid] = sk

        for sk in self.registry.match_triggers(    # 3. 触发词自动路由
                trigger_text, role_kind, role_name):
            picked.setdefault(sk.id, sk)

        decision.skills = self._apply_budget(list(picked.values()), decision)
        return decision

    def _apply_budget(self, skills: list[Skill],
                      decision: LoadDecision) -> list[Skill]:
        """先裁数量再裁字符; 保持加入顺序(绑定优先于申请优先于触发)."""
        if len(skills) > self.max_per_role:
            for sk in skills[self.max_per_role:]:
                decision.rejected.append(f"{sk.id}(超出单角色上限)")
            skills = skills[:self.max_per_role]
        kept, used = [], 0
        for sk in skills:
            if used + sk.chars > self.chars_budget and kept:
                decision.rejected.append(f"{sk.id}(超出字符预算)")
                continue
            kept.append(sk)
            used += sk.chars
        return kept
