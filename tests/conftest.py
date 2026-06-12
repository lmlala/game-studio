# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""测试夹具: 真实 pack(若存在) + 自包含玩具 pack(永远可用)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from studio.core.config import load_config  # noqa: E402

CARD_A = """### TOY-01 玩具卡片甲

状态: draft · 优先级: P0 · 依赖: 无

**目的**：验证解析与门禁的最小卡片。

**设计理念**：保持最小但字段齐全。

**如何设计**：
- 要点一；
- 要点二；
- 引用 TOY-02 做依赖检查。

**验收标准**：
- [机器] 解析通过且字段计数为 5；
- [机器] 引用检查通过。

**评估钩子**：
- 无(测试用)。
"""

CARD_B = """### TOY-02 玩具卡片乙

状态: refined · 优先级: P1 · 依赖: TOY-01

**目的**：第二张卡, 供依赖与相邻关系测试。

**设计理念**：同上。

**如何设计**：
- 要点一。

**验收标准**：
- [机器] 存在即可被索引。

**评估钩子**：
- 无(测试用)。
"""


@pytest.fixture()
def toy_pack(tmp_path: Path) -> Path:
    """生成自包含玩具 pack: docs + 配置, 不依赖仓库其他目录."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "overview.md").write_text("# 总览\n玩具项目总览。\n", encoding="utf-8")
    (docs / "protocol.md").write_text("# 协议\n五字段协议摘要。\n", encoding="utf-8")
    (docs / "cards.md").write_text(
        "# 玩具卡片库\n\n" + CARD_A + "\n" + CARD_B, encoding="utf-8")
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.yaml").write_text(f"""
name: toy
docs_root: {docs}
overview_file: overview.md
protocol_file: protocol.md
card_files: ["*.md"]
immutable_files: [protocol.md, overview.md]
work_dir: ../work
guards:
  vague_words: ["尽量", "适当", "合理"]
  forbidden_synonyms: {{"玩具卡片": ["玩物卡片"]}}
  allowed_ref_prefixes: ["MEN"]
""", encoding="utf-8")
    (pack / "cast.yaml").write_text("""
roles:
  - {name: 提案者, kind: proposer, slot: workhorse, prompt: proposer.md}
  - {name: 批判者, kind: critic, slot: workhorse, prompt: critic.md,
     focus: 测试, rubric: ["质量"]}
  - {name: 主编, kind: referee, slot: judge, prompt: referee.md}
""", encoding="utf-8")
    (pack / "models.yaml").write_text("""
slots:
  workhorse: {provider: fake}
  judge: {provider: fake}
""", encoding="utf-8")
    return pack


@pytest.fixture()
def real_pack_cfg():
    """真实 my-ft pack(docs_root 不在时跳过, 保证迁出独立 repo 后测试仍可跑)."""
    pack_dir = APP_ROOT / "packs" / "my-ft"
    try:
        return load_config(pack_dir)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(f"真实 pack 不可用: {e}")
