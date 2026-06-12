# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""printing 模块测试."""

from __future__ import annotations

from studio.loop.planning import RunPlan, TodoState
from studio.printing import PlainPrinter, RichPrinter, create_printer


def _plan() -> RunPlan:
    return RunPlan(goal="g", source="fallback",
                   todos=[TodoState("A-01", focus="检查 schema",
                                    status="done", result="converged"),
                          TodoState("A-02", status="pending")])


def test_plain_printer_outputs_stable_prefix(capsys):
    printer = PlainPrinter(compact=True)
    printer.event("stage.start", "planning")
    printer.plan(_plan())
    printer.gate("A-01", 1, [{"code": "PARSE", "msg": "bad"}])
    printer.message_start("角色", "A-01")
    printer.message_delta("hello")
    printer.message_end()
    out = capsys.readouterr().out
    assert "[stage:start] planning" in out
    assert "[plan:updated]" in out
    assert "[gate:rejected]" in out
    assert "hello" in out


def test_rich_printer_renders_without_error(capsys):
    printer = RichPrinter(no_color=True, compact=True)
    printer.event("card.start", "Card title", card="A-01")
    printer.plan(_plan())
    printer.message_start("角色", "A-01")
    printer.message_delta("hello")
    printer.message_end()
    printer.report(__file__)
    out = capsys.readouterr().out
    assert "card:start" in out
    assert "plan:updated" in out or "[plan]" in out
    assert "hello" in out


def test_create_printer_fallback_modes():
    assert create_printer(stream=False) is None
    assert isinstance(create_printer(stream=True, no_rich=True), PlainPrinter)
