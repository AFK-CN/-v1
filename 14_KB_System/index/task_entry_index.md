# 任务入口索引

## 通用使用

- 先读：`知识库入口.md`、`14_KB_System/rules/用户操作台.md`、`14_KB_System/index/controller_routes.json`、`14_KB_System/rules/本机使用速查.md`。
- 默认入口：`@知识库 + 需求`。兼容入口：`knowledge-base + 需求`。
- 总控优先：先用 `controller_routes.json` 判断任务类型，再按本索引读取少量相关文件。

## 内容创作

- 读取：`02_Viral_Methods/`、`03_Topic_Ideas/`、`04_Platform_Knowledge/`、`08_Content_Factory/`。
- 知识成长/自媒体方向额外读取：`06_Sub_KB/知识成长自媒体方法论/`。
- 当用户提到账号名、知识成长、自媒体、赚钱方向、出选题、写文案、口播、对标账号时，先读取：`14_KB_System/index/account_knowledge_index.md`。
- 如命中账号中心，例如姜胡说，继续读取：`06_Sub_KB/知识成长自媒体方法论/账号中心/{账号}/账号索引.md`、`内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`，再按方向读取 `方向方法论总结.md`、`粗扫内容和选题.md`。
- 账号中心调用默认禁止全扫候选区；需要证据时再读取正式单卡，需要核查时再读取逐字稿。
- 内容生成不能直接反写正式知识；可沉淀的规则进入复盘或 Skill proposal。

## 账号学习

- 读取：`14_KB_System/index/account_knowledge_index.md`、`14_KB_System/index/controller_routes.json`、`13_Evolving_Skills/active/视频深度学习Skill_v1.md`。
- 工作流：粗扫 -> 深度学习 -> 候选卡 -> 审核 -> 用户确认 -> 正式账号中心。
- 脚本只能生成候选资产、学习卡、报告和状态；正式账号知识必须经过审核。

## 复盘和自我学习

- 读取：`14_KB_System/rules/周复盘规则.md`、`10_Weekly_Review/`、`09_Performance_Feedback/`、`12_User_Preferences/`。
- Skill 更新只能写入 `13_Evolving_Skills/proposals/`。
- 当用户说“以后都这样”“沉淀成规则”“更新 Skill”时，进入 Skill 沉淀路由，只生成 proposal，不直接改 active。

## 其他项目调用

- 读取：`11_Project_Use/项目调用规则.md`。
- 默认禁止调用：`00_Inbox/`、`数据/`、`99_Archive/`、未确认 Skill 提案。
- 其他项目优先调用全局 `@知识库` Skill；若入口失效，回退到读取 `知识库入口.md`。

## 代码批处理

- 读取：`14_KB_System/runtime/tasks/`、`14_KB_System/runtime/reports/`、`14_KB_System/runtime/logs/`。
- 代码只能生成候选资产和报告，不能直接写正式知识。

## 系统审计

- 日常调用先运行 `.venv/bin/python -m tools.kb.cli --root . health-gate`；该命令禁止遍历正式知识文件。
- 新机器、runtime/凭证缺失、schema 不匹配或旧目录待迁移时运行 `kb init`。
- 读取：`14_KB_System/index/controller_routes.json`、`14_KB_System/index/knowledge_index_summary.md`、`14_KB_System/index/account_knowledge_index.json`、`14_KB_System/config/output_contracts.json`。
- `14_KB_System/index/knowledge_index.json` 是全量机器索引，只在脚本验证、全量审计或用户明确要求时读取。
- 运行：`.venv/bin/python -m tools.kb.cli --root . validate-system` 或 `.venv/bin/python -m tools.kb.cli --root . dashboard`。
- 输出：入口、索引、路由、Skill 包、账号中心、proposal、候选注册表、输出契约和报告状态。
