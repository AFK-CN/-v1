---
name: account-learning
description: Learn an account from processed evidence and produce traceable learning cards, validated cross-card methods, structure mechanisms, expression fingerprints, boundaries, pressure tests, and a review-gated account Skill candidate. Use after content processing when Codex needs to learn video, image-text, story, long-copy, knowledge, dialogue, commercial, or platform-project content without contaminating system rules with account-specific conclusions.
---

# 账号学习

把内容处理 Skill 交付的标准证据学习为账号中心内的候选账号 Skill。系统流程必须通用，账号结论只进入对应账号候选和账号中心。

账号学习组件版本：2.9（系统 3.0 的账号 Skill 防回退机制）。

## 执行

1. 读取 `account_learning_pipeline.json`、学习卡契约和状态文件。
2. 单条内容按 `references/unified-learning-card-standard.md` 生成统一学习卡；图文/视频分支必须额外完整执行 `references/image-text-deep-learning.md`，并按 `references/visual-reference-learning.md` 标记可承担生产角色和视觉风险校准的原始证据候选。不能把 OCR、单图描述或发布文案摘抄当作已学完。
3. 再按 `references/professional-extraction-validation.md` 执行整体理解、五视角观察、机制聚合与三重验证、RIA++ 构造、方法链接、压力测试和候选交付；按 `references/genre-adapters.md` 选择观察维度，允许一个账号同时包含多个流派。
4. 单卡只贡献证据和候选，不宣布稳定方法。
5. 阶段 0 和阶段 2 后等待用户确认。
6. 阶段 6 按 `references/account-skill-packaging.md` 生成不可调用的账号 Skill 候选包、四份账号专属中文可见视图和生产交接包；同时按 `references/capability-preserving-upgrades.md` 生成能力兼容清单。已有账号升级时，旧能力 ID 必须逐项进入新清单；删除、替换或弃用只能作为显式提案等待用户确认，不能静默消失。
7. 视觉分支同时按 `references/visual-reference-learning.md` 生成按生产角色与视觉风险覆盖的参考候选包；用户认可的多图成套结果必须作为一个有序回归包保存母图、页面顺序与继承关系，但仍只能做连续性/构图回归，不能成为真实感或后续生图来源。缺失时不得完成阶段 6。
8. 用户审核通过后才写正式账号中心并进入用户层注册表；正式写入验证通过后，将视觉参考候选复制进本账号 Skill，并按 `references/offline-lightweight-source.md` 组建方向均衡轻量数据源。两个轻量层职责不同，必须分别验证。
9. 历史账号升级到 v2.9 时，先运行 `account-skills-v29-audit`定位正式 Skill 缺口；经用户确认后逐账号执行 `account-skills-v29-upgrade`，再用 `account-learning-migrate --all --force` 同步本账号已批准的发布文案、验收规则、脚本和方法索引。最后必须以 `account-learning-v29-audit` 证明注册账号与工作流一一对应、正式与候选快照一致、延期证据已隔离且无生成型垃圾。

## 硬边界

- 原始资料只读，候选与拒绝项都保留审计轨迹。
- 不把方向词、人物、场景、道具或平台常识当成账号方法。
- 不预设结构数量、表达句式和篇幅。
- 不把账号结论写入本系统 Skill。
- 系统 Skill 只保存通用生产角色、风险维度、来源类型和验收 schema；账号图片、source_id、风格和结论只能进入对应账号候选或账号中心。
- 不从学习阶段直接激活账号 Skill。
- 新建和升级账号 Skill 都必须维护稳定能力 ID、升级前后清单、变更理由、用户确认和回滚；旧能力没有出现在新清单时直接阻断。
- 单账号升级只能引用本账号 Skill、提案和资产；整体账号升级也必须逐账号独立验证，禁止合并能力清单、借用其它账号规则或用跨账号素材补缺。
- 系统层只保存兼容 schema 和校验规则，不保存任何账号名、能力结论、素材路径或账号内容。
- 轻量数据源只能在用户审核和正式写入验证通过后组建；阶段 6 不得写入正式账号中心。
- NAS 不可用时保留现有离线包；新账号只标记 `pending_nas_sync`，不得用候选资产填充。
- 旧轻量数据源已存在时默认只输出差异预览，未经明确批准不覆盖。
- 不把整个轻量数据源加载进模型上下文；选择、复制、差异与哈希验证由代码执行。
- 方向均衡轻量源不能替代生产视觉参考源；视觉分支阶段 6 必须证明角色和风险覆盖。
- `account_source_positive`、`user_accepted_ai_output`、`user_rejected_output` 与 `external_reference` 必须按原始来源和用途分层；“用户认可”不能改变 AI 生成来源。
- 只有账号原图可以承担真实性、真实感和生成参考权威。用户认可的 AI 图只能用于页间连续性与构图回归，禁止升级为真实感来源、母版、黄金正例、账号方法或后续生图参考。
- 校准图和首张生成结果只能作为回归基线；禁止由生成结果自我引用、自我强化或跨轮次升格为新正例。
- 生图提示词、模型稳定性约束与验收规则必须分别保存。为提高生成稳定性而减少画面复杂度，只能是运行约束，不能写成账号内容规律。
- `user_rejected_output` 只能用于验收和回归测试，禁止作为生图参考。
- 中文可见视图只能聚合本账号已验证方法、正式表达指纹与边界；不得用方向词、平台词或其他账号模板补齐。
- 发布标题、正文和话题是独立发布层证据；必须学习其机制、细节与协同关系，不能只保存原文或并入泛化表达总结。
- 图文以“一条发布内容及其有序组图”为单卡单位；必须逐图看原图并学习封面、分图、构图、文字设计、动作状态、结果呈现、生活感和组图叙事。
- OCR 只证明图中文字，客观色值和单图转述也不能替代图片深度学习；缺发布层、视觉复核或组图归属时必须显式降级。

详细质量门读取 `references/seven-stage-gates.md`；正式账号 Skill 包必须执行 `account_skill_contract.json`。
