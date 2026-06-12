# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""角色运行时基类: 模板渲染 + 调用 + schema 校验的公共骨架.

角色 = 配置(RoleCfg) + 模板(prompts/*.md) + 产出 schema。
模板占位符用 <<KEY>> 形式(避开 JSON 花括号与 str.format 冲突);
模板以 "\\n---\\n" 分隔 system 段与 user 段。
子类只需声明 schema 与 fake_output —— 新角色种类按此扩展。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from ..core.config import RoleCfg
from ..core.interfaces import BaseRole
from ..llm.client import LLMClient

_PLACEHOLDER_RE = re.compile(r"<<([A-Z_]+)>>")


def render_template(template: str, mapping: dict[str, str]) -> str:
    """<<KEY>> 占位替换; 缺失 key 显式报错而非留洞."""
    out = template
    for k, v in mapping.items():
        out = out.replace(f"<<{k}>>", v)
    leftover = _PLACEHOLDER_RE.findall(out)
    if leftover:
        raise ValueError(f"模板占位符未填充: {leftover}")
    return out


class TemplatedRole(BaseRole):
    """基于模板的角色公共实现."""

    schema: Type[BaseModel]              # 子类声明产出 schema

    def __init__(self, cfg: RoleCfg, prompts_dir: Path):
        if not getattr(self, "schema", None):
            raise TypeError(f"{type(self).__name__} 未声明 schema")
        self.cfg = cfg
        tpl_path = prompts_dir / cfg.prompt
        if not tpl_path.is_file():
            raise FileNotFoundError(f"角色 {cfg.name} 模板缺失: {tpl_path}")
        self.template = tpl_path.read_text(encoding="utf-8")

    # ---------- BaseRole ----------

    @property
    def name(self) -> str:
        return self.cfg.name

    @property
    def kind(self) -> str:
        return self.cfg.kind

    def run(self, client: LLMClient, bundle,
            extra: dict[str, str] | None = None, fake: bool = False,
            on_delta=None, stream: bool = True):
        extra = extra or {}
        if fake:
            return self.fake_output(extra)
        system, user = self._prompt(bundle, extra)
        return client.complete_json(self.cfg.slot, system, user, self.schema,
                                    purpose=self.cfg.name,
                                    on_delta=on_delta, stream=stream)

    # ---------- 内部 ----------

    def _prompt(self, bundle, extra: dict[str, str]) -> tuple[str, str]:
        mapping = {
            "ROLE_NAME": self.cfg.name,
            "FOCUS": self.cfg.focus or "(无附加视角说明)",
            "RUBRIC": "、".join(self.cfg.rubric) or "(自由评分维度)",
            "CONTEXT": bundle.render(),
            **extra,
        }
        if "\n---\n" in self.template:
            sys_t, user_t = self.template.split("\n---\n", 1)
        else:
            sys_t, user_t = "", self.template
        return (render_template(sys_t, mapping).strip(),
                render_template(user_t, mapping).strip())
