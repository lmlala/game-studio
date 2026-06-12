<!--
Project: my-ft
Created Date: 2026-06-12
Author: liming
Email: lmlala@aliyun.com
Copyright (c) 2025 FiuAI
-->

# Studio 开发规则

这些规则约束 `studio/` 内核、项目包 `packs/*/`、任务卡片 `topis/tasks/`
和设计卡片 `topis/football-docs/` 的修改方式。

## 1. 修改前必读

1. `docs/studio/README.md`：当前实现索引；
2. `docs/studio/architecture.md`：子包边界、规划/skills/上下文/记忆；
3. `docs/studio/rules.md`：本文件；
4. 涉及长期蓝图时再读 `docs/framework/`。

## 2. 内核边界

- `studio/` 只放项目无关机制：配置、解析、门禁、角色运行时、规划、
  skills 装载、上下文、记忆、LLM 调用；
- my-ft 领域知识只能放在：
  - `topis/football-docs/`：设计卡片；
  - `topis/tasks/`：任务卡片；
  - `packs/my-ft/`：角色班子、模型、项目技能；
- 不要在 `studio/` 写入足球、球员、荒诞预算等领域事实，除非是测试 fixture；
- 角色没有文件写权；写回只允许通过 `CardRunner -> gates -> atomic_write`。

## 3. 规划规则

- `goal` 默认由规划阶段读任务卡分析得出；
- `topis/tasks/*.yaml` 里的 `goal:` 只是人工覆盖，日常任务不要写；
- 任务卡必须至少有 `name` 与 `target_files`；
- `target_files` 相对 `pack.yaml` 的 `docs_root`（当前 my-ft =
  `topis/football-docs/`），**不是**相对 `topis/` 根；通常不带
  `football-docs/` 前缀；
- CLI `--task` 才写完整路径，如 `topis/tasks/01-foundation.yaml`；
- `direction` 是规划输入和临时方向，不等同于最终 goal；
- `plan.json` 是运行事实，todo 状态只能由内核更新。

## 4. Skills 规则

- 新 skill 必须是 markdown + YAML front-matter；
- `id` 使用小写连字符，必须全局唯一；
- 项目无关方法论放 `studio/skills_builtin/`，领域方法论放 `packs/<pack>/skills/`；
- skill 正文只能放方法论、检查清单、反模式，不放项目事实；
- 批判 issue 若来自 skill，必须填写 `skill_ref`；
- 新增或修改 skill 后必须跑 `python3 -m studio.cli skills --pack packs/my-ft`。

## 5. 上下文与记忆规则

- 不要把原始长历史直接塞进 prompt；必须走 `context.compress` 或记忆 digest；
- 提案者视图不能注入代理经验，也不能看原始批判，只能看主编指令；
- 新增上下文段时必须：
  1. 明确哪个 `role_view` 可见；
  2. 明确是否可裁剪；
  3. 更新 `TRIM_ORDER` 或说明不可裁剪原因；
  4. 增加测试覆盖隔离与预算行为；
- 记忆必须 append-only jsonl；摘要必须确定性生成，不用 LLM 总结。

## 6. 模型、日志与 checkpoint 规则

- 模型供应商差异必须放在 `studio/llm/providers/` 或 `studio/llm/models/`；
  不要在通用 `LLMClient` 里写死 DeepSeek/Qwen/OpenAI 特例；
- DeepSeek JSON Mode 必须按官方文档走 provider policy：
  `response_format={"type":"json_object"}`、prompt 含 `json` 和 JSON 样例、
  空 content 可重试；
- LLM message 流式输出必须通过 provider `on_delta` 回调进入
  `RunLogger.message_delta -> studio/printing`，provider 禁止直接 print；
- cost 相关逻辑放 `studio/cost/`，不要散落在 provider 或 CLI；
- 运行状态输出必须走 `RunLogger`，不要在 `cmd_run/CardRunner` 里新增散落
  `print`；
- 终端展示格式必须放在 `studio/printing/`，不要在业务代码或 logger
  中直接写 Rich 样式；
- 每次 todo 状态变化后必须保存 `plan.json`，并记录 checkpoint；
- 单卡/单角色失败应记录为结构化日志并尽量继续后续卡片，除非是启动期
  配置错误或预算触顶。

## 7. 测试与验证

改 `studio/` 后至少运行：

```bash
python3 -m pytest
python3 -m studio.cli validate --pack packs/my-ft
python3 -m studio.cli skills --pack packs/my-ft
python3 -m studio.cli run --pack packs/my-ft --task topis/tasks/01-foundation.yaml --dry-run
```

如果运行 `--fake --no-git`，它会写回卡片和 `work/` 记忆；验证后必须还原
卡片改动并清理 `work/`，不要把运行产物提交进仓库。

## 8. 文档同步规则

- 改子包边界、规划阶段、上下文配方、skill 格式、记忆结构时，必须同步
  `docs/studio/architecture.md`；
- 改任务 YAML 约定时，必须同步 `topis/tasks/README.md`；
- 改长期蓝图时，必须同步 `docs/framework/README.md` 的阅读顺序或里程碑；
- 新增规则后同步 `.cursor/rules/studio-agent.mdc` 的摘要。
