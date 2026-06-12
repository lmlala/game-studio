# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""CLI 入口: validate / run / status / steer.

用法示例:
  python -m studio.cli validate --pack packs/my-ft
  python -m studio.cli run --pack packs/my-ft --task topis/tasks/run-narrative-director.yaml --dry-run
  python -m studio.cli steer --pack packs/my-ft DIR-04 "荒诞预算改为按队伍独立"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .cards import RepoIndex, atomic_write, replace_card
from .config import StudioConfig, TaskCfg, load_config, load_task
from .context import build_bundle
from .gates import check_revision
from .llm import BudgetExceeded, CostMeter, LLMClient
from .memory import WorkDir
from .roles import Role
from .rounds import CardRunner, Outcome


def _setup(pack: str) -> tuple[StudioConfig, RepoIndex, WorkDir]:
    cfg = load_config(Path(pack))
    repo = RepoIndex.build(cfg.pack.docs_root, cfg.pack.card_files)
    work = WorkDir(cfg.work_dir)
    return cfg, repo, work


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
    cfg, repo, _ = _setup(args.pack)
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
    cfg, repo, work = _setup(args.pack)
    for c in sorted(repo.by_id.values(), key=lambda x: x.id):
        rounds = work.round_count(c.id)
        steer = "S" if work.load_steering(c.id) else " "
        print(f"{c.id}  {c.status:8s} {c.priority} 轮次={rounds:2d} {steer} {c.title}")
    return 0


def cmd_steer(args) -> int:
    cfg, _, work = _setup(args.pack)
    path = work.steer(args.card_id, args.message)
    print(f"已写入方向: {path}")
    return 0


def _git_commit(repo_root: Path, path: Path, card_id: str, msg: str) -> None:
    subprocess.run(["git", "add", str(path)], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m",
                    f"studio({card_id}): {msg}"], cwd=repo_root, check=True)


def cmd_run(args) -> int:
    cfg, repo, work = _setup(args.pack)
    task = load_task(Path(args.task))
    cards = _select_cards(cfg, repo, task)
    run_id = work.new_run_id()
    print(f"run {run_id}: 任务={task.name}, 选中 {len(cards)} 张卡片"
          + (" [dry-run]" if args.dry_run else "")
          + (" [fake]" if args.fake else ""))

    if args.dry_run:
        out_dir = work.run_dir(run_id)
        for c in cards:
            bundle = build_bundle(c, repo, cfg, work, task)
            p = out_dir / f"dryrun-{c.id}.md"
            atomic_write(p, bundle.render())
            print(f"  {c.id}: 上下文 {bundle.total_chars} 字符 -> {p}")
        return 0

    # 任务级覆盖: 轮次上限
    if "high" in task.rounds:
        cfg.pack.settings.max_rounds_high = task.rounds["high"]
    if "normal" in task.rounds:
        cfg.pack.settings.max_rounds_normal = task.rounds["normal"]
    meter = CostMeter(cfg.pack.settings.max_run_usd,
                      cfg.pack.settings.max_run_tokens)
    client = LLMClient(cfg.models, cfg.pack.settings, work.cache, meter)
    proposer = Role(cfg.cast.one("proposer"), cfg.prompts_dir)
    referee = Role(cfg.cast.one("referee"), cfg.prompts_dir)
    # 任务级覆盖: 班子选拔(空 = 全部启用的批判者)
    pool = cfg.cast.critics()
    if task.critics:
        by_name = {r.name: r for r in pool}
        missing = [n for n in task.critics if n not in by_name]
        if missing:
            raise ValueError(f"任务指定的批判者不存在于 cast: {missing}")
        pool = [by_name[n] for n in task.critics]
    critics = [Role(r, cfg.prompts_dir) for r in pool]
    runner = CardRunner(cfg=cfg, repo=repo, work=work, client=client,
                        proposer=proposer, critics=critics, referee=referee,
                        task=task, run_id=run_id, fake=args.fake)
    outcomes: list[Outcome] = []
    try:
        for c in cards:
            print(f"  -> {c.id} {c.title}")
            out = runner.run(c, task.stake.get(c.id, task.default_stake))
            outcomes.append(out)
            _apply_outcome(cfg, repo, work, run_id, c, out, args)
    except BudgetExceeded as e:
        print(f"!! {e} — 提前结束, 已完成的卡片不受影响")
    _write_report(work, run_id, task, outcomes, meter)
    return 0


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


def _write_report(work, run_id, task, outcomes: list[Outcome], meter) -> None:
    lines = [f"# run {run_id} — {task.name}", "",
             f"卡片数: {len(outcomes)} · LLM 调用: {meter.calls} "
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
    for name, fn in [("validate", cmd_validate), ("status", cmd_status)]:
        p = sub.add_parser(name)
        p.add_argument("--pack", required=True)
        p.set_defaults(fn=fn)
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
