---
skill_name: account-learning
from_version: "2.7"
to_version: "2.8"
status: implemented
created_at: "2026-07-19"
confirmed_at: "2026-07-19"
confirmation_evidence: "用户明确要求解决系统学习级 Skill 将用户认可 AI 图升格为真实感来源的问题，并要求这是系统优化而非账号学习。"
scope: "system_skill_and_validation_only"
account_learning_executed: false
account_assets_generated: false
---

# 账号学习 AI 输出来源隔离 v2.8 提案与生效记录

## 问题

旧版虽然区分账号原图、用户认可图、用户拒绝图和外部参考，但仍把用户认可图命名为“正例”，且主要依赖文字约束。它没有用代码同时锁定原始来源、允许用途、真实性权威、母版资格和生成参考资格，因此存在把 AI 输出反向升格为账号真实感来源的风险。

## 生效规则

1. 只有 `account_source_positive + origin_kind=account_original` 可以承担真实性、真实感和后续生成参考权威。
2. 用户认可的 AI 输出统一使用 `user_accepted_ai_output + origin_kind=ai_generated`；认可状态不能改变来源。
3. 用户认可 AI 输出只允许 `page_continuity_regression` 和 `composition_regression`。
4. 用户认可 AI 输出的真实性、真实感、母版、黄金正例、方法证据和生成参考资格必须全部为 `false`。
5. 校准输出和首张生成结果只能作为回归基线；禁止生成结果自我引用、自我强化或跨轮升格。
6. 生图提示词、模型稳定性约束和验收规则分离。为降低生成失败而减少画面复杂度，只是运行约束，不能成为账号内容规律。
7. v2.7 旧字段 `user_accepted_positive` 只作为历史审计兼容标签；v2.8 新流程不得继续生成。

## 代码门禁

- 新流程的账号原图项必须显式声明原图来源、非 AI 生成和三项权威资格。
- 可选用户认可 AI 输出 manifest 必须通过来源、账号、用途和六个 `false` 字段校验。
- 任一 AI 输出被标成真实感、镜头真实感、母版、黄金正例或生成参考时，阶段 6 直接失败。
- v2.7 已有候选不被批量改写；只在显式记录为 AI 生成却冒充原图时立即阻断。

## 污染边界

- 本变更不包含账号名、账号图片、食物、桌面、餐具、颜色、构图或其它账号专属结论。
- 不运行真实账号学习、不生成图片、不修改任何正式账号 Skill。
- 系统只保存通用来源类型、用途、权威字段和验收规则。

## 回滚

若 v2.8 导致合法原图候选无法通过：

1. 恢复 account-learning v2.7、pipeline v2.7 和 account Skill contract v3。
2. 保留本提案与失败报告，不删除原始资料、候选或正式账号内容。
3. 用户认可 AI 输出继续保持不可生成引用、不可方法证据状态，直到修订提案再次确认。
