# 本项目 Codex 使用规则

## 启动默认行为

进入本项目或新开对话时，只读取本文件即可，不要主动扫描项目、不要读取目录树、不要展开 `14_KB_System/index/knowledge_index.json`、不要读取 `数据/`、`00_Inbox/`、`10_Knowledge/candidates/generated_assets/`、`00_System/runtime/` 或其他大文件。

除非用户给出明确任务，默认停在等待状态。可以只说明“已进入知识库项目，等待下一步指令”，不要为了预热上下文而读多个知识文件。

## 知识库入口

优先使用本仓库维护的中文 Skill 源包：`14_KB_System/skill_packages/知识库/`。兼容入口为 `14_KB_System/skill_packages/knowledge-base/`。

当用户在本项目中输入 `使用知识库`、`调用知识库`、`读取知识库`，或要求基于本机知识库工作时，按 `14_KB_System/config/skill_contract.json` 生成的 Skill 包执行固定入口读取顺序，再按 `14_KB_System/index/controller_routes.json` 路由到对应任务。

规则权威源见 `14_KB_System/rules/规则权威源.md`。本文件不再维护另一份任务读取清单，避免与机器路由和 Skill 契约不同步。

## 硬规则

- 原始文件不删除、不修改。
- `数据/` 和 `00_Inbox/` 中的原始资料只读处理。
- 默认按 `14_KB_System/index/` 索引按需调用，禁止全盘扫库；除非用户明确要求，不展开扫描 `数据/`。
- `00_System/runtime/` 是运行产物区，默认不读；只有候选审核、检索报告、状态检查等任务才读取。
- 新增正式子库前必须先向用户确认。
- 修改 active Skill 前必须先进入 proposal，用户确认后再生效。
- 无效信息、重复信息、低价值资料不进入正式知识库。

## Feishu / Lark CLI

When the user asks about Feishu, Lark, 飞书, 飞书文档, 飞书表格, 云文档, 云空间, docs, drive, sheets, document search, spreadsheet read/write, or similar tasks:

- Prefer the local Feishu CLI/API path over browser scraping. The command is exactly `/Users/lao_wu/.local/bin/lark-cli`; do not guess `cli`, `fli`, `lark`, or `feishu`.
- Start with a quick health check when useful: `/Users/lao_wu/.local/bin/lark-cli auth status --verify` or `/Users/lao_wu/.local/bin/lark-cli doctor`.
- Use browser or Chrome only for visual inspection, screenshots, and visible-page interactions; do not rely on browser text extraction for complete Feishu document or spreadsheet data.
- For Feishu official network calls, request sandbox escalation when needed and state that the call is to official Feishu/Lark domains such as `open.feishu.cn`, `accounts.feishu.cn`, or `mcp.feishu.cn`.
- Never write App Secret, access tokens, refresh tokens, or other credentials into repo files, skills, prompts, or notes.
- Do not use non-official mirrors or third-party download sources for Feishu tooling unless the user explicitly approves after risk is explained.
- Before writing to Feishu documents or sheets, inspect/read the target and intended range first, then write, then read back to verify.
