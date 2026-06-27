# JSON 入库清洗规则

## 适用范围

适用于小红书、抖音及后续平台的爬虫 JSON 文件。

## 字段标准化

统一字段：

```yaml
platform: xhs | douyin
source_file: 原始文件路径
source_id: note_id | aweme_id | comment_id | user_id
content_type: content | comment | creator
title: 标题
body: 正文或评论内容
author_id: 作者 ID
author_name: 作者昵称
published_at: 发布时间
last_seen_at: 抓取或修改时间
metrics:
  likes: 点赞
  collects: 收藏
  comments: 评论
  shares: 分享
tags: 平台标签
url: 内容链接
```

## 类型转换

- 所有指标字段转为整数；小红书数据中可能出现字符串数字。
- 空值统一为 `0` 或空字符串。
- 时间字段保留原始值，同时在可判断时转成标准日期。

## 噪音识别

以下内容默认不进入正式知识：

- 标题和正文均为空。
- 只有链接、乱码、无意义符号。
- 与小红书/抖音内容创作无关。
- 指标异常但无法解释，且没有文本价值。
- 评论中纯表情、纯打卡、无明确洞察的内容。

## 决策字段

每条清洗后记录需要保留：

```yaml
relevance_score: 0-10
viral_score: 0-10
topic_score: 0-10
novelty_score: 0-10
reuse_score: 0-10
noise_score: 0-10
decision: keep | review | archive | discard
reason: 简短原因
```

