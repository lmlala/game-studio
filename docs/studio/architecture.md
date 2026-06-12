<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# Studio 当前架构

## 1. 子包边界

| 子包 | 职责 | 主要扩展点 |
| --- | --- | --- |
| `studio/core/` | 配置、卡片解析、机器门禁、抽象接口 | `BaseRole`、`BaseMemory`、`BaseSkillSource` |
| `studio/llm/` | OpenAI 兼容调用、JSON 修复、缓存、成本预算 | 新模型位只改 `models.yaml` |
| `studio/cost/` | Usage、价格计算、预算守卫、ledger 账本条目 | provider/model 价格表 |
| `studio/roles/` | 角色 schema、模板运行时、角色工厂 | `RoleFactory.register(kind, cls)` |
| `studio/skills/` | skill 解析、注册表、装载裁决 | 新 `BaseSkillSource` |
| `studio/context/` | 上下文段、压缩、角色隔离视图、裁剪 | `VIEW_SECTIONS`、`TRIM_ORDER` |
| `studio/memory/` | 工作区、topic 记忆、agent 记忆 | 新 `JsonlMemory` 子类 |
| `studio/loop/` | 规划阶段与卡片轮次循环 | `PlanningService`、`CardRunner` |

内核原则：`studio/` 只认识协议形状、角色种类、技能/记忆/上下文机制；
领域知识只能进入 `packs/*/`、`topis/` 或 skill 文档。

## 2. 运行流

### 2.1 规划阶段

`studio.cli cmd_run()` 先选卡，再创建 `PlanningService`：

1. `manual`：任务 YAML 写了 `goal:`，作为人工覆盖；
2. `planner`：cast 配置 `kind: planner` 时，规划者读取任务卡、目标卡片清单、
   topic 记忆，输出 `Plan{goal,todos,constraints,risks}`；
3. `fallback`：无规划者或 dry-run 时，确定性推导 goal。

计划写入 `work/runs/<run_id>/plan.json`。`todos[].status` 只由内核推进：
`pending -> in_progress -> done/skipped`，模型不能自报状态。
`failed` 表示单卡失败但 run 继续；`--resume <run_id>` 会跳过 `done`，
继续 `pending/in_progress/skipped`，加 `--retry-failed` 时重跑 `failed`。

### 2.2 轮次阶段

每张卡片由 `CardRunner` 执行：

```text
critics(并列互不可见)
    │ evidence 过滤 + skill_requests 收集
    ▼
referee(逐条裁决)
    │ revise / converged / escalate
    ▼
proposer(只看主编指令)
    │
    ▼
core.gates.check_revision()
    │ 通过才写回
    ▼
TopicMemory / AgentMemory
```

## 3. Skills 机制

skill 文件格式：

```markdown
---
id: deterministic-sim
name: 确定性模拟工程检查
version: 1
applies_to_roles: [critic]
triggers: [seed, 随机, RNG, 确定性]
---
## 何时使用
...
```

装载优先级：

1. cast.yaml 显式绑定 `skills: [...]`；
2. 角色上一轮 JSON 产出 `skill_requests`；
3. `triggers` 命中目标卡正文或规划 goal。

`SkillLoader` 统一做白名单、角色适用性、数量和字符预算裁决。被拒申请写入
`work/runs/<id>/journal.jsonl`，不中断运行。

## 4. 上下文隔离与裁剪

`ContextBuilder.build(card, role_view, skills_text)` 生成角色视图：

| 视图 | 可见段 |
| --- | --- |
| `critic` | 依赖、相邻卡、历史摘要、topic 记忆、agent 经验、skills |
| `referee` | 依赖、相邻卡、历史摘要、topic 记忆、agent 经验、skills |
| `proposer` | 依赖、相邻卡、历史摘要、topic 记忆、skills |

所有视图都含不可裁剪段：游戏总览、卡片协议、任务目标、目标卡片。

裁剪顺序：`代理经验 -> 主题记忆 -> 最近轮次摘要 -> 同文件相邻卡片 -> 依赖卡片节选`。
第一轮砍半，第二轮清空；仍超预算则显式失败。

## 5. 记忆

| 记忆 | 路径 | 写入时机 | 注入位置 |
| --- | --- | --- | --- |
| 情景记忆 | `work/reviews/<card>/round-N.json` | 每轮裁决后 | 历史摘要 |
| topic 记忆 | `work/memory/topics/<topic>.jsonl` | 卡片结束时 | 规划者、角色上下文 |
| agent 记忆 | `work/memory/agent.jsonl` | run 结束时 | critic/referee 上下文 |

记忆摘要必须是确定性的提取式摘要，不使用 LLM 二次总结，避免幻觉污染。

## 6. 模型适配与 JSON Mode

`LLMClient` 是 facade，不直接写死 DeepSeek/Qwen/OpenAI 的调用差异。差异放在：

```text
studio/llm/providers/     # deepseek / openai_compat / fake
studio/llm/models/        # provider registry + capabilities
studio/cost/              # usage / pricing / budget
```

DeepSeek JSON Output 遵守官方要求：provider 层传
`response_format={"type":"json_object"}`；prompt 中确保含 `json` 字样并注入
schema 摘要；空 content 按 provider policy 重试。其他 OpenAI-compatible
模型只有在 slot 显式声明支持时才传 `response_format`。

## 7. 日志、流式输出与 checkpoint

每次 run 写入：

```text
work/runs/<run_id>/
├── plan.json      # checkpoint: goal/todos/status/result
├── events.jsonl   # 结构化事件
├── run.log        # 人读日志, 可 tail -f
├── journal.jsonl  # legacy 事件, 保持兼容
└── report.md
```

终端输出由 `RunLogger` 统一刷出，格式稳定，便于 grep：

```text
[stage:start] planning
[plan:updated] done=3 failed=1 in_progress=0 pending=7 skipped=0
[card:start] EVT-01
[round:start] EVT-01 round=1/5
[role:failed] 一致性批判者
[gate:rejected] EVT-01 attempt=1
[checkpoint:saved] work/runs/<id>/plan.json
```

## 8. 当前非目标

- 不做 Claude Code 级自主工具循环；
- 不让角色直接读写文件或运行命令；
- 不让模型决定 todo 状态或写回时机；
- 不在 `studio/` 写入 my-ft 领域事实；
- 不把 `docs/framework/` 蓝图中的 M3 handoff 编译器提前做进核心循环。
