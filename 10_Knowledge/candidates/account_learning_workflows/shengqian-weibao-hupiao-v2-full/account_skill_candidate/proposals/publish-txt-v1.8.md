---
skill_name: account-shengqian-weibao-hupiao
version: "1.8"
status: applied
created_at: "2026-07-18"
trigger: "用户明确要求发布文案不要以 Markdown 保存，统一使用 TXT"
evidence: "用户在第 5 条完整发布包交付后直接指定文件格式"
current_problem: "v1.7 将交付文案固定为发布文案.md，虽然内容可复制，但文件格式与用户当前交付偏好不一致。"
proposed_behavior: "完整发布包只保存发布文案.txt，不再保存同名发布文案.md；文本内容仍保留发布标题、发布文案、话题三个区块；校验脚本直接拦截非 .txt 输入。"
what_will_change: "升级正式账号 Skill 到 v1.8；同步正式规则、可见视图、Manifest、用户层注册和发布文案校验脚本；只约束下一批及后续新生产，不改名当前批次和历史黄金基线。"
risk: "把 TXT 误解为不能使用清晰区块。TXT 内仍允许使用现有 # 标题行作为纯文本结构，只改变文件扩展名。"
rollback_plan: "恢复 v1.7 文件名规则和校验脚本，并将发布文案.txt 改回发布文案.md。"
needs_user_confirmation: false
confirmed_at: "2026-07-18T22:34:04+08:00"
applied_at: "2026-07-18T22:34:04+08:00"
---

# 发布文案 TXT 交付 v1.8

## 新规则

- 交付文件固定命名为 `发布文案.txt`。
- 同一选题文件夹不得同时残留 `发布文案.md`。
- TXT 仍只包含发布标题、发布文案、话题三个区块，不加入页面计划和内部溯源。
- `validate_publishing_copy.py` 必须拒绝 `.md` 等非 `.txt` 输入。

## 生效范围

当前十条生产批次和番茄豆腐历史黄金基线保留原文件名。下一批及后续新生产统一使用 `发布文案.txt`。
