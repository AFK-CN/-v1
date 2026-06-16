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
2. `14_KB_System/index/task_entry_index.md`
3. `14_KB_System/index/knowledge_index.json`

## 边界

- 默认禁止全盘扫库。
- 默认禁止读取 `数据/`。
- 默认禁止读取 `00_Inbox/`、`99_Archive/`、未确认 proposals。
- `14_KB_System/assets/` 只作为候选资产，不能直接当正式知识。
- 正式沉淀仍进入 `02/03/04/06/08/13` 等正式目录。
