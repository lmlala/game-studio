# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""角色运行时: 产出 schema + prompt 渲染 + 调用 + fake 模式.

角色 = 配置(RoleCfg) + 模板(prompts/*.md) + 产出 schema。
模板占位符用 <<KEY>> 形式(避开 JSON 花括号与 str.format 冲突)。
fake 模式返回结构合法的最小产出, 供离线测试与 --fake 试运行。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import RoleCfg
from .context import ContextBundle
from .llm import LLMClient


# ---------- 产出 schema(LLM 输出永远先过这里) ----------

class Issue(BaseModel):
    severity: Literal["blocking", "major", "minor"]
    field: str = ""                      # 指向卡片五字段之一, 可空
    claim: str
    evidence: str                        # 必填语义由门禁强制(空即丢弃)
    suggestion: str = ""


class Critique(BaseModel):
    scores: dict[str, int] = Field(default_factory=dict)   # 维度 -> 1..5
    issues: list[Issue] = Field(default_factory=list)
    praise: list[str] = Field(default_factory=list)


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


SCHEMA_BY_KIND = {"critic": Critique, "referee": Verdict, "proposer": Revision}


# ---------- 模板渲染 ----------

def render_template(template: str, mapping: dict[str, str]) -> str:
    """<<KEY>> 占位替换; 缺失 key 显式报错而非留洞."""
    out = template
    for k, v in mapping.items():
        out = out.replace(f"<<{k}>>", v)
    if "<<" in out and ">>" in out:
        import re
        leftover = re.findall(r"<<([A-Z_]+)>>", out)
        if leftover:
            raise ValueError(f"模板占位符未填充: {leftover}")
    return out


class Role:
    """单个角色的执行器."""

    def __init__(self, cfg: RoleCfg, prompts_dir: Path):
        self.cfg = cfg
        self.template = (prompts_dir / cfg.prompt).read_text(encoding="utf-8")
        self.schema = SCHEMA_BY_KIND[cfg.kind]

    def _prompt(self, bundle: ContextBundle, extra: dict[str, str]) -> tuple[str, str]:
        mapping = {
            "ROLE_NAME": self.cfg.name,
            "FOCUS": self.cfg.focus or "(无附加视角说明)",
            "RUBRIC": "、".join(self.cfg.rubric) or "(自由评分维度)",
            "CONTEXT": bundle.render(),
            **extra,
        }
        # 模板第一段(--- 之前)为 system, 之后为 user
        if "\n---\n" in self.template:
            sys_t, user_t = self.template.split("\n---\n", 1)
        else:
            sys_t, user_t = "", self.template
        return (render_template(sys_t, mapping).strip(),
                render_template(user_t, mapping).strip())

    def run(self, client: LLMClient, bundle: ContextBundle,
            extra: dict[str, str] | None = None, fake: bool = False):
        extra = extra or {}
        if fake:
            return self.fake_output(extra)
        system, user = self._prompt(bundle, extra)
        return client.complete_json(self.cfg.slot, system, user, self.schema,
                                    purpose=f"{self.cfg.name}")

    # ---------- fake 模式(离线/试运行) ----------

    def fake_output(self, extra: dict[str, str]):
        if self.schema is Critique:
            return Critique(
                scores={d: 4 for d in (self.cfg.rubric or ["质量"])},
                issues=[Issue(severity="minor", field="验收标准",
                              claim=f"[fake:{self.cfg.name}] 示例问题",
                              evidence="fake 模式占位证据",
                              suggestion="无需处理")],
                praise=["[fake] 结构完整"])
        if self.schema is Verdict:
            return Verdict(decision="converged", directives=[],
                           rationale="[fake] 试运行直接收敛")
        if self.schema is Revision:
            return Revision(card_markdown=extra.get("CURRENT_CARD", ""),
                            responses=["[fake] 原样返回"],
                            expansion_rationale="")
        raise AssertionError(f"未知 schema: {self.schema}")
