---
name: 知识库
description: 使用本机 Markdown 知识库。先走索引和路由，不默认读取原始资料。
---

# 知识库

触发：`@知识库`、`使用知识库`、`调用知识库`、`读取知识库`。

固定入口文件来自 `skill_contract.json`：

- `/Users/lao_wu/codexAI/知识库/知识库入口.md`
- `/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md`

默认禁止全盘扫库；默认不读取受保护目录：`数据/`, `00_Inbox/`, `99_Archive/`, `14_KB_System/runtime/`。

路由以 `/Users/lao_wu/codexAI/知识库/14_KB_System/index/controller_routes.json` 为准。里面的 Agent 是同一次 AI 调用中的逻辑职责，不是独立进程、权限隔离或安全边界。

候选检索使用 `search-candidates`；如果返回 `requires_init`，停止并提示先执行 `kb init`，不要回读旧 assets。
