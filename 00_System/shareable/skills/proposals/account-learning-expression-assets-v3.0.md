---
skill_name: account-learning
version: "3.0"
status: proposal
created_at: "2026-07-19"
trigger: "系统升级 3.0 吸收外部知识资产仓库中的钩子、金句、开场/结尾动作、痛点、反例和改编模板结构，但用户要求只优化系统、不得直接启动账号学习或污染账号。"
evidence: "外部仓库的资产分类和先小样本后全量流程具有可复用价值；现有知识库已有候选/正式分层、账号隔离、跨卡验证、压力测试和用户确认门，可补足外部方案缺少 schema、校验器、状态机、性能证据边界与回滚的问题。"
current_problem: "当前账号学习能生成方法和生产交接，但没有统一表达资产候选契约；若直接复制外部提示词或具体话术，会把账号内容混入系统规则，也可能把主观结构评分误写成传播效果。"
proposed_behavior: "在 active account-learning 的阶段 1 只提名表达资产，在阶段 6 生成同账号、不可调用的表达资产候选；执行审计、最多 20 条小样本、检索相关性、溯源、抽象质量、改编质量、风险和账号隔离验收。跨卡验证、压力测试、用户确认、回归和回滚齐备前不得进入 approved_callable。"
what_will_change: "用户确认后才升级 active account-learning 到 v3.0，新增 expression-asset-learning 参考并接入 account_learning_pipeline；当前已落地的 expression_asset_contract.json 和校验器继续作为通用 schema，不含账号内容。"
risk: "可能复制账号原句、跨账号补正例、把用户认可等同账号规律、把拒绝产物用于生成、把结构评分冒充效果或让候选提前可调用。通过字段分离、同账号 source 校验、validation_only、callable=false、method_evidence_eligible=false 和确认门控制。"
rollback_plan: "不修改现有 active account-learning v2.7；若确认后升级仍需回滚，则恢复 v2.7 pipeline 与 Skill，停止新表达资产阶段，已有候选保持不可调用且不删除任何正式或原始资料。"
needs_user_confirmation: true
---

# 账号学习表达资产链 v3.0 提案

## 触发原因

吸收外部仓库中可复用的资产组织方式，同时遵守本系统“系统规则通用、账号内容隔离、候选不等于正式知识”的边界。本提案只设计未来 active Skill 如何调用通用契约；当前不运行任何账号学习任务。

## 证据

- 可吸收：钩子、金句、开场动作、结尾动作、痛点、反例、改编模板等资产类型。
- 可吸收：先审计、最多 20 条小样本、真实任务验收后再全量处理。
- 必须改编：把 Markdown 手工流程改为 JSON 契约、代码校验、账号隔离、状态机、证据坐标和回滚。
- 必须拒绝：复制具体话术、仅凭逐字稿宣布有效、用主观评分替代效果证据、把跨账号内容混成公共规则。

## 新规则

1. 系统层只定义类型、字段、来源、状态、风险和验收门，不存账号名、原句、source_id 或账号结论。
2. 原文 `source_excerpt` 与抽象结构 `abstracted_pattern` 分开；改编只使用抽象结构和明确变量。
3. 所有账号记录只进入 `10_Knowledge/candidates/account_assets/expression_assets/{account_id}/`，单文件只能有一个 account_id。
4. 每条来源必须同时绑定同目录 `source_registry.jsonl` 和知识证据层独立生成的 source authority 清单，校验账号、locator、登记哈希与真实来源文件哈希；证据坐标必须以同一 locator 开头，防止同步伪标归属。
5. 候选默认 `knowledge_layer=candidate`、`callable=false`、`method_evidence_eligible=false`、`generation_eligible=false`。
6. “结构可用性”与“传播效果”分开。效果证据采用封闭字段，必须绑定独立 performance authority、真实证据文件哈希、证据类型、指标、唯一样本集合与观察窗口；单条内容、逐字稿和主观分数不得证明传播效果。
7. 用户拒绝产物强制使用 `anti_pattern + rejected + validation_only`，任何消费端都必须排除；外部参考不得声称来自账号，也不得进入账号方法。
8. lifecycle 变更必须有连续 `transition_history` 和逐门 `gate_evidence`；报告必须位于本账号 validation authority 命名空间并校验真实哈希，禁止跨账号借报告或直接跳到高状态。
9. 小样本文件最多 20 条；全量校验必须以同一 account_id 递归执行完整 sample validator，再绑定真实小样本文件、记录哈希集合、validation receipt、审计报告哈希、validator 版本和已通过全部检查的 `sample_acceptance.json`。
10. 进入可调用状态前必须完成跨卡验证、压力测试、用户确认、active Skill 升级、回归和回滚记录。

## 适用范围

- 未来经确认后的账号学习阶段 1 提名与阶段 6 候选包装。
- 文本、图文发布文案和视频逐字稿中的表达结构候选。
- 候选检索、生产前结构参考和验收反例。

## 不适用范围

- 当前系统升级过程中的任何真实账号学习、补学或资产生成。
- 把外部仓库内容直接复制进正式知识、系统 Skill 或账号 Skill。
- 未经用户确认修改 active account-learning v2.7。
- 用表达资产代替正式方法、账号整体理解或效果验证。

## 风险

- 身份绑定与账号泄漏。
- 原句复制与版权风险。
- 无证据效果承诺。
- 商业信息污染与平台错配。
- 上下文依赖导致的错误迁移。

## 回滚方式

确认前无需回滚 active Skill，因为本提案不修改 active。确认后若回归失败，按 `skills/rollback.md` 恢复 v2.7；新候选保持不可调用，原始资料和正式账号中心不删除、不覆盖。
