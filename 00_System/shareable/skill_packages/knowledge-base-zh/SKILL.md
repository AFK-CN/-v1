---
name: knowledge-base-zh
description: 使用本机 Markdown 知识库。先走索引和路由，不默认读取原始资料。
---

# 知识库

触发：`@知识库`、`使用知识库`、`调用知识库`、`读取知识库`。

`<KB_ROOT>` 表示当前知识库仓库根目录。按以下顺序解析：当前目录包含 `00_System/shareable/config/skill_contract.json` 时使用当前仓库；否则读取本全局 Skill 的 `references/kb-root.json`；再否则读取环境变量 `KB_ROOT`。都无法定位时停止并询问本机知识库根目录。

固定入口文件来自 `skill_contract.json`：

- `<KB_ROOT>/知识库入口.md`
- `<KB_ROOT>/00_System/shareable/index/task_entry_index.md`

默认禁止全盘扫库；默认不读取受保护目录：`数据/`, `00_Inbox/`, `99_Archive/`, `20_User/private/`, `20_User/data/`, `20_User/feedback/`, `20_User/local/`, `00_System/runtime/`。

路由以 `<KB_ROOT>/00_System/shareable/index/controller_routes.json` 为准。里面的 Agent 是同一次 AI 调用中的逻辑职责，不是独立进程、权限隔离或安全边界。

可迁移系统只包含三条主流程：`content-processing`、`account-learning`、`content-review`。内容生产通过 `20_User/config/account_skill_registry.json` 解析账号 Skill；本机生产记忆由代码查重，不加载完整数据库。

候选检索使用 `search-candidates`；如果返回 `requires_init`，停止并提示先执行 `kb init`，不要回读旧 assets。
