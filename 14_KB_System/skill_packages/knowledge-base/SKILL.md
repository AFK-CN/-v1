---
name: knowledge-base
description: Use when the user says 使用知识库、调用知识库、读取知识库、@知识库, or asks to use the local Markdown knowledge base at /Users/lao_wu/codexAI/知识库. This skill routes through the index first, avoids full-library scans by default, and blocks default reads of 数据/, 00_Inbox/, 99_Archive/, and unapproved proposals.
---

# Knowledge Base

Use this skill as the stable entrypoint for `/Users/lao_wu/codexAI/知识库`.

## Start Here

Read only these files first:

1. `/Users/lao_wu/codexAI/知识库/知识库入口.md`
2. `/Users/lao_wu/codexAI/知识库/14_KB_System/rules/用户操作台.md`
3. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/controller_routes.json`
4. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`
5. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/knowledge_index_summary.md`

Then use the controller route table to classify the user's task and read only the small set of files required by that route.
`knowledge_index.json` is the full machine index for scripts, full audits, or explicit user requests only.

## Controller Behavior

The user should only need `@知识库` or `knowledge-base` plus the request. This skill acts as the controller:

1. Classify the task.
2. Select the route from `controller_routes.json`.
3. Dispatch planning, retrieval, workflow execution, account learning, content generation, review, Skill evolution, or audit behavior.
4. Report the matched route, knowledge layers used, and whether each source is formal knowledge or candidate evidence.

## Hard Rules

- Do not scan the whole knowledge base unless the user explicitly asks.
- Do not read or expand `/Users/lao_wu/codexAI/知识库/数据/` by default.
- Treat `/Users/lao_wu/codexAI/知识库/14_KB_System/assets/` as candidate assets, not formal knowledge.
- Formal knowledge lives in `02_Viral_Methods/`, `03_Topic_Ideas/`, `04_Platform_Knowledge/`, `06_Sub_KB/`, `08_Content_Factory/`, and `13_Evolving_Skills/`.
- Active Skill changes must first be proposed; do not directly edit active skills.
- Content generation outputs must not be written back into formal knowledge directly.
- Skill evolution writes proposals first; active changes require user confirmation.

## Account Or Topic Specific Requests

When the user asks for content in the style of a specific account or on a specific topic, search candidate assets before saying the knowledge base has no evidence:

```bash
.venv/bin/python -m tools.kb.cli --root . search-candidates --account "<account>" --query "<topic>" --limit 10
```

Use `--include-raw` only when the user explicitly wants to trace the original records.

For detailed routing and examples, read `references/calling-rules.md` only when the task needs more than the quick entry above.
