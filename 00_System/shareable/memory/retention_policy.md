# 记忆保留与清理策略

- 会话摘要默认进入 `10_Knowledge/evidence/memory/session_summaries/`，用于替代长期保留会话。
- 已解决问题进入 `10_Knowledge/evidence/memory/resolved_issues/`，必须包含问题、处理方式和验证证据。
- 待确认内容进入 `00_System/runtime/memory/pending_session_extracts.jsonl`，不进入正式记忆。
- 用户偏好和长期决策进入 `20_User/syncable/memory/`。
- 本机私有登录、路径和账号状态不进入可同步目录。
- 过期、重复、低价值记忆应合并或归档，不长期堆积。
