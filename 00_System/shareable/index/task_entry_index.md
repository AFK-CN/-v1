# 任务入口索引

## 固定总控

- 先读 `知识库入口.md`，再由 `00_System/shareable/index/controller_routes.json` 命中路由。
- 默认入口：`@知识库 + 需求`；兼容入口：`knowledge-base + 需求`。
- `00_System/runtime/`、`20_User/data/`、`20_User/feedback/`、`20_User/private/`、`20_User/local/` 和 `数据/` 默认阻断。

## 内容处理

- 读取 `00_System/shareable/skills/active/content-processing/SKILL.md`。
- 负责接入、下载、解析、转写、OCR、抽帧、清洗、扫描、粗学归类和深学计划。
- 只写候选证据与运行产物，不写正式账号中心。

## 账号学习

- 读取 `00_System/shareable/skills/active/account-learning/SKILL.md` 和 `account_learning_pipeline.json`。
- 剧情、长文案、视频和图文使用同一七阶段主流程与不同观察适配器。
- 阶段 6 生成不可调用的账号 Skill 候选包；用户审核后才写账号中心。
- 用户审核、正式写入和用户层注册验证通过后，按每账号整体 10–20 条、每个正式方向 1–5 条组建轻量数据源；每条保留完整产出物、manifest 与哈希，供 NAS 断开时查看和复查。

## 账号 Skill 生产

- 先读取 `20_User/config/account_skill_registry.json` 解析唯一账号 Skill。
- 只读取该账号 `skill/SKILL.md`；参考文件由 Skill 按需加载，不批量读取旧账号根目录文档。
- 出选题前调用 `topic-memory-check`；确认后记录 `topic_id`；交付后记录 `content_id` 与 Skill 版本。
- 代码只返回生产记忆的少量冲突摘要，模型不读取完整数据库。

## 内容复盘

- 读取 `00_System/shareable/skills/active/content-review/SKILL.md`。
- 以 `content_id` 绑定截图、表格、平台数据或人工反馈。
- 输出继续观察、调整生产、定向补学或账号 Skill 更新提案，不自动进化。

## 用户层

- 新电脑运行 `user-init`；日常可运行 `user-validate` 和 `account-skills-sync`。
- 系统定义结构，用户层保存本机注册、生产记忆、反馈、私有数据和机器配置。

## 正式知识检索

- 运行 `search-formal`，使用 BM25、本地字符向量、严格元数据过滤和重排。
- 只索引 `10_Knowledge/formal/`；候选、原始资料、系统层、用户层、临时层和归档层不进入缓存。
- 只返回短摘要、分项得分和 `path:Lx-Ly` 证据坐标；缓存陈旧时先运行 `formal-search-index`。

## 其他项目调用

- 读取：`00_System/shareable/docs/project_use/项目调用规则.md`。
- 默认禁止调用原始资料、用户数据、用户反馈、本机配置、runtime 和未确认候选。
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

## 系统审计

- 日常调用先运行 `.venv/bin/python -m tools.kb.cli --root . health-gate`；该命令禁止遍历正式知识文件。
- 新机器、runtime/凭证缺失、schema 不匹配或旧目录待迁移时运行 `kb init`。
- 目标分层目录缺失时运行 `.venv/bin/python -m tools.kb.cli --root . init-layers`。
- 读取：`00_System/shareable/index/controller_routes.json`、`10_Knowledge/evidence/index/knowledge_index_summary.md`、`10_Knowledge/evidence/index/account_knowledge_index.json`、`00_System/shareable/config/output_contracts.json`。
- `10_Knowledge/evidence/index/knowledge_index.json` 是全量机器索引，只在脚本验证、全量审计或用户明确要求时读取。
- 运行：`.venv/bin/python -m tools.kb.cli --root . validate-system` 或 `.venv/bin/python -m tools.kb.cli --root . dashboard`。
- 分享前运行 `distribution-audit`；需要独立系统包时运行 `system-export --output <目录>`。
- 输出：三套系统 Skill、用户层、账号 Skill、生产记忆、索引、边界、清理和测试状态。
