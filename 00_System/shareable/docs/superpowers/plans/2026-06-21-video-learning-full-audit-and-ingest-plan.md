# 视频学习全量审计与正式入库通用 Implementation Plan

> 执行要求：使用 profile 化工具。审计、报告、注册表和入库门禁是通用机制；账号只通过参数或配置指定。

**Goal:** 对指定 `profile_id` 的视频深度学习内容做全量审计，修复偷懒、雷同、草率和证据问题，将通过内容正式入库，并整体重构账号级调用文件。

**Profile 参数:** 本计划适用于任意 `profile_id`；账号名称、平台、证据目录和正式账号中心目录均由配置传入。

**Architecture:** `tools/video_learning_audit.py` 负责通用审计；账号专用入口只能是兼容 wrapper。入库工具也应 profile 化：通用脚本处理 learned_base、formal_account_dir、account_id/account_name；账号专用脚本只保留默认参数。

**Tech Stack:** Python 3.12 标准库、unittest、Markdown、JSON。

---

### Task 1: 建立通用全量审计器

**Files:**

- Create/Modify: `tools/video_learning_audit.py`
- Modify: 账号专用兼容 wrapper（如需保留旧入口，只传默认 profile 参数）
- Create/Modify: `tests/test_video_learning_audit.py`
- Keep: 账号专用兼容回归测试（只验证旧入口不承载通用规则）

- [x] 编写 profile 配置测试：临时 `demo_profile` 必须写入自己的 audit 目录，不能落到其他账号目录。
- [x] 运行测试确认缺少通用模块时失败。
- [x] 实现 `AuditConfig.for_profile(profile_id)`、通用路径、通用报告标题和通用 CLI。
- [x] 将账号专用审计入口改为只传默认 profile 的兼容入口。
- [x] 运行通用审计测试与旧入口兼容测试。

### Task 2: 通用化入库门禁

**Files:**

- Create/Modify: `tools/video_learning_account_ingest.py`
- Modify: 账号专用入库 wrapper（兼容 wrapper 或 profile 默认配置）
- Create/Modify: `tests/test_video_learning_account_ingest.py`
- Keep: 账号专用入库回归测试（只验证旧入口不承载通用规则）

- [ ] 编写通用 profile 入库测试：临时 profile、临时正式账号目录、两个方向同时入库。
- [ ] 运行测试确认账号专用实现无法替代通用路径。
- [ ] 抽出 `AccountIngestConfig`：`profile_id`、`account_id`、`account_name`、`learned_base`、`formal_account_dir`、`artifacts_dir`、全局账号索引路径。
- [ ] 入库门禁只接受通用审计注册表中 `decision=pass` 的卡。
- [ ] 账号专用入口只传默认配置，不承载通用规则。

### Task 3: 执行 profile 全量机器审计

当前命令：

```bash
.venv/bin/python tools/video_learning_audit.py --root . --profile {profile_id}
```

输出：

- `01_Case_Cleaning/video_learning/learned_cards/{profile_id}/audit/machine_audit.json`
- `machine_audit.md`
- `similarity_pairs.json`
- `repeated_passages.json`

验收：

- scope 条数与卡片条数一致。
- 缺卡列表为空。
- 高相似、重复长句、结构风险、证据风险全部进入报告。

### Task 4: 逐卡人工审计与修复

**Files:**

- Modify: `01_Case_Cleaning/video_learning/learned_cards/{profile_id}/{方向}/cards/*.md`
- Modify: `01_Case_Cleaning/video_learning/learned_cards/{profile_id}/{方向}/方向方法论总结.md`
- Create/Modify: `01_Case_Cleaning/video_learning/learned_cards/{profile_id}/audit/card_audit_register.json`
- Create/Modify: `01_Case_Cleaning/video_learning/learned_cards/{profile_id}/audit/全量深度学习审计报告.md`

- [ ] 对照机器报告、精选卡、逐字稿和原卡逐条判定。
- [ ] `minor_fix` 只修复有证据支持的字段。
- [ ] `relearn` 必须重新读取证据并重写学习卡。
- [ ] `reject` 不入库，登记原因。
- [ ] 复验后注册表中所有待入库卡必须为 `pass`。

### Task 5: 正式入库

入库目标由配置传入：

```text
profile_id = {profile_id}
formal_account_dir = {formal_account_dir}
```

- [ ] 预演入库，确认方向数、卡片数、逐字稿数、未批准卡数。
- [ ] 执行正式入库。
- [ ] 验证方向包：方法论、粗扫、验收报告、回执、存储清单、cards、transcripts。
- [ ] 正式粗扫文件必须转为粗学与选题池，覆盖标题、正文/文案、话题/标签和内容结构协同；评论正文不纳入学习。

### Task 6: 重构账号级总指引与风格规则

**Files:**

- `账号索引.md`
- `账号方法论总览.md`
- `账号整体方法论.md`
- `内容生产使用说明.md`
- `减少AI味输出规则.md`
- `内容输出标准模板.md`
- `14_KB_System/index/account_knowledge_index.md/json`

- [ ] 从正式方向总结提炼账号总主线和方向关系，不机械拼接。
- [ ] 生成账号整体方法论，沉淀账号级总结、跨方向模型、发布资产学习口径和正式方向入口。
- [ ] 按任务类型重构内容生产路由。
- [ ] 基于本账号正式卡、标题、正文/文案、话题和方向总结归纳去 AI 味规则、禁用表达和批量防雷同规则。
- [ ] 重构账号通用输出模板，保留 `source_id`、来源层级、原链接。
- [ ] 除非用户明确要求对比分析，账号级文件不得写入其他账号名称、风格或“不同于某账号”的表述。

### Task 7: 全量终验

- [ ] 跑通用审计测试、兼容测试、卡片校验、入库测试、索引测试。
- [ ] 重建学习与账号索引。
- [ ] 核对正式方向数、卡片数、逐字稿数、回执数、账号整体方法论、方向总结数、粗学与选题池数、索引状态。
- [ ] 执行调用链内容审计：至少覆盖赚钱选题、短视频口播、个人成长方法解释。
- [ ] 写正式入库总验收报告。
