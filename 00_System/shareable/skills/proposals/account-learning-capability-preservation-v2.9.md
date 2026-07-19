---
skill_name: account-learning
from_version: "2.8"
to_version: "2.9"
status: implemented
created_at: "2026-07-19"
confirmed_at: "2026-07-19"
confirmation_evidence: "用户明确要求任何账号 Skill 的系统性升级或单独升级都不得舍弃既有能力，整体账号升级也要防账号污染，并要求升级后完整检查与账号 Skill 测试验收。"
scope: "generic_account_skill_upgrade_mechanism"
account_specific_content_in_system: false
expression_asset_activation: false
---

# 账号 Skill 能力保留与升级隔离 v2.9

## 问题

旧流程要求候选、用户确认和回滚，但没有稳定能力 ID 和升级前后集合比较。规则文件仍可能在“修复最新问题”时静默删掉旧能力；多图成套结果也可能只剩若干散列引用，无法证明母图、页序和继承关系完整保留。

## 生效机制

1. 新建或升级账号 Skill 必须生成 `UPGRADE_COMPATIBILITY.json`。
2. 升级前所有能力 ID 必须继续出现在升级后清单；新能力集合必须等于真实差集。
3. 替换或弃用不会删除历史 ID，且必须绑定用户确认、替代能力和回滚。
4. 关键 Skill 文件记录 SHA-256；文件变化未登记时验证失败。
5. 一个兼容清单只允许一个账号，能力来源只能位于同一账号 Skill；整体升级逐账号运行，不产生跨账号能力池。
6. 用户认可的多图结果必须以有序回归包保存母图、页序、直接父关系和文件哈希；连续性要求存在时禁止逐页独立重生。
7. 多图回归包仍保持 AI 来源，只允许连续性与构图回归；六项真实感/母版/黄金/方法/生成权威全部为 `false`。

## 污染边界

- 系统契约不含账号名、账号内容、账号能力正文、source_id 或素材路径。
- 单账号升级不能读取或引用其它账号 Skill、提案或资产。
- 整体账号升级只是多个隔离验证结果的集合，禁止跨账号补证据、规则或视觉正例。
- 原始资料、正式知识和历史资产不删除、不覆盖。

## 版本边界

本次升级 active account-learning 至 v2.9。表达资产 v3.0 提案仍保持独立待确认状态，不因本机制自动激活，也不运行新的真实账号全量学习。

## 回滚

恢复 account-learning v2.8、account Skill contract v4 和不含兼容清单的 stage 6；已生成的账号兼容清单与失败报告作为审计保留，不删除账号原图、正式 Skill、候选或生产记录。
