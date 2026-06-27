# 通用知识库系统

本项目由两部分组成：

1. 通用知识库系统底座：规则、CLI、Skill、索引、schema、运行状态和模板包。
2. 当前知识资产：使用这套系统后沉淀的方法论、学习卡、选题、账号中心、复盘和用户偏好。

系统层的目标是未来可以剥离成模板包，给其他人快速建立自己的知识库。知识层不能被姜胡说或任何单一账号写死；账号知识只是知识资产的一种。

## 核心原则

- 原始文件不删除、不修改。`数据/` 和 `00_Inbox/` 中的原始资料只读处理。
- 默认不全盘扫库，日常调用先读入口、任务索引和轻量摘要。
- 系统底座和知识资产分离：系统可以分享，知识资产不进入系统模板包。
- 运行状态和本机配置不分享：`00_System/runtime/`、`80_Local/` 默认阻断。
- 候选资产属于知识层，进入 `10_Knowledge/candidates/`，不能当正式知识直接调用。
- Skill 属于系统能力。通用 active Skill、proposal 模板和回滚规则归系统层；账号风格和个人偏好不写入系统级 Skill。
- 正式子库新增前必须先问用户；active Skill 修改前必须先进入 proposal，确认后再生效。

## 目标分层

- `00_System/`：系统层。`shareable/` 可分享，`runtime/` 不可分享。
- `10_Knowledge/`：知识层。`formal/` 放正式知识，`candidates/` 放候选知识，`evidence/` 放证据索引。
- `20_User/`：用户层。`syncable/` 可同步，`private/` 私有不分享。
- `80_Local/`：本机私有配置，放路径、账号标识、NAS、私有开关和密钥引用说明，默认忽略。
- `90_Temp/`：临时层，只放短期输入、草稿、一次性中间文件和临时导出。
- `99_Archive/`：归档层，放历史、废弃、低价值内容索引。
- `数据/`：受保护原始资料，默认不展开、不删除、不分享。

当前系统层已物理收口到 `00_System/shareable/` 和 `00_System/runtime/`。详细结构见 `00_System/shareable/docs/知识库优化目录结构.md`。

## 已迁移目录

- 旧系统目录已物理迁移完成，不再作为根目录里的系统入口。
- `13_Evolving_Skills/` 已迁入 `00_System/shareable/skills/`。
- `02_Viral_Methods/`、`03_Topic_Ideas/`、`04_Platform_Knowledge/`、`06_Sub_KB/`、`08_Content_Factory/`、`09_Performance_Feedback/`、`10_Weekly_Review/` 已迁入 `10_Knowledge/formal/`。
- `05_Sub_KB_Candidates/` 已迁入 `10_Knowledge/candidates/sub_kbs/`。
- `12_User_Preferences/` 已迁入 `20_User/syncable/preferences/`。
- `01_Case_Cleaning/` 下的学习/粗扫候选资产已迁入 `10_Knowledge/candidates/`；状态、报告和缓存已迁入 `00_System/runtime/`。

## 使用入口

新对话或其他项目调用方式见：

- `知识库入口.md`
- `00_System/shareable/rules/用户操作台.md`
- `00_System/shareable/rules/本机使用速查.md`
- `00_System/shareable/rules/使用文档.md`
- `00_System/shareable/docs/project_use/项目调用规则.md`

默认先读 `00_System/shareable/index/controller_routes.json`、`00_System/shareable/index/task_entry_index.md` 和 `10_Knowledge/evidence/index/knowledge_index_summary.md`。`knowledge_index.json` 是全量机器索引，只给脚本、全量审计或明确要求时使用。

## 系统命令

- 初始化运行生命周期：`.venv/bin/python -m tools.kb.cli --root . init`
- 初始化目标分层目录：`.venv/bin/python -m tools.kb.cli --root . init-layers`
- 日常健康门禁：`.venv/bin/python -m tools.kb.cli --root . health-gate`
- 生成索引：`.venv/bin/python -m tools.kb.cli --root . index`
- 系统验收：`.venv/bin/python -m tools.kb.cli --root . validate-system`

## 环境迁移

环境依赖说明见 `ENVIRONMENT.md`。当前本机验证环境是 macOS；迁移到 Windows 家用电脑时，按 `ENVIRONMENT.md` 里的 Windows 迁移环境补齐 Python、FFmpeg/FFprobe、Tesseract 和中文 OCR 语言包后，再运行系统验收命令。

## Skill 入口

对外固定入口源包：

- `00_System/shareable/skill_packages/知识库/`：中文快捷入口，优先用于 `@知识库`
- `00_System/shareable/skill_packages/knowledge-base/`

其他项目优先通过 `@知识库 + 需求` / “知识库” Skill 入口调用，不要直接用文件搜索选一批 Markdown 文件。
