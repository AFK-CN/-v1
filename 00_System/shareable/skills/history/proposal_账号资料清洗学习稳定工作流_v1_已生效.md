# 账号资料清洗学习稳定工作流 v1 提案

```yaml
skill_name: 账号资料清洗学习稳定工作流
version: v1
status: active_via_system_rule
created_at: 2026-06-28
trigger: 用户确认“没必要分这么多智能体，都去掉智能体，因为实际都是 Codex 在做”
evidence:
  - 本次小森林的小世界学习实际由主 Codex 调用本地代码完成。
  - 之前把动作绑定到多个智能体会制造概念负担，实际执行并不会更稳定。
  - 用户真正需要的是稳定工作流、阶段门、代码执行、验收报告和少依赖人工推进。
current_problem: 当前资料清洗和账号学习容易变成用户一步步催促，缺少从资料接入到正式入库的稳定阶段控制。
proposed_behavior: 去掉多智能体概念，改成“主 Codex + 本地脚本 + 阶段门 + 验收面”的单执行工作流。
what_will_change:
  - 不再把账号学习拆成多个智能体。
  - 工作流只保留阶段、动作、工具、产物、验收条件、阻塞条件。
  - 后续回答不再说“调用某某智能体”，而是说明“执行到哪个阶段、跑了哪些代码、验收结果是什么”。
  - 每次资料清洗/学习/入库生成 workflow_trace，记录阶段进度和产物位置。
risk: 如果未来真的需要并行子任务，需要单独明确“启用子任务/多线程/多智能体”，不能默认套入本流程。
rollback_plan: 不确认本提案即不生效；如已生效，恢复旧 controller_routes 中 agent 字段和说明即可。
needs_user_confirmation: false
activated_by: 用户确认实施系统级清洁计划
active_rule: 00_System/shareable/rules/账号学习标准工作流.md
```

## 触发原因

用户已经明确：当前工作其实都是 Codex 和本地代码在做，没有必要人为拆成多个智能体。继续保留“学习智能体、清洗智能体、审计智能体”等称呼，会让系统看起来复杂，但不会让执行更可靠。

因此本提案把关注点从“谁是智能体”改成“工作流是否稳定”。

## 新规则

1. 账号资料清洗、学习、入库默认由主 Codex 执行，不再声明调用多个智能体。
2. 稳定性由阶段门保证，不由智能体名称保证。
3. 每个阶段必须有：
   - 输入
   - 执行动作
   - 本地工具
   - 输出产物
   - 验收条件
   - 阻塞条件
4. 每次任务需要生成或更新工作流回执，说明执行到哪一步。
5. 用户问“是否调用智能体”时，默认回答：没有独立智能体，只有主 Codex 按阶段工作流执行。
6. 只有用户明确要求“启用子任务/多智能体/并行代理”时，才考虑真实多智能体工具。

## 稳定工作流拆分

### 0. 立项与边界

目的：确认任务是不是资料清洗、账号学习、深度学习、正式入库或 NAS 备份。

输入：

- 账号名或资料范围
- 数据来源
- 目标阶段
- 是否允许正式入库
- 是否需要 NAS 备份

执行动作：

- 确认项目规则和禁止目录。
- 确认本次是否需要读取原始数据。
- 建立 workflow_id。

产物：

- `00_System/runtime/workflows/{workflow_id}/workflow_plan.json`
- `00_System/runtime/workflows/{workflow_id}/workflow_trace.json`

验收：

- 账号、来源、目标阶段、读写边界明确。
- 未默认全盘扫库。

### 1. 资料接入与清洗

目的：把原始资料变成候选摘要，而不是直接变成正式知识。

输入：

- SQLite、JSON、CSV、截图、飞书表格或其他资料来源。

执行动作：

- 字段识别。
- 去重统计。
- 噪音判断。
- 账号匹配。
- 生成候选摘要。

工具：

- `tools.kb.cli sqlite-ingest`
- `tools.sqlite_ingest`
- JSON/表格清洗脚本

产物：

