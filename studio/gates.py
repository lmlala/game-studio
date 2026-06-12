# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""机器门禁: 对 LLM 产出的修订稿做确定性校验, 零 LLM.

原则(见 docs/m0-design-agent.md AGT-05): 信任模型的产出, 验证模型的产出。
所有检查都是纯函数, 返回错误清单; 调用方(rounds)决定拦截或重试。
"""

from __future__ import annotations

from dataclasses import dataclass

from .cards import (Card, CardParseError, FIELD_NAMES, ID_REF_RE,
                    VALID_STATUSES, parse_block)
from .config import GuardCfg


@dataclass
class GateError:
    code: str
    msg: str

    def __str__(self) -> str:  # pragma: no cover - 展示用
        return f"[{self.code}] {self.msg}"


def _check_identity(old: Card, new: Card) -> list[GateError]:
    errs = []
    if new.id != old.id:
        errs.append(GateError("ID_CHANGED", f"ID 被改: {old.id} -> {new.id}"))
    if new.title.strip() != old.title.strip():
        errs.append(GateError("TITLE_CHANGED",
                              f"标题被改: {old.title!r} -> {new.title!r}"))
    return errs


def _check_status(old: Card, new: Card, guards: GuardCfg) -> list[GateError]:
    errs = []
    if new.status not in VALID_STATUSES:
        errs.append(GateError("STATUS_INVALID", f"非法状态: {new.status}"))
        return errs
    if old.status not in guards.writable_statuses:
        errs.append(GateError("READONLY_CARD",
                              f"{old.id} 状态 {old.status} 不可被 agent 修改"))
    # 允许迁移: 保持原状态 或 draft->refined
    legal = {old.status, "refined"} if old.status == "draft" else {old.status}
    if new.status not in legal:
        errs.append(GateError("STATUS_TRANSITION",
                              f"非法状态迁移: {old.status} -> {new.status}"))
    return errs


def _check_fields(new: Card) -> list[GateError]:
    errs = []
    for name in FIELD_NAMES:
        body = new.fields.get(name, "").strip()
        if not body:
            errs.append(GateError("FIELD_MISSING", f"字段缺失或为空: **{name}**"))
    seen = [n for n in new.fields]
    expect = [n for n in FIELD_NAMES if n in seen]
    if seen != expect:
        errs.append(GateError("FIELD_ORDER", f"字段顺序错误: {seen}"))
    return errs


def _check_decidable(new: Card, guards: GuardCfg) -> list[GateError]:
    body = new.fields.get("验收标准", "")
    hits = [w for w in guards.vague_words if w in body]
    if hits:
        return [GateError("VAGUE_ACCEPTANCE",
                          f"验收标准含不可判定词: {hits} (00 协议红线 1)")]
    return []


def _check_refs(new: Card, known_ids: set[str], guards: GuardCfg) -> list[GateError]:
    errs = []
    for ref in sorted(set(ID_REF_RE.findall(new.raw))):
        if ref == new.id or ref in known_ids:
            continue
        prefix = ref.split("-")[0]
        if prefix in guards.allowed_ref_prefixes:
            continue
        errs.append(GateError("DANGLING_REF", f"引用了不存在的卡片: {ref}"))
    # 依赖声明必须真实存在
    for dep in new.deps:
        if dep not in known_ids:
            errs.append(GateError("DANGLING_DEP", f"依赖不存在: {dep}"))
    return errs


def _check_terms(new: Card, guards: GuardCfg) -> list[GateError]:
    errs = []
    for canonical, banned in guards.forbidden_synonyms.items():
        for b in banned:
            if b and b in new.raw:
                errs.append(GateError(
                    "TERM_DRIFT", f"术语漂移: 出现 {b!r}, 规范词为 {canonical!r}"))
    return errs


def _check_bloat(old: Card, new: Card, ratio: float,
                 expansion_justified: bool) -> list[GateError]:
    if old.body_chars == 0:
        return []
    growth = new.body_chars / old.body_chars
    if growth > ratio and not expansion_justified:
        return [GateError("BLOAT",
                          f"膨胀 {growth:.2f}x 超阈值 {ratio}x 且无扩写理由")]
    return []


def check_revision(old: Card, new_block: str, known_ids: set[str],
                   guards: GuardCfg, bloat_ratio: float,
                   expansion_justified: bool = False) -> tuple[Card | None, list[GateError]]:
    """门禁主入口: 解析修订稿并全量校验.

    返回 (解析后的新卡 | None, 错误清单)。解析失败时新卡为 None。
    """
    try:
        new = parse_block(new_block, file=old.file, start=old.start)
    except CardParseError as e:
        return None, [GateError("PARSE", str(e))]
    errs: list[GateError] = []
    errs += _check_identity(old, new)
    errs += _check_status(old, new, guards)
    errs += _check_fields(new)
    errs += _check_decidable(new, guards)
    errs += _check_refs(new, known_ids, guards)
    errs += _check_terms(new, guards)
    errs += _check_bloat(old, new, bloat_ratio, expansion_justified)
    return new, errs


def filter_unevidenced_issues(issues: list[dict]) -> tuple[list[dict], int]:
    """丢弃无证据 issue(反水分核心机制, 见 17/02 §1).

    issue 须含非空 evidence 字段; 返回 (保留清单, 丢弃数)。
    """
    kept = [i for i in issues if str(i.get("evidence", "")).strip()]
    return kept, len(issues) - len(kept)
