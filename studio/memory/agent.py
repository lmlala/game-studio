# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""代理记忆: agent 自身的跨运行经验(与具体主题无关).

记什么: 每次 run 的收敛率、门禁拒收的高频错误码、被丢弃的无证据
issue 计数、技能申请被拒情况。用途: 注入主编/批判者上下文, 让 agent
知道"自己最近常犯什么错"; 也是人工调 prompt/技能的依据。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .store import JsonlMemory


class AgentMemory(JsonlMemory):
    """agent 级经验记忆: 单文件 memory/agent.jsonl."""

    def __init__(self, memory_root: Path, keep_last: int = 300):
        super().__init__(memory_root / "agent.jsonl", keep_last=keep_last)

    # ---------- 业务入口 ----------

    def record_run(self, run_id: str, total: int, converged: int,
                   gate_errors: list[str], dropped_unevidenced: int) -> None:
        if total < 0 or converged < 0 or converged > total:
            raise ValueError(f"非法 run 统计: total={total} converged={converged}")
        self.append({"kind": "run", "run": run_id, "total": total,
                     "converged": converged,
                     "gate_errors": list(gate_errors),
                     "dropped": dropped_unevidenced})

    def record_lesson(self, note: str) -> None:
        """人工或编排层沉淀的一条经验(如: 某类指令模型总是执行错)."""
        if not note.strip():
            raise ValueError("经验内容不能为空")
        self.append({"kind": "lesson", "note": note.strip()})

    # ---------- 摘要 ----------

    def digest(self, max_chars: int) -> str:
        """统计摘要 + 最近 lessons(确定性聚合, 不逐条罗列 run)."""
        if max_chars <= 0:
            return ""
        events = self.load()
        runs = [e for e in events if e.get("kind") == "run"]
        lessons = [e for e in events if e.get("kind") == "lesson"]
        lines: list[str] = []
        if runs:
            total = sum(int(e.get("total", 0)) for e in runs)
            conv = sum(int(e.get("converged", 0)) for e in runs)
            dropped = sum(int(e.get("dropped", 0)) for e in runs)
            gate_counter: Counter = Counter()
            for e in runs:
                gate_counter.update(e.get("gate_errors", []))
            lines.append(f"- 近 {len(runs)} 次运行: 卡片 {total} 张, "
                         f"收敛 {conv} 张, 丢弃无证据 issue {dropped} 条")
            if gate_counter:
                top = ", ".join(f"{c}×{n}" for c, n
                                in gate_counter.most_common(3))
                lines.append(f"- 门禁高频拒收: {top}(修订时优先自查)")
        for e in lessons[-5:]:
            lines.append(f"- [经验] {str(e.get('note', ''))[:140]}")
        out = "\n".join(lines)
        return out if len(out) <= max_chars else out[:max_chars] + "…"
