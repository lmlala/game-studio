# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""上下文组装: 每次调用从文件重建(零会话累积) + 角色隔离视图 + 预算裁剪.

固定菜单:
⓪ 游戏总览  ① 卡片协议  ②a 任务目标  ② 目标卡片+方向  ③ 依赖卡节选
④ 相邻卡标题  ⑤ 最近轮次摘要(压缩)  ⑥ 主题记忆  ⑦ 代理经验  ⑧ 技能
隔离规则:
- 批判者之间互不可见(并列批判, loop 层保证);
- 提案者看不到原始批判, 只看主编指令(extra 注入), 也不注入代理经验;
- 超预算裁剪顺序 ⑦→⑥→⑤→④→③; ⓪①②a②⑧ 永不裁剪。
"""

from __future__ import annotations

from ..core.cards import Card, RepoIndex
from ..core.config import StudioConfig, TaskCfg
from ..memory.agent import AgentMemory
from ..memory.topic import TopicMemory
from ..memory.workdir import WorkDir
from .bundle import ContextBundle, Section, clip
from .compress import compress_history

# 角色视图: 该 kind 可见的可选段(常驻段全员可见)
VIEW_SECTIONS = {
    "critic": {"依赖卡片节选", "同文件相邻卡片", "最近轮次摘要",
               "主题记忆", "代理经验", "技能"},
    "referee": {"依赖卡片节选", "同文件相邻卡片", "最近轮次摘要",
                "主题记忆", "代理经验", "技能"},
    "proposer": {"依赖卡片节选", "同文件相邻卡片", "最近轮次摘要",
                 "主题记忆", "技能"},
}
TRIM_ORDER = ["代理经验", "主题记忆", "最近轮次摘要",
              "同文件相邻卡片", "依赖卡片节选"]


def _dep_excerpt(card: Card, limit: int) -> str:
    """依赖卡只取 目的 + 如何设计 两节(配餐规则)."""
    purpose = card.fields.get("目的", "").strip()
    how = card.fields.get("如何设计", "").strip()
    body = (f"### {card.id} {card.title} [{card.status}]\n"
            f"**目的**：{purpose}\n**如何设计**：\n{how}")
    return clip(body, limit)


class ContextBuilder:
    """为一张卡片按角色视图组装上下文(确定性: 同库状态同输出)."""

    def __init__(self, repo: RepoIndex, cfg: StudioConfig, work: WorkDir,
                 task: TaskCfg, topic_mem: TopicMemory | None = None,
                 agent_mem: AgentMemory | None = None, plan=None):
        self.repo = repo
        self.cfg = cfg
        self.work = work
        self.task = task
        self.topic_mem = topic_mem
        self.agent_mem = agent_mem
        self.plan = plan                 # RunPlan; None = 直接用任务卡字段
        docs = cfg.pack.docs_root
        self._overview = (docs / cfg.pack.overview_file).read_text(encoding="utf-8")
        self._protocol = (docs / cfg.pack.protocol_file).read_text(encoding="utf-8")

    # ---------- 各段生成 ----------

    def _goal_text(self, card: Card) -> str:
        goal = (self.plan.goal if self.plan else self.task.goal) or "(未声明)"
        constraints = (self.plan.constraints if self.plan
                       else self.task.constraints)
        lines = [f"目标: {goal}"]
        if self.plan:
            try:
                focus = self.plan.todo_for(card.id).focus
            except KeyError:
                focus = ""
            if focus:
                lines.append(f"本卡重点: {focus}")
        if constraints:
            lines.append("约束:")
            lines.extend(f"- {c}" for c in constraints)
        return "\n".join(lines)

    def _target_text(self, card: Card) -> str:
        directions = []
        if self.task.direction.strip():
            directions.append(f"[任务方向] {self.task.direction.strip()}")
        steer = self.work.load_steering(card.id)
        if steer:
            directions.append(f"[人工方向(最高优先级)]\n{steer.strip()}")
        return card.raw + ("\n\n" + "\n\n".join(directions) if directions else "")

    def _deps_text(self, card: Card) -> str:
        limit = self.cfg.pack.settings.dep_excerpt_chars
        return "\n\n".join(_dep_excerpt(self.repo.by_id[d], limit)
                           for d in card.deps if d in self.repo.by_id)

    def _siblings_text(self, card: Card) -> str:
        lines = []
        for s in self.repo.siblings(card):
            first = s.fields.get("目的", "").strip().splitlines()
            lines.append(f"- {s.id} {s.title} [{s.status}] — "
                         f"{first[0] if first else ''}")
        return "\n".join(lines)

    def _history_text(self, card: Card) -> str:
        st = self.cfg.pack.settings
        records = self.work.load_rounds(card.id, st.recent_rounds_in_context)
        return compress_history(records, st.history_round_chars)

    def _memory_texts(self, card: Card) -> tuple[str, str]:
        st = self.cfg.pack.settings
        topic = (self.topic_mem.digest(st.topic_memory_chars)
                 if self.topic_mem else "")
        agent = (self.agent_mem.digest(st.agent_memory_chars)
                 if self.agent_mem else "")
        return topic, agent

    # ---------- 组装与裁剪 ----------

    def build(self, card: Card, role_view: str = "critic",
              skills_text: str = "") -> ContextBundle:
        """组装指定角色视图的上下文; 未知视图显式报错."""
        if role_view not in VIEW_SECTIONS:
            raise ValueError(f"未知角色视图: {role_view}")
        visible = VIEW_SECTIONS[role_view]
        topic_text, agent_text = self._memory_texts(card)

        optional = [
            Section("依赖卡片节选", self._deps_text(card), trimmable=True),
            Section("同文件相邻卡片", self._siblings_text(card), trimmable=True),
            Section("最近轮次摘要", self._history_text(card), trimmable=True),
            Section("主题记忆", topic_text, trimmable=True),
            Section("代理经验", agent_text, trimmable=True),
            Section("技能", skills_text, trimmable=False),
        ]
        sections = [
            Section("游戏总览", self._overview, trimmable=False),
            Section("卡片协议", self._protocol, trimmable=False),
            Section("任务目标", self._goal_text(card), trimmable=False),
            Section("目标卡片", self._target_text(card), trimmable=False),
            *[s for s in optional if s.name in visible],
        ]
        bundle = ContextBundle(sections=sections)
        self._trim(bundle, card.id)
        return bundle

    def _trim(self, bundle: ContextBundle, card_id: str) -> None:
        budget = self.cfg.pack.settings.context_budget_chars
        for name in TRIM_ORDER:
            if bundle.total_chars <= budget:
                return
            for s in bundle.sections:
                if s.name == name and s.trimmable:
                    s.text = clip(s.text, max(len(s.text) // 2, 200))
        # 仍超一轮砍半: 可裁段直接清空(摘要可去档案查, 宪法不能丢)
        for name in TRIM_ORDER:
            if bundle.total_chars <= budget:
                return
            for s in bundle.sections:
                if s.name == name and s.trimmable:
                    s.text = ""
        if bundle.total_chars > budget:
            raise ValueError(
                f"{card_id}: 上下文 {bundle.total_chars} 超预算 {budget} "
                f"且不可再裁(检查总览/协议/技能体积)")
