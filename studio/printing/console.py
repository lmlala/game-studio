# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""Printer 工厂."""

from __future__ import annotations

from .printer import BasePrinter, PlainPrinter, RichPrinter


def create_printer(*, stream: bool = True, no_rich: bool = False,
                   no_color: bool = False,
                   compact: bool = False) -> BasePrinter | None:
    """根据 CLI 参数创建 printer; rich 不可用时自动回退 plain."""
    if not stream:
        return None
    if no_rich:
        return PlainPrinter(no_color=no_color, compact=compact)
    try:
        return RichPrinter(no_color=no_color, compact=compact)
    except ImportError:
        return PlainPrinter(no_color=no_color, compact=compact)
