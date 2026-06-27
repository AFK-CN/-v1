# 姜胡说全量深度学习审计与正式入库 Implementation Plan（已由通用计划取代）

> 本文件保留为历史执行上下文。当前执行以通用计划为准：`00_System/shareable/docs/superpowers/plans/2026-06-21-video-learning-full-audit-and-ingest-plan.md`。审计、报告、注册表和入库门禁必须 profile 化；姜胡说只是当前默认 profile。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全量审计姜胡说127张深度学习卡，修复偷懒、雷同、草率和证据问题，将通过内容按13方向正式入库，并整体重构账号级调用文件。

**Architecture:** 新增独立审计器，先解析卡片固定章节，再对结构、内容深度、重复片段、模板相似度和证据状态生成机器报告；机器报告只做风险定位，最终结论由逐卡语义复核写入审计清单。扩展现有入库脚本，使其支持一次传入多个已通过方向，先复制正式内容包，再一次性生成账号索引；账号总方法论、调用说明、去AI味规则和输出模板最后基于13方向正式总结人工重构。

**Tech Stack:** Python 3.12 标准库、unittest、Markdown、JSON。

---

### Task 1: 建立全量审计器

**Files:**
- Create: `tools/jianghushuo_learning_audit.py`
- Create: `tests/test_jianghushuo_learning_audit.py`
- Create: `01_Case_Cleaning/video_learning/learned_cards/jianghushuo/audit/`（运行产物目录）

- [ ] **Step 1: 编写章节解析失败测试**

测试构造一张缺少“可复用案例”的卡，调用 `parse_card()` 与 `audit_card()`，断言返回 `structure_errors`，且不得判为 `pass`。

- [ ] **Step 2: 运行单测确认失败**

Run: `.venv/bin/python -m unittest tests.test_jianghushuo_learning_audit -v`
Expected: FAIL，原因是模块不存在。

- [ ] **Step 3: 实现卡片解析和结构门**

实现：

```python
SECTION_TITLES = [
    "为什么值得学习", "核心观点", "内容结构", "表达素材与金句提炼",
    "视频层学习", "可复用案例", "可复用方法论", "可复用模板",
    "证据缺口/后续问题", "入库判断",
]

def parse_card(path: Path) -> CardDocument: ...
def audit_card(card: CardDocument, evidence: EvidenceRecord) -> CardAudit: ...
```

结构门验证8项元数据、10章节、收尾字段、主方向与路径一致性。

- [ ] **Step 4: 编写并实现草率卡检测测试**

测试覆盖：章节为空、章节只有“未明确”、核心观点重复标题、方法论无动作词、模板少于两行、入库判断无具体对象。

- [ ] **Step 5: 编写并实现重复片段检测测试**

实现标准库 TF-IDF/余弦或词项集合相似度，返回：完全重复段、标准化后重复段、同章节高相似卡对。测试要求只换方向名的两张卡被标记，而共享固定章节标题不会误报。

- [ ] **Step 6: 编写并实现证据状态测试**

从 `selected_deep_cards` 和 `video_artifacts/.../transcript.json` 读取证据状态；场景失败但卡片声称具体镜头时标为风险，逐字稿缺失时标为证据缺口，不能自动写成 `unsupported`。

- [ ] **Step 7: 输出机器审计报告**

生成：

- `audit/machine_audit.json`
- `audit/machine_audit.md`
- `audit/similarity_pairs.json`

每条包含 `source_id`、方向、结构问题、深度风险、证据状态、重复卡对、机器建议状态。

- [ ] **Step 8: 运行审计器测试与现有卡片校验**

Run: `.venv/bin/python -m unittest tests.test_jianghushuo_learning_audit tests.test_jianghushuo_card_validator -v`
Expected: 全部通过。

### Task 2: 执行127张卡逐卡审计与修复

**Files:**
- Modify: `01_Case_Cleaning/video_learning/learned_cards/jianghushuo/{方向}/cards/*.md`
- Modify: `01_Case_Cleaning/video_learning/learned_cards/jianghushuo/{方向}/方向方法论总结.md`
- Create: `01_Case_Cleaning/video_learning/learned_cards/jianghushuo/audit/card_audit_register.json`
- Create: `01_Case_Cleaning/video_learning/learned_cards/jianghushuo/audit/全量深度学习审计报告.md`

- [ ] **Step 1: 运行全量机器审计**

Run: `.venv/bin/python tools/jianghushuo_learning_audit.py --root .`
Expected: 输出127条记录和风险排序，不修改卡片。

- [ ] **Step 2: 按方向逐卡语义复核**

每张卡对照标题、selected card、逐字稿和机器风险，记录：

```json
{
  "source_id": "...",
  "direction": "...",
  "decision": "pass|minor_fix|relearn|reject",
  "issues": [],
  "evidence": [],
  "reviewed_sections": [1,2,3,4,5,6,7,8,9,10]
}
```

- [ ] **Step 3: 修复 minor_fix 卡**

只改有证据支持的字段；补充具体动作、边界或证据说明，不增加原视频不存在的案例和数字。

- [ ] **Step 4: 重写 relearn 卡**

重新读取该条逐字稿和精选卡，重写核心观点、结构、案例、方法论、模板与证据缺口；保留 source_id 和原链接。

- [ ] **Step 5: 重跑机器审计和逐卡复验**

Run: `.venv/bin/python tools/jianghushuo_learning_audit.py --root . --register audit/card_audit_register.json`
Expected: 正式候选中没有未处理的 `relearn` 或 `unsupported`。

