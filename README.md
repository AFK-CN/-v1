# 本机知识库系统

系统被收敛为三条稳定能力：

1. `content-processing`：接入、下载、解析、清洗、扫描、粗学归类和深学计划。
2. `account-learning`：系统性学习证据，生成经审核的账号 Skill。
3. `content-review`：把生产反馈绑定到真实内容，生成补学或账号 Skill 更新提案。

真正用于内容生产的是各账号中心自己的账号 Skill。账号 Skill 注册表和生产记忆位于 `20_User/`，因此系统可以迁移到其他电脑，而每台电脑保留自己的账号启用状态、选题记录、内容记录和反馈。

入口见 `知识库入口.md`；路由见 `00_System/shareable/index/controller_routes.json`；规则权威源见 `00_System/shareable/rules/规则权威源.md`。

常用命令：

```bash
.venv/bin/python -m tools.kb.cli --root . skill-install
.venv/bin/python -m tools.kb.cli --root . init
.venv/bin/python -m tools.kb.cli --root . user-validate
.venv/bin/python -m tools.kb.cli --root . validate-system
.venv/bin/python -m tools.kb.cli --root . release-gate
.venv/bin/python -m tools.kb.cli --root . distribution-audit
.venv/bin/python -m tools.kb.cli --root . system-export --output /tmp/kb-system
```

新电脑先执行 `skill-install`，把中英文全局入口绑定到当前知识库根目录；再执行 `init` 建立本机用户层和运行状态。

`release-gate` 是本机与 CI 共用的完整发布门，覆盖系统验证、Doctor、用户层、污染边界、分发、正式检索和性能。`distribution-audit` 检查系统分享面是否混入账号、用户数据、本机绝对路径或凭证；`system-export` 按分享清单生成不含知识层和用户层的独立系统包。

可迁移系统包采用 Apache-2.0；许可证只覆盖 `00_System/shareable/share_manifest.json` 选中的系统文件。正式知识、候选、账号资产、用户数据、原始资料、运行产物和归档不在开源授权范围内，具体见 `LICENSE_SCOPE.md`。

`数据/` 和 `00_Inbox/` 中的原始资料只读，默认不展开扫描。
