# 闲鱼故事 UGC 视觉前向测试报告

- 视觉正例：4/4 通过
- 视觉反例：5/5 正确拦截
- 命令行验证：通过
- 综合结论：通过

## 正例

- `platform_listing_object_chat`：`platform_evidence_chain`，pass
- `object_context_detail_result`：`object_truth_sequence`，pass
- `hook_card_then_real_proof`：`hook_card_then_proof`，pass
- `single_photo_boundary`：`single_visual`，pass

## 反例

- `reject_fabricated_chat_screenshot`：命中 `visual_frame_3_screenshot_must_be_real`，reject
- `reject_unreviewed_visual_package`：命中 `visual_claims_require_reviewed_evidence`，reject
- `reject_missing_privacy_check`：命中 `privacy_check_requires_all_fields`，reject
- `reject_visual_performance_claim`：命中 `visual_performance_claims_must_be_empty_list`，reject
- `reject_unsupported_publish_order`：命中 `actual_publish_order_claim_requires_evidence`，reject

## 测试边界

全部正例为未见合成事实与图片清单，只用于验证 Skill 路由、结构和边界，不回流为视觉学习证据。
真实视觉方法仍只来自 230 张已复核飞书图片。
