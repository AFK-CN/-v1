# 内容处理流水线

## 固定阶段

1. 接入：登记账号、来源、平台、媒介和 source_id。
2. 解析：获取正文、元数据、视频、图片、逐字稿、OCR、抽帧和视觉状态；图文把发布记录与有序图片组绑定，正文保留全文而非首行摘要。
3. 清洗：字段标准化、ID 去重、文本指纹去重、噪音和缺失识别。
4. 治理：账号归属、合拍、广告、平台项目、低信息和证据风险分轨。
5. 扫描：方向统计、内容分类、方向级完整粗学与选题池。
6. 选择：只把 Top 和候补作为深学优先级，不截断完整选题池。
7. 计划：生成账号概述、粗学与选题池、deep_learning_plan.json 和待学习清单。

## 机器入口

- SQLite：`sqlite-ingest --dry-run`，确认后 `sqlite-ingest --apply`。
- 视频：通用 scan、select、learn、status 工具。
- 图文：`image-text-ingest -> structure -> scan -> select -> learn -> status`。优先提供 `posts.jsonl` 或 `--posts-file`，每条包含 `source_id`、`title`、`caption/body`、`tags/topics`、`url` 和有序 `images`；无发布清单的散图只能降级登记。
- 候选检索：`search-candidates`。

内容处理完成只表示证据已经可学，不表示账号方法已经成立。
