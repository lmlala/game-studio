# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""CLI 入口: validate / run / status / steer / skills / memory.

用法示例:
  python -m studio.cli validate --pack packs/my-ft
  python -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --dry-run
  python -m studio.cli skills --pack packs/my-ft
  python -m studio.cli memory --pack packs/my-ft [--topic 05-event-system]
  python -m studio.cli steer --pack packs/my-ft DIR-04 "荒诞预算改为按队伍独立"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .context.builder import ContextBuilder
from .core.cards import RepoIndex, atomic_write, replace_card
from .core.config import StudioConfig, TaskCfg, load_config, load_task
from .core.gates import check_revision
from .llm.client import BudgetExceeded, CostMeter, LLMClient
from .loop.planning import PlanningService, RunPlan
from .loop.runner import CardRunner, Outcome
from .memory.agent import AgentMemory
from .memory.topic import TopicMemory
from .memory.workdir import WorkDir
from .roles.factory import RoleFactory
from .skills.loader import SkillLoader
from .skills.registry import SkillRegistry


def _setup(pack: str) -> tuple[StudioConfig, RepoIndex, WorkDir, SkillRegistry]:
    cfg = load_config(Path(pack))
    repo = RepoIndex.build(cfg.pack.docs_root, cfg.pack.card_files)
    work = WorkDir(cfg.work_dir)
    registry = SkillRegistry.build(cfg.pack.skills_dirs)
    return cfg, repo, work, registry


def _select_cards(cfg: StudioConfig, repo: RepoIndex, task: TaskCfg) -> list:
    """任务目标卡片筛选与排序: stake > 优先级 > 文件内顺序."""
    targets = []
    immutable = {str((cfg.pack.docs_root / f).resolve())
                 for f in cfg.pack.immutable_files}
    for rel in task.target_files:
        path = (cfg.pack.docs_root / rel).resolve()
        if str(path) in immutable:
            raise ValueError(f"任务目标是禁改文件: {rel}")
        if path not in repo.files:
            raise ValueError(f"任务目标未被索引(检查 pack.card_files): {rel}")
        for c in repo.files[path].cards:
            if task.include_ids and c.id not in task.include_ids:
                continue
            if c.id in task.exclude_ids:
                continue
            if c.status not in cfg.pack.guards.writable_statuses:
                continue
            targets.append(c)
    stake_rank = {"high": 0, "normal": 1, "low": 2}
    prio_rank = {"P0": 0, "P1": 1, "P2": 2}
    targets.sort(key=lambda c: (
        stake_rank.get(task.stake.get(c.id, task.default_stake), 1),
        prio_rank.get(c.priority, 1)))
    return targets[:task.max_cards]


def cmd_validate(args) -> int:
    cfg, repo, _, _ = _setup(args.pack)
    n_err = 0
    for card in repo.by_id.values():
        _, errs = check_revision(card, card.raw, set(repo.by_id),
                                 cfg.pack.guards,
                                 cfg.pack.settings.bloat_ratio)
        real = [e for e in errs if e.code not in {"READONLY_CARD"}]
        for e in real:
            print(f"{card.file.name} {card.id}: {e}")
        n_err += len(real)
    print(f"validate: {len(repo.by_id)} 张卡片, {n_err} 个存量问题")
    return 0  # 存量问题只报告不阻塞(它们正是 agent 要修的对象)


def cmd_status(args) -> int:
    cfg, repo, work, _ = _setup(args.pack)
    for c in sorted(repo.by_id.values(), key=lambda x: x.id):
        rounds = work.round_count(c.id)
        steer = "S" if work.load_steering(c.id) else " "
        print(f"{c.id}  {c.status:8s} {c.priority} 轮次={rounds:2d} {steer} {c.title}")
    return 0


def cmd_steer(args) -> int:
    cfg, _, work, _ = _setup(args.pack)
    path = work.steer(args.card_id, args.message)
    print(f"已写入方向: {path}")
    return 0


