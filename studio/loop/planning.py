# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""规划阶段: agent 读任务卡 -> 分析出 goal / todo / 约束, 再执行.

goal 来源优先级:
1. manual   — 任务卡里人工写了 goal(人工覆盖, 不调规划者);
2. planner  — cast 配置了规划者: LLM 读任务卡+卡片清单+主题记忆分析得出;
3. fallback — 无规划者时的确定性推导(永远可用, 离线零成本)。
计划落盘 runs/<id>/plan.json, todo 状态由内核随执行推进(不信任模型自报)。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..context.bundle import ContextBundle, Section
from ..core.cards import Card, atomic_write
from ..core.config import TaskCfg
from ..core.interfaces import BaseRole
from ..memory.topic import TopicMemory
from ..roles.schemas import Plan

TODO_STATUSES = {"pending", "in_progress", "done", "skipped"}


@dataclass
class TodoState:
    """一条工作项; status/result 只由内核写."""

    card_id: str
    focus: str = ""
    status: str = "pending"
    result: str = ""


@dataclass
class RunPlan:
    """一次运行的执行计划(可审计: 全程落盘)."""

    goal: str
    source: str                          # manual | planner | fallback
    todos: list[TodoState] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def todo_for(self, card_id: str) -> TodoState:
        for t in self.todos:
            if t.card_id == card_id:
                return t
        raise KeyError(f"计划中无此卡片: {card_id}")

    def mark(self, card_id: str, status: str, result: str = "") -> None:
        if status not in TODO_STATUSES:
            raise ValueError(f"非法 todo 状态: {status}")
        t = self.todo_for(card_id)
        t.status, t.result = status, result[:120]

    def save(self, path: Path) -> None:
        atomic_write(path, json.dumps(asdict(self), ensure_ascii=False,
                                      indent=1))


class PlanningService:
    """规划入口: 三条路径产出 RunPlan, 并对模型产出做校验补全."""

    def __init__(self, memory_root: Path, topic_chars: int = 1200):
        if topic_chars <= 0:
            raise ValueError("topic_chars 必须为正")
        self.memory_root = memory_root
        self.topic_chars = topic_chars

    def build(self, task: TaskCfg, cards: list[Card],
              planner: BaseRole | None, client, fake: bool) -> RunPlan:
        if not cards:
            raise ValueError("规划需要至少一张目标卡片")
        if task.goal.strip():
            return self._manual(task, cards)
        if planner is not None:
            return self._from_planner(task, cards, planner, client, fake)
        return self._fallback(task, cards)

    # ---------- 路径 1: 人工覆盖 ----------

    def _manual(self, task: TaskCfg, cards: list[Card]) -> RunPlan:
        return RunPlan(goal=task.goal.strip(), source="manual",
                       todos=[TodoState(card_id=c.id) for c in cards],
                       constraints=list(task.constraints))

    # ---------- 路径 2: 规划者分析 ----------

    def _from_planner(self, task: TaskCfg, cards: list[Card],
                      planner: BaseRole, client, fake: bool) -> RunPlan:
        bundle = self._planning_context(task, cards)
        plan: Plan = planner.run(client, bundle,
                                 extra={"TASK_NAME": task.name}, fake=fake)
        if not plan.goal.strip():
            return self._fallback(task, cards)
        # 校验补全: 未知 card_id 丢弃, 缺失卡片补默认项, 保持选卡顺序
        focus_by_id = {t.card_id: t.focus for t in plan.todos
                       if t.card_id in {c.id for c in cards}}
        todos = [TodoState(card_id=c.id, focus=focus_by_id.get(c.id, ""))
                 for c in cards]
        constraints = list(dict.fromkeys(
            list(task.constraints) + [c for c in plan.constraints if c.strip()]))
        return RunPlan(goal=plan.goal.strip(), source="planner", todos=todos,
                       constraints=constraints,
                       risks=[r for r in plan.risks if r.strip()][:3])

    def _planning_context(self, task: TaskCfg,
                          cards: list[Card]) -> ContextBundle:
        task_text = "\n".join(filter(None, [
            f"任务名: {task.name}",
            f"目标文件: {', '.join(task.target_files)}",
            f"方向注入: {task.direction.strip()}" if task.direction.strip() else "",
            f"约束: {'; '.join(task.constraints)}" if task.constraints else "",
        ]))
        card_lines = "\n".join(
            f"- {c.id} {c.title} [{c.status}/{c.priority}] 依赖: "
            f"{', '.join(c.deps) or '无'}" for c in cards)
        return ContextBundle(sections=[
            Section("任务卡", task_text, trimmable=False),
            Section("目标卡片清单", card_lines, trimmable=False),
            Section("主题记忆", self._topics_digest(cards), trimmable=True),
        ])

    def _topics_digest(self, cards: list[Card]) -> str:
        parts = []
        for stem in sorted({c.file.stem for c in cards}):
            d = TopicMemory(self.memory_root, stem).digest(self.topic_chars)
            if d:
                parts.append(f"[{stem}]\n{d}")
        return "\n\n".join(parts)

    # ---------- 路径 3: 确定性回退 ----------

    def _fallback(self, task: TaskCfg, cards: list[Card]) -> RunPlan:
        files = ", ".join(dict.fromkeys(c.file.stem for c in cards))
        goal = f"完成 {files} 中 {len(cards)} 张目标卡片的精修收敛"
        direction = task.direction.strip()
        if direction:
            goal += f"; 重点: {direction.splitlines()[0][:80]}"
        return RunPlan(goal=goal, source="fallback",
                       todos=[TodoState(card_id=c.id) for c in cards],
                       constraints=list(task.constraints))
