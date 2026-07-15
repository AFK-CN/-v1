# 账号学习卡三层融合 v2 提案

```yaml
skill_name: 账号专业学习
version: v2.1
status: active
created_at: 2026-07-11
activated_at: 2026-07-11
activated_by: 用户确认采用“证据层 + 内容拆解层 + 跨卡方法层”并要求落地
evidence:
  - 旧版十段式学习卡保留核心观点、内容结构、金句、案例、方法论和模板，内容生产可用性强。
  - 新版证据型学习卡保留证据边界、多维分类、广告隔离和逐字稿证据，审计可靠性强。
  - RIA-TV++ 适合在跨卡层做 Adler 理解、五视角提取、三重验证、RIA++ 构造、关系图和压力测试。
proposed_behavior: 建立统一三层学习契约。单卡合并证据层和内容拆解层；单卡只生成 RIA++ 方法候选；跨卡层继续执行完整 RIA-TV++。
activated_outputs:
  - 00_System/shareable/config/account_learning_card_contract.json
  - 00_System/shareable/rules/统一学习卡产出标准.md
  - tools/account_learning_card.py
  - tools.kb.cli account-learning-validate-card
rollback_plan: 停止生成 unified_three_layer_v2 卡，恢复原生成模板；保留历史卡和跨卡方法产物，不修改原始证据。
needs_user_confirmation: false
```

## 生效规则

1. 单卡证据层记录证据边界、分类、广告隔离和媒体状态。
2. 单卡内容层记录为什么值得学习、核心观点、动态内容结构、发布层、金句、案例、方法候选和模板。
3. 原文金句、系统提炼表达、可复用句式必须分开标注。
4. 单卡 RIA++ 只作为候选；完整方法必须跨至少两张卡通过三重验证。
5. Adler 分析、五视角候选池、方法关系图和压力测试保持账号/批次级产物。
6. 历史旧卡不批量迁移，验证器保持兼容；新生成卡必须使用统一契约。
7. 系统规则只写通用产物标准，不包含任何账号专属内容。

## 验收结果

- 统一卡十二段、三种动态内容结构、RIA++ 候选和金句分型均有专项测试。
- 历史十段式卡保持兼容。
- 通用视频学习出口和账号专用生成器均产出同一契约。
- 全量 unittest 与 `validate-system` 通过。

## 回滚方式

恢复原学习卡生成函数和验证器；删除统一卡机器契约引用。历史卡、原始证据和跨卡候选池保持不变。
