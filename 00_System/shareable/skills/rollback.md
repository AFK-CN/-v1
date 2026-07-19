# Skill 变更与回滚规则

## 回滚规则

当某个 active Skill 导致输出明显变差，或与你的工作习惯不一致时：

1. 记录问题：哪个 Skill、哪次输出、哪里变差。
2. 从 Git 提交或发布标签找到上一版；系统包不另外保存重复的 history 文档。
3. 将上一版恢复为 active，并重新运行 Skill 和系统验证。
4. 在新的提案中记录回滚原因和证据。
5. 如果需要，重新生成更小范围的提案并等待用户确认。

## 提案中的回滚记录模板

```yaml
date:
skill:
from_version:
to_version:
reason:
evidence:
next_action:
```

## 当前可回滚版本

```yaml
date: 2026-07-19
skill: account-learning
from_version: "2.7"
to_version: "2.8"
reason: 阻断用户认可AI输出被升格为真实性、真实感、母版、黄金正例或后续生图来源
evidence: 00_System/shareable/skills/proposals/account-learning-ai-output-provenance-v2.8.md
next_action: 若v2.8误阻断合法账号原图，恢复v2.7并保留失败报告与候选审计轨迹
```
