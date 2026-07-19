# 升级兼容与能力保留

- 账号：李宗恒
- 基线版本：1.3
- 当前版本：1.4
- 基线能力数：13
- 升级范围：系统账号批次中的单账号成员

## 强制规则

1. 每次升级先读取 `UPGRADE_COMPATIBILITY.json`，对比旧能力 ID 和当前能力 ID。
2. 旧能力不得静默丢失；替换或弃用必须有用户确认、替代能力和回滚路径。
3. 单账号只能引用本账号正式 Skill、方法、规则、校验器和视图。
4. 整体账号升级必须一账号一清单、逐账号验收，禁止跨账号合并规则、素材或正例。
5. 本次只新增升级防回退能力，没有替换或弃用任何基线能力。

## 基线能力 ID

- `topic_memory_deduplication`
- `topic_memory_recording`
- `production_memory_recording`
- `acceptance_gates`
- `evidence_boundaries`
- `production_mechanism`
- `publishing_copy_specialization`
- `style_fingerprint`
- `formal_method_lz_m1_system_transfer`
- `formal_method_lz_m2_control_right_reversal`
- `formal_method_lz_m3_semantic_reinterpretation`
- `formal_method_lz_m4_fixed_rule_escalation`
- `account_view_sync`
