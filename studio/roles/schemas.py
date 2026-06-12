# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""角色产出 schema: LLM 输出永远先过这里(pydantic 硬校验).

skill_requests 是技能自主调用的申请通道: 角色在产出里声明下一轮想
装载的技能 id, 由 SkillLoader 按白名单与预算裁决 —— 模型有自主权,
内核有否决权。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    severity: Literal["blocking", "major", "minor"]
    field: str = ""                      # 指向卡片五字段之一, 可空
    claim: str
    evidence: str                        # 必填语义由门禁强制(空即丢弃)
    suggestion: str = ""
    skill_ref: str = ""                  # 引用技能检查点编号(如 SB-2), 可空


class Critique(BaseModel):
    scores: dict[str, int] = Field(default_factory=dict)   # 维度 -> 1..5
    issues: list[Issue] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)
    skill_requests: list[str] = Field(default_factory=list)  # 下一轮申请装载


class Directive(BaseModel):
    issue_ref: str = ""                  # 引用 issue 摘要或编号
    action: Literal["accept", "reject", "defer"]
    instruction: str = ""                # accept 时给提案者的修订指令


class Verdict(BaseModel):
    decision: Literal["revise", "converged", "escalate"]
    directives: list[Directive] = Field(default_factory=list)
    rationale: str = ""


class Revision(BaseModel):
    card_markdown: str                   # 完整卡片块(### 标题行起)
    responses: list[str] = Field(default_factory=list)  # 逐条指令的落实说明
    expansion_rationale: str = ""        # 非空 = 申请突破膨胀阈值
