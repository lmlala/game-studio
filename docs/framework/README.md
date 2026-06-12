<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# Design Studio — 可复用设计 agent 框架（开发设计文档）

> 代号 **studio**（设计编辑部）。本目录是**软件开发设计文档**，不是游戏
> 设计卡片：你将按这份文档实现 agent。与 `14-design-agent.md` 的关系：
> 14 是单角色确定性闭环（本框架的 M0 里程碑）；本目录把它扩展为
> **多角色、多轮迭代、跨项目可复用**的完整框架。

## 1. 愿景与三条硬需求

把「一个产品理念」加工成「编码 agent 可直接执行的实现文档」的自动化
设计工作室：

1. **可复用**：内核与项目无关。下一个游戏、下一个效率 app，只需要写
   一个新「项目包」（商业目标、风格、理念、系统模块、角色班子、skill
   选集），内核零改动；
2. **多轮多角色迭代**：不是对单 task 调一次 LLM。设计单元经历
   提案 → 多视角批判（商业/UX/技术/心理学/一致性）→ 模拟用户评估 →
   主编裁决 → 修订 的多轮循环，直到通过验收标准或升级人工；支持
   人工随时注入方向（steering）；
3. **标准 tool / skill 能力**：角色可调用受控工具（读工作区、跑模拟、
   查指标、做校验），并按需装载领域 skill（商业、UX、心理学、叙事等
   知识模块）。

最终产物：交接包（handoff bundle）= 产品 PRD + UX 规格 + 技术规格 +
测试用例 + 有序任务清单，格式直接喂 Claude Code / Cursor 落地编码。

## 2. 非目标（防止内核膨胀）

- 不做编码 agent（编码交给 Claude Code / Cursor，studio 只产文档）；
- 不做通用聊天助理 / 消息网关（Hermes/OpenClaw 的领域，不重复）；
- 不做无人值守的全自动设计：人是终审与品味来源，框架只放大你；
- 不追求框架本身的产品化发布（先服务自己的两个项目，复用性靠
  「第二个项目包跑通」验证，不靠假想需求）。

## 3. 文档结构与阅读顺序

| 文件 | 内容 |
| --- | --- |
| [`01-architecture.md`](01-architecture.md) | 内核/项目包分离、工作区与数据模型、状态机、编排器、模型路由、成本管理 |
| [`02-roles-and-iteration.md`](02-roles-and-iteration.md) | 角色系统、多轮迭代协议、收敛与停机规则、方向注入、防退化 |
| [`03-pipeline-and-handoff.md`](03-pipeline-and-handoff.md) | 端到端六阶段管线、输入 brief 规范、交接包格式（PRD/UX/Tech/Test/Tasks）、与编码 agent 的对接 |
| [`04-tools-and-skills.md`](04-tools-and-skills.md) | 工具运行时（两级调用模型）、内置工具清单、skill 格式与装载、游戏设计领域 skill 目录 |

## 4. 仓库布局建议

内核独立成库（复用的物理前提），项目包跟随各自项目仓：

```text
design-studio/                  # 独立仓库: 内核 (Python)
├── studio/
│   ├── orchestrator.py         # 编排器: 阶段机 + 轮次循环
│   ├── roles/                  # 角色运行时 (加载 cast 配置)
│   ├── tools/                  # 工具运行时 + 内置工具
│   ├── skills/                 # skill 装载器 (skill 内容在项目包)
│   ├── schema/                 # 工件 front-matter / 消息 JSON schema
│   ├── gates/                  # 机器门禁 (lint/引用/可判定性)
│   ├── models.py               # 模型路由 + 成本计量
│   └── workspace.py            # git 工作区操作
├── kernel-skills/              # 项目无关的通用 skill (可选少量)
└── tests/

my-ft/                          # 本项目仓库
└── studio-pack/                # 项目包 #1 (首个用户)
    ├── brief.yaml              # 商业目标/风格/理念/用户画像/约束
    ├── cast.yaml               # 角色班子配置 (批判者/模拟用户绑定)
    ├── schema.yaml             # 设计单元 schema (= 00 卡片协议的机读版)
    ├── skills/                 # 领域 skill (markdown)
    ├── gates/                  # 项目门禁 (术语表/禁用词/规则 DSL 引用)
    ├── adapters/               # 项目工具适配器 (sim_run / funnel_report)
    └── templates/              # 交接包模板 (prd/ux/tech/tests/task)
```

## 5. 里程碑（按此顺序实现）

| 里程碑 | 内容 | 验收 |
| --- | --- | --- |
| **M0** | 内核骨架：工作区 + schema + 单角色（提案者+验收官）闭环 = 14 号文档的流水线 | 对 topis/football-docs 现有卡片跑通精修，采纳率 ≥ 60% |
| **M1** | 角色班子 + 主编 + 多轮收敛；方向注入 | 同一卡片多轮后质量盲评优于 M0 单轮（人工对比 10 例） |
| **M2** | tool 运行时 + skill 装载；模拟用户角色 | 批判产出中引用 skill 检查点 / 工具证据的比例 ≥ 50% |
| **M3** | 交接包编译器（PRD/UX/Tech/Test/Tasks） | 取 1 个模块生成交接包，喂 Cursor/Claude Code 实现，一次跑通编译+测试骨架 |
| **M4** | 复用验证：第二个项目包（建议拿一个小效率 app 的 brief 做干跑） | 不改内核代码完成 Phase 0-2，缺口全部记录为内核 issue |

## 6. 顶层风险与对策

| 风险 | 对策 |
| --- | --- |
| 多角色成本爆炸 | 按设计单元的 stake 分级路由（P0 全班子，P2 精简班子）；轮次上限；见 02 §6 |
| 批判者同质化（同一模型扮演所有角色 → 同一盲区） | 角色差异来自 skill+量表+工具证据而非「演技」；定期强模型多样性审计；见 02 §3 |
| 收敛剧场（轮数在涨、质量没涨） | 主编裁决必须逐条引用上一轮 issue 的处置；振荡检测；改进分数不单调即停机升级人工 |
| 内核被项目细节污染 | 铁律：任何领域知识只能进项目包（skill/gates/templates/adapters），内核 PR 审查首项检查 |
| 框架建设吞噬游戏开发时间 | 里程碑严格递进，每个 M 都必须立刻服务 my-ft 的真实设计任务；M4 之前不为「通用性」写一行多余代码 |
