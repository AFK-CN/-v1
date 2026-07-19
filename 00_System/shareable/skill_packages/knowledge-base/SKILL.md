---
name: knowledge-base
description: Use the local Markdown knowledge base from its repository root. Route through indexes first and avoid raw protected data by default.
---

# Knowledge Base

Treat `<KB_ROOT>` as the repository root of this knowledge base. Resolve it in this order: use the current repository when it contains `00_System/shareable/config/skill_contract.json`; otherwise read `references/kb-root.json` from this installed Skill; otherwise use the `KB_ROOT` environment variable. If none resolves to a valid repository, stop and ask for the local knowledge-base root.

Start with the fixed entry files generated from `skill_contract.json`:

- `<KB_ROOT>/知识库入口.md`
- `<KB_ROOT>/00_System/shareable/index/task_entry_index.md`

Do not scan the whole knowledge base by default. Do not read protected directories by default: `数据/`, `00_Inbox/`, `99_Archive/`, `20_User/private/`, `20_User/data/`, `20_User/feedback/`, `20_User/local/`, `00_System/runtime/`.

Use `<KB_ROOT>/00_System/shareable/index/controller_routes.json` for routing. The agents listed there are logical AI roles, not independent processes or permission boundaries.

The portable system has three workflows: `content-processing`, `account-learning`, and `content-review`. Content production resolves an account Skill through `20_User/config/account_skill_registry.json`; local production memory is queried by code and never loaded in full.

For candidate retrieval, use `search-candidates`; if it returns `requires_init`, stop and ask for `kb init` instead of reading legacy assets.
