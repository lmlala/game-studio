# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""具体角色实现: 批判者 / 主编 / 提案者(各自 schema 与 fake 产出)."""

from __future__ import annotations

from .base import TemplatedRole
from .schemas import Critique, Directive, Issue, Revision, Verdict


class CriticRole(TemplatedRole):
    """批判者: 并列运行, 互不可见; 产出 Critique."""

    schema = Critique

    def fake_output(self, extra: dict[str, str]) -> Critique:
        return Critique(
            scores={d: 4 for d in (self.cfg.rubric or ["质量"])},
            issues=[Issue(severity="minor", field="验收标准",
                          claim=f"[fake:{self.cfg.name}] 示例问题",
                          evidence="fake 模式占位证据",
                          suggestion="无需处理")],
            praise=["[fake] 结构完整"],
            skill_requests=[])


class RefereeRole(TemplatedRole):
    """主编: 逐条处置 issue, 判收敛; 产出 Verdict."""

    schema = Verdict

    def fake_output(self, extra: dict[str, str]) -> Verdict:
        return Verdict(decision="converged", directives=[],
                       rationale="[fake] 试运行直接收敛")


class ProposerRole(TemplatedRole):
    """提案者: 按主编指令修订; 产出 Revision."""

    schema = Revision

    def fake_output(self, extra: dict[str, str]) -> Revision:
        return Revision(card_markdown=extra.get("CURRENT_CARD", ""),
                        responses=["[fake] 原样返回"],
                        expansion_rationale="")


# 供测试构造最小 Verdict/Directive 的便捷再导出
__all__ = ["CriticRole", "RefereeRole", "ProposerRole",
           "Critique", "Verdict", "Revision", "Directive", "Issue"]
