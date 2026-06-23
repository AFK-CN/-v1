# 知识库 Skill 调用规则

## 默认入口

其他项目调用知识库时，先使用 Skill 入口，不要直接 `@` 一堆 Markdown 文件。

默认读取：

1. `知识库入口.md`
2. `14_KB_System/rules/用户操作台.md`
3. `14_KB_System/index/controller_routes.json`
4. `14_KB_System/index/task_entry_index.md`

先用 `controller_routes.json` 判断任务类型，再按任务入口索引读取少量文件。

## 总控与高级入口

- 普通用户只需要 `@知识库 + 需求`。
- 高级场景可以显式要求账号学习、Skill 沉淀、系统审计等路由。
- 总控必须说明本次命中的路由、读取的知识层级，以及正式知识/候选证据边界。

## 按任务读取

- 内容创作：读取 `02_Viral_Methods/`、`03_Topic_Ideas/`、`04_Platform_Knowledge/`、`08_Content_Factory/` 中与任务匹配的文件。
- 知识成长/自媒体：额外读取 `06_Sub_KB/知识成长自媒体方法论/`。
- 复盘：读取 `09_Performance_Feedback/`、`10_Weekly_Review/`、`12_User_Preferences/` 和 active Skill。
- Skill 进化：只能生成 proposal，用户确认后再进入 active。

## 账号/主题定向检索

按账号风格或指定主题生成内容前，先查候选资产：

```bash
.venv/bin/python -m tools.kb.cli --root . search-candidates --account "<账号名>" --query "<主题词>" --limit 10
```

候选资产没有命中且用户要求追溯原始资料时，才加 `--include-raw`。

## 默认禁止

- 禁止全盘扫库。
- 禁止默认读取 `数据/`。
- 禁止默认读取 `00_Inbox/`。
- 禁止默认读取 `99_Archive/`。
- 禁止把 `14_KB_System/assets/` 当作正式知识。
- 禁止把未确认的 proposals 当作已生效规则。
- 内容生成结果不能直接反写正式知识。
- Skill 更新只能先写入 `13_Evolving_Skills/proposals/`。

## 其他项目安装方式

当前仓库维护 Skill 源文件：

```text
/Users/lao_wu/codexAI/知识库/14_KB_System/skill_packages/knowledge-base
```

要让所有项目都出现 `$knowledge-base` / “知识库”入口，需要把这个目录同步到：

```text
/Users/lao_wu/.codex/skills/knowledge-base
```

如果只想在某个项目显示，则同步到该项目：

```text
<项目根目录>/.agents/skills/knowledge-base
```
