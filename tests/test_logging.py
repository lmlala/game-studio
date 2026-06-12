# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""RunLogger 测试."""

from __future__ import annotations

import json

from studio.core.gates import GateError
from studio.logging import RunLogger
from studio.loop.planning import RunPlan, TodoState
from studio.printing import PlainPrinter


def test_run_logger_writes_stdout_jsonl_and_text(tmp_path, capsys):
    logger = RunLogger(tmp_path, stream=True,
                       printer=PlainPrinter(compact=True))
    plan = RunPlan(goal="g", source="fallback",
                   todos=[TodoState("A-01", status="done"),
                          TodoState("A-02", status="failed")])
    logger.stage("planning", "start")
    logger.plan(plan)
    logger.gate_rejected("A-02", 1, [GateError("PARSE", "bad json")])
    logger.message_start("角色", "A-01")
    logger.message_delta("角色", "A-01", "hello")
    logger.message_end("角色", "A-01")
    out = capsys.readouterr().out
    assert "[stage:start] planning" in out
    assert "[plan:updated]" in out
    events = [json.loads(line)
              for line in (tmp_path / "events.jsonl").read_text(
                  encoding="utf-8").splitlines()]
    assert [e["event"] for e in events] == [
        "stage.start", "plan.updated", "gate.rejected",
        "message.start", "message.end"]
    gate = [e for e in events if e["event"] == "gate.rejected"][0]
    assert gate["errors"][0]["code"] == "PARSE"
    assert "gate:rejected" in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_run_logger_no_stream_writes_files_only(tmp_path, capsys):
    logger = RunLogger(tmp_path, stream=False)
    logger.stage("planning", "start")
    assert capsys.readouterr().out == ""
    assert (tmp_path / "events.jsonl").is_file()
    assert (tmp_path / "run.log").is_file()
