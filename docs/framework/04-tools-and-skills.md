<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# 04 — 工具运行时与 skill 体系

> 回答第三点：agent 的标准 tool / skill 能力怎么做，以及游戏设计领域
> （商业、UX、心理学等）哪些 skill 值得先写。

## 1. 工具运行时：两级调用模型

中档模型 + 自主工具循环 = 不稳定。框架采用两级模型，把「自主性」
留在便宜且可控的位置：

- **管线级工具（主路径）**：由编排器在固定阶段**确定性调用**，结果
  注入角色上下文——角色不发起，只消费。例：批判前自动跑
  `dependency_graph` 和 `glossary_lookup`，技术批判者上下文自动附
  最近跑批指标。90% 的工具价值走这条零风险路径；
- **角色级工具请求（辅路径）**：角色在产出 JSON 中声明
  `tool_requests: [{tool, args, why}]`，内核校验白名单与预算后执行，
  结果回填，**同一角色同一轮最多一次补充调用**（一问一答，不开
  自主循环）。满足「批判者想看一眼证据」的需求，又锁死了失控面。

### 工具规格（每个工具一份声明）

```yaml
- name: sim_run
  side_effects: none          # 只读沙箱: 全部工具禁止写工作区(写权只在内核)
  cost_class: heavy           # light(本地) / heavy(跑批/网络) → 预算约束
  args_schema: {check: string, seeds: int_range}
  provider: pack_adapter      # kernel 内置 或 项目包 adapter
```

### 内置工具清单（kernel）

| 工具 | 功能 | 主要消费者 |
| --- | --- | --- |
| read_artifact | 按 id/路径读单元、brief、决策日志 | 全角色 |
| search_workspace | ripgrep 式全库检索 | 一致性批判者、提案者 |
| glossary_lookup | 术语表精确查询 | 一致性批判者、门禁 |
| dependency_graph | 单元依赖子图与影响面 | 主编、一致性批判者 |
| schema_validate | 单元/产出 JSON 校验 | 验收官、门禁 |
| diff_summary | 修订 diff 摘要 | 主编、振荡检测 |
| web_research | 限频联网检索（结果缓存+引用留痕） | 商业批判者（可选开） |

### 项目包适配器工具（my-ft）

| 工具 | 功能 |
| --- | --- |
| sim_run | 调 `sim_cli batch` 定向跑批（如 `--check absurdity`），返回指标摘要 |
| metrics_query | 查 runs/baseline 与历史实验指标（EVAL-02） |
| funnel_report | 查 15-mentor 漏斗的规则通过率/Reject 样本 |
| event_dryrun | 单事件定义试触发（EVT-01 单测的工具化封装） |

> 互操作备注：工具接口与 MCP（Model Context Protocol）语义兼容但
> 不直接依赖——日后若想把这些工具暴露给 Cursor/Claude Code 复用，
> 写一层 MCP server 包装即可，内核不绑定。

## 2. skill 体系

### 2.1 格式（与 agentskills 开放标准对齐的 markdown 模块）

```markdown
---
id: sdt-motivation
name: 自我决定论动机分析
version: 2
applies_to_roles: [critic_psych, proposer]
tokens: ~900
triggers: [动机, 留存, 奖励, 粘性]      # 路由关键词(单元正文命中即装载)
---
## 何时使用
评估任何涉及玩家动机/留存/奖励结构的设计单元。
## 检查清单 (批判时逐条核对, issue 须引用编号)
- SDT-1 自主性: 设计是给玩家选择还是替玩家选择? 假选择(选项使用率>80%)?
- SDT-2 胜任感: 反馈回路是否让玩家感到"我变强/变懂了"? 归因是否清晰?
- SDT-3 关联感: 是否制造玩家与角色/世界的双向关系(角色记得玩家)?
- SDT-4 外在奖励侵蚀: 是否用外部奖励替代了本该内在有趣的环节?
## 锚定样例
- 好: my-ft 记忆系统让球员记住玩家承诺 (SDT-3 强)
- 坏: 每日签到送金币 (SDT-4 典型侵蚀, 另触发 dark-pattern skill)
## 反模式
- 把"粘性"做成损失厌恶 (转 ethics-darkpatterns skill 处理)
```

### 2.2 装载与纪律

- **渐进披露**：角色 prompt 常驻仅 skill 索引（id+name+何时使用，
  几百 token）；命中 triggers 或 cast.yaml 显式绑定才装全文；单角色
  单轮 ≤ 3 个 skill（中档模型上下文纪律）；
- **当前实现的三路装载**：
  1. cast.yaml 显式绑定 `skills: [id]`；
  2. 批判者产出 JSON 的 `skill_requests` 申请下一轮装载；
  3. `triggers` 命中目标卡正文或规划 goal；
  三路统一进入 `SkillLoader`，被白名单、角色适用性、数量和字符预算裁决；
- **skill 即测试对象**：每个 skill 配 3-5 道回归题（给一段设计 +
  标准 issue 要点），换模型/改 skill 后跑回归——skill 的有效性
  可度量，不靠信仰；
