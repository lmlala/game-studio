# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""轮次循环: 提案 → 批判 → 裁决 → 修订, 直到收敛或停机.

写回策略(保守): 只有 converged 的卡片才写回库; 未收敛的最佳候选稿
存入 runs/<id>/candidates/ 供人工裁决 —— agent 永远不把半成品塞进库。
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field

from .cards import Card, RepoIndex, parse_block
from .config import StudioConfig, TaskCfg
from .context import build_bundle
from .gates import check_revision, filter_unevidenced_issues
from .llm import LLMClient
from .memory import WorkDir
from .roles import Critique, Revision, Role, Verdict

META_STATUS_RE = re.compile(r"^(状态:\s*)(\S+)", re.M)


@dataclass
class Outcome:
    card_id: str
    result: str                 # converged | escalated | failed | max_rounds
    rounds: int
    reason: str = ""
    changed: bool = False
    best_score: float = 0.0
    final_block: str = ""       # converged 时的最终块
    candidate_block: str = ""   # 未收敛时的最佳候选
    dropped_issues: int = 0


def _mean_score(critiques: dict[str, Critique]) -> float:
    vals = [v for c in critiques.values() for v in c.scores.values()]
    return sum(vals) / len(vals) if vals else 0.0


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _bump_status(block: str) -> str:
    """收敛后由代码确定性地把 draft 升为 refined(不信任模型自报)."""
    def repl(m: re.Match) -> str:
        return m.group(1) + ("refined" if m.group(2) == "draft" else m.group(2))
    return META_STATUS_RE.sub(repl, block, count=1)


@dataclass
class CardRunner:
    cfg: StudioConfig
    repo: RepoIndex
    work: WorkDir
    client: LLMClient
    proposer: Role
    critics: list[Role]
    referee: Role
    task: TaskCfg
    run_id: str
    fake: bool = False
    known_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.known_ids:
            self.known_ids = set(self.repo.by_id)

    # ---------- 单轮内的步骤 ----------

    def _critique_phase(self, bundle) -> tuple[dict[str, Critique], list[dict], int]:
        critiques: dict[str, Critique] = {}
        all_issues: list[dict] = []
        dropped = 0
        for critic in self.critics:
            c: Critique = critic.run(self.client, bundle, fake=self.fake)
            kept, n_drop = filter_unevidenced_issues(
                [i.model_dump() for i in c.issues])
            dropped += n_drop
            c.issues = [i for i in c.issues
                        if str(i.evidence).strip()]
            critiques[critic.cfg.name] = c
            for i in kept:
                all_issues.append({"from": critic.cfg.name, **i})
        return critiques, all_issues, dropped

    def _verdict_phase(self, bundle, all_issues: list[dict],
                       open_issues: list[dict]) -> Verdict:
        extra = {
            "CRITIQUES": json.dumps(all_issues, ensure_ascii=False, indent=1),
            "OPEN_ISSUES": json.dumps(open_issues, ensure_ascii=False, indent=1),
        }
        return self.referee.run(self.client, bundle, extra=extra, fake=self.fake)

    def _revise_phase(self, bundle, verdict: Verdict, current_card: Card,
                      original: Card) -> tuple[Card | None, str, list[str]]:
        """提案者修订 + 门禁; 失败带错误重试一次. 返回(新卡|None, 块, 错误)."""
        directives = [d.model_dump() for d in verdict.directives
                      if d.action == "accept"]
        extra = {"DIRECTIVES": json.dumps(directives, ensure_ascii=False, indent=1),
                 "CURRENT_CARD": current_card.raw}
        for attempt in (0, 1):
            rev: Revision = self.proposer.run(self.client, bundle,
                                              extra=extra, fake=self.fake)
            new_card, errs = check_revision(
                original, rev.card_markdown, self.known_ids,
                self.cfg.pack.guards, self.cfg.pack.settings.bloat_ratio,
                expansion_justified=bool(rev.expansion_rationale.strip()))
            if not errs:
                return new_card, rev.card_markdown, []
            if attempt == 0:
                extra["DIRECTIVES"] += (
                    "\n\n[机器门禁拒收, 必须修复以下问题后重新输出完整卡片]\n"
                    + "\n".join(str(e) for e in errs))
        return None, "", [str(e) for e in errs]

    # ---------- 主循环 ----------

    def run(self, card: Card, stake: str) -> Outcome:
        st = self.cfg.pack.settings
        max_rounds = (st.max_rounds_high if stake == "high"
                      else st.max_rounds_normal)
        original = card
        current = card
        history_blocks = [card.raw]
        open_issues: list[dict] = []
        best_score, best_block = -1.0, card.raw
        prev_score: float | None = None
        total_dropped = 0
        rounds_done = 0

        for round_no in range(1, max_rounds + 1):
            rounds_done = round_no
            self.work.journal(self.run_id, "round.start",
                              card=card.id, round=round_no)
            bundle = build_bundle(current, self.repo, self.cfg,
                                  self.work, self.task)
            critiques, all_issues, dropped = self._critique_phase(bundle)
            total_dropped += dropped
            score = _mean_score(critiques)
            if score > best_score:
                best_score, best_block = score, current.raw
            verdict = self._verdict_phase(bundle, all_issues, open_issues)
            self.work.record_round(card.id, self.work.round_count(card.id) + 1, {
                "run_id": self.run_id, "stake": stake, "score": score,
                "critiques": {k: v.model_dump() for k, v in critiques.items()},
                "verdict": verdict.model_dump(),
                "open_issues": all_issues, "dropped_unevidenced": dropped,
            })
            # 分数回退保护
            if prev_score is not None and prev_score - score >= st.score_regression_stop:
                return Outcome(card.id, "escalated", round_no,
                               reason=f"分数回退 {prev_score:.2f}->{score:.2f}, "
                                      f"已回滚至最优版本",
                               candidate_block=best_block,
                               best_score=best_score,
                               dropped_issues=total_dropped)
            prev_score = score

            if verdict.decision == "converged":
                final = _bump_status(current.raw)
                return Outcome(card.id, "converged", round_no,
                               reason=verdict.rationale[:200],
                               changed=(final != original.raw),
                               final_block=final, best_score=best_score,
                               dropped_issues=total_dropped)
            if verdict.decision == "escalate":
                return Outcome(card.id, "escalated", round_no,
                               reason=verdict.rationale[:200],
                               candidate_block=best_block,
                               best_score=best_score,
                               dropped_issues=total_dropped)

            new_card, new_block, errs = self._revise_phase(
                bundle, verdict, current, original)
            if new_card is None:
                return Outcome(card.id, "failed", round_no,
                               reason="门禁两次拒收: " + "; ".join(errs)[:300],
                               candidate_block=best_block,
                               best_score=best_score,
                               dropped_issues=total_dropped)
            # 振荡检测: 与两轮前文本高度相似 = 来回改
            if len(history_blocks) >= 2 and _similarity(
                    new_block, history_blocks[-2]) > st.oscillation_ratio:
                return Outcome(card.id, "escalated", round_no,
                               reason="振荡检测: 修订在两个版本间来回",
                               candidate_block=best_block,
                               best_score=best_score,
                               dropped_issues=total_dropped)
            history_blocks.append(new_block)
            current = new_card
            open_issues = [d.model_dump() for d in verdict.directives
                           if d.action == "accept"]

        return Outcome(card.id, "max_rounds", rounds_done,
                       reason="达到轮次上限未收敛",
                       candidate_block=(current.raw if current.raw != original.raw
                                        else best_block),
                       best_score=best_score, dropped_issues=total_dropped)
