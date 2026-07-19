---
skill_name: account-shengqian-weibao-hupiao
version: "1.2"
status: applied
created_at: "2026-07-17"
applied_at: "2026-07-17"
trigger: "用户要求精简选题文件夹中的发布文案.md，并明确要求沉淀到账号 Skill"
evidence: "绑定 content_shengqian_20260716_tomato_tofu 的人工反馈与当前三段式交付文件"
current_problem: "完整发布包中的发布文案.md 混入食材清单、页面计划、发布检查和内部溯源，影响直接复制发布。"
proposed_behavior: "将发布文案.md 固定为仅含发布标题、发布文案、话题三个一级区块；制作信息留在内部流程。"
what_will_change: "只调整用户交付文件契约和验收，不修改账号方法、证据结论或正文表达机制。"
risk: "把用户交付偏好误写成账号原文规律。通过在 Skill 中明确标注为用户偏好控制。"
rollback_plan: "移除三段式文件契约并恢复 v1.1 Manifest 与中文视图版本。"
needs_user_confirmation: false
---

# 发布文案交付文件 v1.2

## 用户确认

用户明确要求：选题文件夹中的 `发布文案.md` 只保留发布标题、发布文案和话题，并要求沉淀到账号 Skill。

## 执行

- 当前 `发布文案.md` 已精简为三个一级区块。
- 正式 Skill、发布文案规则、生产规则、视觉规则和验收规则均加入同一文件契约。
- 四份中文可见视图和正式 Manifest 同步到 v1.2。
- 此项仅是用户交付偏好，不新增或修改正式方法。