- **来源纪律**：skill 正文是你审过的知识压缩（agent 可起草，你签收
  入库），错误的 skill 比没有 skill 危害大——它会被批判者当圣经
  引用；
- 项目无关的方法论 skill（如 scope-control）放 `studio/skills_builtin/`，
  领域 skill 放项目包——同一条复用边界。

当前落地路径：

| 类型 | 路径 | 已有示例 |
| --- | --- | --- |
| 内核通用 skill | `studio/skills_builtin/` | `decidable-acceptance`、`scope-control` |
| 项目领域 skill | `packs/my-ft/skills/` | `systems-balance`、`deterministic-sim`、`sdt-motivation` |

校验命令：`python3 -m studio.cli skills --pack packs/my-ft`。

## 3. 游戏设计领域 skill 目录（建议清单）

按「角色 × 优先级」组织。⭐ = 首批必写（约 12 个，每个半小时到
一小时，是你写 agent 之外最值的内容投资）。

### 商业 / 市场（critic_business）

| skill | 核心内容 | 优先 |
| --- | --- | --- |
| steam-positioning | 标签策略、对标品选择、愿望单基准线、商店页钩子结构 | ⭐ |
| scope-control | MoSCoW、砍功能决策树、副业工时预算法、"窄而深"检查 | ⭐ |
| pricing-business-model | 买断/EA/DLC 路线选择、定价锚点、地区定价 | |
| competitor-teardown | 竞品拆解框架（机制/钩子/评价区痛点挖掘） | ⭐ |
| launch-cadence | demo/Next Fest/EA 节奏、愿望单转化经验值 | |

### UX（critic_ux）

| skill | 核心内容 | 优先 |
| --- | --- | --- |
| ia-heuristics | 信息架构 + Nielsen 十启发式的游戏化改写 | ⭐ |
| cognitive-load | Miller/Hick 定律、同屏信息预算、决策疲劳信号 | ⭐ |
| onboarding-design | 渐进披露、教学即剧情、首小时漏斗设计 | ⭐ |
| game-ui-text | 微文案、信息层级↔排版映射、本地化预检 | |
| usability-test-script | 可用性测试任务脚本与访谈题设计（给真人测试用） | |

### 心理学（critic_psych + sim_user 校准）

| skill | 核心内容 | 优先 |
| --- | --- | --- |
| sdt-motivation | 自我决定论：自主/胜任/关联 + 外在奖励侵蚀 | ⭐ |
| flow-difficulty | 心流通道、挑战-技能平衡、倒 U 压力曲线 | ⭐ |
| behavioral-econ | 损失厌恶、禀赋效应、可变奖励、峰终定律 | ⭐ |
| fairness-attribution | 归因理论、随机容忍度、可解释性与信任修复 | ⭐ |
| ethics-darkpatterns | 黑模式清单与替代方案（PSY-07 的知识版） | ⭐ |
| player-typology | Bartle/Quantic 动机分型、画像→机制映射法 | |

### 游戏设计方法（proposer + 各批判者共用）

| skill | 核心内容 | 优先 |
| --- | --- | --- |
| mda-framework | 机制-动态-美感分析法（从体验倒推机制） | |
| emergent-narrative | 涌现叙事设计模式：RimWorld/DF/CK 案例的可移植规律（压力发牌/记忆回响/失败叙事） | ⭐ |
| systems-balance | 反馈环识别、源-汇经济、优势策略检测、数值带设计 | ⭐ |
| narrative-craft | 弧线结构、角色一致性、黑色幽默的错位技法、文本节制 | |

### 技术（critic_tech）

| skill | 核心内容 | 优先 |
| --- | --- | --- |
| deterministic-sim | 确定性模拟工程清单（RNG 流/迭代序/浮点/回归合同） | ⭐ |
| save-migration | 存档版本化与迁移模式、内容包钉版（CNT-02 知识版） | |
| data-driven-design | 配置外置、schema 演进、热调参边界 | |

> 注意分工：skill 是**通用方法论**，brief/单元内容是**项目事实**。
> 「my-ft 的荒诞预算上限是 4.0」永远不进 skill——进的是「预算经济
> 模型的设计与校准方法」。这条边界保证 skill 真正跨项目复用（效率
> app 项目直接复用 UX/心理学/商业全套，只有游戏设计方法目录不装载）。

## 4. 本文件实现验收标准

- [机器] 工具两级调用：管线级注入有快照测试；角色级请求超白名单/
  超预算/超次数被拒绝（构造用例）；
- [机器] 全部工具 side_effects=none 的静态保证（工具进程只读挂载
  工作区或路径白名单）；
- [机器] skill front-matter 校验；渐进披露 token 预算生效；每个
  入库 skill 回归题通过；
- [人工] M2 验收（README §5）：批判产出引用 skill 检查点编号或
  工具证据的比例 ≥ 50%；
- [人工] 首批 ⭐ skill（12 个）由你签收入库，每个 ≤ 1200 token。