def cmd_skills(args) -> int:
    """列出全部技能(加载即校验, 坏技能在此显式失败)."""
    _, _, _, registry = _setup(args.pack)
    if not registry.by_id:
        print("无已注册技能")
        return 0
    for s in sorted(registry.by_id.values(), key=lambda x: x.id):
        roles = ",".join(s.applies_to_roles) or "全角色"
        trig = ",".join(s.triggers) or "-"
        print(f"{s.id:24s} v{s.version} {s.chars:5d}字 角色[{roles}] 触发[{trig}]")
    print(f"skills: {len(registry.by_id)} 个技能可用")
    return 0


def cmd_memory(args) -> int:
    """查看 agent 经验与主题记忆摘要."""
    cfg, _, work, _ = _setup(args.pack)
    st = cfg.pack.settings
    agent = AgentMemory(work.memory)
    print("== 代理经验 ==")
    print(agent.digest(st.agent_memory_chars) or "(空)")
    topics_dir = work.memory / "topics"
    names = ([args.topic] if args.topic else
             sorted(p.stem for p in topics_dir.glob("*.jsonl"))
             if topics_dir.is_dir() else [])
    for name in names:
        print(f"\n== 主题记忆: {name} ==")
        print(TopicMemory(work.memory, name).digest(st.topic_memory_chars)
              or "(空)")
    return 0


def _git_commit(repo_root: Path, path: Path, card_id: str, msg: str) -> None:
    subprocess.run(["git", "add", str(path)], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m",
                    f"studio({card_id}): {msg}"], cwd=repo_root, check=True)


def cmd_run(args) -> int:
    cfg, repo, work, registry = _setup(args.pack)
    task = load_task(Path(args.task))
    cards = _select_cards(cfg, repo, task)
    run_id = work.new_run_id()
    st = cfg.pack.settings
    meter = CostMeter(st.max_run_usd, st.max_run_tokens)
    client = LLMClient(cfg.models, st, work.cache, meter)

    # 规划阶段: 读任务卡分析 goal/todo(dry-run 不调 LLM, 走确定性回退)
    planning = PlanningService(work.memory, st.topic_memory_chars)
    planner = (None if args.dry_run
               else RoleFactory.build_planner(cfg.cast, cfg.prompts_dir))
    plan = planning.build(task, cards, planner, client, args.fake)
    plan_path = work.run_dir(run_id) / "plan.json"
    plan.save(plan_path)
    print(f"run {run_id}: 任务={task.name}, 目标[{plan.source}]={plan.goal[:60]}, "
          f"选中 {len(cards)} 张卡片"
          + (" [dry-run]" if args.dry_run else "")
          + (" [fake]" if args.fake else ""))

    builder = ContextBuilder(repo, cfg, work, task,
                             agent_mem=AgentMemory(work.memory), plan=plan)
    if args.dry_run:
        out_dir = work.run_dir(run_id)
        for c in cards:
            bundle = builder.build(c, role_view="critic")
            p = out_dir / f"dryrun-{c.id}.md"
            atomic_write(p, bundle.render())
            print(f"  {c.id}: 上下文 {bundle.total_chars} 字符 -> {p}")
        return 0

    if "high" in task.rounds:
        st.max_rounds_high = task.rounds["high"]
    if "normal" in task.rounds:
        st.max_rounds_normal = task.rounds["normal"]
    proposer, critics, referee = RoleFactory.build_cast(
        cfg.cast, cfg.prompts_dir, task.critics)
    loader = SkillLoader(registry, st.max_skills_per_role,
                         st.skill_context_chars)
    runner = CardRunner(cfg=cfg, repo=repo, work=work, client=client,
                        proposer=proposer, critics=critics, referee=referee,
                        task=task, run_id=run_id, skill_loader=loader,
                        builder=builder, fake=args.fake)
    outcomes: list[Outcome] = []
    try:
        for c in cards:
            print(f"  -> {c.id} {c.title}")
            plan.mark(c.id, "in_progress")
            plan.save(plan_path)
            out = runner.run(c, task.stake.get(c.id, task.default_stake))
            outcomes.append(out)
            plan.mark(c.id, "done", out.result)
            plan.save(plan_path)
            _apply_outcome(cfg, repo, work, run_id, c, out, args)
    except BudgetExceeded as e:
        print(f"!! {e} — 提前结束, 已完成的卡片不受影响")
        for t in plan.todos:
            if t.status in {"pending", "in_progress"}:
                plan.mark(t.card_id, "skipped", "预算触顶")
        plan.save(plan_path)
    _write_report(work, run_id, plan, task, outcomes, meter)
    _record_agent_memory(work, run_id, outcomes)
    return 0


