<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# topis — 原始议题与任务卡片

`topis/` 是 loop agent 的输入工作区，放置设计讨论从高层想法进入研发、
美术等可执行设计文档前的原始材料。

## 目录

| 路径 | 内容 | 消费方 |
| --- | --- | --- |
| `topis/football-docs/` | 原始议题与设计卡片，按五字段协议组织 | `packs/my-ft/pack.yaml` 的 `docs_root` |
| `topis/tasks/` | agent 精修任务卡片，按执行顺序选择目标卡 | `python -m studio.cli run --task ...` |

## 约定

- 议题卡片文件继续只保存设计内容，任务选择、班子、方向放在 `topis/tasks/`；
- **路径分工**：
  - CLI `--task` → 相对仓库根，如 `topis/tasks/01-foundation.yaml`；
  - 任务内 `target_files` → 相对 **`pack.yaml` 的 `docs_root`**
    （当前 = `topis/football-docs/`），**不是**相对 `topis/` 根；
  - 因此 `target_files` 里通常**不带** `football-docs/` 前缀，子目录由
    `docs_root` 承担；
- 新增议题目录时，为对应 pack 更新 `docs_root` 指向 `topis/<子目录>/`，
  不要在 Python 代码里写死路径。详见 [`tasks/README.md`](tasks/README.md#路径解析两层不要混)。
