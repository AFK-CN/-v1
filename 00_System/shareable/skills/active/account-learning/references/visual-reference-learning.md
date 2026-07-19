# 视觉生产参考学习

本规则把“已经看懂账号图片”推进为“已经形成可追溯的生产参考包”。系统只规定证据和验收结构，不规定任何账号的具体风格、主体、场景、颜色或构图。

## 两种抽样不得混用

- 方向均衡抽样：覆盖正式方向，服务离线复查和证据回溯。
- 生产参考抽样：覆盖生产角色和视觉风险，服务生成前的少量引用。

方向样本数量足够，不代表生产参考已经完成。视觉分支必须在阶段 1 标记参考候选，在阶段 6 生成 `VISUAL_REFERENCE_PROFILE.json` 与 `visual_reference_candidate/manifest.json`。

## 通用生产角色

只从账号真实证据中选择适用角色，不为凑齐而虚构：

- `cover_or_primary_result`：首屏承诺、完整结果或主视觉。
- `process_or_proof`：过程、动作、证据或状态变化。
- `detail_or_outcome`：细节、材质、局部结果或完成状态。
- `environment_or_context`：真实环境、空间关系或使用场景。
- `identity_or_recurring_element`：经证据确认的固定人物、物件或视觉身份。
- `annotation_or_typography`：画面文字、标注和信息层级。

profile 先声明本账号的 `production_role_inventory`；manifest 必须覆盖其中每一项。系统角色是观察坐标，不是账号结论。

## 通用视觉风险维度

- `morphology_sensitive`：主体结构、形态、解剖或有机差异容易失真。
- `identity_sensitive`：人物、手、角色或固定物件身份容易漂移。
- `material_sensitive`：表面材质、纤维、颗粒、液体或反光容易变假。
- `spatial_relationship_sensitive`：容器、工具、环境和主体关系容易不成立。
- `temporal_state_sensitive`：前后状态、动作过程或完成状态容易错位。
- `typography_sensitive`：文字、标注、箭头和层级容易出错。

profile 只声明该账号证据实际出现的风险维度；manifest 必须用至少一项原始证据覆盖每个已声明风险。

## 来源类型隔离

| source_kind | 允许用途 | 禁止用途 |
| --- | --- | --- |
| `account_source_positive` | 生成参考、真实性/真实感校准、视觉验收 | 单独晋升账号方法；跨账号使用 |
| `user_accepted_ai_output` | 页间连续性回归、构图回归 | 真实性/真实感/镜头真实感来源；母版；黄金正例；账号方法；后续生图参考 |
| `user_rejected_output` | 失败识别、回归测试 | 生图参考、风格学习、方法证据 |
| `external_reference` | 用户明确指定的当次角色 | 自动进入账号证据或长期偏好 |

阶段 6 的账号学习正例候选只打包 `account_source_positive`。用户认可不能改变 `ai_generated` 来源；后续若记录 `user_accepted_ai_output`，必须放入独立 manifest，并把用途限制为 `page_continuity_regression` 和 `composition_regression`。禁止把名称、目录或人工认可状态改成“账号原图正例”。

旧字段 `user_accepted_positive` 只允许作为 v2.7 及更早审计记录的兼容标签；新流程不得继续生成该字段，也不得据此获得任何正例权威。

## 真实性权威与回归基线

- 账号原图项必须声明 `origin_kind=account_original`、`ai_generated=false`、`authenticity_authority=true`、`realism_authority=true`、`generation_reference_eligible=true`。
- 用户认可 AI 图必须声明 `origin_kind=ai_generated`，并把 `authenticity_authority`、`realism_authority`、`master_reference_eligible`、`golden_positive_eligible`、`method_evidence_eligible` 和 `generation_reference_eligible` 全部设为 `false`。
- 校准输出、首张输出和用户认可输出都只能是回归基线；不得反向承担原图真实性、材质真实感、镜头真实感或账号事实。
- 下一轮生成需要真实感校准时，只能回到账号原图；不能引用上一轮 AI 输出形成闭环。

## 生图与验收分离

- 生图提示词只描述本次生成任务，不复制进验收表或学习结论。
- 验收表只保存可观察检查项、结果、证据坐标和失败原因，不整段收录提示词。
- 为降低生成失败率而减少主体、容器、纹理或画面复杂度，属于 `model_runtime_only` 稳定性约束；除非账号原始证据独立证明，否则不得写进账号方法、内容规律或风格偏好。

## 候选包契约

```text
账号学习候选工作流/
├── VISUAL_REFERENCE_PROFILE.json
├── visual_reference_candidate/
│   ├── manifest.json
│   └── assets/
└── account_skill_candidate/references/visual-evidence.md
```

`VISUAL_REFERENCE_PROFILE.json` 必须记录：schema、适用状态、账号、两种抽样职责、角色清单、风险清单、正例 manifest、可选反例 manifest、来源隔离和候选边界。

正例 manifest 每项必须记录：

- 唯一 ID、相对路径与 SHA-256；
- 同账号名称、source_id 和正式证据坐标；
- 一个或多个生产角色与视觉风险维度；
- `allowed_use` 只能包含 `generation_reference`、`validation`；
- `method_evidence_eligible=false`。
- v2.8 新流程还必须记录 `origin_kind=account_original`、`ai_generated=false`、`authenticity_authority=true`、`realism_authority=true` 与 `generation_reference_eligible=true`。

可选的用户认可 AI 输出 manifest 必须记录：

- `source_kind=user_accepted_ai_output`、`origin_kind=ai_generated`；
- `reference_policy=page_continuity_and_composition_regression_only`；
- `allowed_use` 只能包含 `page_continuity_regression`、`composition_regression`；
- 六个权威/资格字段全部为 `false`，且不得出现 `generation_reference`、`food_realism`、`camera_realism`、`authenticity_reference`、`master_reference` 或 `golden_positive` 用途。

禁止写 NAS 绝对路径、跨账号 source、无证据图片、重复哈希或生成建议冒充原始证据。

## 阶段 6 验收

视觉分支必须全部满足：

1. profile 与 manifest 保持 `ready_for_review`、`formal_write=false`、`callable=false`。
2. 正例不少于三项，并完整覆盖 profile 声明的角色与风险。
3. 每项文件存在、路径不越界、SHA-256 一致、账号归属一致。
4. 正例中不存在用户认可生成图、用户拒绝图、外部参考或其它账号资产。
5. `visual-evidence.md` 明确写出四类来源的用途边界，并声明“用户认可不改变 AI 来源”。
6. 若存在反例包，其 source_kind 必须为 `user_rejected_output`、用途必须为 `validation_only`，且与正例无 ID/哈希重叠。
7. 若存在用户认可 AI 输出包，代码校验其来源、用途和六个 `false` 权威字段；任一项被升格即阻断阶段 6。

任一项失败时阻断阶段 6。不能用“暂无素材”让视觉账号进入正式生产；应返回缺口并补学。

## 正式生效

用户批准账号 Skill 后，把阶段 6 的账号原图参考候选复制到该账号 Skill 的视觉资产目录，并保留 manifest 与哈希；同时继续生成方向均衡离线源。两类轻量层均通过验证后，才把视觉生产写为已就绪。
