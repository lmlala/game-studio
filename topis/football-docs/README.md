<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# topis/football-docs — 设计卡片工作区

> 本目录是 **设计精修工作区**：把游戏的全部设计拆成统一格式的「设计卡片」，
> 供人和设计 agent 共同迭代。它不立即替换 `docs/`；当某张卡片达到 `locked`
> 状态后，再人工合并回 `docs/` 正式文档。

## 定位

- 读者一：**你自己**（开发者），用来做设计决策和实现对照。
- 读者二：**设计 agent**（实现与软件设计见 `studio/`），
  按 [`00-design-card-spec.md`](00-design-card-spec.md) 的协议逐卡精修。
- 读者三：**评估管线**（见 [`13-evaluation-pipeline.md`](13-evaluation-pipeline.md)），
  按卡片中的「评估钩子」生成模拟指标与 LLM 评分，反向产生新的设计任务。

> 边界说明：本目录只放**游戏设计**。设计 agent 自身的软件设计文档
> 已迁至 `docs/`（随应用一起迁出仓库）。

## 文件索引

| 文件 | 主题 | 卡片前缀 |
| --- | --- | --- |
| [`00-design-card-spec.md`](00-design-card-spec.md) | 卡片协议、全局原则、术语表 | META |
| [`00a-game-overview.md`](00a-game-overview.md) | **游戏总览**（agent 常驻上下文：定位/幻想/循环/系统路由表/范围红线） | 只读宪法 |
| [`01-engine-overview.md`](01-engine-overview.md) | 游戏引擎总体设计 | ENG |
| [`02-worldview.md`](02-worldview.md) | 世界观设计 | WV |
| [`03-narrative-director.md`](03-narrative-director.md) | 主叙事引擎（风格化 / 荒诞控制 / 世界线演化） | DIR |
| [`04-engine-catalog.md`](04-engine-catalog.md) | 子引擎 / 子子引擎总目录 | CAT |
| [`05-event-system.md`](05-event-system.md) | 事件系统 | EVT |
| [`06-actor-system.md`](06-actor-system.md) | 人物系统 | ACT |
| [`07-relationship-system.md`](07-relationship-system.md) | 关系与派系系统 | REL |
| [`08-seed-system.md`](08-seed-system.md) | seed / 确定性 / 世界生成 | SEED |
| [`09-match-system.md`](09-match-system.md) | 比赛系统 | MAT |
| [`10-art-style.md`](10-art-style.md) | 美术风格（定调，不深入） | ART |
| [`11-ux-interaction.md`](11-ux-interaction.md) | UX 用户交互主要途径 | UX |
| [`12-player-psychology.md`](12-player-psychology.md) | 游戏心理学与粘性 | PSY |
| [`13-evaluation-pipeline.md`](13-evaluation-pipeline.md) | 模拟跑批 + LLM 评估（爽点/荒诞等指标） | EVAL |
| [`15-mentor-storyline-funnel.md`](15-mentor-storyline-funnel.md) | Mentor 故事线漏斗（**思路稿**，待讨论后拆卡） | MEN（预留） |
| [`16-content-pipeline.md`](16-content-pipeline.md) | 故事线种子、内容包、服务端分发与壁垒定位 | CNT |
| [`18-numeric-design.md`](18-numeric-design.md) | **数值设计原则与方法**（量纲/堆叠/随机预算/速率表/频率配额/校准，关键点[锁死]） | NUM |
| [`19-player-agency.md`](19-player-agency.md) | **玩家代理感**：可控面取舍、动词杠杆表、决策入因果链、长线回敬 | AGY |
| [`20-golden-scenario.md`](20-golden-scenario.md) | **黄金样例**：替补门将的怨恨——纵切 worked example（团队对齐 + 回归基线） | 样例文档 |

（原 `14-design-agent.md` 与 `17-agent-framework/` 属于工具的软件
设计，已迁至 `docs/`，编号 14/17 保留空缺。）

## 推荐阅读顺序

1. `00`（协议与原则）→ `00a`（游戏总览）→ `20`（黄金样例，先看故事怎么跑通）；
2. 总纲：`01`（总体架构）→ `04`(引擎目录) → `18`（数值宪法）→ `19`（代理感）；
3. 叙事主线：`03` → `05` → `06` → `07`；
4. 模拟基座：`08` → `09`；
5. 产品面：`02` → `10` → `11` → `12`；
6. 工具链：`13` → `15`（思路稿）→ `16`；agent 软件设计在 `docs/`。

## 团队导读（假想把文档交给一个完整团队时的分工读法）

| 角色 | 必读 | 工作方式 |
| --- | --- | --- |
| 产品 | `00a` → `20` → `02` `12` `19` `16` | 用 `20` 校验体验成立性；改方向走 steering 与 brief，不直接改卡 |
| 系统策划 | `00` → `20` → 各系统卡（`03`-`09`）+ `18` | 修订卡片必须过五字段与验收标准；数值只引用 `18` 的总表 |
| 开发 | `01` `08` `18` → 负责系统的卡 → `20` | 卡片的「如何设计」是规格、「验收标准[机器]」是测试清单；`20` 是第一条端到端集成测试剧本 |
| QA | `20`（QA 断言）→ 各卡「验收标准」→ `13` `15` | 单卡验收走卡片标准；批级/世界线级验收走评估管线与漏斗规则 |
| 文案/叙事 | `02` `05`(EVT-06/07) `18`(NUM-05 配额) | 事件写作规范在 EVT-07；荒诞分级样例库在 WV-05 |

理解一致性的三个机制：① `00a`+`00` 是所有人的共同宪法（也是 agent
的常驻上下文）；② `20` 黄金样例是跨角色的"同一个故事"——任何人对
系统的理解分歧都能在这条线上具体化；③ 卡片 ID 是唯一引用语言，
讨论必须落到卡片 ID，否则不进决策。

## 与现有 docs/ 和 rust/ 的关系

- `docs/` 是当前已实现/已验收内容的权威记录，**不要让 agent 直接改写**。
- `topis/football-docs/` 是设计前沿。卡片状态机：`draft → refined → reviewed → locked`。
- `locked` 卡片由人工合并进 `docs/` 对应文件，并按 `docs/AGENTS.md` 要求更新 changelog。
- 冲突时以 `00-design-card-spec.md` 的全局原则为最高约束。
- **对现有 `rust/` 代码：卡片是目标态规格，实现可以完全重构对齐卡片**，
  不被既有实现绑架；卡片撰写时不需要照顾现状（已确认的项目决策）。

## 当前状态

所有卡片初始状态均为 `draft`——内容已写到「可实现」的细度，但预期被设计
agent 和评估数据持续修订。每张卡片的「验收标准」是它能否进入 `refined`
的判据；「评估钩子」是它接入模拟跑批后的量化检验方式。
