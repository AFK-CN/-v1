---
name: content-processing
description: Standardize account materials into clean, traceable evidence, rough topic pools, classifications, and deep-learning plans. Use when Codex needs to ingest links, SQLite records, NAS or local packages; download or parse video, image, text, metadata, transcripts, OCR, and frames; deduplicate and classify content; or prepare an account for deep learning without producing account methods.
---

# 内容处理

把原始资料处理成账号学习 Skill 可以稳定接收的标准证据。不要在本 Skill 中总结账号稳定方法或生产内容。

## 执行

1. 确认账号、资料范围、平台和媒介分支。
2. 按 `references/pipeline.md` 接入链接、SQLite、NAS 或本地资料。
3. 下载或解析正文、元数据、视频、图片、逐字稿、OCR 和抽帧；图文必须按“单条发布记录 + 标题 + 正文 + 话题 + 有序图片组”登记，散图只能进入归属未知的降级轨，工具缺失时明确降级。
4. 按 `references/deduplication.md` 去重，并检查账号归属、合拍、广告、平台项目、低信息和转写风险；结构化 JSON 额外读取 `references/json-cleaning.md`。
5. 完成扫描、粗学归类和方向级完整选题池，不用 Top 清单代替完整池。
6. 输出深学计划、待学习清单、证据坐标和阻塞项；图文计划分别报告发布层完整性、逐图视觉复核状态和组图顺序状态。
7. 运行对应分支状态与验证命令后再交给 `$account-learning`。

## 输出边界

- 原始资料只读。
- 候选资产写入 `10_Knowledge/candidates/`。
- 缓存、日志和状态写入 `00_System/runtime/`。
- 一次性队列和导出写入 `90_Temp/`。
- 不写正式账号中心，不生成正式账号 Skill。

读取 `references/evidence-boundaries.md` 处理证据降级、广告隔离和账号归属；读取 `references/media-branches.md` 选择视频、图文或结构化数据分支。
