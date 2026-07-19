---
name: account-xiaosenlin
description: Produce evidence-bounded skincare experience, product-decision, image-text, spoken, lifestyle-trust, community, commercial, and platform-project content using the formally validated methods and expression rules of the 小森林的小世界 account. Use only when the user explicitly requests this account or its production system.
---

# 小森林的小世界账号生产

账号 Skill 版本：1.4

使用本账号正式经验、方法和证据边界生产内容。不要把个人肤质经验改写成医学结论或人人有效的功效承诺。

## 生产前

1. 确认内容轨道：自然经验、产品决策、商业内容、平台项目、生活信任或社群互动。
2. 生成新选题时，整批调用 `topic-memory-check --account-skill-id xiaosenlin_xiaoshijie`；只接收少量冲突摘要。
3. 从 `../METHOD_INDEX.json` 选择一个主方法；流程任务才叠加递进方法，多产品任务使用条件化决策分流。
4. 需要案例时按正式卡索引读取少量对应证据，不全扫候选区或原始资产。
5. 动笔前在内部确定：这条内容只解决什么任务、适用什么条件、哪些是固定结构、哪些是可替换变量、证据处于什么等级、出现什么情况要停止或改口。
6. 只要交付发布标题、发布文案、话题或完整图文包，必须读取 `references/publishing-copy.md`，让标题承诺、正文过程、视觉证据和话题范围保持一致。

## 生产

按需读取 `references/production.md`、`style.md`、`publishing-copy.md`、`boundaries.md` 和 `acceptance.md`。先按 `production.md` 选定结构，再从具体肤质、当天状态、使用场景或选择难题进入，写清条件、顺序、观察点和判停点。成品必须同时通过身份感、自然经验口吻、发布层协同、证据与医学边界、条件化利他和结构闭合验收。

## 生产后

1. 选题写入 `topic-memory-record`。
2. 成品写入 `production-memory-record`，登记账号 Skill 版本 1.3。
3. 原文、个人经验、外部事实和系统提炼保持清晰边界。

## 升级兼容

升级本账号 Skill 前必须读取 `UPGRADE_COMPATIBILITY.json` 和 `references/upgrade-compatibility.md`。旧能力 ID 不得静默丢失；替换或弃用必须经用户确认并保留回滚。整体账号升级仍只能使用本账号证据，禁止跨账号合并能力、规则、素材和正例。
