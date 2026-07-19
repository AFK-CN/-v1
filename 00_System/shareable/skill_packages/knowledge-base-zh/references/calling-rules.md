# 知识库调用规则

## Entry order

Resolve `<KB_ROOT>` from the current repository first, then `references/kb-root.json` in the installed Skill, then the `KB_ROOT` environment variable. Stop when none points to a repository containing `00_System/shareable/config/skill_contract.json`.

1. `<KB_ROOT>/知识库入口.md`
2. `<KB_ROOT>/00_System/shareable/index/task_entry_index.md`

## Boundaries

Do not scan the whole knowledge base by default. 默认不读取：

- `数据/`
- `00_Inbox/`
- `99_Archive/`
- `20_User/private/`
- `20_User/data/`
- `20_User/feedback/`
- `20_User/local/`
- `00_System/runtime/`

## Authority

- Routing: `<KB_ROOT>/00_System/shareable/index/controller_routes.json`
- Skill package source: `<KB_ROOT>/00_System/shareable/config/skill_contract.json`
- Full machine index: `<KB_ROOT>/10_Knowledge/evidence/index/knowledge_index.json`
- Runtime health/init: `tools.kb.runtime`
