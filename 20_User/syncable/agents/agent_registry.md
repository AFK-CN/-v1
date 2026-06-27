# 智能体登记表

更新时间：2026-06-27T19:28:22

当前登记表记录智能体功能、ID、能力和记忆边界；真实登录状态放在 `20_User/private/agents/`。

| agent_id | agent_name | agent_type | owner_layer | primary_function | capabilities | entry_command | service | auth_required | auth_status | credential_location_hint | allowed_actions | blocked_actions | memory_scope | last_verified_at | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| controller | 知识库总控智能体 | logical_role | 00_System/shareable | 作为唯一默认入口，识别用户需求、选择路由、调度规划器、检索器、工作流和专用智能体。 | 意图识别、路由选择、任务调度 | @知识库 | local_knowledge_base | no | not_required |  | 按 controller_routes.json 中的路由边界执行 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 可读取记忆总入口和系统记忆规则；写入需走候选 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| planner | 任务规划器 | logical_role | 00_System/shareable | 把复杂需求拆成读取、检索、学习、生成、验证等可执行步骤。 | 任务拆解、步骤规划 | @知识库 | local_knowledge_base | no | not_required |  | 按 controller_routes.json 中的路由边界执行 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 只读必要记忆入口；默认不写长期记忆 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| retriever | 检索器 | logical_role | 00_System/shareable | 只负责查找正式知识、候选资产和证据链，不负责生成内容或写入正式知识。 | 索引检索、候选证据检索 | @知识库 | local_knowledge_base | no | not_required |  | 读取允许范围内的索引、正式知识和候选证据 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 只读必要记忆入口；默认不写长期记忆 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| workflow_runner | 工作流执行器 | logical_role | 00_System/shareable | 调用本地脚本、生成候选报告、维护任务状态和运行日志。 | 本地脚本调用、任务状态维护 | @知识库 | local_knowledge_base | no | not_required |  | 写 runtime、候选报告和任务状态；按规则调用本地脚本 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 只读必要记忆入口；默认不写长期记忆 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| account_knowledge | 账号知识智能体 | logical_role | 00_System/shareable | 维护账号中心、账号学习、方向方法论、内容规则、证据卡和逐字稿索引。 | 账号中心维护、方向知识读取 | @知识库 | local_knowledge_base | no | not_required |  | 按 controller_routes.json 中的路由边界执行 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 只读必要记忆入口；默认不写长期记忆 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| content_generator | 内容生成智能体 | logical_role | 00_System/shareable | 基于正式知识和必要候选证据输出选题、文案、脚本、标题和封面方向。 | 选题、文案、脚本生成 | @知识库 | local_knowledge_base | no | not_required |  | 基于正式知识和候选证据生成内容 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核；不得直接反写正式知识 | 只读必要记忆入口；默认不写长期记忆 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| skill_evolution | Skill 沉淀智能体 | logical_role | 00_System/shareable | 把反复出现的用户纠正和稳定流程写成 proposal，不直接修改 active Skill。 | 规则沉淀 proposal | @知识库 | local_knowledge_base | no | not_required |  | 写 Skill proposal 和复盘建议 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核；不得直接覆盖 active Skill | 可生成规则记忆候选和 Skill proposal |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| review | 复盘智能体 | logical_role | 00_System/shareable | 根据表现数据判断方法论有效、失效和需要补充的证据。 | 截图/表格/表现复盘 | @知识库 | local_knowledge_base | no | not_required |  | 按 controller_routes.json 中的路由边界执行 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 可生成 resolved issue 和复盘记忆候选 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
| auditor | 验证审计器 | logical_role | 00_System/shareable | 检查入口、路由、索引、候选待审、proposal、测试和边界违规。 | 系统验证、边界审计 | @知识库 | local_knowledge_base | no | not_required |  | 按 controller_routes.json 中的路由边界执行 | 不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核 | 可读取记忆总入口和系统记忆规则；写入需走候选 |  | 由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。 |
