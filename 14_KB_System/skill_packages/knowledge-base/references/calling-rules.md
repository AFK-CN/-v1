# Knowledge-base calling rules

## Entry order

1. `/Users/lao_wu/codexAI/知识库/知识库入口.md`
2. `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`

## Boundaries

Do not scan the whole knowledge base by default. 默认不读取：

- `数据/`
- `00_Inbox/`
- `99_Archive/`
- `80_Local/`
- `20_User/private/`
- `00_System/runtime/`
- `00_System/runtime/`

## Authority

- Routing: `/Users/lao_wu/codexAI/知识库/14_KB_System/index/controller_routes.json`
- Skill package source: `/Users/lao_wu/codexAI/知识库/14_KB_System/config/skill_contract.json`
- Runtime health/init: `tools.kb.runtime`
