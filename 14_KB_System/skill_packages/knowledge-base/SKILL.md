---
name: knowledge-base
description: Use the local Markdown knowledge base at /Users/lao_wu/codexAI/知识库. Route through indexes first and avoid raw protected data by default.
---

# Knowledge Base

Start with the fixed entry files generated from `skill_contract.json`:

- `/Users/lao_wu/codexAI/知识库/知识库入口.md`
- `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`

Do not scan the whole knowledge base by default. Do not read protected directories by default: `数据/`, `00_Inbox/`, `99_Archive/`, `14_KB_System/runtime/`.

Use `/Users/lao_wu/codexAI/知识库/14_KB_System/index/controller_routes.json` for routing. The agents listed there are logical AI roles, not independent processes or permission boundaries.

For candidate retrieval, use `search-candidates`; if it returns `requires_init`, stop and ask for `kb init` instead of reading legacy assets.
