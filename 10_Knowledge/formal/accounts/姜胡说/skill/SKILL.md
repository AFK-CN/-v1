---
name: account-jianghushuo
description: Produce topics, spoken scripts, long-form copy, titles, captions, and complete publishing packages using the formally validated methods, evidence-grounded case and model structures, expression boundaries, and beneficiary closure of the 姜胡说 account. Use only when the user explicitly requests this account, its production system, or its style.
---

# 姜胡说账号生产

账号 Skill 版本：1.4

使用本账号正式方法和证据生产内容。不要把本 Skill 当作通用成长、商业或口播模板。

## 生产前

1. 明确一类受众、一个具体问题、平台和输出形式。
2. 生成新选题时，先形成受众、问题、方向、角度、机制和流派字段，整批调用 `topic-memory-check --account-skill-id jianghushuo`。
3. 高度重复项重做；警告项必须说明真实新变量；禁止读取完整生产数据库。
4. 从 `../METHOD_INDEX.json` 只选一个主方法；支持方法删除后不改变结构就移除。
5. 只按需要读取对应方向正式卡，不全扫候选区、NAS 或全部单卡。
6. 写草稿前在内部确定一个 `content_engine`、固定单元、可变槽位和完成门；不得只因题材相同就复用同一结构。
7. 只要交付发布标题、发布文案、话题或完整发布包，必须读取 `references/publishing-copy.md`，先确定标题承诺、正文兑现方式和话题范围。

## 生产

读取：

- `references/production.md`：正文发动机、生产顺序和交付包。
- `references/style.md`：表达指纹与防模板规则。
- `references/publishing-copy.md`：发布标题、正文、话题和成品协同规则。
- `references/boundaries.md`：证据和真实性边界。
- `references/acceptance.md`：单条与批量验收。

先按 `production.md` 完成“主方法—正文发动机—篇幅层级”路由。可以从具体案例进入，也可以先给反常识判断或直接问题，但判断必须立即由案例、模型关系或可回查过程托住。最后交付受众能使用的判断标准、自检问题或下一步行动，并写清证据和误用边界。写完必须按 `acceptance.md` 同时检查账号辨识度、口语、证据、利他和结构完成度。

## 生产后

1. 将所有交付选题写入 `topic-memory-record`；批量候选状态为 `candidate`。
2. 成品写入 `production-memory-record`，登记 topic_id、content_id 和 Skill 版本 1.3。
3. 内部方法、source_id 和证据说明只放溯源区，不进入成品正文。

## 升级兼容

升级本账号 Skill 前必须读取 `UPGRADE_COMPATIBILITY.json` 和 `references/upgrade-compatibility.md`。旧能力 ID 不得静默丢失；替换或弃用必须经用户确认并保留回滚。整体账号升级仍只能使用本账号证据，禁止跨账号合并能力、规则、素材和正例。
