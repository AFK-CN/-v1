# 小森林的小世界反偷懒审计

- 门禁：`pass`
- 深学卡：379；唯一原证据哈希：379；唯一卡哈希：379
- 唯一五阶段证据锚点签名：379
- 单卡字符：最少 5121 / 中位 5800 / 最多 6903
- 证据单元：最少 3 / 中位 36
- 保留原文引用：374；无有效原句但显式标注边界：5
- 人工视觉证据补位：5
- 媒介分布：{"video": 271, "normal": 108}
- 主机制分布：{"list_decision": 93, "problem_result": 76, "step_sequence": 134, "identity_proof": 17, "time_feedback": 44, "evidence_gate": 10, "version_iteration": 5}
- 49条延期项未生成深学卡；379条学习卡均为 candidate_learned / callable=false。

## 逐项检查

- [x] `all_learned_cards_present`
- [x] `source_ids_unique`
- [x] `source_text_hashes_unique`
- [x] `card_hashes_unique`
- [x] `evidence_anchor_signatures_unique`
- [x] `every_card_has_at_least_3_evidence_units`
- [x] `every_card_is_substantive_length`
- [x] `all_source_paths_exist`
- [x] `no_quote_cases_have_explicit_boundary`
- [x] `deferred_items_have_no_deep_card`
- [x] `learned_and_deferred_do_not_overlap`
- [x] `all_six_primary_mechanisms_have_support`
- [x] `all_cards_remain_noncallable_candidates`