- [ ] **Step 6: 复核13份方向总结**

检查总结覆盖、跨卡共性、跨方向主归属、方法名自然度、案例证据与边界；必要时重写。

- [ ] **Step 7: 生成全量审计报告**

报告必须列出127条最终状态、修复前问题、修复动作、证据等级和方向汇总；总数与范围文件一致。

### Task 3: 修复多方向正式入库能力

**Files:**
- Modify: `tools/jianghushuo_account_ingest.py`
- Modify: `tests/test_jianghushuo_account_ingest.py`

- [ ] **Step 1: 编写多方向覆盖回归测试**

在临时目录创建两个方向，调用新接口：

```python
result = ingest_directions(root, ["赚钱", "创业"])
```

断言账号索引同时含两个方向，第二次运行不会删除第一个方向，逐字稿计数分别正确。

- [ ] **Step 2: 运行测试确认旧实现失败**

Run: `.venv/bin/python -m unittest tests.test_jianghushuo_account_ingest -v`
Expected: 新测试因缺少 `ingest_directions` 或索引被覆盖而失败。

- [ ] **Step 3: 实现方向复制与账号汇总分离**

新增：

```python
def ingest_direction_package(root: Path, direction: str, approved_ids: set[str] | None = None) -> dict[str, Any]: ...
def ingest_directions(root: Path, directions: list[str], approved_ids: set[str] | None = None) -> dict[str, Any]: ...
```

前者只复制方向包和生成回执；后者汇总所有方向后一次生成账号索引和全局索引，不覆盖其他正式方向。

- [ ] **Step 4: 增加审计门禁**

CLI必须接收 `--audit-register`；只允许 `pass` 或修复后复验通过的 source_id 入库。方向目标数与批准数不一致时终止，不产生半成品。

- [ ] **Step 5: 运行入库与索引测试**

Run: `.venv/bin/python -m unittest tests.test_jianghushuo_account_ingest tests.test_jianghushuo_learning_index -v`
Expected: 全部通过。

### Task 4: 正式入库13方向

**Files:**
- Create/Modify: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/directions/{方向}/`
- Modify: `14_KB_System/index/account_knowledge_index.json`
- Modify: `14_KB_System/index/account_knowledge_index.md`

- [ ] **Step 1: 预演入库**

Run: `.venv/bin/python tools/jianghushuo_account_ingest.py --root . --all-approved --audit-register 01_Case_Cleaning/video_learning/learned_cards/jianghushuo/audit/card_audit_register.json --dry-run`
Expected: 13方向、127卡、逐方向逐字稿数量和0个未批准卡。

- [ ] **Step 2: 执行正式入库**

运行同一命令去掉 `--dry-run`。赚钱方向允许幂等更新，不重复创建方向。

- [ ] **Step 3: 验证方向包**

逐方向核对方法论、粗扫、验收报告、回执、存储清单、cards 和 transcripts；正式卡总数必须等于批准卡总数。

### Task 5: 重构账号级总指引与风格规则

**Files:**
- Modify: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/账号索引.md`
- Modify: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/账号方法论总览.md`
- Modify: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/内容生产使用说明.md`
- Modify: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/减少AI味输出规则.md`
- Modify: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/内容输出标准模板.md`

- [ ] **Step 1: 账号总览重构**

从13份正式方向总结提炼账号总主线、方向关系、优先调用顺序、交叉方向和证据边界，不把13份总结机械拼接。

- [ ] **Step 2: 内容生产路由重构**

按赚钱/创业/机会/自媒体/短视频/表达/学习/成长/人生等任务路由方向，明确单卡、总结、粗扫和逐字稿的调用层级。

- [ ] **Step 3: 去AI味规则重构**

基于127张正式卡归纳真实表达特征：判断先行、具体场景、个人弯路、短句停顿、反问、类比、方法命名和行动收束；加入禁用套话、批量防雷同、事实边界和“不要为了体系感造词”。

- [ ] **Step 4: 输出模板重构**

提供选题、短口播、长口播、方法解释、案例复盘和批量内容模板；每种模板保留 source_id、正式层级和原链接。

### Task 6: 全量终验

**Files:**
- Create: `06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说/正式入库总验收报告.md`

- [ ] **Step 1: 运行所有相关测试**

Run: `.venv/bin/python -m unittest tests.test_jianghushuo_learning_audit tests.test_jianghushuo_card_validator tests.test_jianghushuo_account_ingest tests.test_jianghushuo_learning_index -v`
Expected: 全部通过。

- [ ] **Step 2: 重建学习与账号索引**

Run: `.venv/bin/python tools/jianghushuo_learning_index.py --root .`
Expected: 127唯一 source_id、13方向、0待处理。

- [ ] **Step 3: 执行正式库完整性审计**

核对正式方向数、卡片数、逐字稿数、回执数、总结数、粗扫数、索引状态和路径存在性；任何不一致均视为失败。

- [ ] **Step 4: 执行调用链内容审计**

用三个代表任务验证读取路由：赚钱选题、短视频口播、个人成长方法解释。输出必须能定位正式方向、单卡 source_id 和原链接，不读取候选或原始数据目录。

- [ ] **Step 5: 写正式入库总验收报告**

报告记录127条审计结果、修复数量、正式卡数量、13方向状态、账号文件状态、测试输出和剩余证据限制。

> 说明：当前工作区包含用户既有未提交修改，本计划不自动执行 git 提交、暂存或分支切换；所有变更在现有工作区按路径隔离并逐步验收。
