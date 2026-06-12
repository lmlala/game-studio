# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""价格计算.

当前价格仍来自 models.yaml 的 slot 字段; 独立模块方便以后切换为
provider/model 价格表、缓存命中价格、reasoner 特殊价格等。
"""

from __future__ import annotations

from ..core.config import SlotCfg
from .meter import Usage


def apply_slot_pricing(slot: SlotCfg, usage: Usage) -> Usage:
    """按 slot 的 USD/百万 token 价格写入 usage.usd."""
    usage.usd = (
        usage.in_tokens * slot.price_in_per_m
        + usage.out_tokens * slot.price_out_per_m
    ) / 1e6
    return usage
