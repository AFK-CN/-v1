# Skill 提案：截图复盘 v1

状态：history，已生效为 `13_Evolving_Skills/active/截图复盘Skill_v1.md`，不再作为待确认 proposal 调用。

## 触发原因

你预计后续会给平台截图作为数据反馈。截图中的指标可能不完整、字段名称可能随平台变化，因此需要固定读取顺序，避免误读。

## 新规则

读取截图时按以下顺序：

1. 先识别平台和页面类型。
2. 只记录截图中明确可见的指标。
3. 不猜测被遮挡或看不清的数值。
4. 标注不确定字段。
5. 将截图指标与对应内容 ID、标题、发布时间绑定。
6. 进入周复盘时，优先比较同平台同周期的相对表现。

## 输出

截图读取后生成：

```yaml
platform:
page_type:
content_id:
visible_metrics:
uncertain_metrics:
performance_signal:
next_review_action:
```

## 风险

- 截图清晰度不足时容易误读。
- 平台页面字段变化时需要更新规则。

## 回滚方式

如果该 Skill 导致截图解读变差，撤回本提案，不进入 active。
