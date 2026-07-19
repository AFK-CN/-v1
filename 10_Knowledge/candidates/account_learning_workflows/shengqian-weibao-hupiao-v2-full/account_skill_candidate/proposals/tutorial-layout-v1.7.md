---
skill_name: account-shengqian-weibao-hupiao
version: "1.7"
status: applied
created_at: "2026-07-18"
trigger: "用户在十条内容批量生产中指出步骤图连续使用四宫格，整体过于雷同，并明确要求记入 Skill"
evidence: "本轮已完成的步骤页连续采用 2x2 四宫格；用户实时验收反馈"
current_problem: "现行 Skill 只要求步骤页有设计感和按复杂度分配，没有约束同批教程版式的重复率，导致内容不同但视觉骨架机械复制。"
proposed_behavior: "为每张 tutorial 页面记录 layout_family；四宫格只作为一种可选版式。四张及以上教程页时四宫格占比不得超过 40%，六张及以上至少使用三类教程版式；版式必须服从动作和关键状态，不能通过删步骤制造变化。"
what_will_change: "升级正式账号 Skill 到 v1.7；修改 visual-production、package-cycle、acceptance、批次校验脚本和四份中文可见视图；同步 Manifest 与用户层账号注册版本。"
risk: "为追求版式变化而牺牲步骤可读性。规则因此只约束布局骨架，菜谱步骤、火候、时间和结束状态仍必须完整。"
rollback_plan: "恢复 v1.6 正式文件、注册版本与批次校验脚本；保留本提案和用户反馈作为历史证据。"
needs_user_confirmation: false
confirmed_at: "2026-07-18T22:07:16+08:00"
applied_at: "2026-07-18T22:07:16+08:00"
---

# 步骤页版式轮换 v1.7 提案

## 触发原因

同一批内容连续使用等分 2x2 四宫格，读者先看到模板重复，再看到菜品差异。用户已明确要求停止这种雷同并写入 Skill。

## 新规则

- 每张教程页在内部套餐计划中声明 `layout_family`。
- 可用版式至少包括：`grid_2x2`、`vertical_story`、`horizontal_story`、`hero_plus_steps`、`diagonal_cards`。
- 四张及以上教程页时，`grid_2x2` 占比不得超过 40%。
- 六张及以上教程页时，至少使用三类版式。
- 版式变化不能删除必要步骤；文字仍需逐字复核，厨房、锅具和手部锚点规则继续生效。

## 本轮应用

已完成内容保留原生产版本；从当前第 5 条《咖喱虾仁豆腐》起使用非四宫格教程版式。第 6 条及以后暂停生产，待用户继续时按 v1.7 计划执行。