- `00_Inbox/...` 轻量候选摘要
- `10_Knowledge/candidates/account_assets/...` 账号候选入口
- `00_System/runtime/...` 清洗报告

验收：

- 原始资料只读。
- 有字段统计、去重统计、失败项。
- 输出是候选，不是正式知识。

### 2. 选题粗扫

目的：完成全量方向归类、发布内容层粗学和选题池，不靠人工逐条推进。此阶段通常还没下载视频，不学习逐字稿、抽帧或分镜。

执行动作：

- 内容方向归类。
- 价值排序。
- 学习发布内容层：标题、正文/文案、话题/标签和内容结构协同。
- 待复核识别。
- 生成深度学习范围。

工具：

- `tools.content_rough_scan`
- `tools.video_learning scan/select`

产物：

- `10_Knowledge/candidates/account_assets/content_rough_scan/{profile}/`
- `deep_learning_scope.json`
- `validation_report.json`

验收：

- 粗学范围清楚。
- 粗学只覆盖发布内容层，不把未下载的视频内容层写成已学习。
- scope_count 与计划一致。
- 待复核项明确列出。
- 不偷懒、不私自限制总条数。
- 评论正文不进入学习；评论数只作为平台互动指标。

### 3. 学习计划

目的：把粗扫结果拆成可执行计划。

执行动作：

- 区分视频、图文、元数据内容。
- 生成下载计划。
- 生成深度学习计划。
- 标注排除项和原因。

产物：

- `10_Knowledge/candidates/review_registers/plans/{profile}_*.json`
- `90_Temp/scratch/video_learning/queues/*.json`

验收：

- 计划总数、视频数、图文数、排除数清楚。
- 不把“够 10 条”误当成总量限制。

### 4. 媒体下载与证据补齐

目的：把视频、图片、文案、话题等证据拉齐。

执行动作：

- 下载视频。
- 下载或登记图片证据。
- 抽取标题、文案、话题。
- 校验平台前缀，例如小红书 `xhs_`，抖音 `douyin_`。

工具：

- `tools.video_learning download`
- `ffprobe`
- 媒体校验脚本

产物：

- `00_System/runtime/cache/video_learning/video_artifacts/{platform}_{source_id}/`
- `00_System/runtime/cache/video_learning/image_artifacts/{platform}_{source_id}/`
- 下载报告

验收：

- 成功、失败、复用、缺失都清楚。
- 本地文件有效性通过。
- 不能只看下载命令退出码。

### 5. 深度学习

目的：一条发布资产形成一张完整学习卡；完整学习包括发布内容层和视频内容层。视频内容层在下载后学习逐字稿、抽帧/分镜和视频层表达，图文/元数据内容学习标题、正文/文案、话题和图片边界。

执行动作：

- 生成 selected card。
- 生成 learned card。
- 视频转音频。
- 生成逐字稿。
- 生成分镜。
- 图文内容保留标题、文案、话题、图片边界。

工具：

- `tools.video_learning learn`

产物：

- `10_Knowledge/candidates/learning_cards/selected_deep_cards/`
- `10_Knowledge/candidates/learning_cards/learned_cards/{profile}/`
- `00_System/runtime/cache/video_learning/video_artifacts/`

验收：

- 学习卡数量等于 scope。
- 视频处理链路有效。
- 图文内容没有被错误排除。
- 每张学习卡完整学习账号发布资产整体：发布内容层 + 视频内容层；缺失任何一层都要在卡片和审计报告中标注。

### 6. 机器审计

目的：用代码验收是否偷懒、重复、不准确、不全面。

执行动作：

- 检查缺失卡片。
- 检查结构风险。
- 检查证据风险。
- 检查发布内容层风险：标题、正文/文案、话题/标签、内容结构协同是否被学习。
- 检查视频内容层风险：逐字稿、抽帧/分镜、视频层表达是否存在并被正确学习。
- 检查高相似。
- 检查重复段落。
- 汇总待复核项。

工具：

- `tools.video_learning_audit`

产物：

- `machine_audit.json`
- `machine_audit.md`
- `similarity_pairs.json`
- `repeated_passages.json`

