# 智能体能力与权限规则

当前知识库智能体默认是 `logical_role`：同一次 AI 调用中的逻辑职责，不是独立进程、独立账号或权限隔离边界。

## 登记规则

- 系统层记录智能体 schema、能力规则和路由定义。
- 用户可同步层记录智能体功能表、ID、用途和偏好。
- 用户私有层记录登录状态、账号标签和凭证位置提示。
- 不在任何可分享文件中记录真实密钥、token、密码或 App Secret。

## 能力边界

- `controller` 只负责路由和调度，不直接写正式知识。
- `retriever` 只负责检索，不负责生成内容或写入正式知识。
- `workflow_runner` 可调用本地脚本，但必须遵守原始资料只读和 runtime 写入边界。
- `content_generator` 只能基于正式知识和必要候选证据输出内容，不反写正式知识。
- `skill_evolution` 只能写 proposal，不能直接覆盖 active Skill。
