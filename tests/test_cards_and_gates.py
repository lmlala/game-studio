# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""解析无损性(round-trip) + 门禁拒收用例."""

from __future__ import annotations

from pathlib import Path

from studio.core.cards import RepoIndex, parse_block, parse_file, replace_card
from studio.core.config import GuardCfg
from studio.core.gates import check_revision

from conftest import CARD_A


def test_roundtrip_real_repo(real_pack_cfg):
    """对 topis/football-docs 全库: 解析后重组 == 原文; 原样替换 == 原文."""
    repo = RepoIndex.build(real_pack_cfg.pack.docs_root,
                           real_pack_cfg.pack.card_files)
    assert len(repo.by_id) >= 80, "应索引到全部 88 张卡片"
    for path, cf in repo.files.items():
        original = path.read_text(encoding="utf-8")
        assert cf.text() == original, f"{path} 行重组不无损"
        for card in cf.cards:
            assert replace_card(cf, card.id, card.raw) == original, \
                f"{path}:{card.id} 原样替换不无损"
            reparsed = parse_block(card.raw, file=path, start=card.start)
            assert reparsed.id == card.id
            assert set(reparsed.fields) == set(card.fields)


def test_real_cards_have_five_fields(real_pack_cfg):
    repo = RepoIndex.build(real_pack_cfg.pack.docs_root,
                           real_pack_cfg.pack.card_files)
    for card in repo.by_id.values():
        assert len(card.fields) == 5, f"{card.id} 字段数 {len(card.fields)}"


def _gate(old_block: str, new_block: str, known=("TOY-01", "TOY-02"),
          **kw):
    old = parse_block(old_block)
    guards = kw.pop("guards", GuardCfg(
        forbidden_synonyms={"玩具卡片": ["玩物卡片"]},
        allowed_ref_prefixes=["MEN"]))
    _, errs = check_revision(old, new_block, set(known), guards,
                             bloat_ratio=1.5, **kw)
    return [e.code for e in errs]


def test_gate_accepts_identity():
    assert _gate(CARD_A, CARD_A) == []


def test_gate_rejects_bad_revisions(tmp_path: Path):
    cases = {
        "ID_CHANGED": CARD_A.replace("TOY-01", "TOY-99"),
        "TITLE_CHANGED": CARD_A.replace("玩具卡片甲", "改名卡片"),
        "FIELD_MISSING": CARD_A.replace("**评估钩子**：", "**备注**："),
        "VAGUE_ACCEPTANCE": CARD_A.replace("引用检查通过", "引用检查尽量通过"),
        "DANGLING_REF": CARD_A.replace("TOY-02", "TOY-77"),
        "STATUS_TRANSITION": CARD_A.replace(
            "状态: draft", "状态: locked"),
        "STATUS_INVALID": CARD_A.replace("状态: draft", "状态: done"),
        "TERM_DRIFT": CARD_A.replace("最小卡片", "玩物卡片"),
        "BLOAT": CARD_A + "\n填充内容。" * 200,
        "PARSE": "不是卡片的内容",
    }
    for code, bad in cases.items():
        codes = _gate(CARD_A, bad)
        assert code in codes, f"期望 {code}, 实得 {codes}"


def test_gate_bloat_waived_with_rationale():
    big = CARD_A + "\n补充要点。" * 200
    codes = _gate(CARD_A, big, expansion_justified=True)
    assert "BLOAT" not in codes


def test_gate_readonly_card():
    locked = CARD_A.replace("状态: draft", "状态: locked")
    codes = _gate(locked, locked)
    assert "READONLY_CARD" in codes


def test_gate_allows_reserved_prefix():
    with_men = CARD_A.replace("引用 TOY-02", "引用 TOY-02 与 MEN-03")
    assert "DANGLING_REF" not in _gate(CARD_A, with_men)


def test_gate_status_bump_draft_to_refined():
    bumped = CARD_A.replace("状态: draft", "状态: refined")
    assert _gate(CARD_A, bumped) == []


def test_parse_file_duplicate_id(tmp_path: Path):
    p = tmp_path / "dup.md"
    p.write_text(CARD_A + "\n" + CARD_A, encoding="utf-8")
    try:
        parse_file(p)
        raise AssertionError("应当抛重复 ID")
    except Exception as e:
        assert "重复" in str(e)
