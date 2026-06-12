# -- coding: utf-8 --
# Project: my-ft
# Created Date: 2026-06-12
# Author: liming
# Email: lmlala@aliyun.com
# Copyright (c) 2025 FiuAI
"""配置加载与校验: pack.yaml / cast.yaml / models.yaml / 任务文件.

所有路径在加载时解析为绝对路径(相对配置文件所在目录), 业务代码不再做
路径推断。任何配置错误在启动期以可读信息失败, 不留到运行中。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class SettingsCfg(BaseModel):
    """运行参数(pack.yaml 的 settings 节, 全部有默认值)."""

    context_budget_chars: int = 36000      # ~12k zh token
    max_rounds_high: int = 5
    max_rounds_normal: int = 3
    score_epsilon: float = 0.3             # 两轮总分增量低于此 → 视为收敛分量
    oscillation_ratio: float = 0.85        # 与两轮前文本相似度超此 → 振荡
    score_regression_stop: float = 0.5     # 分数回退超此 → 回滚并停
    bloat_ratio: float = 1.5               # 卡片膨胀阈值
    max_run_usd: float = 2.0               # 单次 run 费用封顶
    max_run_tokens: int = 2_000_000        # 单次 run token 封顶
    dep_excerpt_chars: int = 1200          # 依赖卡节选预算/张
    recent_rounds_in_context: int = 2


class GuardCfg(BaseModel):
    """门禁词表与保护规则(pack.yaml 的 guards 节)."""

    vague_words: list[str] = Field(
        default=["尽量", "适当", "合理", "良好", "若干", "酌情"])
    # 术语漂移: 规范词 -> 禁用同义词列表
    forbidden_synonyms: dict[str, list[str]] = Field(default_factory=dict)
    # 引用检查允许的"预留前缀"(如 MEN 系列已预告未定义)
    allowed_ref_prefixes: list[str] = Field(default_factory=list)
    # 状态机: agent 允许的状态写入
    writable_statuses: list[str] = Field(default=["draft", "refined"])


class PackCfg(BaseModel):
    """项目包主配置(pack.yaml)."""

    name: str
    docs_root: Path                        # 卡片库根目录
    overview_file: str                     # 游戏总览(常驻上下文 ⓪)
    protocol_file: str                     # 00 卡片协议(常驻上下文 ①)
    card_files: list[str]                  # 参与解析的卡片文件(glob 相对 docs_root)
    immutable_files: list[str] = Field(default_factory=list)  # 代码级禁改
    work_dir: Optional[Path] = None        # 工作区(相对 pack 目录解析)
    settings: SettingsCfg = Field(default_factory=SettingsCfg)
    guards: GuardCfg = Field(default_factory=GuardCfg)

    @field_validator("docs_root")
    @classmethod
    def _must_exist(cls, v: Path) -> Path:
        if not v.is_dir():
            raise ValueError(f"docs_root 不存在: {v}")
        return v


class RoleCfg(BaseModel):
    """单个角色的配置(cast.yaml)."""

    name: str
    kind: str                              # proposer | critic | referee
    slot: str                              # models.yaml 中的模型位名
    prompt: str                            # prompts/ 下模板文件名
    focus: str = ""                        # 批判者视角说明(注入模板)
    rubric: list[str] = Field(default_factory=list)  # 评分维度
    enabled: bool = True

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in {"proposer", "critic", "referee"}:
            raise ValueError(f"未知角色 kind: {v}")
        return v


class CastCfg(BaseModel):
    roles: list[RoleCfg]

    def one(self, kind: str) -> RoleCfg:
        hits = [r for r in self.roles if r.kind == kind and r.enabled]
        if len(hits) != 1:
            raise ValueError(f"cast 中 kind={kind} 必须恰好启用 1 个, 实际 {len(hits)}")
        return hits[0]

    def critics(self) -> list[RoleCfg]:
        return [r for r in self.roles if r.kind == "critic" and r.enabled]


class SlotCfg(BaseModel):
    """模型位(models.yaml): 角色通过位名间接绑定模型."""

    provider: str = "openai_compat"        # openai_compat | fake
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""
    temperature: float = 0.2
    max_output_tokens: int = 4096
    price_in_per_m: float = 0.0            # 每百万输入 token 价格(USD), 记账用
    price_out_per_m: float = 0.0

    @field_validator("provider")
    @classmethod
    def _provider_ok(cls, v: str) -> str:
        if v not in {"openai_compat", "fake"}:
            raise ValueError(f"未知 provider: {v}")
        return v


class ModelsCfg(BaseModel):
    slots: dict[str, SlotCfg]

    def slot(self, name: str) -> SlotCfg:
        if name not in self.slots:
            raise ValueError(f"models.yaml 缺少模型位: {name}")
        return self.slots[name]


class TaskCfg(BaseModel):
    """一次运行的任务定义(tasks/*.yaml)."""

    name: str
    target_files: list[str]                # 相对 docs_root
    include_ids: list[str] = Field(default_factory=list)   # 空=文件内全部
    exclude_ids: list[str] = Field(default_factory=list)
    max_cards: int = 8
    stake: dict[str, str] = Field(default_factory=dict)    # 卡ID -> high/normal
    default_stake: str = "normal"
    direction: str = ""                    # 任务级方向注入(steering)
    critics: list[str] = Field(default_factory=list)       # 班子选拔(空=全部启用)
    rounds: dict[str, int] = Field(default_factory=dict)   # 轮次覆盖 {high, normal}


class StudioConfig(BaseModel):
    """聚合配置: CLI 入口构造后贯穿全程."""

    pack_dir: Path
    pack: PackCfg
    cast: CastCfg
    models: ModelsCfg
    prompts_dir: Path
    work_dir: Path


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"缺少配置文件: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"配置必须是 YAML 映射: {path}")
    return data


def load_config(pack_dir: Path, work_dir: Optional[Path] = None) -> StudioConfig:
    """加载并校验一个项目包的全部配置."""
    pack_dir = pack_dir.resolve()
    raw = _load_yaml(pack_dir / "pack.yaml")
    # docs_root / work_dir 相对 pack_dir 解析
    raw["docs_root"] = (pack_dir / raw.get("docs_root", ".")).resolve()
    if raw.get("work_dir"):
        raw["work_dir"] = (pack_dir / raw["work_dir"]).resolve()
    pack = PackCfg(**raw)
    cast = CastCfg(**_load_yaml(pack_dir / "cast.yaml"))
    models = ModelsCfg(**_load_yaml(pack_dir / "models.yaml"))
    # 角色引用的模型位与模板必须存在
    prompts_dir = Path(__file__).parent / "prompts"
    for role in cast.roles:
        models.slot(role.slot)
        tpl = prompts_dir / role.prompt
        if not tpl.is_file():
            raise FileNotFoundError(f"角色 {role.name} 模板缺失: {tpl}")
    wd = (work_dir or pack.work_dir
          or pack_dir.parent.parent / "work").resolve()
    return StudioConfig(pack_dir=pack_dir, pack=pack, cast=cast,
                        models=models, prompts_dir=prompts_dir, work_dir=wd)


def load_task(path: Path) -> TaskCfg:
    return TaskCfg(**_load_yaml(path.resolve()))
