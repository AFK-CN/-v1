---
name: knowledge-base
description: Use when the user says 使用知识库、调用知识库、读取知识库、@知识库, or asks to use the local Markdown knowledge base at /Users/lao_wu/codexAI/知识库. This skill routes through the index first, avoids full-library scans by default, and blocks default reads of 数据/, 00_Inbox/, 99_Archive/, and unapproved proposals.
---

# Knowledge Base

Use this skill as the stable entrypoint for `/Users/lao_wu/codexAI/知识库`.

## Start Here

Read only these files first:

1. `/Users/lao_wu/codexAI/知识库/知识库入口.md`
2. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`
3. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/knowledge_index.json`

Then read only the small set of files required by the user's task.

## Hard Rules

- Do not scan the whole knowledge base unless the user explicitly asks.
- Do not read or expand `/Users/lao_wu/codexAI/知识库/数据/` by default.
- Treat `/Users/lao_wu/codexAI/知识库/14_KB_System/assets/` as candidate assets, not formal knowledge.
- Formal knowledge lives in `02_Viral_Methods/`, `03_Topic_Ideas/`, `04_Platform_Knowledge/`, `06_Sub_KB/`, `08_Content_Factory/`, and `13_Evolving_Skills/`.
- Active Skill changes must first be proposed; do not directly edit active skills.

For detailed routing and examples, read `references/calling-rules.md` only when the task needs more than the quick entry above.
