# Skill 提案：表格复盘 v1

状态：history，已生效为 `13_Evolving_Skills/active/表格复盘Skill_v1.md`，不再作为待确认 proposal 调用。

## 触发原因

你预计后续可能给平台导出数据表格。表格适合做批量对比、排序和趋势分析。

## 新规则

处理表格时按以下顺序：

1. 识别平台、时间范围、账号或项目。
2. 读取字段名，保留原始字段解释。
3. 找到核心指标：曝光、播放、点赞、收藏、评论、分享、转粉、完播、点击。
4. 按平台分开排序，不跨平台硬比。
5. 输出最佳内容、最差内容、异常内容。
6. 反推已验证/失效的方法论。

## 输出

```yaml
platform:
date_range:
rows:
columns:
best_items:
worst_items:
method_updates:
topic_updates:
uncertain_columns:
```

## 风险

- 不同平台导出字段含义不同。
- 表格缺少内容文本时，必须回查内容标题或原始案例。

## 回滚方式

如果该 Skill 让复盘过度依赖数字、忽略内容质量，撤回本提案并改小范围。
