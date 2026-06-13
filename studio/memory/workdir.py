# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""记忆与工作区: 一切持久状态都是文件.

记忆分层(见 docs/m0-design-agent.md 设计):
- 卡片本身 = 长期状态(由 core.cards 管理);
- reviews/<卡>/round-N.json = 情景记忆(每轮全部角色发言与裁决);
- memory/topics/<主题>.jsonl = 主题记忆(topic.py);
- memory/agent.jsonl = 代理自身经验(agent.py);
- ledger.jsonl + runs/<id>/ = 成本台账与运行报告。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from ..core.cards import atomic_write


class WorkDir:
    """工作区目录约定与读写(全部原子写)."""

    def __init__(self, root: Path):
        self.root = root
        self.reviews = root / "reviews"
        self.steering = root / "steering"
        self.runs = root / "runs"
        self.memory = root / "memory"
        self.cache = root / ".cache" / "llm"
        self.ledger = root / "ledger.jsonl"
        self._last_run_ms = 0
        self._run_seq = 0
        for d in (self.reviews, self.steering, self.runs,
                  self.memory, self.cache):
            d.mkdir(parents=True, exist_ok=True)

    # ---------- 轮次记录(情景记忆) ----------

    def record_round(self, card_id: str, round_no: int, payload: dict) -> None:
        payload = dict(payload, ts=time.time(), round=round_no)
        path = self.reviews / card_id / f"round-{round_no:02d}.json"
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=1))

    def load_rounds(self, card_id: str, last_n: int = 2) -> list[dict]:
        d = self.reviews / card_id
        if not d.is_dir():
            return []
        files = sorted(d.glob("round-*.json"))[-last_n:]
        out = []
        for f in files:
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue            # 损坏的历史记录跳过, 不阻塞运行
        return out

    def round_count(self, card_id: str) -> int:
        d = self.reviews / card_id
        return len(list(d.glob("round-*.json"))) if d.is_dir() else 0

    # ---------- 方向注入(steering) ----------

    def steer(self, card_id: str, message: str) -> Path:
        path = self.steering / f"{card_id}.md"
        stamp = time.strftime("%Y-%m-%d %H:%M")
        prev = path.read_text(encoding="utf-8") if path.is_file() else ""
        atomic_write(path, f"{prev}\n## {stamp}\n\n{message}\n")
        return path

    def load_steering(self, card_id: str) -> Optional[str]:
        path = self.steering / f"{card_id}.md"
        return path.read_text(encoding="utf-8") if path.is_file() else None

    # ---------- 台账与运行产物 ----------

    def append_ledger(self, entry: dict) -> None:
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def new_run_id(self) -> str:
        now_ms = int(time.time() * 1000)
        if now_ms == self._last_run_ms:
            self._run_seq += 1
        else:
            self._last_run_ms = now_ms
            self._run_seq = 0
        return (time.strftime("%Y%m%d-%H%M%S")
                + f"-{now_ms % 1000:03d}-{self._run_seq:02d}")

    def run_dir(self, run_id: str) -> Path:
        d = self.runs / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def journal(self, run_id: str, event: str, **kw) -> None:
        """运行日志: 每个关键步骤一条, 崩溃后可还原现场."""
        path = self.run_dir(run_id) / "journal.jsonl"
        rec = {"ts": time.time(), "event": event, **kw}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def event_log(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "events.jsonl"

    def text_log(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.log"

    def write_report(self, run_id: str, text: str) -> Path:
        path = self.run_dir(run_id) / "report.md"
        atomic_write(path, text)
        return path
