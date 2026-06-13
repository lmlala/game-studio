<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# 任务序列与运行手册

> 15 个任务按依赖顺序排列：**被依赖的系统先收敛**——上游卡 refined 后，
> 下游卡上下文里的依赖节选质量更高，批判更准。每晚跑一个任务，串行执行
> （工作区是文件态，并行任务会互踩）。

任务文件必填字段：`name`、`target_files`。**goal 默认不用写**——run
开始时由规划者（planner 角色）读任务卡 + 目标卡片清单 + 主题记忆，
分析出本次 goal、逐卡 todo（focus）与约束，落盘 `runs/<id>/plan.json`
并注入所有角色上下文；任务文件里写 `goal:` 则是人工覆盖（不调规划者）。
可选字段：`constraints`、`direction`（规划与执行的方向输入）、
`critics`/`stake`/`rounds`。

## 路径解析（两层，不要混）

| 路径类型 | 写法示例 | 解析基准 |
| --- | --- | --- |
| 任务卡本身 | `--task topis/tasks/01-foundation.yaml` | 仓库根目录 |
| 目标设计文档 | `target_files: [01-engine-overview.md]` | **`pack.yaml` 的 `docs_root`**，不是 `topis/` 根 |

当前 my-ft 的 `packs/my-ft/pack.yaml` 已设置：

```yaml
docs_root: ../../topis/football-docs
```

因此任务里写 `01-engine-overview.md` 实际解析为
`topis/football-docs/01-engine-overview.md`。**不需要**在 `target_files`
里再写 `football-docs/` 前缀——子目录名已经包含在 `docs_root` 里。

```text
topis/
├── football-docs/          ← pack.docs_root 指向这里
│   └── 01-engine-overview.md
└── tasks/
    └── 01-foundation.yaml  ← target_files: [01-engine-overview.md]
                              相对 football-docs/，不是相对 topis/
```

若以后新增第二个议题目录（如 `topis/other-game/`），正确做法是：

1. 新建 pack（或改 `docs_root` 指向 `topis/other-game/`）；
2. 该 pack 下的任务 `target_files` 仍只写文件名或该目录内相对路径；
3. **不要**在 Python 里写死 `football-docs` 字符串。

## 执行顺序与班子

| # | 任务 | 目标 | 班子（除提案者/主编外） | 高危卡(5轮) | 估算调用 |
| --- | --- | --- | --- | --- | --- |
| 01 | foundation | ENG×7 + SEED×5 | 一致性·工程·数值 | ENG-01/02/03/07, SEED-01/03 | ~190 |
| 02 | numeric | NUM×7 | 一致性·数值·工程 | NUM-01/02/05/06 | ~130 |
| 03 | actor | ACT×7 | 一致性·叙事·数值·体验 | ACT-01/03/05 | ~150 |
| 04 | relationship | REL×6 | 一致性·叙事·工程·数值 | REL-01/03 | ~130 |
| 05 | events | EVT×7 | 一致性·叙事·数值 | EVT-01/02/07 | ~130 |
| 06 | director | DIR×8 | 一致性·叙事·数值·体验 | DIR-01/02/04 | ~170 |
| 07 | match | MAT×7 | 一致性·数值·工程·叙事 | MAT-01/06 | ~150 |
| 08 | worldview | WV×6 | 一致性·叙事·体验 | WV-04/05 | ~110 |
| 09 | catalog | CAT×6 | 一致性·叙事·数值·工程 | CAT-06 | ~130 |
| 10 | agency | AGY×6 | 一致性·体验·叙事·数值 | AGY-01/02/05 | ~130 |
| 11 | ux | UX×7 | 一致性·体验·叙事 | UX-01/02 | ~120 |
| 12 | psychology | PSY×7 | 一致性·体验·叙事 | PSY-02/03/04 | ~120 |
| 13 | evaluation | EVAL×6 | 一致性·工程·数值 | EVAL-02/03 | ~110 |
| 14 | content-art | CNT×5 + ART×4 | 一致性·叙事·体验 | CNT-02/03 | ~130 |
| 15 | sweep | 全库二遍巡检 | 仅一致性（轮次上限 2） | — | ~300 |

