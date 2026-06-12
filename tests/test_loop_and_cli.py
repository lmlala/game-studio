# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""fake 模式端到端: CLI 全流程(validate/dry-run/fake run/steer)离线可跑."""

from __future__ import annotations

from pathlib import Path

from studio.cli import main
from studio.context.builder import ContextBuilder
from studio.core.cards import RepoIndex
from studio.core.config import load_config, load_task
from studio.memory.workdir import WorkDir


def _write_task(pack: Path, **over) -> Path:
    p = pack / "task.yaml"
    lines = ["name: toy-task", "goal: 玩具任务目标", "target_files: [cards.md]",
             "max_cards: 8", "default_stake: normal"]
    for k, v in over.items():
        lines.append(f"{k}: {v}")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def test_validate_and_status(toy_pack: Path, capsys):
    assert main(["validate", "--pack", str(toy_pack)]) == 0
    assert main(["status", "--pack", str(toy_pack)]) == 0
    out = capsys.readouterr().out
    assert "TOY-01" in out and "TOY-02" in out


def test_run_id_has_subsecond_entropy(tmp_path: Path):
    work = WorkDir(tmp_path / "work")
    ids = {work.new_run_id() for _ in range(3)}
    assert len(ids) == 3


def test_dry_run_writes_context(toy_pack: Path):
    task = _write_task(toy_pack)
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--dry-run"]) == 0
    work = toy_pack.parent / "work"          # 默认 work_dir = pack 上两级/work
    dumps = list(work.rglob("dryrun-TOY-01.md"))
    assert dumps, "dry-run 应导出上下文文件"
    text = dumps[0].read_text(encoding="utf-8")
    for section in ["游戏总览", "卡片协议", "任务目标", "目标卡片",
                    "同文件相邻卡片"]:
        assert section in text
    assert "玩具任务目标" in text


def test_dry_run_plain_compact_and_no_stream(toy_pack: Path, capsys):
    task = _write_task(toy_pack)
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--dry-run", "--no-rich", "--compact"]) == 0
    out = capsys.readouterr().out
    assert "[stage:start] planning" in out
    assert "[plan:updated]" in out
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--dry-run", "--no-stream"]) == 0
    assert capsys.readouterr().out == ""
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--dry-run", "--disable-message", "--no-rich"]) == 0


def test_fake_run_converges_and_bumps_status(toy_pack: Path):
    """fake 主编直接判收敛 → draft 卡应被代码升级为 refined 并写回."""
    task = _write_task(toy_pack)
    cards_file = None
    cfg = load_config(toy_pack)
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--fake", "--no-git"]) == 0
    cards_file = cfg.pack.docs_root / "cards.md"
    text = cards_file.read_text(encoding="utf-8")
    assert "### TOY-01" in text
    block = text.split("### TOY-01")[1]
    assert "状态: refined" in block.split("###")[0], "draft 应升级为 refined"
    # refined 卡(TOY-02)保持原状
    assert "状态: refined · 优先级: P1" in text
    # 报告与轮次记录落盘
    work = WorkDir(cfg.work_dir)
    assert list(work.runs.rglob("report.md"))
    assert work.round_count("TOY-01") == 1


def test_steer_appears_in_context(toy_pack: Path):
    assert main(["steer", "--pack", str(toy_pack), "TOY-01",
                 "改为按队伍独立预算"]) == 0
    cfg = load_config(toy_pack)
    repo = RepoIndex.build(cfg.pack.docs_root, cfg.pack.card_files)
    work = WorkDir(cfg.work_dir)
    task = load_task(_write_task(toy_pack))
    builder = ContextBuilder(repo, cfg, work, task)
    rendered = builder.build(repo.by_id["TOY-01"]).render()
    assert "改为按队伍独立预算" in rendered
    assert "人工方向" in rendered


def test_immutable_file_rejected_as_target(toy_pack: Path):
    task = _write_task(toy_pack, target_files="[protocol.md]")
    try:
        main(["run", "--pack", str(toy_pack), "--task", str(task),
              "--dry-run"])
        raise AssertionError("禁改文件作为任务目标应当报错")
    except ValueError as e:
        assert "禁改" in str(e)


def test_task_critic_selection(toy_pack: Path):
    """任务级班子选拔: 合法名单生效, 未知名单报错."""
    task = _write_task(toy_pack, critics="[批判者]")
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--fake", "--no-git"]) == 0
    bad = _write_task(toy_pack, critics="[不存在的角色]")
    try:
        main(["run", "--pack", str(toy_pack), "--task", str(bad),
              "--fake", "--no-git"])
        raise AssertionError("未知批判者应报错")
    except ValueError as e:
        assert "不存在" in str(e)


def test_task_rounds_override(toy_pack: Path):
    task_path = _write_task(toy_pack, rounds="{high: 2, normal: 1}")
    t = load_task(task_path)
    assert t.rounds == {"high": 2, "normal": 1}


def test_task_goal_optional(toy_pack: Path):
    """goal 是可选的人工覆盖: 不写由规划阶段分析得出."""
    p = toy_pack / "no-goal-task.yaml"
    p.write_text("name: ng\ntarget_files: [cards.md]\n", encoding="utf-8")
    t = load_task(p)
    assert t.goal == ""


def test_fake_run_writes_plan(toy_pack: Path):
    """run 必须先产出计划: plan.json 落盘且 todo 全部完成."""
    import json
    task = _write_task(toy_pack)
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--fake", "--no-git"]) == 0
    cfg = load_config(toy_pack)
    plans = sorted(WorkDir(cfg.work_dir).runs.rglob("plan.json"))
    assert plans, "run 应落盘 plan.json"
    plan = json.loads(plans[-1].read_text(encoding="utf-8"))
    assert plan["goal"] == "玩具任务目标" and plan["source"] == "manual"
    assert all(t["status"] == "done" for t in plan["todos"])
    run_dir = plans[-1].parent
    assert (run_dir / "events.jsonl").is_file()
    assert (run_dir / "run.log").is_file()
    assert "card:done" in (run_dir / "run.log").read_text(encoding="utf-8")


def test_resume_skips_done_todos(toy_pack: Path, capsys):
    """resume 读取 plan.json, 默认跳过 done todo."""
    task = _write_task(toy_pack)
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--fake", "--no-git"]) == 0
    cfg = load_config(toy_pack)
    work = WorkDir(cfg.work_dir)
    run_id = sorted(p.parent.name for p in work.runs.rglob("plan.json"))[-1]
    assert main(["run", "--pack", str(toy_pack), "--task", str(task),
                 "--resume", run_id, "--fake", "--no-git"]) == 0
    out = capsys.readouterr().out
    assert "resume:loaded" in out
    assert "cards=0" in out


def test_context_budget_trims(toy_pack: Path):
    """超预算时可裁段被裁剪, 宪法段保留."""
    cfg = load_config(toy_pack)
    cfg.pack.settings.context_budget_chars = 1200
    cfg.pack.settings.dep_excerpt_chars = 200
    repo = RepoIndex.build(cfg.pack.docs_root, cfg.pack.card_files)
    work = WorkDir(cfg.work_dir)
    task = load_task(_write_task(toy_pack))
    builder = ContextBuilder(repo, cfg, work, task)
    bundle = builder.build(repo.by_id["TOY-02"])
    assert bundle.total_chars <= 1200
    names = [s.name for s in bundle.sections if s.text.strip()]
    assert "游戏总览" in names and "卡片协议" in names
