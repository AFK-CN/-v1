# 小森林的小世界 Skill v2.2 真实验收报告

- 状态：`passed`
- 全量有效深学卡：379
- 证据延期：49
- 重建五视角候选：1895
- 严重问题：旧阶段1曾把49条延期来源生成五视角候选，且旧验收漏检跨字段语义冲突；已触发当前379条有效卡全量扫描与重建。
- 正式写入：false；可调用：false

## 分层结果

- `normal_visual`：passed；总体 55；抽样 10
- `normal_long_transcript`：passed；总体 31；抽样 10
- `product_ad`：not_applicable；总体 0；抽样 0
- `platform_project`：passed；总体 2；抽样 2
- `collaboration_ownership`：passed；总体 17；抽样 10
- `low_information_or_asr_risk`：passed；总体 6；抽样 6

## 商业与项目分轨

- 明确商品广告：0/0，不计自然方法V1。
- 平台项目：2/2，单独学习。
- 商业属性不明：319/319，保持证据门。
- 无时间码或帧号的品牌、活动、购买利益和视觉结论均未声称已核验。

## 语义与范围一致性

- 跨字段语义冲突：0
- 总览覆盖：379条深学 + 49条延期 = 428条来源。
