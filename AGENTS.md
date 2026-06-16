# 本项目 Codex 使用规则

## 知识库入口

当用户在本项目中输入 `使用知识库`、`调用知识库`、`读取知识库`，或要求基于本机知识库工作时，先读取：

1. `知识库入口.md`
2. `本机使用速查.md`
3. `README.md`

然后根据任务类型继续读取相关文件：

- JSON 入库：读取 `13_Evolving_Skills/active/JSON入库Skill_v1.md`、`JSON入库清洗规则.md`、`去重规则.md`。
- 截图复盘：读取 `13_Evolving_Skills/active/截图复盘Skill_v1.md`、`09_Performance_Feedback/反馈入库模板.md`。
- 表格复盘：读取 `13_Evolving_Skills/active/表格复盘Skill_v1.md`、`10_Weekly_Review/周复盘模板.md`。
- 内容创作：读取 `02_Viral_Methods/`、`03_Topic_Ideas/`、`04_Platform_Knowledge/`、`08_Content_Factory/`。
- 知识成长/自媒体方向：额外读取 `06_Sub_KB/知识成长自媒体方法论/`。
- 子库判断：读取 `子知识库创建规则.md`、`05_Sub_KB_Candidates/`、`06_Sub_KB/`。

## 硬规则

- 原始文件不删除、不修改。
- `数据/` 和 `00_Inbox/` 中的原始资料只读处理。
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