def _record_agent_memory(work: WorkDir, run_id: str,
                         outcomes: list[Outcome]) -> None:
    if not outcomes:
        return
    gate_codes = []
    for o in outcomes:
        gate_codes.extend(e.split("]")[0].strip("[") for e in o.gate_errors if e)
    AgentMemory(work.memory).record_run(
        run_id, total=len(outcomes),
        converged=sum(1 for o in outcomes if o.result == "converged"),
        gate_errors=gate_codes,
        dropped_unevidenced=sum(o.dropped_issues for o in outcomes))


def _apply_outcome(cfg, repo, work, run_id, card, out: Outcome, args) -> None:
    work.journal(run_id, "card.done", card=card.id, result=out.result,
                 rounds=out.rounds, score=round(out.best_score, 2))
    if out.result == "converged" and out.changed:
        cf = repo.files[card.file]
        new_text = replace_card(cf, card.id, out.final_block)
        atomic_write(card.file, new_text)
        if not args.no_git:
            repo_root = card.file.parent
            _git_commit(repo_root, card.file, card.id,
                        f"refine via {run_id} (rounds={out.rounds})")
        print(f"     converged({out.rounds}轮) 已写回")
    elif out.candidate_block and out.candidate_block != card.raw:
        p = work.run_dir(run_id) / "candidates" / f"{card.id}.md"
        atomic_write(p, out.candidate_block)
        print(f"     {out.result}({out.reason[:60]}) 候选稿 -> {p}")
    else:
        print(f"     {out.result}: {out.reason[:80]}")


def _write_report(work, run_id, plan: RunPlan, task, outcomes: list[Outcome],
                  meter) -> None:
    lines = [f"# run {run_id} — {task.name}", "",
             f"目标[{plan.source}]: {plan.goal}", ""]
    if plan.risks:
        lines += ["预判风险: " + "; ".join(plan.risks), ""]
    lines += ["## 计划执行", "", "| 卡片 | 重点 | 状态 |", "|---|---|---|"]
    for t in plan.todos:
        lines.append(f"| {t.card_id} | {t.focus or '-'} "
                     f"| {t.status}{(' · ' + t.result) if t.result else ''} |")
    lines += ["", f"卡片数: {len(outcomes)} · LLM 调用: {meter.calls} "
              f"(缓存命中 {meter.cache_hits}) · 费用: ${meter.total_usd:.4f}", "",
              "| 卡片 | 结果 | 轮次 | 最佳分 | 说明 |", "|---|---|---|---|---|"]
    for o in outcomes:
        lines.append(f"| {o.card_id} | {o.result} | {o.rounds} "
                     f"| {o.best_score:.2f} | {o.reason[:60]} |")
    work.write_report(run_id, "\n".join(lines) + "\n")
    for e in meter.entries:
        work.append_ledger({"run": run_id, **e})
    print(f"报告: {work.run_dir(run_id) / 'report.md'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="studio", description="设计卡片精修 agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("validate", cmd_validate), ("status", cmd_status),
                     ("skills", cmd_skills)]:
        p = sub.add_parser(name)
        p.add_argument("--pack", required=True)
        p.set_defaults(fn=fn)
    p = sub.add_parser("memory")
    p.add_argument("--pack", required=True)
    p.add_argument("--topic", default="")
    p.set_defaults(fn=cmd_memory)
    p = sub.add_parser("steer")
    p.add_argument("--pack", required=True)
    p.add_argument("card_id")
    p.add_argument("message")
    p.set_defaults(fn=cmd_steer)
    p = sub.add_parser("run")
    p.add_argument("--pack", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fake", action="store_true",
                   help="不调真实 LLM, 用结构合法的假产出走全流程")
    p.add_argument("--no-git", action="store_true")
    p.set_defaults(fn=cmd_run)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
