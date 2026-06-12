# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""运行时日志: stdout 流式输出 + JSONL 事件 + 人读 run.log."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..printing import BasePrinter, PlainPrinter
from ..printing.formatters import format_event_line


class RunLogger:
    """单次 run 的日志器.

    事件写入:
    - stdout: 便于运行时观察, flush=True;
    - events.jsonl: 机器可读;
    - run.log: 人读, 可 tail -f。
    """

    def __init__(self, run_dir: Path, stream: bool = True,
                 printer: BasePrinter | None = None):
        self.run_dir = run_dir
        self.stream = stream
        self.printer = printer if stream else None
        if stream and self.printer is None:
            self.printer = PlainPrinter()
        self.events_path = run_dir / "events.jsonl"
        self.text_path = run_dir / "run.log"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    # ---------- generic ----------

    def event(self, event: str, message: str = "", **fields: Any) -> None:
        self._record(event, message, fields)
        if self.printer:
            self.printer.event(event, message, **fields)

    def stage(self, name: str, status: str, **fields: Any) -> None:
        self.event(f"stage.{status}", name, stage=name, **fields)

    def step(self, message: str, **fields: Any) -> None:
        self.event("step", message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self.event("error", message, **fields)

    # ---------- structured helpers ----------

    def plan(self, plan) -> None:
        counts: dict[str, int] = {}
        for todo in plan.todos:
            counts[todo.status] = counts.get(todo.status, 0) + 1
        msg = " ".join(f"{k}={counts.get(k, 0)}"
                       for k in ("done", "failed", "in_progress",
                                 "pending", "skipped"))
        self._record("plan.updated", msg, {
            "goal": plan.goal,
            "source": plan.source,
            "counts": counts,
            "todos": [asdict(t) for t in plan.todos],
        })
        if self.printer:
            self.printer.plan(plan)

    def checkpoint(self, path: Path) -> None:
        self.event("checkpoint.saved", str(path), path=str(path))

    def gate_rejected(self, card_id: str, attempt: int, errors: list) -> None:
        payload = [{"code": getattr(e, "code", ""),
                    "msg": getattr(e, "msg", str(e))}
                   for e in errors]
        self._record("gate.rejected", f"{card_id} attempt={attempt}", {
            "card": card_id,
            "attempt": attempt,
            "errors": payload,
        })
        if self.printer:
            self.printer.gate(card_id, attempt, payload)

    def report(self, path: Path) -> None:
        self._record("report.done", str(path), {"path": str(path)})
        if self.printer:
            self.printer.report(path)

    # ---------- IO ----------

    def _append_jsonl(self, rec: dict) -> None:
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _append_text(self, line: str) -> None:
        with self.text_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _record(self, event: str, message: str,
                fields: dict[str, Any]) -> None:
        rec = {"ts": time.time(), "event": event, **fields}
        self._append_jsonl(rec)
        self._append_text(self._format_line(event, message, fields))

    def _format_line(self, event: str, message: str,
                     fields: dict[str, Any]) -> str:
        return format_event_line(event, message, fields)
