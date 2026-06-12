# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""角色 schema 校验测试."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.roles.schemas import Revision


def test_revision_requires_card_markdown_heading():
    with pytest.raises(ValidationError, match="card_markdown must start"):
        Revision(card_markdown="rust\npub trait Judgment {}")


def test_revision_accepts_card_markdown_block():
    rev = Revision(card_markdown="### ENG-03 引擎统一接口契约\n\n状态: draft · 优先级: P0 · 依赖: 无\n")
    assert rev.card_markdown.startswith("### ENG-03")
