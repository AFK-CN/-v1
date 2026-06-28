# 知识库索引摘要

这是给 Codex 和人工快速判断状态的轻量索引。默认不要读取全量索引 `knowledge_index.json` 或全量审计索引 `知识库总索引.md`。

生成时间：2026-06-28T01:40:15
全量文件数：1593
正式知识条目：477
候选资产条目：934
默认禁止读取边界：6
清理候选：12

## 默认读取顺序

1. `知识库入口.md`
2. `00_System/shareable/rules/用户操作台.md`
3. `00_System/shareable/index/controller_routes.json`
4. `00_System/shareable/index/task_entry_index.md`
5. `10_Knowledge/evidence/index/knowledge_index_summary.md`

## 分层索引

- `knowledge_index.json`：全量机器索引，只给脚本和全量审计使用。
- `knowledge_index_summary.md`：轻量状态摘要，给 Codex 和人工默认查看。
- `task_entry_index.md`：任务入口索引。
- `account_knowledge_index.json/md`：账号中心索引。
- `formal_knowledge_index.json`：正式知识索引。
- `candidate_asset_index.json`：候选资产索引。
- `raw_blocked_index.json`：默认禁止读取目录边界。
- `知识库总索引.md`：全量人类审计索引，默认不读。
