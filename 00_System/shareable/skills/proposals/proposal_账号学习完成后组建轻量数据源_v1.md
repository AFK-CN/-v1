# Proposal：账号学习完成后组建轻量数据源 v1

- 状态：`approved_active`
- 提案日期：2026-07-17
- 用户确认：2026-07-17
- 生效日期：2026-07-17
- 影响流程：`account-learning`
- 不改变：七阶段学习、阶段 6 候选态、原始资料只读边界

## 目标

账号学习通过用户审核并写入正式账号中心后，为该账号组建一份可脱离 NAS 查看、复查和证据回溯的轻量数据源。

轻量数据源是学习交付物，不是新的知识层、候选层或原始库。

## 插入位置

保留现有七阶段不变：

1. 阶段 0–5 继续执行学习、验证与压力测试。
2. 阶段 6 只生成不可调用的账号 Skill 候选包。
3. 用户审核通过后，先完成正式账号中心写入和用户层注册。
4. 正式写入验证通过后，执行“轻量数据源组建”后置交付。

不得在用户审核前向正式账号中心写入轻量数据源。

## 选择契约

以单个账号 Skill 为单位：

- 必须覆盖该账号所有正式方向。
- 每个方向先选 1 条，根据总量需要可增加到 2–5 条。
- 单方向最多 5 条。
- 单账号整体保持 10–20 条。
- 方向数已超过 10 时，优先保证全方向各 1 条，不为凑数重复复制。
- 优先选择证据完整、可离线回查且体积较小的条目。
- 若任一正式方向没有可便携源目录，不得声称组建完成，必须报告缺口。

## 单条完整产出物

每条入选内容必须是自包含离线包，至少包含：

- `学习卡.md`：该条正式学习卡的离线副本。
- `完整产出物/`：复制该 `source_id` 的已有源目录树。
- 视频类：源视频、封面、音频、逐字稿、抽帧、视频信息、状态与 manifest。
- 图文类：原图、封面、OCR、视觉分析、组图摘要、状态与 manifest。
- `bundle_manifest.json`：记录账号、方向、`source_id`、来源、文件数、字节数与逐文件 SHA-256。

只排除 `.DS_Store`、`._*` 等操作系统垃圾；不得为减小体积而删掉入选内容的已有产出物。

## 目标目录

```text
10_Knowledge/formal/accounts/{账号}/轻量数据源/
├── README.md
├── manifest.json
└── directions/
    └── {方向}/
        └── {platform}_{source_id}/
            ├── 学习卡.md
            ├── bundle_manifest.json
            └── 完整产出物/
```

## 写入与断网边界

- NAS 和原始资料一律只读，不删除、不改名、不回写。
- 首次组建时，目标目录不存在才直接写入。
- 目标已存在时，默认只运行 dry-run 并输出新旧选择差异；未经明确批准不覆盖。
- NAS 不可用时，保留现有轻量数据源，报告 `nas_unavailable_existing_bundle_preserved`；不删除、不降级、不用候选资产填充。
- 新账号首次学习时若 NAS 不可用，正式账号 Skill 可独立写入，但轻量数据源状态必须标记为 `pending_nas_sync`。
- 不把完整轻量数据源加载进模型上下文；检索与验证由代码批处理。

## 验收门

组建后必须同时满足：

1. 账号数量在 10–20 条之间。
2. 每个正式方向至少 1 条、单方向不超过 5 条。
3. 每条都有正式学习卡、媒体和对应处理产出。
4. 目标目录中不存在指向 NAS 的符号链接。
5. 每个已复制文件的字节数和 SHA-256 验证通过。
6. `README.md` 列出方向、`source_id`、类型、体积和离线学习卡入口。
7. `account-learning` 正式写入结果必须返回轻量数据源状态、内容数、方向数、总体积、manifest 路径和缺口。

## 已生效的权威文件

用户确认后已修改并通过验证：

1. `00_System/shareable/skills/active/account-learning/SKILL.md`
2. `00_System/shareable/skills/active/account-learning/references/offline-lightweight-source.md`
3. `00_System/shareable/config/account_learning_pipeline.json`
4. `00_System/shareable/index/controller_routes.json`
5. `00_System/shareable/config/output_contracts.json`
6. `00_System/shareable/index/task_entry_index.md`
7. `tools/kb/indexer.py`、`tools/kb/validator.py` 与 `tools/account_learning_pipeline.py`
8. `tests/test_account_offline_source.py` 及相关系统验证测试

`tools.account_offline_source` 已作为执行器注册到 `account-learning` 路由和输出契约，并已补齐旧包差异预览与断网状态。

## 生效验证

- Active Skill 结构校验：通过。
- 全量单元与系统测试：208 项通过。
- `validate-system`：通过，系统边界违规为 0，分享层绝对路径为 0。
- `distribution-audit`：可便携，未发现机器路径、秘密文件或账号泄漏。
- 4 个已有账号离线包共 49 条、822,770,591 字节，逐文件大小和 SHA-256 复核通过。
- `闲鱼故事UGC任务` 在 NAS 未连接时按契约写入 `pending_nas_sync` 状态清单，未用候选资产填充。

## 回滚

如果生效后验证失败：

- 回退 active Skill、pipeline、路由和输出契约的本次增量。
- 保留已验证的轻量数据源，不自动删除用户资料。
- 把本提案标记为 `rolled_back`，记录验证失败原因。
