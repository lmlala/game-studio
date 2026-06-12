# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""技能装载 / 记忆 / 上下文隔离与压缩的单元测试."""

from __future__ import annotations

from pathlib import Path

import pytest

from studio.context.builder import VIEW_SECTIONS, ContextBuilder
from studio.context.compress import compress_history, summarize_round
from studio.core.cards import RepoIndex
from studio.core.config import load_config, load_task
from studio.memory.agent import AgentMemory
from studio.memory.topic import TopicMemory
from studio.memory.workdir import WorkDir
from studio.skills.loader import SkillLoader
from studio.skills.model import SkillParseError, parse_skill_file
from studio.skills.registry import SkillRegistry

SKILL_MD = """---
id: toy-skill
name: 玩具技能
version: 1
applies_to_roles: [critic]
triggers: [玩具]
---
## 何时使用
评审玩具卡片时。
- TS-1 检查点一
"""


def _skill_dir(tmp_path: Path, *texts: str) -> Path:
    d = tmp_path / "skills"
    d.mkdir(exist_ok=True)
    for i, t in enumerate(texts):
        (d / f"s{i}.md").write_text(t, encoding="utf-8")
    return d


# ---------- 技能模型与注册表 ----------

def test_skill_parse_and_index(tmp_path: Path):
    d = _skill_dir(tmp_path, SKILL_MD)
    sk = parse_skill_file(d / "s0.md")
    assert sk.id == "toy-skill" and sk.matches("这是玩具卡片")
    assert "toy-skill" in sk.index_line()


def test_skill_parse_errors(tmp_path: Path):
    cases = ["无 front-matter",
             "---\nid: BAD_ID\nname: x\n---\n正文",
             "---\nid: ok-id\nname: x\n---\n"]
    for i, text in enumerate(cases):
        p = tmp_path / f"bad{i}.md"
        p.write_text(text, encoding="utf-8")
        with pytest.raises(SkillParseError):
            parse_skill_file(p)


def test_registry_role_filter_and_triggers(tmp_path: Path):
    d = _skill_dir(tmp_path, SKILL_MD)
    reg = SkillRegistry.build([d], include_builtin=False)
    assert reg.has("toy-skill")
    assert reg.for_role("critic", "任意批判者")
    assert not reg.for_role("proposer", "提案者"), "applies_to_roles 应隔离角色"
    assert reg.match_triggers("玩具卡片正文", "critic", "x")
    assert not reg.match_triggers("无关文本", "critic", "x")


def test_registry_builtin_loaded():
    reg = SkillRegistry.build([])
    assert reg.has("decidable-acceptance") and reg.has("scope-control")


# ---------- 装载裁决(自主申请 + 预算) ----------

def test_loader_request_whitelist_and_budget(tmp_path: Path):
    d = _skill_dir(tmp_path, SKILL_MD)
    reg = SkillRegistry.build([d], include_builtin=False)
    loader = SkillLoader(reg, max_per_role=1, chars_budget=10000)
    # 合法申请被装载
    dec = loader.decide("critic", "批判者", [], ["toy-skill"], "")
    assert [s.id for s in dec.skills] == ["toy-skill"]
    # 不存在/不适用的申请被拒并留痕
    dec = loader.decide("critic", "批判者", [], ["ghost"], "")
    assert any("ghost" in r for r in dec.rejected)
    dec = loader.decide("proposer", "提案者", [], ["toy-skill"], "")
    assert any("不适用" in r for r in dec.rejected)


def test_loader_trigger_and_count_cap(tmp_path: Path):
    second = SKILL_MD.replace("toy-skill", "toy-skill-b").replace(
        "玩具技能", "玩具技能B")
    d = _skill_dir(tmp_path, SKILL_MD, second)
    reg = SkillRegistry.build([d], include_builtin=False)
    loader = SkillLoader(reg, max_per_role=1, chars_budget=10000)
    dec = loader.decide("critic", "批判者", [], [], "评审玩具卡片")
    assert len(dec.skills) == 1, "超出单角色上限应被裁掉"
    assert any("上限" in r for r in dec.rejected)


