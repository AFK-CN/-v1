# 2026-06-29 系统级清洁报告

## 目标

将知识库从单账号演化痕迹较重的状态，清理为可持续学习任意自媒体账号的标准化系统。

## 已完成

- 账号学习路由已改为通用 profile 化工具，不再把 `tools.jianghushuo_account_ingest` 作为标准入口。
- 新增 `tools.video_learning_card_validator`，支持任意 profile 的学习卡模板校验；旧姜胡说校验命令保留为兼容包装。
- 新增 `account-validate-cards` 和 `account-ingest-direction` CLI 入口，用于新账号学习验收和正式入库。
- 新增 `00_System/shareable/rules/账号学习标准工作流.md`，固化账号学习的阶段门、必要产物和验收条件。
- `视频深度学习Skill_v1.md` 已引用通用阶段门，并明确旧账号专属命令只作为兼容入口。
- `账号资料清洗学习稳定工作流 v1` proposal 已移入 history，并标记为通过系统规则生效。
- 内容创作入口已中性化：方向词只作为账号方向，不再把知识成长、赚钱或某个账号当作通用默认模板。
- 系统说明里的单账号示例已替换为占位符示例。
- 新增 `tools.kb.system_cleaner`，用于迁移旧账号学习路径并审计规则/知识边界。
- `validate-system` 已接入边界审计：通用入口、规则、active Skill、路由和输出契约中不得出现具体账号 token 或候选账号知识路径。
- `candidate_asset_index.json` 已为候选资产增加 `knowledge_layer: candidate_knowledge`，能识别账号目录的条目增加 `account_id`，避免候选账号知识被误当系统规则。
- `deep_learning_scope.json`、学习卡、深卡、审计注册表等候选知识里的旧 `01_Case_Cleaning/video_learning/...` 引用已迁移到当前分层路径。

## 清理结果

- 已删除工作区 `.DS_Store`。
- 已删除 `tools/` 和 `tests/` 下可再生的 `__pycache__`。
- 已删除 `90_Temp/trash_review/ds_store/` 中的临时 `.DS_Store` 清理样本。
- 未删除原始资料、正式知识、候选资产、runtime 报告或历史证据。
- 根目录整理计划当前无可删除项；`.github` 已明确为工程控制目录，不进入清理队列。

## 保留边界

- `content_rough_scan_profiles.json` 中保留姜胡说和小森林 profile，因为它们是已学习账号的配置和回归样例，不是系统默认规则。
- 旧 `jianghushuo-*` 独立脚本文件保留为历史兼容；总控 CLI 不再暴露它们作为系统入口，新账号只使用 `account-*` 通用入口。
- 历史计划和历史 proposal 保留在 history/docs 中，用于追溯，不作为 active 规则。
- `tools/` 和 `tests/` 当前作为物理执行入口保留；它们的逻辑归属属于系统层，但物理迁移需要单独迁移计划。
- 账号知识文件中出现账号名、账号话题、原链接和账号方向是知识层证据，不是系统规则污染；污染判定只针对通用规则、入口、路由、active Skill、输出契约和候选知识路径是否被写成默认规则。

## 验收要求

- `validate-system` 必须通过。
- 新增通用 profile 测试必须通过。
- 账号学习路由不得包含 `tools.jianghushuo_account_ingest`。
- 根目录整理计划不得出现 `delete_candidate`。
- 工作区不得残留 `.DS_Store` 和项目代码缓存。
- `plan-reorg` 不得把 `.github` 标为 `manual_review`。
- `clean-system-boundaries --dry-run` 必须返回 `changed_file_count: 0`、`violations: []`、`legacy_path_references: []`。
- 通用规则层不得命中具体账号 token；`10_Knowledge/candidates/` 中不得残留旧 `01_Case_Cleaning/video_learning/...` 学习资产引用。
