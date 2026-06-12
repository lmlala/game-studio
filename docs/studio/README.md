<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# Studio 当前实现设计索引

本目录记录 `studio/` 当前代码实现的设计约定。`docs/framework/` 是长期蓝图，
本目录是当前工程事实：后续 agent 改 `studio/` 前应先读这里。

## 阅读顺序

| 文件 | 作用 |
| --- | --- |
| [`architecture.md`](architecture.md) | 当前子包结构、运行流、扩展点、文件态工作区 |
| [`rules.md`](rules.md) | 后续开发必须遵守的工程规则与边界 |
| [`../framework/README.md`](../framework/README.md) | 长期框架蓝图与里程碑 |
| [`../m0-design-agent.md`](../m0-design-agent.md) | M0 单角色闭环的历史设计 |

## 当前能力一览

```text
topis/tasks/*.yaml
        │
        ▼
PlanningService
  manual goal override / planner / fallback
        │  writes work/runs/<id>/plan.json
        ▼
ContextBuilder(role_view)
  task goal + card + deps + history + memory + skills
        │
        ▼
CardRunner
  critic(s) → referee → proposer → gates → memory
```

| 能力 | 当前实现 |
| --- | --- |
| 目录拆分 | `core/llm/roles/skills/context/memory/loop` 七个子包 |
| 角色扩展 | `BaseRole` + `RoleFactory.register()` |
| 规划阶段 | 先读任务卡分析 `goal/todos/constraints/risks`，再执行 |
| skills | markdown front-matter，绑定/申请/触发三路装载，预算裁决 |
| 上下文 | 角色隔离视图 + 提取式历史压缩 + 确定性裁剪 |
| 记忆 | topic 级记忆 + agent 级经验记忆，全部 jsonl |
| 门禁 | 卡片 schema、状态迁移、引用、术语、可判定性、膨胀 |

## 常用命令

```bash
python3 -m studio.cli validate --pack packs/my-ft
python3 -m studio.cli skills --pack packs/my-ft
python3 -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --dry-run
python3 -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --fake --no-git
python3 -m studio.cli memory --pack packs/my-ft
python3 -m pytest
```
