---
skill_name: 视频深度学习Skill
version: v1.1
status: 已生效
confirmed_at: 2026-06-30T11:00:44
source_proposal: 00_System/shareable/skills/proposals/账号粗学全量选题池口径_v1_提案.md
---

# 账号粗学全量选题池口径 v1

## 生效结果

已同步到 `00_System/shareable/skills/active/视频深度学习Skill_v1.md` 和 `00_System/shareable/rules/账号学习标准工作流.md`。

## 核心规则

1. 粗扫阶段必须生成方向级全量选题池。
2. `粗学与选题池.md` 必须包含该账号粗扫范围内所有条目，并按方向分组。
3. 每个方向可以按 `已深学/high/medium/low/热度` 排序，但不得截断为 Top。
4. Top 内容清单只能用于候补深学队列、深学执行优先级、快速阅读视图或 `deep_learning_plan.json`。
5. 验收时必须核对 `粗学与选题池.md` 条目总数与粗扫清单一致。

## 适用范围

- 新账号学习。
- 旧账号补学习。
- SQLite/JSON/平台导入后的账号粗扫。
- 正式账号中心综合入库前验收。

## 不适用范围

- 内容生产时的精选选题输出。
- 深度学习卡本身。
- 方向方法论总结。
- 用户明确只要求 Top 榜单或候补深学清单的场景。
