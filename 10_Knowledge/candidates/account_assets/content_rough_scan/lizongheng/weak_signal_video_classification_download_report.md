# 李宗恒弱信号视频判定下载报告

- 状态：blocked_missing_video_url
- 抽样数量：40
- 找到记录：40
- 下载成功：0
- 下载失败：40
- 原因：SQLite 候选记录只有抖音页面链接，没有可直接下载的 `video_url`；当前下载器只支持已有直链或小红书页面解析，不支持抖音页面解析直链。
- 运行报告：`00_System/runtime/reports/video_learning/latest_video_download_report.md`

## 下一步

1. 给这 40 条补充可下载 `video_url`，再重跑下载/转写。
2. 或增加一个抖音页面到视频直链的解析器，再重跑本计划。
3. 在直链缺失前，不应把弱信号内容强行纳入最终深学分类。
