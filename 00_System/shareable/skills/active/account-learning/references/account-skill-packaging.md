# 账号 Skill 候选封装

阶段 6 在候选工作流内生成：

```text
account_skill_candidate/
├── SKILL.md
├── UPGRADE_COMPATIBILITY.json
├── references/
│   ├── production.md
│   ├── style.md
│   ├── boundaries.md
│   ├── acceptance.md
│   └── visual-evidence.md（视觉分支必需）
├── account_views/
│   ├── 账号整体方法论.md
│   ├── 内容生产使用说明.md
│   ├── 减少AI味输出规则.md
│   └── 内容输出标准模板.md
└── ACCOUNT_SKILL_MANIFEST.json
```

要求：

- `callable=false`、`formal_write=false`、`user_review_required=true`。
- `UPGRADE_COMPATIBILITY.json` 必须按 `capability-preserving-upgrades.md` 保存稳定能力 ID、升级前后差异、来源文件快照、显式变更、回滚和同账号隔离状态。已有账号的任一旧能力 ID 未进入新清单时，阶段 6 失败。
- 只纳入通过跨卡验证和压力测试的方法。
- 证据不足的结构、表达和验收项明确标记，不补造。
- `account_views/` 是给用户审核的中文可见层，必须逐份声明账号 Skill 版本和底层权威来源。
- `账号整体方法论.md` 聚合定位、正式方法、编排、表达和边界；不新增方法。
- `内容生产使用说明.md` 说明从任务到交付的调用顺序；不得复制其他账号流程。
- `减少AI味输出规则.md` 必须来自本账号表达指纹、结构、动作和边界证据，禁止领域模板换词。
- `内容输出标准模板.md` 将本账号正式生产机制改写为可填写模板，固定单元不可删，可变槽位必须来自本题。
- 新选题生产规则必须调用用户层生产记忆的批量查重接口。
- 视觉分支必须同时交付 `VISUAL_REFERENCE_PROFILE.json`、`visual_reference_candidate/manifest.json` 和 `references/visual-evidence.md`；它们只引用同账号原始证据，不写入系统 Skill。
- `visual-evidence.md` 只说明本账号参考清单、来源类型和生产调用边界；不得把用户认可/拒绝的生成图写成账号方法证据。用户认可 AI 图只能登记为连续性/构图回归基线，不能成为真实感来源、母版、黄金正例或后续生图参考。
- 用户确认后才把 Skill 五件套复制到 `10_Knowledge/formal/accounts/{账号}/skill/`，并把 `account_views/` 四份文件复制到账号根目录。
- 正式升级时同时复制兼容清单；若有替换或弃用，必须绑定同一账号提案中的用户确认与回滚。整体账号升级也按账号分别生成，禁止共享一个跨账号清单。
- 同时在账号根目录写入 `ACCOUNT_SKILL_MANIFEST.json`，账号必须是 `accounts/` 的直属子目录，不得套主题或“账号中心”中间层。
- 完成后由代码重建账号索引并同步用户层注册表。
