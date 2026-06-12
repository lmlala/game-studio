<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# design-studio — 设计卡片精修 agent（v1）

把 `football-docs/` 的设计卡片送进「提案 → 多角批判 → 主编裁决 → 修订」
的多轮循环，收敛后写回并升级状态。对应设计文档（随本应用一起迁出）：
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

## 模块地图

| 模块 | 职责 |
| --- | --- |
| `studio/config.py` | pack/cast/models/task 四类配置的加载与校验（pydantic） |
| `studio/cards.py` | 卡片解析与**无损回写**（行区间替换 + 原子写），RepoIndex 全库索引 |
| `studio/gates.py` | 机器门禁：五字段/状态机/ID 不可变/可判定词/悬挂引用/术语漂移/膨胀 |
| `studio/context.py` | 上下文组装：总览+协议(不可裁) + 目标卡+方向 + 依赖节选 + 相邻卡 + 轮次摘要(可裁) |
| `studio/llm.py` | OpenAI 兼容客户端：重试退避、JSON 提取+修复重试、磁盘缓存、成本预算 |
| `studio/roles.py` | 角色运行时：Critique/Verdict/Revision 三个产出 schema + 模板渲染 + fake 产出 |
| `studio/rounds.py` | 轮次循环：收敛判定、振荡检测、分数回退回滚、保守写回策略 |
| `studio/memory.py` | 工作区：reviews 轮次记录、steering 方向、ledger 台账、run 日志与报告 |
| `studio/cli.py` | `validate / status / steer / run` 四个子命令 |

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
cd apps/design-studio
pip install -r requirements.txt

# 1. 自检: 解析全库卡片 + 报告存量协议问题(不阻塞)
python -m studio.cli validate --pack packs/my-ft

# 2. 干跑: 不调 LLM, 导出每张卡的完整组装上下文供人工检查
python -m studio.cli run --pack packs/my-ft \
    --task tasks/01-foundation.yaml --dry-run

# 3. 假产出全流程演练(不花钱, 验证 loop/门禁/写回路径)
python -m studio.cli run --pack packs/my-ft \
    --task tasks/01-foundation.yaml --fake --no-git

# 4. 真跑(任务序列与运行手册见 tasks/README.md, 按 01..15 顺序)
export DEEPSEEK_API_KEY=sk-...
python -m studio.cli run --pack packs/my-ft --task tasks/01-foundation.yaml

# 工具
python -m studio.cli status --pack packs/my-ft
python -m studio.cli steer --pack packs/my-ft DIR-04 "荒诞预算改为按队伍独立"
pytest                       # 离线测试(不需要 API key)
```

## 迁出独立 repo

整个 `design-studio/` 目录自包含：复制到新 repo 后只需修改
`packs/my-ft/pack.yaml` 的 `docs_root` 指向卡片库位置。验收命令：
`cp -r design-studio /tmp/x && cd /tmp/x && pytest`。

## v2 路线（对应 17-agent-framework 里程碑）

M2 模拟用户角色 + 工具运行时（sim_run/metrics_query 注入批判者证据）、
skill 装载；M3 交接包编译器（PRD/UX/Tech/Tests/Tasks）；M4 第二个
项目包验证复用性。
