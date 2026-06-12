# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""角色工厂: kind -> 实现类的唯一映射, 新角色种类在此注册."""

from __future__ import annotations

from pathlib import Path
from typing import Type

from ..core.config import CastCfg, RoleCfg
from .base import TemplatedRole
from .runtime import CriticRole, PlannerRole, ProposerRole, RefereeRole


class RoleFactory:
    """按配置创建角色实例; 未知 kind 显式失败."""

    _REGISTRY: dict[str, Type[TemplatedRole]] = {
        "proposer": ProposerRole,
        "critic": CriticRole,
        "referee": RefereeRole,
        "planner": PlannerRole,
    }

    @classmethod
    def register(cls, kind: str, role_cls: Type[TemplatedRole]) -> None:
        """扩展点: 注册新角色种类(如未来的模拟用户/验收官)."""
        if not kind or not issubclass(role_cls, TemplatedRole):
            raise ValueError("注册需要非空 kind 与 TemplatedRole 子类")
        cls._REGISTRY[kind] = role_cls

    @classmethod
    def create(cls, cfg: RoleCfg, prompts_dir: Path) -> TemplatedRole:
        if cfg.kind not in cls._REGISTRY:
            raise ValueError(f"未注册的角色 kind: {cfg.kind}")
        return cls._REGISTRY[cfg.kind](cfg, prompts_dir)

    @classmethod
    def build_cast(cls, cast: CastCfg, prompts_dir: Path,
                   critic_names: list[str] | None = None,
                   ) -> tuple[TemplatedRole, list[TemplatedRole], TemplatedRole]:
        """构建 (提案者, 批判者班子, 主编); critic_names 空 = 全部启用."""
        proposer = cls.create(cast.one("proposer"), prompts_dir)
        referee = cls.create(cast.one("referee"), prompts_dir)
        pool = cast.critics()
        if critic_names:
            by_name = {r.name: r for r in pool}
            missing = [n for n in critic_names if n not in by_name]
            if missing:
                raise ValueError(f"任务指定的批判者不存在于 cast: {missing}")
            pool = [by_name[n] for n in critic_names]
        critics = [cls.create(r, prompts_dir) for r in pool]
        return proposer, critics, referee

    @classmethod
    def build_planner(cls, cast: CastCfg,
                      prompts_dir: Path) -> TemplatedRole | None:
        """规划者可选: 未配置时返回 None(planning 层走确定性回退)."""
        cfg = cast.maybe_one("planner")
        return cls.create(cfg, prompts_dir) if cfg else None
