# 视频学习全量审计与正式入库通用设计

日期：2026-06-21
机制范围：所有基于 `profile_id` 的视频深度学习内容包
当前执行 profile：`jianghushuo`（姜胡说）
设计原则：审计标准、报告 schema、入库门禁和总验收文件必须通用；账号只作为配置，不作为规则本身。

## 1. 目标

1. 对某个 `profile_id` 下的深度学习卡做全量审计，确认是否真正完成深度学习。
2. 排除偷懒、套壳、雷同、草率填表、无证据推断和 AI 批量复制痕迹。
3. 对不合格卡执行 `minor_fix`、`relearn` 或 `reject`，复验通过后才允许入库。
4. 将通过审计的方向包写入对应正式账号中心。
5. 入库后重构账号级索引、总方法论、内容生产说明、减少 AI 味规则和输出模板。

## 2. 通用 profile 配置

每个 profile 至少需要以下路径：

| 配置项 | 默认规则 |
|---|---|
| `profile_id` | 账号或资料集唯一 ID，例如 `jianghushuo` |
| `scope_path` | `01_Case_Cleaning/content_rough_scan/{profile_id}/deep_learning_scope.json` |
| `learned_base` | `01_Case_Cleaning/video_learning/learned_cards/{profile_id}` |
| `selected_dir` | `01_Case_Cleaning/video_learning/selected_deep_cards` |
| `artifacts_dir` | `01_Case_Cleaning/video_learning/video_artifacts` |
| `audit_dir` | `{learned_base}/audit` |
| `formal_account_dir` | 正式知识库中的账号中心目录，由入库配置指定 |

姜胡说只是当前 profile：

```text
profile_id = jianghushuo
formal_account_dir = 06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说
```

## 3. 禁止事项

- 不读取或修改 `数据/`、`00_Inbox/` 原始资料。
- 不把字段齐全等同于深度学习合格。
- 不把标题复述、空泛总结或 AI 补写当成证据。
- 不批量复制候选卡到正式区后再补审计。
- 不把视频、音频、分镜图复制到正式热知识区。
- 不删除候选产物和媒体证据。
- 不把审计脚本、审计注册表 schema、报告模板写成某一个账号专用。

## 4. 四道审计门

### 4.1 结构完整门

每张卡必须具备：

- 8 个元数据字段。
- 10 个固定章节。
- 明确的 `source_id`、方向、原视频链接、学习批次和状态。
- `收尾/互动引导` 字段。
- 唯一卡片路径，且与 scope 记录一致。

结构门只证明格式完整，不单独证明深度学习完成。

### 4.2 雷同与偷懒门

对 profile 内全部卡片关键章节做全量比较：

- 核心观点。
- 内容结构。
- 可复用方法论。
- 可复用模板。
- 证据缺口与入库判断。

检查类型：

- 完全重复或仅替换关键词。
- 同方向多卡共享相同模板正文。
- 跨方向卡只有方向字段不同，正文基本相同。
- 高频空话、通用总结、无来源的万能方法论。
- 章节过短、无具体动作、无适用边界。

机器报告只用于定位风险；最终结论必须进入人工审计注册表。

### 4.3 证据一致门

逐卡对照可用证据：

- 核心观点能否被标题、精选卡或逐字稿支持。
- 案例、数字、人物、引用是否来自证据，还是后加推断。
- 视频层判断是否与媒体状态一致；场景分析失败时不得虚构画面细节。
- 金句与互动只提取或明确标为候选提炼。
- 证据不足必须写明，不得用笼统语句掩盖。

证据结论分为：`supported`、`partially_supported`、`unsupported`。出现 `unsupported` 的卡不得入库。

### 4.4 深度与可复用门

合格卡至少同时满足：

- 能讲清视频为什么值得学习，而非只写“热度高”。
- 核心观点包含具体判断，不是标题换写。
- 内容结构能指出开头、转折、论证和行动指向。
- 至少一个可验证案例或明确说明无案例。
- 方法论包含可执行步骤、适用场景或判断标准。
- 模板与本卡方法对应，不是万能口播模板。
- 至少一个事实、证据或适用边界说明。
- 入库判断明确指出可沉淀内容及限制。

## 5. 审计注册表 schema

审计注册表是通用文件，通常位于：

```text
01_Case_Cleaning/video_learning/learned_cards/{profile_id}/audit/card_audit_register.json
```

推荐结构：

```json
{
  "profile_id": "jianghushuo",
  "generated_at": "2026-06-21T00:00:00",
  "items": [
    {
      "source_id": "123",
      "direction": "赚钱",
      "card_path": "01_Case_Cleaning/video_learning/learned_cards/{profile_id}/赚钱/cards/...",
      "decision": "pass",
      "evidence_status": "supported",
      "issues": [],
      "fixes": [],
      "reviewed_sections": [1,2,3,4,5,6,7,8,9,10]
    }
  ]
}
```

只允许四种 `decision`：

| 结果 | 含义 | 入库处理 |
|---|---|---|
| `pass` | 四道门全部通过 | 可入库 |
| `minor_fix` | 存在局部问题 | 修复复验为 `pass` 后才可入库 |
| `relearn` | 套壳、草率、雷同或缺深度 | 重学复验为 `pass` 后才可入库 |
| `reject` | 证据不足或价值不足 | 不入库 |

## 6. 正式入库通用结构

通过审计的方向写入正式账号中心：

```text
{formal_account_dir}/directions/{方向}/
├── 方向方法论总结.md
├── 粗扫内容和选题.md
├── 入库回执.md
├── 存储分层清单.md
├── cards/
│   └── 一视频一文件
└── transcripts/
    ├── {source_id}_transcript.json
    └── {source_id}_transcript.srt
```

规则：

- 只复制审计注册表中 `decision=pass` 的卡。
- 有逐字稿则跟随单卡入库；缺失时在回执注明。
- 视频、音频、分镜和机器中间产物只登记，不复制到正式热知识区。
- 每方向生成回执和存储分层清单。
- 已正式入库方向允许幂等更新，但不得退回候选措辞。

## 7. 账号级文件完善

全部方向入库后统一更新：

1. `账号索引.md`：列出正式方向、状态、单卡数、逐字稿数和入口。
2. `账号方法论总览.md`：形成跨方向总方法论、方向关系、调用优先级和边界。
3. `内容生产使用说明.md`：按任务类型路由方向，明确单卡、总结、粗扫和逐字稿的证据层级。
4. `减少AI味输出规则.md`：从正式卡中提炼真实句式、节奏、案例使用、禁用表达和批量防雷同规则。
5. `内容输出标准模板.md`：覆盖选题、口播、长文案、方法论解释和批量内容，保留证据来源字段。
6. `14_KB_System/index/account_knowledge_index.md/json`：同步账号中心入口。

账号级文件不得只追加方向名；必须基于已正式入库内容重新组织调用逻辑。

## 8. 最终验收条件

只有同时满足以下条件才可宣告某个 profile 完成：

- scope 内每条卡都有明确审计结论。
- 所有正式卡均通过四道审计门，且不存在未修复的 `unsupported`。
- 正式卡、scope、方向总结、逐字稿、回执数量一致或差异已登记。
- 方向状态与账号索引一致。
- 账号级五个核心文件已按正式内容整体重构。
- 已正式入库方向保持正式状态，遗留候选措辞已清理。
- 审计脚本、索引重建、入库门禁和调用链测试均无错误。
