<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# design-studio — 设计卡片精修 agent（v1）

把 `topis/football-docs/` 的设计卡片送进「提案 → 多角批判 → 主编裁决 → 修订」
的多轮循环，收敛后写回并升级状态。对应设计文档（随本应用一起迁出）：
[`docs/studio/`](docs/studio/README.md)（当前实现索引）、
[`docs/m0-design-agent.md`](docs/m0-design-agent.md)（M0/M1 范围）与
[`docs/framework/`](docs/framework/README.md)（完整框架蓝图）。

## 核心思路

**确定性编排 + LLM 纯文本函数**。流程、文件 IO、状态机全部在 Python
代码里；模型只做「prompt 进、JSON 出」，无自主工具循环、无会话状态。
这是 DeepSeek/Qwen 中档模型可靠工作的前提，也让全流程可重放、可断点、
可离线测试（`--fake`）。

```text
选卡(stake×优先级) ─► 组装上下文 ─► 批判者×N(并列) ─► 证据过滤 ─► 主编裁决
                          ▲                                        │
                          └────── 提案者修订 ◄── 机器门禁 ◄─ revise ─┘
收敛(converged) → 代码升级状态 draft→refined → 写回 + git commit
未收敛(escalate/振荡/回退/轮次顶) → 最佳候选稿存 runs/<id>/candidates/ 等人工
```

## 模块地图（子包结构）

| 子包 | 职责 |
| --- | --- |
| `studio/core/` | 配置加载校验、卡片解析与**无损回写**、机器门禁、抽象接口（BaseRole/BaseMemory/BaseSkillSource） |
| `studio/llm/` | OpenAI 兼容客户端：重试退避、JSON 提取+修复重试、磁盘缓存、成本预算 |
| `studio/roles/` | 产出 schema + 模板角色基类 + 具体角色（批判/主编/提案）+ **RoleFactory**（新角色种类在此注册） |
| `studio/skills/` | 技能模型（markdown+front-matter）、注册表（内核+项目包聚合）、装载裁决（绑定>申请>触发，预算封顶） |
| `studio/context/` | 上下文组装：**角色隔离视图**、轮次摘要提取式压缩、预算裁剪 |
| `studio/memory/` | 工作区（reviews/steering/ledger/runs）+ **topic 级记忆** + **agent 级经验记忆** |
| `studio/loop/` | **规划阶段**（读任务卡分析 goal/todo，plan.json 落盘）+ 轮次循环：收敛判定、振荡检测、分数回退回滚、保守写回、记忆写入 |
| `studio/skills_builtin/` | 内核通用技能（项目无关方法论）；项目技能放 `packs/*/skills/` |
| `studio/cli.py` | `validate / status / steer / skills / memory / run` 六个子命令 |

## 技能自主调用（两级模型）

- **确定性路由（主路径）**：技能 front-matter 的 `triggers` 命中目标卡正文或任务目标 → 自动装载；cast.yaml 角色可显式绑定 `skills: [id]`；
- **角色自主申请（辅路径）**：批判者在产出 JSON 的 `skill_requests` 中按 id 申请，下一轮经白名单与预算校验后装载——模型有自主权，内核有否决权；
- 纪律：单角色单轮 ≤ `max_skills_per_role`(3)，技能段 ≤ `skill_context_chars` 字符；角色 prompt 常驻只有技能索引行（渐进披露），命中才装全文。

## 规划阶段（goal 与 todo 从任务卡分析得出）

run 开始先规划再执行，goal 来源三级：

1. **manual**：任务 YAML 写了 `goal:` → 人工覆盖，不调规划者；
2. **planner**：cast 配置了规划者角色 → LLM 读任务卡 + 目标卡片清单 + 主题记忆，产出 `{goal, todos[{card_id, focus}], constraints, risks}`，内核校验补全（未知卡丢弃、缺失卡补齐）；
3. **fallback**：无规划者时确定性推导（dry-run 也走这条，零 LLM 成本）。

计划落盘 `work/runs/<id>/plan.json`，todo 状态（pending/in_progress/done/skipped）由内核随执行推进——不信任模型自报；每卡的 focus 注入该卡的 `<<<任务目标>>>` 段；run 报告含计划执行表。

## 上下文：裁剪 · 压缩 · 隔离

- **隔离**：批判者并列互不可见；提案者只见主编指令、不见原始批判、不注入代理经验；每个角色按 `VIEW_SECTIONS` 取自己的视图；
- **压缩**：轮次历史用提取式摘要（裁决+采纳指令+高严重度 issue），零 LLM 成本、确定可重放；完整现场在 `work/reviews/<卡>/`；
- **裁剪**：超预算按 代理经验→主题记忆→轮次摘要→相邻卡→依赖节选 顺序砍半再清空；总览/协议/任务目标/目标卡/技能永不裁剪。

## 记忆分层

