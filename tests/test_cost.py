# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""cost 模块测试."""

from __future__ import annotations

import pytest

from studio.core.config import SlotCfg
from studio.cost import BudgetExceeded, CostMeter, Usage, apply_slot_pricing


def test_apply_slot_pricing():
    slot = SlotCfg(provider="fake", model="fake",
                   price_in_per_m=1.0, price_out_per_m=2.0)
    usage = apply_slot_pricing(slot, Usage(in_tokens=1000, out_tokens=2000))
    assert usage.usd == pytest.approx(0.005)


def test_cost_meter_budget_and_cache():
    meter = CostMeter(max_usd=0.001, max_tokens=10_000)
    meter.add("workhorse", "cached", Usage(cached=True))
    assert meter.cache_hits == 1
    with pytest.raises(BudgetExceeded):
        meter.add("workhorse", "expensive", Usage(in_tokens=10_000, usd=1.0))
