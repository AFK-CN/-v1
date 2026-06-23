# @知识库 调用规则

## 使用方式

优先使用：

```text
@知识库
```

如果当前界面不支持中文 Skill 触发，再使用兼容入口：

```text
$knowledge-base
```

## 读取顺序

1. `知识库入口.md`
2. `14_KB_System/rules/用户操作台.md`
3. `14_KB_System/index/controller_routes.json`
4. `14_KB_System/index/task_entry_index.md`
5. `14_KB_System/index/knowledge_index_summary.md`

先用 `controller_routes.json` 判断任务类型，再按任务入口索引读取少量文件。
`knowledge_index.json` 是全量机器索引，只给脚本、全量审计或用户明确要求时使用。

## 总控与高级入口

- 普通用户只需要 `@知识库 + 需求`。
- 高级场景可以显式要求账号学习、Skill 沉淀、系统审计等路由。
- 总控必须说明本次命中的路由、读取的知识层级，以及正式知识/候选证据边界。

## 账号/主题定向检索

如果任务是：

- 按某账号的方式写内容。
- 查某账号是否做过某主题。
- 基于某个主题生成选题。

先使用候选资产检索：

```bash
.venv/bin/python -m tools.kb.cli --root . search-candidates --account "<账号名>" --query "<主题词>" --limit 10
```

如果候选资产没有命中，但用户明确要求从原始资料中找证据，再使用：

```bash
.venv/bin/python -m tools.kb.cli --root . search-candidates --account "<账号名>" --query "<主题词>" --limit 10 --include-raw
```

例如用户问“按李宗恒的方式写高考选题”，应先查 `account=李宗恒 query=高考`，不能只读正式知识后回答没有发现。

## 边界

- 默认禁止全盘扫库。
- 默认禁止读取 `数据/`。
- 默认禁止读取 `00_Inbox/`、`99_Archive/`、未确认 proposals。
- `14_KB_System/assets/` 只作为候选资产，不能直接当正式知识。
- 正式沉淀仍进入 `02/03/04/06/08/13` 等正式目录。
- 内容生成结果不能直接反写正式知识。
- Skill 更新只能先写入 `13_Evolving_Skills/proposals/`。
