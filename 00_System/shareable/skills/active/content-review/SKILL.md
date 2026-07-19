---
name: content-review
description: Review published or produced content by linking screenshots, tables, platform metrics, comments, and manual feedback to the exact topic, content record, account Skill version, methods, and evidence. Use when Codex needs to diagnose topic, hook, structure, expression, platform fit, or evidence problems; create targeted relearning tasks; or propose a user-approved account Skill update without automatic evolution.
---

# 内容复盘与强化

把反馈绑定到真实生产记录，再判断哪些选题、结构、表达和账号方法有效、失效或需要补证据。不要自动修改任何 active Skill。

## 执行

1. 获取 content_id；使用 `review-context` 只读取这一条内容、对应选题、账号 Skill 版本和已有反馈。
2. 按 `references/input-adapters.md` 解析截图、表格、评论摘要或人工反馈；看不清和定义不明的字段保留不确定状态。
3. 按 `references/diagnosis.md` 区分选题、钩子、结构、表达、证据、平台和发布时间问题。
4. 写入反馈数据库，并区分单次信号、重复信号和稳定规律。
5. 输出继续观察、调整生产、定向补学或账号 Skill 升级提案。
6. 账号 Skill 变更必须由用户确认并重新验证，不存在自动进化。

## 边界

- 不跨平台硬比字段。
- 不用一张截图决定长期规律。
- 不把相关性写成因果。
- 不读取完整生产数据库，只读取 content_id 对应上下文和必要对照项。
- 不把用户私有反馈写入可分享系统层。

读取 `references/upgrade-gates.md` 判断何时只能记录、何时补学、何时可以提出 Skill 升级。
