# 任务入口索引

## 通用使用

- 先读：`知识库入口.md`、`00_System/shareable/rules/用户操作台.md`、`00_System/shareable/index/controller_routes.json`、`00_System/shareable/rules/本机使用速查.md`。
- 默认入口：`@知识库 + 需求`。兼容入口：`knowledge-base + 需求`。
- 总控优先：先用 `controller_routes.json` 判断任务类型，再按本索引读取少量相关文件。
- 分层权威源：`00_System/shareable/config/layer_map.json`。`00_System/shareable/` 才是可分享系统底座；`00_System/runtime/`、`80_Local/`、`20_User/private/`、`数据/` 默认阻断。

## 内容创作

- 读取：`10_Knowledge/formal/methods/`、`10_Knowledge/formal/topics/`、`10_Knowledge/formal/platforms/`、`10_Knowledge/formal/content_factory/`。
- 当用户提到账号名、对标账号、出选题、写文案、口播或账号风格时，先读取：`10_Knowledge/evidence/index/account_knowledge_index.md`。
- 只有账号索引命中正式账号中心后，才继续读取该账号的 `账号索引.md`、`账号概述.md`、`账号方法论总览.md`、`账号整体方法论.md`、`内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`，再按方向读取 `方向方法论总结.md`、`粗扫内容和选题.md`。
- 图文成品生成是选题确认后的内容生产分支：先输出图文脚本包，用户确认后再按账号图文风格调用 image2 生图；规则见 `00_System/shareable/rules/图文成品生成标准流程.md`。
- `知识成长`、`赚钱`、`护肤`、`生活方式` 等只是可能的账号方向词，不是通用系统默认路由；不得因为某个方向词直接套用单一账号模板。
- 账号中心调用默认禁止全扫候选区；需要证据时再读取正式单卡，需要核查时再读取逐字稿。
- 内容生成不能直接反写正式知识；可沉淀的规则进入复盘或 Skill proposal。

## 账号学习

- 读取：`10_Knowledge/evidence/index/account_knowledge_index.md`、`00_System/shareable/index/controller_routes.json`、`00_System/shareable/skills/active/视频深度学习Skill_v1.md`；图文样本任务还要读取 `00_System/shareable/rules/图文账号学习标准工作流.md`。
- 工作流分两大阶段：学习阶段、生产复盘阶段。学习阶段包含粗学与深学计划、深度学习总结、综合入库；生产复盘阶段包含内容生产、反馈复盘、针对性强化。
- 媒介分支：视频学习走 `scan -> select -> learn -> status`；图文学习从统一入口 `tools.kb.cli image-text-*` 走 `ingest -> structure -> scan -> select -> learn -> status`，结构化结果先进入候选资产和审核清单。
- 粗学完成必须有 `账号概述.md`、`粗学与选题池.md`、`deep_learning_plan.json`；缺任何一个都要提醒用户，不宣布完成。
- 脚本只能生成候选资产、学习卡、报告和状态；候选资产目标层是 `10_Knowledge/candidates/`，正式账号知识必须经过审核。
- 阶段 1 在现有学习卡上派生结构机制与表达指纹观察，不给单卡增加强制字段；阶段 2 经多卡聚合和 V1/V2/V3 后，阶段 6 才生成候选态 `ACCOUNT_PRODUCTION_HANDOFF.json`，映射账号结构库、表达指纹、反 AI 规则、内容模板和验收项。
- 默认使用通用 profile 化工具；旧账号专属命令只作为兼容入口，不作为新账号学习标准。

## 复盘和自我学习

- 读取：`00_System/shareable/rules/周复盘规则.md`、`10_Knowledge/formal/reviews/`、`20_User/syncable/`。
- Skill 更新只能写入系统级 proposal：`00_System/shareable/skills/proposals/`。
- 当用户说“以后都这样”“沉淀成规则”“更新 Skill”时，进入 Skill 沉淀路由，只生成 proposal，不直接改 active。

## 其他项目调用

- 读取：`00_System/shareable/docs/project_use/项目调用规则.md`。
- 默认禁止调用：`00_Inbox/`、`数据/`、`99_Archive/`、`80_Local/`、`20_User/private/`、runtime、未确认 Skill 提案。
- 其他项目优先调用全局 `@知识库` Skill；若入口失效，回退到读取 `知识库入口.md`。

## 代码批处理

- 读取 runtime tasks、reports、logs。旧路径兼容：`00_System/runtime/`。
- 代码只能生成候选资产和报告，不能直接写正式知识。

## 博主数据导出

- 触发：`导出{博主}内容`、`导出博主数据到飞书`、`返回飞书链接`、`导出评论`。
- 运行：`.venv/bin/python -m tools.kb.cli --root . export-creator-db --creator "{博主名}" --to-feishu --public-share`。
- 可选：不导出评论时加 `--no-comments`；指定平台时加 `--platform douyin/xhs/weibo/bilibili/kuaishou/tieba/zhihu`。
- 边界：`数据/sqlite_tables.db` 只读；只写 `90_Temp/exports/creator_db/` 导出文件和用户明确要求创建的飞书表格。
- 输出：飞书链接、内容数量、评论数量、分享权限读回状态、本地 manifest 路径；脚本返回前不需要实时陪跑。

## 知识图谱

- 触发：`看知识图谱`、`看系统关系`、`查账号关系`、`查学习流程`、`图谱查询`。
- 读取：`00_System/shareable/config/graph_sources.json`、`00_System/shareable/config/graph_views.json`、`00_System/shareable/rules/知识图谱构建与调用规则.md`。
- 构建：`.venv/bin/python -m tools.kb.cli --root . graph build`；状态：`.venv/bin/python -m tools.kb.cli --root . graph status`。
- 查询：`.venv/bin/python -m tools.kb.cli --root . graph query "问题" --view system/knowledge/accounts/workflows/cross_layer`。
- 本地 Web：`.venv/bin/python -m tools.kb.cli --root . graph web`，默认地址 `http://127.0.0.1:8790`。
- 边界：正式知识从索引取清单；候选层只显示汇总；原始、私有、归档、临时和 runtime 不进入输入。

## 系统审计

- 日常调用先运行 `.venv/bin/python -m tools.kb.cli --root . health-gate`；该命令禁止遍历正式知识文件。
- 新机器、runtime/凭证缺失、schema 不匹配或旧目录待迁移时运行 `kb init`。
- 目标分层目录缺失时运行 `.venv/bin/python -m tools.kb.cli --root . init-layers`。
- 读取：`00_System/shareable/index/controller_routes.json`、`10_Knowledge/evidence/index/knowledge_index_summary.md`、`10_Knowledge/evidence/index/account_knowledge_index.json`、`00_System/shareable/config/output_contracts.json`。
- `10_Knowledge/evidence/index/knowledge_index.json` 是全量机器索引，只在脚本验证、全量审计或用户明确要求时读取。
- 运行：`.venv/bin/python -m tools.kb.cli --root . validate-system` 或 `.venv/bin/python -m tools.kb.cli --root . dashboard`。
- 输出：入口、索引、路由、Skill 包、账号中心、proposal、候选注册表、输出契约和报告状态。
