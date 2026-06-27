# Knowledge-base calling rules

## Entry order

`<KB_ROOT>` means the repository root of the knowledge base.

1. `<KB_ROOT>/知识库入口.md`
2. `<KB_ROOT>/00_System/shareable/index/task_entry_index.md`

## Boundaries

Do not scan the whole knowledge base by default. 默认不读取：

- `数据/`
- `00_Inbox/`
- `99_Archive/`
- `80_Local/`
- `20_User/private/`
- `00_System/runtime/`

## Authority

- Routing: `<KB_ROOT>/00_System/shareable/index/controller_routes.json`
- Skill package source: `<KB_ROOT>/00_System/shareable/config/skill_contract.json`
- Full machine index: `<KB_ROOT>/10_Knowledge/evidence/index/knowledge_index.json`
- Runtime health/init: `tools.kb.runtime`
