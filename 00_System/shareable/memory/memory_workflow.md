# 记忆工作流

## 写入流程

1. 系统先判断当前会话或任务结果是否值得生成记忆候选。
2. 未达到阈值时跳过，不写任何候选。
3. 达到阈值时生成候选记忆。
4. 检查是否包含敏感信息。
5. 判断目标层级。
6. 未确认内容先进入 runtime pending。
7. 用户确认或工具审核通过后写入对应层级。
8. 写入后记录到 `00_System/runtime/memory/memory_write_log.jsonl`。

## 自动候选入口

使用：

```bash
.venv/bin/python -m tools.kb.cli --root . memory --evaluate-text "<会话摘要或任务结论>"
```

该命令只在判断分数达到阈值时写入 `00_System/runtime/memory/pending_session_extracts.jsonl`。

只看判断结果、不写候选：

```bash
.venv/bin/python -m tools.kb.cli --root . memory --evaluate-text "<会话摘要或任务结论>" --dry-run
```

## 日常入口

日常查看只从 `20_User/syncable/memory/记忆总入口.md` 进入。底层文件可分散，但入口必须集中。
