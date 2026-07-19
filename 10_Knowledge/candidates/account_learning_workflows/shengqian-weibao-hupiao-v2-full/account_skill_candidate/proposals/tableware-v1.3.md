---
skill_name: account-shengqian-weibao-hupiao
version: "1.3"
status: applied
created_at: "2026-07-17"
applied_at: "2026-07-17"
trigger: "用户确认胡桃木桌面与手作陶器版本，并明确要求沉淀到账号 Skill 供后续默认生成"
evidence: "绑定 content_shengqian_20260716_tomato_tofu 的人工反馈、五张用户确认的局部替换成图与材质锚点"
current_problem: "现有视觉规则只写深色桌面和相近碗具，无法稳定复现用户确认的具体木纹、色调、器型与手作陶器质感。"
proposed_behavior: "将深暖胡桃木自然木纹与协调但不完全同款的低饱和手作陶器设为后续默认生产基线；保存已确认成图作为材质锚点，并允许当次明确参考覆盖。"
what_will_change: "只调整账号专属视觉生产偏好、材质锚点与验收；不新增方法，不修改 METHOD_INDEX，不把用户偏好冒充账号原帖规律。"
risk: "过度复制锚点中的番茄豆腐、文字或构图，或把参考图里的额外物件带入新内容。通过材质角色限定、局部替换锁定项和逐页验收控制。"
rollback_plan: "删除材质锚点与 v1.3 新增视觉偏好，恢复 v1.2 的 Skill、Manifest、references 和四份中文视图后重新同步注册表。"
needs_user_confirmation: false
---

# 默认胡桃木桌面与手作陶器 v1.3

## 用户确认

用户在查看五张局部替换成图后明确要求：将这套餐具和桌面记录到账号 Skill，后续按此生成。

## 正式生产偏好

- 默认桌面：深暖胡桃木餐桌，自然深棕木纹清晰可见，偏哑光。
- 默认餐具：米白、砂岩、灰绿或浅灰褐的低饱和手作陶器；器皿协调但不完全同款，带细小斑点、轻微不规则口沿和柔和釉面。
- 默认器型：带汁主菜优先宽口浅碗/浅盘，青菜使用暖砂色陶碗，米饭使用浅米白陶碗；具体仍服从菜品与构图。
- 覆盖顺序：用户当次明确参考 > 本默认偏好 > 正式卡中的一般深色桌面规则。
- 材质锚点：`skill/assets/visual/default-walnut-tableware-anchor.png`；只校准木材和陶器，不复制菜品、文字、箭头、构图或无关物件。

## 执行结果

1. 正式账号 Skill 从 v1.2 升至 v1.3。
2. 更新 `visual-production.md`、`production.md`、`style.md` 与 `acceptance.md`。
3. 同步四份中文可见视图和正式 Manifest。
4. 不新增账号方法；本次变更标记为用户生产偏好。
