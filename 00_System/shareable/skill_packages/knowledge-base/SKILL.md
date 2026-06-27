---
name: knowledge-base
description: Use the local Markdown knowledge base from its repository root. Route through indexes first and avoid raw protected data by default.
---

# Knowledge Base

Treat `<KB_ROOT>` as the repository root of this knowledge base. Start with the fixed entry files generated from `skill_contract.json`:

- `<KB_ROOT>/知识库入口.md`
- `<KB_ROOT>/00_System/shareable/index/task_entry_index.md`

Do not scan the whole knowledge base by default. Do not read protected directories by default: `数据/`, `00_Inbox/`, `99_Archive/`, `80_Local/`, `20_User/private/`, `00_System/runtime/`.

Use `<KB_ROOT>/00_System/shareable/index/controller_routes.json` for routing. The agents listed there are logical AI roles, not independent processes or permission boundaries.

For candidate retrieval, use `search-candidates`; if it returns `requires_init`, stop and ask for `kb init` instead of reading legacy assets.