费用量级（DeepSeek 价位）：单任务 ≈ 1-2M token ≈ **$0.3-0.8**；
全序列含 sweep ≈ **$6-10**。首跑建议先用 `--dry-run` 看上下文，再
`--fake --no-git` 走一遍流程，最后真跑。

排序原因一句话：01/02 是所有批判的依据（架构契约 + 数值宪法）→
03/04/05 是叙事原子（人物→关系→事件）→ 06/07 是两大消费引擎
（Director、比赛）→ 08-12 内容与玩家面 → 13/14 工具与产品面 →
15 跨卡巡检收口。

## 每日节奏（建议）

```bash
# 晚上
python3 -m studio.cli validate --pack packs/my-ft          # 跑前体检
python3 -m studio.cli run --pack packs/my-ft --task topis/tasks/NN-xxx.yaml
# 早上(10-20 分钟)
#  1. 看 work/runs/<id>/report.md: converged/escalated/failed 一览
#  2. git diff 审 converged 卡(它们已写回+commit): 不满意 → git revert 单卡
#  3. 看 candidates/ 未收敛候选稿: 可手工采纳/丢弃/steer 后重跑
#  4. frozen/escalated 卡: steer 注入方向, 用 include_ids 单卡重跑
python3 -m studio.cli steer --pack packs/my-ft DIR-04 "你的裁决"
```

单卡重跑：复制任务文件加 `include_ids: [DIR-04]` 即可（缓存使未变
的调用零成本，改过 steering/卡片正文的调用自动失效缓存重新计算）。

## 人工抽查与状态晋升

- agent 最高只能把卡片升到 `refined`；`reviewed` 必须你手改状态行；
- 抽查比例建议：high 卡 100% 精读 / normal 50% / low 抽 10%；
- 抽查要点（比读全文快）：验收标准是否真的可判定、数值是否引用
  NUM 总表而非自带、修订是否保留了原卡优点（对照 review 记录中的
  praise 字段）；
- `converged ≠ 正确`：主编也是中档模型，它判收敛只代表"班子内部
  无未决分歧"，品味终审永远在你。

## 失败处理速查

| 结果 | 含义 | 处理 |
| --- | --- | --- |
| failed | 门禁两次拒收修订 | 看 report 错误码; 多为格式/术语问题, 直接重跑一次, 复发则查 prompt |
| escalated(振荡) | 两版本来回改 | 说明存在真实设计分歧, steer 拍板后单卡重跑 |
| escalated(回退) | 分数变差已回滚 | 同上, 候选稿是历史最优版 |
| max_rounds | 到顶未收敛 | 候选稿通常已比原卡好, 人工 diff 决定采纳 |
| BudgetExceeded | 预算触顶 | 正常保护; 已完成卡不受影响, 次日续跑(缓存生效) |

## 你可能没想到的几点

1. **direction/cast 改动会自动失效缓存**（prompt 变了哈希就变）——
   这是特性：调整指令后重跑就是干净实验；
2. **00/00a/20 是 agent 禁区**：宪法两件套代码级禁改；20 黄金样例
   是人工维护文档，各任务收敛后你应顺手核对 20 是否失真；
3. **15-mentor 思路稿不在任务序列里**：它等我们讨论定稿拆卡后才进
   精修流程；
4. **跨卡修改的单侧原则**：批判者发现 A/B 两卡冲突时，agent 只改
   当前任务内的卡，对侧卡进 issue 由你决定是否开补充任务——避免
   连锁改动失控；
5. **模型实验方法**：换 models.yaml 的位绑定后，用任务 03（中等
   难度、卡片质量已知）重跑对比采纳率，再决定是否全面换模型；
6. **何时停**：两遍 pass 后（01-14 + 15 sweep）边际收益会骤降，
   应转入实现阶段，之后的设计修订由评估管线弱项驱动（EVAL-05），
   不再做全库轮询；
7. **git 纪律**：每任务跑完是一串单卡 commit，review 后统一 push；
   不满意的卡 `git revert <commit>` 单独回滚，不影响其他卡。
