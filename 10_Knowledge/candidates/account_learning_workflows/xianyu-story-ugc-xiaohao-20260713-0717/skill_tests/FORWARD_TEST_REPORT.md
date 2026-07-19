# 闲鱼故事 UGC Skill 前向测试报告

- 真实生成正例：5/5 通过
- 边界反例：5/5 正确拦截
- 命令行验证：通过
- 综合结论：通过

## 正例覆盖

- `old_suitcase_next_stop`：xugc-m02，pass
- `buyer_corrected_price`：xugc-m03，pass
- `plant_watering_service`：xugc-m04，pass
- `pottery_wheel_goodbye`：xugc-m05，pass
- `book_note_short`：xugc-m06，pass

## 反例覆盖

- `reject_abstract_platform_opening`：命中 `abstract_or_platform_opening_forbidden`，reject
- `reject_fabricated_identity`：命中 `fabricated_claims_must_be_empty_list`，reject
- `reject_unreviewed_visual_claim`：命中 `visual_claims_require_reviewed_evidence`，reject
- `reject_overlong_short_story`：命中 `short_transaction_story_too_long`，reject
- `reject_invalid_method_decoy`：命中 `primary_method_invalid`，reject

## 测试边界

正例使用未出现在学习样本中的合成事实包，用于验证方法调用和交付结构；不把合成故事当作新的学习证据。
图片内容未纳入本轮学习，所有正例均保持 `visual_claims=[]`。
