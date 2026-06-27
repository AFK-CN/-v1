# 任务入口索引

## 通用使用

- 先读：`知识库入口.md`、`14_KB_System/rules/用户操作台.md`、`14_KB_System/index/controller_routes.json`、`14_KB_System/rules/本机使用速查.md`。
- 默认入口：`@知识库 + 需求`。兼容入口：`knowledge-base + 需求`。
- 总控优先：先用 `controller_routes.json` 判断任务类型，再按本索引读取少量相关文件。
- 分层权威源：`14_KB_System/config/layer_map.json`。`00_System/shareable/` 才是可分享系统底座；`00_System/runtime/`、`80_Local/`、`20_User/private/`、`数据/` 默认阻断。

## 内容创作

- 读取：`10_Knowledge/formal/methods/`、`10_Knowledge/formal/topics/`、`10_Knowledge/formal/platforms/`、`10_Knowledge/formal/content_factory/`。
- 知识成长/自媒体方向额外读取：`10_Knowledge/formal/accounts/知识成长自媒体方法论/`。
- 当用户提到账号名、知识成长、自媒体、赚钱方向、出选题、写文案、口播、对标账号时，先读取：`14_KB_System/index/account_knowledge_index.md`。
- 如命中账号中心，例如姜胡说，继续读取：`10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/{账号}/账号索引.md`、`内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`，再按方向读取 `方向方法论总结.md`、`粗扫内容和选题.md`。
- 账号中心调用默认禁止全扫候选区；需要证据时再读取正式单卡，需要核查时再读取逐字稿。
- 内容生成不能直接反写正式知识；可沉淀的规则进入复盘或 Skill proposal。

## 账号学习

- 读取：`14_KB_System/index/account_knowledge_index.md`、`14_KB_System/index/controller_routes.json`、`00_System/shareable/skills/active/视频深度学习Skill_v1.md`。
- SQLite 总库接入：`数据/sqlite_tables.db` 仍是受保护原始资料；先运行 `tools.kb.cli sqlite-ingest --dry-run/--apply` 生成增量候选摘要和轻量索引，再进入账号学习流程。
- SQLite 账号候选入口：`10_Knowledge/candidates/account_assets/sqlite_imports/latest_account_candidates.md`；评论暂不进入学习流程。
- 工作流：粗扫 -> 深度学习 -> 候选卡 -> 审核 -> 用户确认 -> 正式账号中心。
- 脚本只能生成候选资产、学习卡、报告和状态；候选资产目标层是 `10_Knowledge/candidates/`，正式账号知识必须经过审核。

## 复盘和自我学习

- 读取：`14_KB_System/rules/周复盘规则.md`、`10_Knowledge/formal/reviews/`、`20_User/syncable/`。
- Skill 更新只能写入系统级 proposal：`00_System/shareable/skills/proposals/`。
- 当用户说“以后都这样”“沉淀成规则”“更新 Skill”时，进入 Skill 沉淀路由，只生成 proposal，不直接改 active。

## 其他项目调用

- 读取：`00_System/shareable/docs/project_use/项目调用规则.md`。
- 默认禁止调用：`00_Inbox/`、`数据/`、`99_Archive/`、`80_Local/`、`20_User/private/`、runtime、未确认 Skill 提案。
- 其他项目优先调用全局 `@知识库` Skill；若入口失效，回退到读取 `知识库入口.md`。

## 代码批处理

- 读取 runtime tasks、reports、logs。旧路径兼容：`00_System/runtime/`。
- SQLite ingest 读取 `数据/sqlite_tables.db` 时只能生成 `00_Inbox/sqlite_imports/` 候选摘要、`00_System/runtime/state/sqlite_ingest/` 状态和 `14_KB_System/index/sqlite_*` 轻量索引；禁止把数据库完整镜像到 Inbox。
- 代码只能生成候选资产和报告，不能直接写正式知识。

## 系统审计

- 日常调用先运行 `.venv/bin/python -m tools.kb.cli --root . health-gate`；该命令禁止遍历正式知识文件。
- 新机器、runtime/凭证缺失、schema 不匹配或旧目录待迁移时运行 `kb init`。
- 目标分层目录缺失时运行 `.venv/bin/python -m tools.kb.cli --root . init-layers`。
- 读取：`14_KB_System/index/controller_routes.json`、`14_KB_System/index/knowledge_index_summary.md`、`14_KB_System/index/account_knowledge_index.json`、`14_KB_System/config/output_contracts.json`。
- `14_KB_System/index/knowledge_index.json` 是全量机器索引，只在脚本验证、全量审计或用户明确要求时读取。
- 运行：`.venv/bin/python -m tools.kb.cli --root . validate-system` 或 `.venv/bin/python -m tools.kb.cli --root . dashboard`。
- 输出：入口、索引、路由、Skill 包、账号中心、proposal、候选注册表、输出契约和报告状态。