| 层 | 位置 | 内容 |
| --- | --- | --- |
| 长期状态 | 卡片本身 | 设计事实（core.cards 管理） |
| 情景记忆 | `work/reviews/<卡>/round-N.json` | 每轮完整发言与裁决 |
| **主题记忆** | `work/memory/topics/<议题文件>.jsonl` | 收敛结论、escalate 原因、defer 的开放问题——下次跑同主题时注入上下文 |
| **代理经验** | `work/memory/agent.jsonl` | 收敛率、门禁高频拒收码、人工沉淀的 lesson——注入批判者/主编上下文 |

## 关键机制速查

- **Loop**：外层按任务选卡（stake > 优先级），内层每轮 = 批判(并列) →
  无证据 issue 直接丢弃 → 主编逐条处置(含上一轮遗留) → 提案者修订 →
  门禁(拒收带错误重试一次)。收敛 = 主编判 converged；停机 = 轮次上限 /
  振荡(与两轮前相似度 >0.85) / 分数回退 ≥0.5(回滚至最优)。
- **上下文**：每次调用从文件重新组装，零会话累积；预算 36k 字符，
  超限按 轮次摘要→相邻卡→依赖节选 顺序裁剪；总览与协议永不裁剪。
- **Harness**：所有 LLM 产出先过 pydantic schema，修订稿再过 7 类
  机器门禁；写文件一律 tmp+rename 原子写；只有 converged 才写回库，
  半成品永远进 candidates/ 不进库。
- **Memory**：三层全文件化——卡片即长期状态；`work/reviews/<卡>/`
  每轮完整记录（回灌最近 2 轮防拉锯）；`work/ledger.jsonl` 成本台账 +
  `work/runs/<id>/` 日志、报告、候选稿。
- **LLM 管理**：`packs/*/models.yaml` 定义模型位（workhorse/judge），
  角色按位绑定；响应按 prompt 哈希落盘缓存（重跑幂等且省钱）；单次
  run 有 USD 与 token 双封顶，触顶安全终止。

## 快速开始

```bash
cd game-studio
pip install -r requirements.txt

# 1. 自检: 解析全库卡片 + 报告存量协议问题(不阻塞)
python -m studio.cli validate --pack packs/my-ft

# 2. 干跑: 不调 LLM, 导出每张卡的完整组装上下文供人工检查
python -m studio.cli run --pack packs/my-ft \
    --task topis/tasks/01-foundation.yaml --dry-run

# 3. 假产出全流程演练(不花钱, 验证 loop/门禁/写回路径)
python -m studio.cli run --pack packs/my-ft \
    --task topis/tasks/01-foundation.yaml --fake --no-git

# 3.1 断点续跑: 跳过已 done 的 todo; 需要重跑失败卡时加 --retry-failed
python -m studio.cli run --pack packs/my-ft \
    --task topis/tasks/01-foundation.yaml --resume 20260612-xxxx --fake --no-git

# 4. 真跑(任务序列与运行手册见 topis/tasks/README.md, 按 01..15 顺序)
export DEEPSEEK_API_KEY=sk-...
python -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml

# 工具
python -m studio.cli status --pack packs/my-ft
python -m studio.cli skills --pack packs/my-ft          # 技能清单(加载即校验)
python -m studio.cli memory --pack packs/my-ft          # 代理经验+主题记忆摘要
python -m studio.cli steer --pack packs/my-ft DIR-04 "荒诞预算改为按队伍独立"
pytest                       # 离线测试(不需要 API key)
```

每次 run 会写入 `work/runs/<run_id>/events.jsonl`、`run.log`、`llm.log`、
`plan.json` 和 `report.md`。终端输出由 `RunLogger` 流式刷新 stage/plan 事件；
LLM 完整对话默认写入 `llm.log`（不刷 token）。排查 JSON 失败时可执行
`tail -f work/runs/<run_id>/llm.log`。

终端展示默认使用 Rich；如需纯文本或脚本环境，可用：

```bash
python -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --no-rich --compact
python -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --enable-message
python -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --no-stream
```

`--enable-message` 开启 LLM token 终端流式展示（默认关闭，对话见 `llm.log`）；
`--no-stream` 会关闭全部终端输出，仅写 `events.jsonl` 和 `run.log`。

## 迁出独立 repo

整个 `game-studio/` 仓库自包含：复制到新 repo 后只需修改
`packs/my-ft/pack.yaml` 的 `docs_root` 指向卡片库位置。验收命令：
`cp -r game-studio /tmp/x && cd /tmp/x && pytest`。

## v2 路线（对应 17-agent-framework 里程碑）

M2 模拟用户角色 + 工具运行时（sim_run/metrics_query 注入批判者证据）、
skill 装载；M3 交接包编译器（PRD/UX/Tech/Tests/Tasks）；M4 第二个
项目包验证复用性。
