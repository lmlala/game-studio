# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""CLI 输出样式名.

只在 printing 模块里集中管理样式, 业务代码不得直接写 Rich style。
"""

STYLE_BY_EVENT_PREFIX = {
    "stage": "bold cyan",
    "plan": "bold blue",
    "checkpoint": "dim",
    "card": "bold",
    "round": "cyan",
    "role": "magenta",
    "gate": "bold red",
    "budget": "bold yellow",
    "error": "bold red",
}

STATUS_STYLE = {
    "done": "green",
    "failed": "red",
    "in_progress": "yellow",
    "pending": "dim",
    "skipped": "cyan",
}
