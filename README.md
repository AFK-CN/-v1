# 小红书 + 抖音自媒体创作知识库

本知识库用于沉淀三类资产：

1. 爆款方法论：从小红书、抖音案例和反馈数据中提炼可复用的内容结构、选题机制、表达方式。
2. 选题灵感库：保存可执行、可组合、可按平台改写的选题，不直接堆原始标题。
3. 内容生产与复盘：支持生成图文、短视频脚本、标题、封面方向，并通过周复盘持续进化。

当前第一阶段只服务两个平台：小红书、抖音。后续平台需要等这套流程跑顺后再加入。

## 核心原则

- 原始文件不删除、不修改。`数据/` 和后续 `00_Inbox/` 中的原始资料只读处理。
- 正式知识库不直接堆数据。先清洗、去重、评分，再决定进入方法论、选题库、子知识库或归档索引。
- 子知识库先候选、后确认。AI 可以提出候选子库，但不能直接把候选变成正式子库。
- Skill 先提案、后生效。AI 可以根据你的反馈提出 Skill 更新，但不能直接覆盖 active 规则。
- 其他项目调用知识库时按 `11_Project_Use/项目调用规则.md` 执行，默认不接触原始数据和低价值归档。

## 目录

- `00_Inbox/`：后续新增 JSON、截图、表格的入口。
- `01_Case_Cleaning/`：清洗、去重、评分、案例结构化结果。
- `02_Viral_Methods/`：小红书/抖音爆款方法论。
- `03_Topic_Ideas/`：选题灵感库。
- `04_Platform_Knowledge/`：平台差异、指标解释、内容机制。
- `05_Sub_KB_Candidates/`：待你确认的候选子知识库。
- `06_Sub_KB/`：已确认子知识库。
- `07_Trend_Radar/`：联网检索与热词观察。
- `08_Content_Factory/`：标题、脚本、图文、短视频模板。
- `09_Performance_Feedback/`：发布后的截图、表格、手动反馈。
- `10_Weekly_Review/`：周复盘、方法论更新、下周选题建议。
- `11_Project_Use/`：其他项目调用本知识库的规则。
- `12_User_Preferences/`：你的偏好、修改习惯、正负反馈。
- `13_Evolving_Skills/`：可进化 Skill、提案、历史版本、回滚机制。
- `14_KB_System/`：系统操作层，只放索引、状态、任务、日志、报告和候选资产，不放正式知识。
- `14_KB_System/skill_packages/`：对外调用 Skill 源包，只放入口封装，不放正式知识。
- `99_Archive/`：低价值、无效、重复资料的索引，不放原始删除动作。

## 当前已读原始数据

- `数据/xhs/json/creator_contents_2026-06-13.json`：小红书内容 15 条。
- `数据/douyin/json/creator_contents_2026-06-13.json`：抖音内容 709 条。
- `数据/douyin/json/creator_comments_2026-06-13.json`：抖音评论 5970 条。
- `数据/douyin/json/creator_creators_2026-06-13.json`：抖音创作者 2 条。

第一版候选方向：

- 小红书：美食 / 减脂 / 一人食 / 备餐，当前仍为候选。
- 抖音：知识成长 / 自媒体方法论 / 普通人行动系统，已转为正式子知识库。

## 使用入口

新对话或其他项目调用方式见：

- `知识库入口.md`
- `14_KB_System/rules/用户操作台.md`
- `14_KB_System/rules/本机使用速查.md`
- `14_KB_System/rules/使用文档.md`
- `11_Project_Use/项目调用规则.md`

默认先读 `14_KB_System/index/controller_routes.json` 和 `14_KB_System/index/task_entry_index.md`，按任务精准读取文件。除非你明确要求，其他项目禁止全库扫描，也禁止读取 `数据/`、`00_Inbox/`、`99_Archive/` 和未确认 Skill 提案。

## Skill 入口

对外固定入口源包：

- `14_KB_System/skill_packages/知识库/`：中文快捷入口，优先用于 `@知识库`
- `14_KB_System/skill_packages/knowledge-base/`

其他项目优先通过 `@知识库 + 需求` / “知识库” Skill 入口调用，不要直接用文件搜索选一批 Markdown 文件。该 Skill 默认只读入口、用户操作台、总控路由和索引，再按任务读取少量正式知识文件。若当前界面不识别中文入口，再使用兼容入口 `knowledge-base + 需求`。
