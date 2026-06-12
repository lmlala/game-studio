# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""规划阶段测试: goal 来源优先级 / planner 产出校验 / todo 状态机."""

from __future__ import annotations

from pathlib import Path

import pytest

from studio.core.cards import RepoIndex
from studio.core.config import RoleCfg, load_config, load_task
from studio.loop.planning import PlanningService, RunPlan, TodoState
from studio.roles.runtime import PlannerRole

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "studio" / "prompts"


def _cards_and_task(toy_pack: Path, goal: str = "", direction: str = ""):
    cfg = load_config(toy_pack)
    repo = RepoIndex.build(cfg.pack.docs_root, cfg.pack.card_files)
    p = toy_pack / "ptask.yaml"
    lines = ["name: plan-task", "target_files: [cards.md]"]
    if goal:
        lines.append(f"goal: {goal}")
    if direction:
        lines.append(f"direction: {direction}")
    p.write_text("\n".join(lines), encoding="utf-8")
    return list(repo.by_id.values()), load_task(p)


def test_manual_goal_overrides_planner(toy_pack: Path, tmp_path: Path):
    """人工写了 goal: 不调规划者, source=manual."""
    cards, task = _cards_and_task(toy_pack, goal="人工目标")
    planner = PlannerRole(RoleCfg(name="规划者", kind="planner",
                                  slot="workhorse", prompt="planner.md"),
                          PROMPTS_DIR)
    plan = PlanningService(tmp_path).build(task, cards, planner,
                                           client=None, fake=True)
    assert plan.source == "manual" and plan.goal == "人工目标"
    assert {t.card_id for t in plan.todos} == {c.id for c in cards}


def test_planner_path_validates_todos(toy_pack: Path, tmp_path: Path):
    """规划者产出: 未知 card_id 丢弃, 缺失卡补全, 顺序保持选卡顺序."""
    cards, task = _cards_and_task(toy_pack)
    planner = PlannerRole(RoleCfg(name="规划者", kind="planner",
                                  slot="workhorse", prompt="planner.md"),
                          PROMPTS_DIR)
    plan = PlanningService(tmp_path).build(task, cards, planner,
                                           client=None, fake=True)
    assert plan.source == "planner" and plan.goal.startswith("[fake]")
    assert [t.card_id for t in plan.todos] == [c.id for c in cards]


def test_fallback_without_planner(toy_pack: Path, tmp_path: Path):
    """无规划者且无人工 goal: 确定性回退, direction 进 goal."""
    cards, task = _cards_and_task(toy_pack, direction="重点收紧验收标准")
    plan = PlanningService(tmp_path).build(task, cards, planner=None,
                                           client=None, fake=False)
    assert plan.source == "fallback"
    assert "cards" in plan.goal and "重点收紧验收标准" in plan.goal


def test_planning_requires_cards(toy_pack: Path, tmp_path: Path):
    _, task = _cards_and_task(toy_pack)
    with pytest.raises(ValueError):
        PlanningService(tmp_path).build(task, [], None, None, False)


def test_todo_state_machine(tmp_path: Path):
    plan = RunPlan(goal="g", source="manual",
                   todos=[TodoState(card_id="TOY-01")])
    plan.mark("TOY-01", "in_progress")
    plan.mark("TOY-01", "done", "converged")
    assert plan.todo_for("TOY-01").result == "converged"
    with pytest.raises(ValueError):
        plan.mark("TOY-01", "未知状态")
    with pytest.raises(KeyError):
        plan.mark("GHOST-99", "done")
    path = tmp_path / "plan.json"
    plan.save(path)
    assert "converged" in path.read_text(encoding="utf-8")
