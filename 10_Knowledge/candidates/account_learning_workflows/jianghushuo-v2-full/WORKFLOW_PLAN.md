# 姜胡说账号专业学习计划

- workflow_id: `jianghushuo-v2-full`
- 资料范围: SQLite 姜胡说 598 条；当前正确 NAS /Volumes/AFK/zhishikushuju/dy/accounts/dy_77700555383：548 条证据就绪并按 Skill v2.2 完成分批重学，50 条证据阻断
- 媒介分支: video
- 方法: RIA-TV++ adapted for account learning
- 写入边界: 只写候选学习区，不直接写正式账号中心。

## 七阶段

1. **整体账号理解**：Adler structural, interpretive, critical and applicability analysis。
   产物：`ACCOUNT_OVERVIEW.md`、`ACCOUNT_OVERVIEW.json`。
2. **五视角并行提取**：Independent extraction for positioning, topics, structures, expression and counterexamples。
   产物：`candidates/positioning.jsonl`、`candidates/topics.jsonl`、`candidates/structures.jsonl`、`candidates/expression.jsonl`、`candidates/counterexamples.jsonl`、`REAL_ACCEPTANCE_REPORT_<date>.md`、`REAL_ACCEPTANCE_SUMMARY.json`。
3. **三重验证筛选**：Consolidate five-lens observations into mechanism clusters, then verify cross-context evidence, predictive usefulness and account exclusivity。
   产物：`candidate_clusters.jsonl`、`verified.jsonl`、`rejected.jsonl`。
4. **RIA++ 方法单元构造**：Reading, interpretation, past application, future trigger, execution and boundary。
   产物：`methods/`。
5. **方法链接与知识图谱**：Depends-on, contrasts-with and composes-with relations。
   产物：`METHOD_INDEX.json`、`GLOSSARY.md`。
6. **触发与边界压力测试**：Executed positive, lexical-decoy, edge, cross-scene transfer and sibling-method confusion tests with per-case evidence。
   产物：`methods/*/test-prompts.json`、`methods/*/test-results.json`。
7. **学习交付与入库候选**：Candidate-only digest and promotion manifest; formal ingest remains approval-gated。
   产物：`LEARNING_DIGEST.md`、`promotion_manifest.json`。

## 确认门

- 阶段 0 完成后确认整体账号理解，再进入五视角提取。
- 阶段 2 完成后确认通过与淘汰名单，再构造方法单元。
- 阶段 6 只交付候选和审核清单；正式入库继续走原有审核流程。