# ---------- 记忆 ----------

def test_topic_memory_roundtrip(tmp_path: Path):
    mem = TopicMemory(tmp_path, "05-event-system")
    mem.record("escalated", "EVT-01", "批判者对触发语义有根本分歧")
    mem.record("deferred", "EVT-02", "等 NUM 定稿后再校准频率")
    digest = mem.digest(500)
    assert "EVT-01" in digest and "deferred" in digest
    with pytest.raises(ValueError):
        mem.record("unknown-kind", "EVT-01", "x")


def test_agent_memory_stats(tmp_path: Path):
    mem = AgentMemory(tmp_path)
    mem.record_run("r1", total=4, converged=3,
                   gate_errors=["VAGUE_ACCEPTANCE", "VAGUE_ACCEPTANCE"],
                   dropped_unevidenced=5)
    mem.record_lesson("数值类指令要附 NUM 条款编号")
    digest = mem.digest(600)
    assert "收敛 3" in digest and "VAGUE_ACCEPTANCE×2" in digest
    assert "NUM 条款编号" in digest
    with pytest.raises(ValueError):
        mem.record_run("r2", total=1, converged=2,
                       gate_errors=[], dropped_unevidenced=0)


# ---------- 上下文: 隔离视图与压缩 ----------

def _builder(toy_pack: Path, with_memory: bool = False):
    cfg = load_config(toy_pack)
    repo = RepoIndex.build(cfg.pack.docs_root, cfg.pack.card_files)
    work = WorkDir(cfg.work_dir)
    task_p = toy_pack / "task.yaml"
    task_p.write_text("name: t\ngoal: 测试目标\nconstraints: [不扩写]\n"
                      "target_files: [cards.md]\n", encoding="utf-8")
    task = load_task(task_p)
    agent = AgentMemory(work.memory) if with_memory else None
    topic = TopicMemory(work.memory, "cards") if with_memory else None
    return ContextBuilder(repo, cfg, work, task, topic_mem=topic,
                          agent_mem=agent), repo


def test_view_isolation(toy_pack: Path):
    builder, repo = _builder(toy_pack, with_memory=True)
    builder.agent_mem.record_lesson("注意验收标准量纲")
    card = repo.by_id["TOY-01"]
    critic_view = builder.build(card, role_view="critic").render()
    proposer_view = builder.build(card, role_view="proposer").render()
    assert "代理经验" in critic_view
    assert "代理经验" not in proposer_view, "提案者视图不应注入代理经验"
    assert "任务目标" in proposer_view and "不扩写" in proposer_view
    with pytest.raises(ValueError):
        builder.build(card, role_view="unknown")
    assert set(VIEW_SECTIONS) == {"critic", "referee", "proposer"}


def test_skills_section_injected(toy_pack: Path):
    builder, repo = _builder(toy_pack)
    rendered = builder.build(repo.by_id["TOY-01"], role_view="critic",
                             skills_text="[技能 x] 检查清单").render()
    assert "<<<技能>>>" in rendered and "检查清单" in rendered


def test_round_summary_compression():
    record = {
        "round": 2, "score": 3.5,
        "verdict": {"decision": "revise", "rationale": "理由" * 100,
                    "directives": [
                        {"action": "accept", "instruction": "明确触发阈值"},
                        {"action": "reject", "instruction": "无关修改"}]},
        "open_issues": [{"severity": "blocking", "claim": "缺少因果 ID"}],
    }
    s = summarize_round(record, 300)
    assert len(s) <= 301 and "revise" in s
    assert "明确触发阈值" in s and "缺少因果 ID" in s
    assert "无关修改" not in s, "被 reject 的指令不应进摘要"
    assert compress_history([], 300) == ""
