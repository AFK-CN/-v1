---
name: 知识库
description: 当用户输入 @知识库、使用知识库、调用知识库、读取知识库，或要求使用 /Users/lao_wu/codexAI/知识库 这个本机 Markdown 知识库时使用。该入口先读索引，不默认全盘扫库，不默认读取 数据/、00_Inbox/、99_Archive/ 和未确认提案。
---

# 知识库

这是 `/Users/lao_wu/codexAI/知识库` 的中文快捷入口。

## 默认先读

1. `/Users/lao_wu/codexAI/知识库/知识库入口.md`
2. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`
3. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/knowledge_index.json`

然后按任务只读取少量相关正式知识文件。

## 禁止默认行为

- 禁止全盘扫库。
- 禁止默认读取 `/Users/lao_wu/codexAI/知识库/数据/`。
- 禁止默认读取 `/Users/lao_wu/codexAI/知识库/00_Inbox/`。
- 禁止默认读取 `/Users/lao_wu/codexAI/知识库/99_Archive/`。
- 禁止把 `14_KB_System/assets/` 候选资产当作正式知识。
- 禁止把未确认的 proposals 当作已生效规则。

如需更细的调用边界，读取 `references/calling-rules.md`。