验收：

- 缺失为 0。
- 待复核项处理完或明确阻塞。
- 审计报告必须包含 `publish_content_layer_risks` 和 `video_content_layer_risks`。
- 高相似和重复段落有结论。

### 7. 正式入库预览

目的：正式写入主库前先预览数量。

执行动作：

- dry-run。
- 对齐方向数、卡片数、逐字稿数。
- 检查平台证据目录。

工具：

- `tools.video_learning_account_ingest --dry-run`

验收：

- dry-run 数量与审计数量一致。
- 小红书使用 `xhs_` 证据目录。
- 抖音使用 `douyin_` 证据目录。

### 8. 正式入库

目的：写入正式账号中心。

执行动作：

- 写入账号索引。
- 写入账号方法论总览。
- 写入账号整体方法论。
- 写入内容生产说明。
- 写入内容输出模板。
- 写入方向方法论、单卡、逐字稿。
- 更新全局账号索引。
- 清理候选态残留词。

工具：

- `tools.video_learning_account_ingest`
- 系统验证工具

产物：

- `10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/{账号}/`
- `10_Knowledge/evidence/index/account_knowledge_index.md`
- `10_Knowledge/evidence/index/account_knowledge_index.json`

验收：

- 正式卡片数、逐字稿数、方向数对齐。
- 状态词清零。
- 全局账号索引命中。
- `validate-system` 通过。
- 账号级产物只记录本账号规律；除非用户明确要求对比，不写入其他账号名称或“不同于某账号”的表达。

### 9. NAS 备份

目的：把本机正式文件和必要证据备份到 NAS 指定目录。

执行动作：

- 检查 NAS 是否挂载。
- 写入备份。
- 生成备份清单。
- 回读校验。

产物：

- `/Volumes/AFK/zhishikushuju/{账号或profile}/`
- `_backup_manifest.json`
- `_latest_report.md`

验收：

- NAS 路径存在且可写。
- 有备份清单。
- 回读数量一致。
- NAS 不替代本地主库。

### 10. 交接和记忆候选

目的：让下次能接着跑，不靠用户复述。

执行动作：

- 生成工作流结果摘要。
- 判断是否值得记忆候选。
- 只写 pending，不直接写长期记忆。

工具：

- `tools.kb.cli memory --evaluate-text`

产物：

- `00_System/runtime/memory/pending_session_extracts.jsonl`
- workflow 结果摘要

验收：

- 可复用规则进入 pending。
- 不写敏感信息。

## 应同步修改的生效面

用户确认后，建议修改：

1. `00_System/shareable/index/controller_routes.json`
   - 去掉 `agent_model`、`agent_model_notice`、`agents` 和各 route 的 `agents` 字段。
   - 改成 `workflow_model: staged_single_executor`。
   - 账号学习 route 增加 `workflow_contract: account_material_cleaning_learning`。
2. `00_System/shareable/index/task_entry_index.md`
   - 将“智能体”表述改成“阶段工作流”。
3. `00_System/shareable/config/output_contracts.json`
   - 账号学习输出契约增加 `workflow_id`、`stage_statuses`、`acceptance_results`。
4. `00_System/shareable/agents/agent_capability_rules.md`
   - 标记为历史说明或改成“当前不使用多智能体，除非用户明确要求”。
5. 新增或迁移机器契约：
   - `00_System/shareable/config/workflow_contracts.json`

## 验证用例

1. 用户说“学习某账号”：系统先输出阶段计划，不再说启动哪个智能体。
2. 用户说“继续下一步”：系统根据 workflow_trace 判断下一阶段。
3. 用户问“有没有调用智能体”：系统回答没有独立智能体，按主 Codex 阶段工作流执行。
4. 正式入库前：必须有审计和 dry-run。
5. NAS 未挂载：必须明确阻塞备份。

## 回滚方式

不确认本提案即不生效。若已生效后需要回滚：

1. 恢复 controller_routes 中的 agents 字段。
2. 移除 `workflow_contracts.json` 的强制阶段契约。
3. 保留历史 workflow_trace 作为运行记录。
