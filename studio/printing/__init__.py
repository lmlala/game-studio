# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""printing: CLI 终端交互展示(Rich + plain fallback)."""

from .console import create_printer  # noqa: F401
from .printer import BasePrinter, PlainPrinter, RichPrinter  # noqa: F401
