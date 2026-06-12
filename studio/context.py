# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""上下文组装: 每次调用从文件系统重新构建, 无会话累积.

固定菜单(docs/m0-design-agent.md AGT-04):
⓪ 游戏总览  ① 00 协议  ② 目标卡片+方向注入  ③ 依赖卡节选
④ 同文件相邻卡标题  ⑤ 最近轮次摘要
超预算按 ⑤→④→③ 顺序裁剪; ⓪①② 永不裁剪(宪法与对象不可省)。
"""

from __future__ import annotations

from dataclasses import dataclass

from .cards import Card, RepoIndex
from .config import StudioConfig, TaskCfg
from .memory import WorkDir


@dataclass
class Section:
    name: str
    text: str
    trimmable: bool


@dataclass
class ContextBundle:
    """组装结果: 有序段落 + 统计; render() 产出最终 user prompt 主体."""

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


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[截断, 原文 {len(text)} 字符]"


def _dep_excerpt(card: Card, limit: int) -> str:
    """依赖卡只取 目的 + 如何设计 两节(14 AGT-04 的配餐规则)."""
    purpose = card.fields.get("目的", "").strip()
    how = card.fields.get("如何设计", "").strip()
    body = (f"### {card.id} {card.title} [{card.status}]\n"
            f"**目的**：{purpose}\n**如何设计**：\n{how}")
    return _clip(body, limit)


def build_bundle(card: Card, repo: RepoIndex, cfg: StudioConfig,
                 work: WorkDir, task: TaskCfg) -> ContextBundle:
    """为一张卡片组装完整上下文(确定性: 同库状态同输出)."""
    st = cfg.pack.settings
    docs = cfg.pack.docs_root
    overview = (docs / cfg.pack.overview_file).read_text(encoding="utf-8")
    protocol = (docs / cfg.pack.protocol_file).read_text(encoding="utf-8")

    # ② 目标卡 + 方向
    directions = []
    if task.direction.strip():
        directions.append(f"[任务方向] {task.direction.strip()}")
    steer = work.load_steering(card.id)
    if steer:
        directions.append(f"[人工方向(最高优先级)]\n{steer.strip()}")
    target = card.raw + ("\n\n" + "\n\n".join(directions) if directions else "")

    # ③ 依赖卡节选(按声明顺序, 缺失依赖由 gates 报, 这里跳过)
    deps_text = "\n\n".join(
        _dep_excerpt(repo.by_id[d], st.dep_excerpt_chars)
        for d in card.deps if d in repo.by_id)

    # ④ 相邻卡标题+目的首行(防重复/冲突)
    sib_lines = []
    for s in repo.siblings(card):
        first = s.fields.get("目的", "").strip().splitlines()
        sib_lines.append(f"- {s.id} {s.title} [{s.status}] — "
                         f"{first[0] if first else ''}")
    siblings = "\n".join(sib_lines)

    # ⑤ 最近轮次摘要(防拉锯: 模型必须知道上几轮改了什么/为什么)
    hist_parts = []
    for r in work.load_rounds(card.id, st.recent_rounds_in_context):
        verdict = r.get("verdict", {})
        hist_parts.append(
            f"[第{r.get('round')}轮] 裁决={verdict.get('decision')} "
            f"理由={verdict.get('rationale', '')[:300]} "
            f"开放问题={[i.get('claim', '')[:80] for i in r.get('open_issues', [])]}")
    history = "\n".join(hist_parts)

    sections = [
        Section("游戏总览", overview, trimmable=False),
        Section("卡片协议", protocol, trimmable=False),
        Section("目标卡片", target, trimmable=False),
        Section("依赖卡片节选", deps_text, trimmable=True),
        Section("同文件相邻卡片", siblings, trimmable=True),
        Section("最近轮次摘要", history, trimmable=True),
    ]
    bundle = ContextBundle(sections=sections)

    # 预算裁剪: ⑤→④→③ 逐段砍半直至达标(确定性)
    order = ["最近轮次摘要", "同文件相邻卡片", "依赖卡片节选"]
    for name in order:
        if bundle.total_chars <= st.context_budget_chars:
            break
        for s in bundle.sections:
            if s.name == name and s.trimmable:
                s.text = _clip(s.text, max(len(s.text) // 2, 400))
    if bundle.total_chars > st.context_budget_chars:
        # 仍超: 非可裁段过大属于配置问题, 显式失败优于静默截断宪法
        raise ValueError(
            f"{card.id}: 上下文 {bundle.total_chars} 超预算 "
            f"{st.context_budget_chars} 且不可再裁(检查总览/协议文件体积)")
    return bundle
