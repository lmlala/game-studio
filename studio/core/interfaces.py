# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""内核抽象层: 角色 / 记忆 / 技能源的扩展契约.

新增角色种类、记忆后端或技能来源时, 实现这里的抽象基类即可接入,
编排层(loop)只依赖这些接口, 不依赖具体实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseRole(ABC):
    """角色抽象: 一次调用 = (上下文, 附加变量) -> 结构化产出."""

    @property
    @abstractmethod
    def name(self) -> str:
        """角色名(cast.yaml 中唯一)."""

    @property
    @abstractmethod
    def kind(self) -> str:
        """角色种类: proposer | critic | referee | 未来扩展."""

    @abstractmethod
    def run(self, client: Any, bundle: Any,
            extra: dict[str, str] | None = None, fake: bool = False) -> Any:
        """执行一次角色调用, 返回过 schema 校验的产出."""

    @abstractmethod
    def fake_output(self, extra: dict[str, str]) -> Any:
        """离线/试运行模式的结构合法产出."""


class BaseMemory(ABC):
    """记忆抽象: 追加事件 + 产出供上下文注入的紧凑摘要.

    实现约定: 事件持久化为文件(jsonl), digest 必须确定性生成且自带
    字符预算 —— 记忆永远不允许撑爆上下文。
    """

    @abstractmethod
    def append(self, event: dict) -> None:
        """追加一条记忆事件(实现方负责补时间戳与原子写)."""

    @abstractmethod
    def digest(self, max_chars: int) -> str:
        """生成不超过 max_chars 的摘要文本; 无记忆时返回空串."""


class BaseSkillSource(ABC):
    """技能来源抽象: 注册表从一个或多个来源聚合技能."""

    @abstractmethod
    def load_all(self) -> list[Any]:
        """返回本来源的全部技能(解析失败必须显式抛错, 不静默跳过)."""
