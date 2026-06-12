# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""终端 printer: plain fallback + Rich 渲染."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .formatters import format_event_line, format_plan_summary, plan_counts
from .theme import STATUS_STYLE, STYLE_BY_EVENT_PREFIX


class BasePrinter(ABC):
    """终端展示接口."""

    compact: bool = False

    @abstractmethod
    def event(self, event: str, message: str = "", **fields: Any) -> None:
        """展示一个事件."""

    @abstractmethod
    def plan(self, plan) -> None:
        """展示 plan/todo 状态."""

    @abstractmethod
    def gate(self, card_id: str, attempt: int, errors: list[dict]) -> None:
        """展示门禁拒收."""

    @abstractmethod
    def report(self, path: Path) -> None:
        """展示报告路径."""

    @abstractmethod
    def message_start(self, role: str, card: str, purpose: str = "") -> None:
        """开始展示模型 message."""

    @abstractmethod
    def message_delta(self, delta: str) -> None:
        """展示模型增量 token."""

    @abstractmethod
    def message_end(self) -> None:
        """结束模型 message."""


class PlainPrinter(BasePrinter):
    """无依赖、管道友好的纯文本输出."""

    def __init__(self, no_color: bool = False, compact: bool = False):
        self.no_color = no_color
        self.compact = compact

    def event(self, event: str, message: str = "", **fields: Any) -> None:
        print(format_event_line(event, message, fields), flush=True)

    def plan(self, plan) -> None:
        print(format_plan_summary(plan), flush=True)

    def gate(self, card_id: str, attempt: int, errors: list[dict]) -> None:
        for err in errors:
            msg = f"{card_id} attempt={attempt} {err.get('code')}: {err.get('msg')}"
            print(format_event_line("gate.rejected", msg), flush=True)

    def report(self, path: Path) -> None:
        print(format_event_line("report.done", str(path)), flush=True)

    def message_start(self, role: str, card: str, purpose: str = "") -> None:
        label = f"{role} card={card}" + (f" purpose={purpose}" if purpose else "")
        print(format_event_line("message.start", label), flush=True)

    def message_delta(self, delta: str) -> None:
        print(delta, end="", flush=True)

    def message_end(self) -> None:
        print("", flush=True)


class RichPrinter(BasePrinter):
    """Rich 终端输出."""

    def __init__(self, no_color: bool = False, compact: bool = False):
        from rich.console import Console

        self.console = Console(no_color=no_color)
        self.compact = compact

    def event(self, event: str, message: str = "", **fields: Any) -> None:
        prefix = event.split(".", 1)[0]
        style = STYLE_BY_EVENT_PREFIX.get(prefix, "")
        line = format_event_line(event, message, fields)
        self.console.print(line, style=style, markup=False)

    def plan(self, plan) -> None:
        if self.compact:
            self.console.print(format_plan_summary(plan), style="bold blue",
                               markup=False)
            return
        from rich.table import Table

        counts = plan_counts(plan)
        summary = " ".join(f"{key}={counts.get(key, 0)}"
                           for key in ("done", "failed", "in_progress",
                                       "pending", "skipped"))
        self.console.print(f"[plan] {summary}", style="bold blue", markup=False)
        table = Table(title="Todo", show_lines=False)
        table.add_column("Card", no_wrap=True)
        table.add_column("Focus")
        table.add_column("Status", no_wrap=True)
        table.add_column("Result")
        for todo in plan.todos:
            style = STATUS_STYLE.get(todo.status)
            status_text = f"[{style}]{todo.status}[/]" if style else todo.status
            table.add_row(todo.card_id, todo.focus or "-",
                          status_text,
                          todo.result or "-")
        self.console.print(table)

    def gate(self, card_id: str, attempt: int, errors: list[dict]) -> None:
        for err in errors:
            self.console.print(
                f"[gate:rejected] {card_id} attempt={attempt} "
                f"{err.get('code')}: {err.get('msg')}",
                style="bold red", markup=False)

    def report(self, path: Path) -> None:
        self.console.print(format_event_line("report.done", str(path)),
                           style="bold green", markup=False)

    def message_start(self, role: str, card: str, purpose: str = "") -> None:
        label = f"{role} card={card}" + (f" purpose={purpose}" if purpose else "")
        self.console.print(format_event_line("message.start", label),
                           style="dim", markup=False)

    def message_delta(self, delta: str) -> None:
        self.console.out(delta, end="")

    def message_end(self) -> None:
        self.console.out("")
