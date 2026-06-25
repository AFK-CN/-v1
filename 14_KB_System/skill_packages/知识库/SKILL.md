---
name: 知识库
description: 当用户输入 @知识库、使用知识库、调用知识库、读取知识库，或要求使用 /Users/lao_wu/codexAI/知识库 这个本机 Markdown 知识库时使用。该入口先读索引，不默认全盘扫库，不默认读取 数据/、00_Inbox/、99_Archive/ 和未确认提案。
---

# 知识库

这是 `/Users/lao_wu/codexAI/知识库` 的中文快捷入口。

## 默认先读

调用前先运行：

```bash
.venv/bin/python -m tools.kb.cli --root /Users/lao_wu/codexAI/知识库 health-gate
```

`healthy` 时直接读取；`requires_init` 时执行一次 `kb init`；`requires_doctor` 时执行 `kb doctor`，仅 repairable 时执行 `kb repair`。`health-gate` 不是 preflight，禁止遍历正式知识文件，同一 KB root 的凭证当天跨项目共享。

1. `/Users/lao_wu/codexAI/知识库/知识库入口.md`
2. `/Users/lao_wu/codexAI/知识库/14_KB_System/rules/用户操作台.md`
3. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/controller_routes.json`
4. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`
5. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/knowledge_index_summary.md`

然后由总控路由判断任务类型，再只读取少量相关正式知识文件。
`knowledge_index.json` 是全量机器索引，只给脚本、全量审计或用户明确要求时使用。

## 总控智能体

用户只需要说 `@知识库 + 需求`。本 Skill 负责：

1. 识别需求类型。
2. 按 `controller_routes.json` 选择路由。
3. 调度规划器、检索器、工作流执行器、账号知识、内容生成、复盘、Skill 沉淀或审计能力。
4. 输出本次命中的路由、读取的知识层级、正式知识与候选证据边界。

## 禁止默认行为

- 禁止全盘扫库。
- 禁止默认读取 `/Users/lao_wu/codexAI/知识库/数据/`。
- 禁止默认读取 `/Users/lao_wu/codexAI/知识库/00_Inbox/`。
- 禁止默认读取 `/Users/lao_wu/codexAI/知识库/99_Archive/`。
- 禁止把 `14_KB_System/runtime/cache/assets/` 候选资产当作正式知识。
- 禁止把未确认的 proposals 当作已生效规则。
- 禁止内容生成结果直接反写正式知识。
- active Skill 修改必须先进入 `13_Evolving_Skills/proposals/`，用户确认后再生效。

## 账号/主题定向创作

当用户要求“按某账号方式/某主题”生成选题或内容时，先查候选资产，不要只查正式知识后直接回答“没有发现”。

优先使用本地命令：

```bash
.venv/bin/python -m tools.kb.cli --root . search-candidates --account "<账号名>" --query "<主题词>" --limit 10
```

如果候选资产没有命中，且用户明确要求基于原始资料追溯，再加 `--include-raw` 做动态检索。该模式会读取原始记录，但仍只输出候选检索报告，不自动写入正式知识。

如需更细的调用边界，读取 `references/calling-rules.md`。
