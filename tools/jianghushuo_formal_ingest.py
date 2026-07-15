from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows/jianghushuo-v2-full")
FORMAL = Path("10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说")
DOWNGRADE_ROOT = Path(
    "10_Knowledge/candidates/account_assets/downgraded_formal_cards/jianghushuo/2026-07-12"
)
SNAPSHOT_NAME = "account_center_snapshot_pre_v2_2_formal_ingest_2026-07-14"
ACCOUNT_INDEX_JSON = Path("10_Knowledge/evidence/index/account_knowledge_index.json")
ACCOUNT_INDEX_MD = Path("10_Knowledge/evidence/index/account_knowledge_index.md")
REQUIRED_TOP_LEVEL = {
    "账号索引.md",
    "账号概述.md",
    "账号方法论总览.md",
    "账号整体方法论.md",
    "内容生产使用说明.md",
    "减少AI味输出规则.md",
    "内容输出标准模板.md",
    "批量内容验收标准.md",
    "方法组合与交叉验证.md",
    "正式入库总验收报告.md",
    "正式选题母题.md",
    "METHOD_INDEX.json",
    "FORMAL_CARD_INDEX.jsonl",
    "FORMAL_INGEST_RECEIPT.json",
    "deep_learning_plan.json",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    write_text(path, "\n".join(json.dumps(item, ensure_ascii=False) for item in values))


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}[：:]\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def workflow_cards(root: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted((root / WORKFLOW / "batches").glob("batch_*/cards/*.md")):
        text = path.read_text(encoding="utf-8")
        source_id = metadata_value(text, "source_id")
        direction = metadata_value(text, "主方向")
        if not source_id or not direction:
            raise ValueError(f"card missing source_id or direction: {path}")
        if source_id in cards:
            raise ValueError(f"duplicate source_id: {source_id}")
        cards[source_id] = {
            "source_id": source_id,
            "direction": direction,
            "source_url": metadata_value(text, "原内容链接"),
            "candidate_path": path,
            "candidate_relative_path": path.relative_to(root).as_posix(),
            "text": text,
        }
    return cards


def pending_ownership_ids(root: Path) -> set[str]:
    path = root / WORKFLOW / "commercial_learning/COLLABORATION_OWNERSHIP_INDEX.jsonl"
    return {str(item["source_id"]) for item in read_jsonl(path)}


def method_payloads(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    index = read_json(root / WORKFLOW / "METHOD_INDEX.json")
    methods: dict[str, dict[str, Any]] = {}
    for row in index.get("methods", []):
        method_id = str(row["id"])
        method_dir = root / WORKFLOW / "methods" / method_id
        methods[method_id] = {
            "index": row,
            "dir": method_dir,
            "json": read_json(method_dir / "method.json"),
            "md": (method_dir / "METHOD.md").read_text(encoding="utf-8"),
        }
    return index, methods


def preflight(root: Path) -> dict[str, Any]:
    workflow = root / WORKFLOW
    formal = root / FORMAL
    snapshot = root / DOWNGRADE_ROOT / SNAPSHOT_NAME
    staging = formal.parent / f".{formal.name}.v2_2_formal_ingest_staging"
    if not formal.is_dir():
        raise FileNotFoundError(f"formal account center missing: {formal}")
    if snapshot.exists():
        raise FileExistsError(f"snapshot already exists: {snapshot}")
    if staging.exists():
        raise FileExistsError(f"staging already exists: {staging}")

    acceptance = read_json(workflow / "REAL_ACCEPTANCE_SUMMARY.json")
    full_audit = read_json(workflow / "audit/full_relearning_audit.json")
    stage_audit = read_json(workflow / "audit/stage3_6_audit.json")
    pipeline = read_json(workflow / "PIPELINE_STATE.json")
    promotion = read_json(workflow / "promotion_manifest.json")
    if not acceptance.get("ok") or acceptance.get("status") != "passed" or acceptance.get("skill_version") != "2.2":
        raise ValueError("v2.2 real acceptance has not passed")
    if not full_audit.get("ok") or full_audit.get("errors"):
        raise ValueError("full relearning audit has not passed")
    if not stage_audit.get("ok") or not stage_audit.get("all_pressure_cases_passed"):
        raise ValueError("stage 3-6 audit has not passed")
    if pipeline.get("status") != "completed" or any(item.get("status") != "completed" for item in pipeline.get("stages", [])):
        raise ValueError("seven-stage pipeline is not completed")
    if promotion.get("status") != "ready_for_review" or not promotion.get("formal_promotion_requires_explicit_user_approval"):
        raise ValueError("promotion manifest is not awaiting explicit approval")

    cards = workflow_cards(root)
    pending_ids = pending_ownership_ids(root)
    method_index, methods = method_payloads(root)
    expected_ready = int(acceptance["scope"]["evidence_ready"])
    expected_pending = int(acceptance["classification_consistency"]["counts"]["collaboration_ownership"])
    expected_natural = int(acceptance["classification_consistency"]["counts"]["natural_content"])
    if len(cards) != expected_ready or len(pending_ids) != expected_pending:
        raise ValueError("card or ownership-pending count differs from acceptance")
    if len(set(cards) - pending_ids) != expected_natural:
        raise ValueError("natural formal-card count differs from acceptance")
    if not pending_ids <= set(cards):
        raise ValueError("ownership-pending source is missing from cards")
    promoted_ids = {str(item) for item in promotion.get("method_ids", [])}
    indexed_ids = {str(item["id"]) for item in method_index.get("methods", [])}
    if promoted_ids != indexed_ids or indexed_ids != set(methods):
        raise ValueError("method ids disagree across promotion and method index")
    if len(methods) != int(stage_audit["method_count"]):
        raise ValueError("method count differs from stage audit")
    for method_id, item in methods.items():
        if item["json"].get("status") != "verified_candidate" or item["json"].get("callable") is not False:
            raise ValueError(f"method is not a verified candidate: {method_id}")
        for name in ("METHOD.md", "method.json", "test-prompts.json", "test-results.json"):
            if not (item["dir"] / name).is_file():
                raise FileNotFoundError(f"method artifact missing: {method_id}/{name}")

    source_files = sorted(path for path in formal.rglob("*") if path.is_file())
    source_dirs = sorted(path for path in formal.rglob("*") if path.is_dir())
    return {
        "acceptance": acceptance,
        "cards": cards,
        "pending_ids": pending_ids,
        "method_index": method_index,
        "methods": methods,
        "formal": formal,
        "snapshot": snapshot,
        "staging": staging,
        "source_files": source_files,
        "source_dirs": source_dirs,
    }


def formalize_card(text: str, ingested_at: str) -> str:
    if "学习卡契约：unified_three_layer_v2" not in text:
        raise ValueError("card is not unified_three_layer_v2")
    if not re.search(r"^状态：candidate_learned$", text, re.MULTILINE):
        raise ValueError("card is not candidate_learned")
    text = re.sub(r"^状态：candidate_learned$", "状态：formal_evidence_card", text, count=1, flags=re.MULTILINE)
    marker = "状态：formal_evidence_card"
    formal_meta = (
        f"{marker}\n"
        f"正式入库时间：{ingested_at}\n"
        "正式用途：单条证据、内容结构、表达和选题回查\n"
        "方法调用：false（单卡方法候选不直接调用；只调用 methods/ 下 approved_callable 方法）"
    )
    text = text.replace(marker, formal_meta, 1)
    return (
        text.rstrip()
        + "\n\n## 正式入库状态\n\n"
        + "- 本卡已通过 Skill v2.2 单卡契约、引用和批次审计，作为正式证据卡入库。\n"
        + "- 本卡第 10 节仍是单卡方法候选，不因证据卡正式化而成为可调用方法。\n"
        + "- 正式方法只认账号中心 `methods/` 中状态为 `approved_callable` 的方法单元。\n"
    )


def formalize_method_md(text: str, ingested_at: str) -> str:
    old = "状态：`verified_candidate`；调用：`false`；账号范围：`姜胡说`。"
    new = "状态：`approved_callable`；调用：`true`；账号范围：`姜胡说`。"
    if old not in text:
        raise ValueError("method markdown is missing the verified-candidate boundary")
    return (
        text.replace(old, new, 1).rstrip()
        + "\n\n## 正式批准\n\n"
        + f"- 入库时间：{ingested_at}\n"
        + "- 批准依据：用户明确批准正式入库；三重验证和 80/80 压力测试已通过。\n"
        + "- 调用仍须服从本方法的触发信号、do_not_use 和证据边界。\n"
    )


def method_table(method_index: dict[str, Any]) -> list[str]:
    lines = ["| 方法 ID | 正式方法 | 状态 |", "|---|---|---|"]
    for item in method_index.get("methods", []):
        lines.append(f"| `{item['id']}` | {item['title']} | approved_callable |")
    return lines


def direction_summary(direction: str, count: int) -> str:
    return f"""# {direction}方向正式证据说明

- 正式证据卡：{count} 张。
- 状态：`formal_ingested`。
- 方法边界：方向词只用于证据路由，不自动触发任何方法。

## 调用方式

1. 先从本方向正式卡确认原始问题、结构、表达和 source_id。
2. 再按任务的核心因果，从账号级 `methods/` 选择一个 `approved_callable` 方法。
3. 只命中“{direction}”题材词、人物或场景时，不得调用方法。
4. 需要组合时按 `方法组合与交叉验证.md` 执行逐方法消融。

## 证据边界

- 单卡用于证据与案例回查，单卡内部的方法候选不可直接调用。
- 2 条采访/合作归属待核验内容未进入正式方向；50 条缺证据记录未进入正式中心。
- 商品广告和平台项目当前均无明确样本；如后续出现，必须单独分轨。
"""


def top_level_files(
    method_index: dict[str, Any],
    direction_counts: Counter[str],
    formal_card_count: int,
    ingested_at: str,
) -> dict[str, str]:
    method_lines = method_table(method_index)
    direction_rows = [
        f"| {direction} | formal_ingested | {count} | `directions/{direction}/` |"
        for direction, count in sorted(direction_counts.items())
    ]
    relation_rows = [
        f"| `{item['source']}` | {item['type']} | `{item['target']}` | {item['reason']} |"
        for item in method_index.get("relations", [])
    ]
    method_list = "\n".join(f"- `{item['id']}`：{item['title']}" for item in method_index.get("methods", []))
    base = FORMAL.as_posix()
    return {
        "账号索引.md": "\n".join(
            [
                "# 姜胡说账号索引",
                "",
                "用途：从正式账号中心调用 Skill v2.2 重新学习并获批的账号方法与证据，不读取旧降级快照。",
                "",
                "## 固定读取顺序",
                "",
                "1. `账号概述.md`：确认正式状态、范围和未入库例外。",
                "2. `账号方法论总览.md`：选择一个正式方法。",
                "3. `方法组合与交叉验证.md`：检查依赖、组合和消融。",
                "4. `正式选题母题.md`：把正式方法转成一个受众问题、一个冲突和一条受众收益。",
                "5. `内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`：进入单条内容生产。",
                "6. `批量内容验收标准.md`：一次生产多条内容时做结构、证据、利他和长度验收。",
                "7. `directions/{方向}/cards/`：只在需要具体证据时读取。",
                "8. `methods/`：只调用状态为 `approved_callable` 的 10 个方法。",
                "",
                "## 正式方向",
                "",
                "| 方向 | 状态 | 正式证据卡 | 入口 |",
                "|---|---|---:|---|",
                *direction_rows,
                "",
                f"正式证据卡合计：{formal_card_count}；正式方法：{len(method_index.get('methods', []))}。",
            ]
        ),
        "账号概述.md": f"""# 姜胡说账号概述

- 账号：姜胡说
- 平台：抖音
- 正式状态：`formal_ingested_v2_2`
- 正式入库时间：{ingested_at}
- 权威数据源：`/Volumes/AFK/zhishikushuju/dy/accounts/dy_77700555383`
- 计划范围：598；证据就绪：548；正式证据卡：{formal_card_count}；证据阻断：50；归属待核验：2
- 正式方法：{len(method_index.get('methods', []))} 个，全部完成三重验证和压力测试

## 账号定位

把抽象知识转成普通人可执行的学习、成长、内容创作与商业实践路径。内容反复把输入、行动、公开表达、真实问题、反馈、资产化和价值交换连接为可验证系统。

## 正式证据边界

- 546 条自然内容可作为正式证据卡调用。
- 2 条采访/合作内容在说话人与原始来源核验前继续留在候选层。
- 50 条缺视频、有效逐字稿、抽帧或场景证据的记录不进入正式中心。
- 商品广告与平台项目当前没有明确样本，不用讨论广告的内容冒充广告样本。
- 单卡正式化不等于单卡方法候选可调用；正式方法只认 `methods/`。
""",
        "账号方法论总览.md": "\n".join(
            [
                "# 姜胡说账号方法论总览",
                "",
                "以下 10 个方法已通过 Skill v2.2 三重验证、边界审计和压力测试，并经用户明确批准正式调用。",
                "",
                *method_lines,
                "",
                "## 固定调用规则",
                "",
                "- 先按任务核心因果选一个主方法，不按方向词或来源名词触发。",
                "- 需要组合时只使用 `METHOD_INDEX.json` 中的真实关系，并执行逐方法消融。",
                "- 单卡用于证据回查，不能绕过方法触发边界。",
                "- 商业内容、平台项目和归属未清内容先分流，再决定是否调用方法。",
            ]
        ),
        "账号整体方法论.md": """# 姜胡说账号整体方法论

## 核心闭环

`真实问题 -> 结构化判断 -> 最小行动或输出 -> 公开反馈 -> 记录封装 -> 关系、信任或价值交换`

十个正式方法不是十套并行口号，而是这条闭环中的不同判断单元：

- 输入与行动：让输入经过使用和输出；把长期目标改成每天可交付的小过程。
- 理解与表达：用结构模型压缩复杂问题；用生活细节承载抽象观点。
- 验证与产品：从真实问题出发，交付最小结果并根据反馈修正。
- 记录与关系：把过程封装成复利资产，用持续有用内容建立关系，以真实经历积累信任。
- 商业与机会：从规则和资源变化中识别机会，用可验证价值交换判断收入。

## 编排边界

- 一次任务只选择一个主因果方法；支持方法必须让输出产生结构性变化。
- 方法可以跨方向迁移，但人物、场景、道具和题材词不能单独触发。
- 删除某个组合方法后输出没有变化，说明该方法不应保留。
- 任何方法都不承诺爆款、收入或外部结果，只约束判断与执行过程。

## 内容生产编排

- 内容不是先列观点再补例子，而是先让具体的人、事、动作、卡点、转折或反馈完成推进，再提炼一个被证据支撑的判断。
- 常用正文发动机包括人物/项目推进、可核验结果复盘、受众追问续讲、生活场景与案例组、复杂问题与模型案例；一条只选一个主发动机。
- 口语节奏按受众自然疑问推进，下一段回答上一段刚引出的“然后呢、为什么、那我怎么办”。
- 利他闭环必须给出受众第一步、完成标准和常见误用；只让人感叹案例厉害，不算完成。
- 时长服从问题、案例链、解释和行动闭环的完整度，不把统一分钟数或统一字数当成通过标准。
""",
        "内容生产使用说明.md": """# 姜胡说内容生产使用说明

1. 先明确任务要解决的具体问题和目标受众。
2. 从 `METHOD_INDEX.json` 选择一个与核心因果匹配的主方法。
3. 需要证据时读取对应方向的正式单卡，不全扫候选区或 NAS。
4. 用生活细节、真实问题和可检查动作承载抽象观点。
5. 需要组合时只使用索引登记关系，并做逐方法消融。
6. 输出前检查：证据是否可回查、动作是否可执行、边界是否清楚、是否误用归属未清内容。

禁止只替换来源人物、场景、案例或原句；必须迁移可解释的核心机制。商品广告、平台项目和采访合作内容先分轨，不混入自然方法频次。
""",
        "减少AI味输出规则.md": """# 姜胡说减少AI味输出规则

- 先写一个真实问题、具体动作或生活矛盾，再提出抽象概念。
- 不用“认知、成长、价值、复利”等大词自证深度；必须说明它改变了什么判断或行动。
- 不包装完美人设，保留经历中的卡点、试错、反馈和证据边界。
- 每段只推进一个因果，不用同义排比重复结论。
- 行动建议写成最小可交付步骤，并给出完成标准或判停条件。
- 案例只复用问题—行动—反馈结构，不复制来源身份、故事事实和原句。
- 标题可以给结果承诺，但正文必须说明限制条件和验证路径。
- 赚钱类内容先写谁为什么付费、交付什么结果，不先写流量、规模或情绪口号。
- 阅读学习类内容必须落到使用、复述、输出或项目检验，不做书摘堆砌。
- 结尾回到下一步行动或可验证问题，不额外拔高价值观。
""",
        "内容输出标准模板.md": """# 姜胡说内容输出标准模板

## 发布包

- 目标受众与具体问题
- 核心判断：一句可证伪的结论
- 主方法 ID：只选一个 `approved_callable` 方法
- 可选支持方法：说明组合关系与删除后的结构变化
- 发布标题：结果承诺 + 适用限制
- 黄金三秒：具体矛盾、反常识判断或可验证结果
- 正文：问题、关键概念、真实案例、最小行动、反馈标准、边界
- 发布文案与话题：服务同一问题，不用标签代替内容分类
- 证据：正式单卡 source_id 或正式方法 source_refs
- 复用边界：不可复制的人物、经历、原句和外部结果

## 输出前检查

1. 是否命中方法机制，而不只是命中方向词。
2. 是否有具体动作和完成标准。
3. 是否把单条案例误写成稳定规律。
4. 是否误用了采访/合作归属未清内容。
5. 删除支持方法后，结构是否确实发生变化。
""",
        "批量内容验收标准.md": """# 姜胡说批量内容验收标准

用途：一次生产多条选题、口播、文案或短视频脚本时，检查每条是否有真实证据、正文承重结构、自然口语节奏、受众收益和足够差异。硬性失败项优先于总分。

## 1. 触发条件

- 用户要求一次输出多条选题、口播、文案或脚本。
- 需要检查同批内容是否只换关键词、案例装饰化、讲道理过早或长度机械一致。
- 需要把一批选题从母题推进到完整成品，而不是只交付提纲。

## 2. 写稿前每条指纹

每条先登记内部指纹，不进入成品正文：

1. 目标受众与一个具体问题。
2. 正式方法与正式单卡来源。
3. 正文发动机。
4. 入口：人、事、结果、追问、场景或复杂问题。
5. 案例链：原处境、动作、卡点、转折、结果/反馈；无完整故事时标缺失。
6. 一个主要因果判断。
7. 受众第一步、完成标准和常见误用。
8. 时长依据：必须讲清哪些环节，而不是预设统一分钟数。
9. 与同批其他内容的真实差异点。

## 3. 单条硬性失败项

出现任一项，整条重写：

- 没有具体问题、人物、事件、动作、场景或可核验结果，只讲抽象概念。
- 故事只在开头出现一两句，后面变成与案例无关的连续说教。
- 人物/故事型内容没有动作、卡点、转折或反馈，却补造完整经历。
- 没有受众第一步、完成标准或常见误用，讲完只能让人感叹案例厉害。
- 只替换方向名、受众名、案例名、数字或关键词，句子骨架和推进顺序不变。
- 编造第一人称经历、朋友故事、收入、成交、身份、数据、评论反馈或平台机制。
- 把粗扫线索、候选金句或综合提炼写成原视频事实。
- 正文出现账号名、知识库、source_id、方法 ID、来源层级、证据边界等内部生产痕迹。
- 没有可回查的原内容链接，或把归属未清内容写成作者本人经历。
- 为统一时长删掉关键案例环节，或为凑长反复解释同一个观点。

## 4. 批量防偷懒标准

- 每条的“问题 + 来源 + 正文发动机 + 案例链 + 行动”组合必须可区分；文字不同但组合相同，仍算重复。
- 同一正式单卡原则上最多支撑两条内容，且两条的受众问题、正文发动机和行动必须不同。
- 同一种黄金三秒句式、同一个案例、同一种结尾不能连续出现。
- 不要求每批机械覆盖固定方向比例，但必须由任务和正式证据产生真实结构差异。
- 不允许所有内容使用相同段落数、相同推进顺序和近似字数。
- 不允许全部使用“很多人以为……其实……”或“先讲场景一句，再列三点方法”的结构。
- 长短可以不同；差异必须能由问题难度、案例数量、解释需要和行动闭环说明。
- 用户连续观看时若会产生“上一条好像也在说这个”的感觉，即使字面相似度不高，也要重写或错开发。

## 5. 五项评分

总分 100，每项 20 分：

1. **证据真实度**：来源可回查，不编造人物、经历、数据或结果。
2. **正文承重度**：具体过程、动作、卡点、转折和反馈足以支撑判断。
3. **口语自然度**：按听者疑问推进，不靠填充词，不出现报告腔。
4. **受众收益度**：明确第一步、完成标准、边界或常见误用。
5. **同批差异度**：入口、发动机、案例链、解释位置、行动和长度有真实差异。

判定：85 分及以上通过；80-84 分局部修改；80 分以下重写。命中硬性失败项时不看总分。

## 6. 时长验收

- 不再使用“某分钟必须达到固定字数”的统一门槛。
- 先检查四个完成门：问题已回答、案例或证据链已闭环、受众行动能执行、限制与误用已说明。
- 用户限定时长时，优先减少案例数量、补充模型或次要观点，只保留一个主因果；不能把关键环节各压成一句口号。
- 用户未限定时长时，四个完成门通过即可收束；不为对齐同批字数继续加同义观点。
- 验收记录可以保留预计时长，但预计时长只用于排期和剪辑，不作为内容质量的单独通过条件。

## 7. 批量交付验收表

| 条目 | 具体问题 | 来源 | 正文发动机 | 案例链完整度 | 受众行动 | 时长依据 | 差异点 | 分数 | 结论 |
|---|---|---|---|---|---|---|---|---:|---|
| 1 |  |  |  |  |  |  |  |  |  |
""",
        "方法组合与交叉验证.md": "\n".join(
            [
                "# 姜胡说方法组合与交叉验证",
                "",
                "## 已验证关系",
                "",
                "| 方法 | 关系 | 方法 | 证据化原因 |",
                "|---|---|---|---|",
                *relation_rows,
                "",
                "## 强制编排",
                "",
                "- 一个任务只选一个主冲突或主因果方法。",
                "- `depends_on` 必须先完成前置方法；`composes_with` 只表示可组合，不表示每次都组合。",
                "- 每个组合方法都要消融；删除后无结构变化则移除。",
                "- 词汇重合、方向相同、人物相同或场景相同不构成方法关系。",
                "- 商业、平台和归属未清内容先分轨，不能增加自然方法 V1 权重。",
            ]
        ),
        "正式选题母题.md": f"""# 姜胡说正式选题母题

本文件只把 10 个正式方法转成可继续验证的选题母题，不把 548 条阶段 1 topic 观察全部晋升为正式选题。

{method_list}

## 选题卡必填

- 目标受众：只选一类人。
- 具体问题：只解决一个可描述的卡点。
- 来源证据：正式方法 + 至少一张正式单卡；不得只靠方向词造题。
- 真实张力：人物处境、结果差距、行动卡点、受众追问或复杂判断，至少命中一项。
- 正文发动机：人物/项目推进、可核验结果复盘、受众追问续讲、生活场景与案例组、复杂问题与模型案例，五选一。
- 受众收益：第一步、完成标准和最容易误用的地方。
- 时长依据：预计需要几个案例环节和解释单元，不先锁统一分钟数。
- 批量差异：和同批内容在问题、来源、发动机、案例链或行动上有什么不同。

## 使用规则

- 每个母题必须换成新的受众问题、关系和场景，并重新提供证据。
- 方向词不是母题；“成长、赚钱、阅读、自媒体”等只负责路由。
- 标题与案例可以变化，但核心机制、行动步骤和边界必须保持。
- 选题生产前读取正式方法的 A2、E、B 三段；输出后做重复与边界检查。
- 母题不是成品标题。只有补齐具体受众、真实张力、正式来源、正文发动机和受众收益后，才能进入写稿。
- 不生产“一个抽象概念 + 三条方法”的空选题；如果没有具体过程或证据承重，保留为待补证据。
- 批量选题写稿前读取 `批量内容验收标准.md`，先做内部指纹，再决定哪些题进入完整内容。
""",
        "正式入库总验收报告.md": f"""# 姜胡说 Skill v2.2 正式入库总验收报告

- 正式入库时间：{ingested_at}
- 用户批准：已明确批准将旧账号中心整体平移到上次降级目录，并将新学习内容正式入库。
- 计划范围：598；证据就绪：548；正式证据卡：{formal_card_count}；证据阻断：50；归属待核验：2。
- 正式方法：{len(method_index.get('methods', []))} 个，状态均为 `approved_callable`。
- 批次验收：55/55 通过；548/548 张学习卡通过统一契约和引用审计。
- 五视角产出：2740 条；三重验证：10 个方法通过、14 个机制簇拒绝或保留证据门。
- 压力测试：80/80 通过；重复方法体、重复测试提示和高相似卡对均为 0。

## 正式边界

- 546 张自然内容卡作为正式证据卡，可用于事实、结构、表达和案例回查。
- 单卡内的方法候选仍不可调用；正式方法只认 `methods/` 中的 `approved_callable` 状态。
- 2 张采访/合作归属未清卡继续留在候选层；50 条缺证据记录继续阻断。
- 商品广告和平台项目当前没有明确样本；后续新增时必须单独分轨。
- 正式入库不证明任何方法必然带来播放、收入或外部经营结果。

## 审计来源

- 候选完成审计：`evidence/FINAL_COMPLETION_AUDIT.md`
- 全量反偷懒审计：`evidence/full_relearning_audit.md`
- 真实验收：`evidence/REAL_ACCEPTANCE_REPORT_2026-07-14.md`
- 机器回执：`FORMAL_INGEST_RECEIPT.json`
""",
    }


def build_account_index_entry(direction_counts: Counter[str], formal_card_count: int) -> dict[str, Any]:
    base = FORMAL.as_posix()
    directions = [
        {
            "direction": direction,
            "status": "formal_ingested_v2_2",
            "card_count": count,
            "transcript_file_count": 0,
            "formal_direction_dir": f"{base}/directions/{direction}",
        }
        for direction, count in sorted(direction_counts.items())
    ]
    layers = [
        {"layer": "account_status_overview", "path": f"{base}/账号概述.md", "description": "Skill v2.2 正式状态、范围和证据边界。"},
        {"layer": "account_overview", "path": f"{base}/账号方法论总览.md", "description": "10 个正式可调用方法入口。"},
        {"layer": "account_summary", "path": f"{base}/账号整体方法论.md", "description": "账号闭环、方法编排和边界。"},
        {"layer": "content_usage", "path": f"{base}/内容生产使用说明.md", "description": "内容生产固定读取顺序。"},
        {"layer": "anti_ai_style", "path": f"{base}/减少AI味输出规则.md", "description": "由新学习方法导出的表达约束。"},
        {"layer": "account_content_template", "path": f"{base}/内容输出标准模板.md", "description": "正式内容交付模板。"},
        {"layer": "formal_topic_archetypes", "path": f"{base}/正式选题母题.md", "description": "把正式方法转成具体问题、正文发动机和受众收益的选题入口。"},
        {"layer": "batch_content_acceptance", "path": f"{base}/批量内容验收标准.md", "description": "批量选题与内容的证据、结构、利他、差异和时长验收。"},
        {"layer": "method_index", "path": f"{base}/METHOD_INDEX.json", "description": "正式方法和关系机器索引。"},
        {"layer": "formal_card_index", "path": f"{base}/FORMAL_CARD_INDEX.jsonl", "description": f"{formal_card_count} 张正式证据卡机器索引。"},
    ]
    for item in directions:
        direction = item["direction"]
        direction_base = item["formal_direction_dir"]
        layers.extend(
            [
                {"layer": "direction_method", "direction": direction, "path": f"{direction_base}/方向正式证据说明.md", "description": "方向证据路由与方法边界。"},
                {"layer": "single_cards", "direction": direction, "path": f"{direction_base}/cards", "description": "Skill v2.2 正式证据卡。"},
            ]
        )
    return {
        "account_id": "jianghushuo",
        "account_name": "姜胡说",
        "platform": "抖音",
        "formal_account_dir": base,
        "formal_status": "formal_ingested_v2_2",
        "formal_card_count": formal_card_count,
        "formal_method_count": 10,
        "directions": directions,
        "knowledge_layers": layers,
    }


def render_account_index_md(payload: dict[str, Any]) -> str:
    lines = ["# 账号知识总索引", "", "| 账号 | 平台 | 正式目录 | 已入库方向 |", "|---|---|---|---|"]
    for account in payload.get("accounts", []):
        directions = "、".join(item["direction"] for item in account.get("directions", []))
        lines.append(f"| {account['account_name']} | {account['platform']} | {account['formal_account_dir']} | {directions} |")
    return "\n".join(lines) + "\n"


def update_account_indexes(root: Path, direction_counts: Counter[str], formal_card_count: int) -> None:
    path = root / ACCOUNT_INDEX_JSON
    payload = read_json(path)
    accounts = [item for item in payload.get("accounts", []) if item.get("account_id") != "jianghushuo"]
    accounts.append(build_account_index_entry(direction_counts, formal_card_count))
    accounts.sort(key=lambda item: item.get("account_name", ""))
    payload["generated_at"] = now_iso()
    payload["accounts"] = accounts
    write_json(path, payload)
    write_text(root / ACCOUNT_INDEX_MD, render_account_index_md(payload))


def build_staging(root: Path, state: dict[str, Any], ingested_at: str) -> dict[str, Any]:
    staging: Path = state["staging"]
    cards: dict[str, dict[str, Any]] = state["cards"]
    pending_ids: set[str] = state["pending_ids"]
    formal_cards = [item for source_id, item in sorted(cards.items()) if source_id not in pending_ids]
    direction_counts: Counter[str] = Counter(item["direction"] for item in formal_cards)
    method_index = json.loads(json.dumps(state["method_index"], ensure_ascii=False))
    method_index["schema_version"] = "2.2"
    method_index["status"] = "formal_ingested"
    method_index["formal_ingested_at"] = ingested_at
    method_index["methods"] = [dict(item, status="approved_callable", callable=True) for item in method_index["methods"]]

    staging.mkdir(parents=True)
    for name, content in top_level_files(method_index, direction_counts, len(formal_cards), ingested_at).items():
        write_text(staging / name, content)

    card_index: list[dict[str, Any]] = []
    for item in formal_cards:
        target = staging / "directions" / item["direction"] / "cards" / f"douyin_{item['source_id']}.md"
        write_text(target, formalize_card(item["text"], ingested_at))
        card_index.append(
            {
                "source_id": item["source_id"],
                "direction": item["direction"],
                "status": "formal_evidence_card",
                "callable_as_evidence": True,
                "single_card_method_callable": False,
                "source_url": item["source_url"],
                "formal_path": (FORMAL / target.relative_to(staging)).as_posix(),
                "candidate_source": item["candidate_relative_path"],
            }
        )
    write_jsonl(staging / "FORMAL_CARD_INDEX.jsonl", card_index)
    for direction, count in sorted(direction_counts.items()):
        write_text(staging / "directions" / direction / "方向正式证据说明.md", direction_summary(direction, count))

    write_json(staging / "METHOD_INDEX.json", method_index)
    for method_id, item in state["methods"].items():
        target = staging / "methods" / method_id
        write_text(target / "METHOD.md", formalize_method_md(item["md"], ingested_at))
        payload = json.loads(json.dumps(item["json"], ensure_ascii=False))
        payload.update(
            {
                "status": "approved_callable",
                "callable": True,
                "knowledge_layer": "formal",
                "formal_ingested_at": ingested_at,
                "approval_basis": "2026-07-14 user explicit formal-ingest approval after Skill v2.2 audit",
            }
        )
        write_json(target / "method.json", payload)
        shutil.copy2(item["dir"] / "test-prompts.json", target / "test-prompts.json")
        shutil.copy2(item["dir"] / "test-results.json", target / "test-results.json")

    glossary = (root / WORKFLOW / "GLOSSARY.md").read_text(encoding="utf-8")
    write_text(staging / "GLOSSARY.md", glossary.replace("候选方法术语", "正式方法术语", 1))
    evidence_dir = staging / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for relative in (
        "REAL_ACCEPTANCE_SUMMARY.json",
        "REAL_ACCEPTANCE_REPORT_2026-07-14.md",
        "REAL_ACCEPTANCE_MANUAL_VISUAL_REVIEW.md",
        "FINAL_COMPLETION_AUDIT.json",
        "FINAL_COMPLETION_AUDIT.md",
        "audit/full_relearning_audit.json",
        "audit/full_relearning_audit.md",
        "audit/stage2_clustering_audit.json",
        "audit/stage3_6_audit.json",
    ):
        source = root / WORKFLOW / relative
        target = evidence_dir / Path(relative).name
        shutil.copy2(source, target)
    write_text(
        evidence_dir / "README.md",
        """# 晋升前学习审计证据

本目录保存 Skill v2.2 在候选交付阶段形成的原始审计快照，因此其中会保留 `formal_write=false`、`callable=false` 和“等待正式晋升”等历史措辞。

这些文件只证明晋升前候选质量，不代表当前状态。当前正式状态只认账号中心根目录的 `FORMAL_INGEST_RECEIPT.json`、`正式入库总验收报告.md`，以及候选工作流中的 `PROMOTION_STATUS.json` 和 `FORMAL_PROMOTION_AUDIT.md`。
""",
    )

    plan = {
        "schema_version": "2.2",
        "status": "formal_ingested",
        "account_name": "姜胡说",
        "account_id": "dy_77700555383",
        "planned_source_count": 598,
        "evidence_ready_count": 548,
        "formal_evidence_card_count": len(formal_cards),
        "ownership_pending_candidate_count": len(pending_ids),
        "evidence_blocked_count": 50,
        "formal_method_count": len(state["methods"]),
        "formal_ingested_at": ingested_at,
        "source_workflow": WORKFLOW.as_posix(),
        "authoritative_nas": "/Volumes/AFK/zhishikushuju/dy/accounts/dy_77700555383",
    }
    write_json(staging / "deep_learning_plan.json", plan)
    receipt = {
        "ok": True,
        "schema_version": "2.2",
        "status": "formal_ingested",
        "account_name": "姜胡说",
        "formal_account_dir": FORMAL.as_posix(),
        "ingested_at": ingested_at,
        "counts": {
            "evidence_ready_cards": 548,
            "formal_evidence_cards": len(formal_cards),
            "ownership_pending_candidate_cards": len(pending_ids),
            "evidence_blocked": 50,
            "formal_methods": len(state["methods"]),
        },
        "excluded_candidate_source_ids": sorted(pending_ids),
        "source_acceptance_sha256": sha256(root / WORKFLOW / "REAL_ACCEPTANCE_SUMMARY.json"),
        "source_full_audit_sha256": sha256(root / WORKFLOW / "audit/full_relearning_audit.json"),
        "previous_account_center_snapshot": (DOWNGRADE_ROOT / SNAPSHOT_NAME).as_posix(),
        "user_confirmation": "2026-07-14 explicit request to move the current Jianghushuo account center into the previous downgrade folder and formally ingest the Skill v2.2 learning",
    }
    write_json(staging / "FORMAL_INGEST_RECEIPT.json", receipt)
    return {
        "formal_cards": formal_cards,
        "direction_counts": direction_counts,
        "method_index": method_index,
        "receipt": receipt,
    }


def validate_staging(state: dict[str, Any], built: dict[str, Any]) -> dict[str, Any]:
    staging: Path = state["staging"]
    missing = sorted(name for name in REQUIRED_TOP_LEVEL if not (staging / name).is_file())
    cards = sorted(staging.glob("directions/*/cards/*.md"))
    method_jsons = sorted(staging.glob("methods/*/method.json"))
    method_mds = sorted(staging.glob("methods/*/METHOD.md"))
    errors: list[str] = []
    if missing:
        errors.append(f"missing_top_level:{','.join(missing)}")
    if len(cards) != 546:
        errors.append(f"formal_card_count:{len(cards)}")
    if len(method_jsons) != 10 or len(method_mds) != 10:
        errors.append(f"formal_method_count:{len(method_jsons)}/{len(method_mds)}")
    for path in cards:
        text = path.read_text(encoding="utf-8")
        if "状态：formal_evidence_card" not in text or "方法调用：false" not in text:
            errors.append(f"bad_formal_card:{path.name}")
    for path in method_jsons:
        payload = read_json(path)
        if payload.get("status") != "approved_callable" or payload.get("callable") is not True:
            errors.append(f"bad_formal_method:{path.parent.name}")
    staged_ids = {metadata_value(path.read_text(encoding="utf-8"), "source_id") for path in cards}
    if staged_ids & state["pending_ids"]:
        errors.append("ownership_pending_card_entered_formal")
    if len(staged_ids) != len(cards):
        errors.append("duplicate_or_missing_formal_source_id")
    return {
        "ok": not errors,
        "errors": errors,
        "formal_card_count": len(cards),
        "formal_method_count": len(method_jsons),
        "direction_count": len(built["direction_counts"]),
    }


def snapshot_records(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    formal: Path = state["formal"]
    snapshot_relative = DOWNGRADE_ROOT / SNAPSHOT_NAME
    return [
        {
            "source": path.relative_to(root).as_posix(),
            "snapshot": (snapshot_relative / path.relative_to(formal)).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in state["source_files"]
    ]


def update_downgrade_metadata(
    root: Path,
    state: dict[str, Any],
    records: list[dict[str, Any]],
    ingested_at: str,
) -> dict[str, Any]:
    downgrade_root = root / DOWNGRADE_ROOT
    snapshot = state["snapshot"]
    verified = all((root / item["snapshot"]).is_file() and sha256(root / item["snapshot"]) == item["sha256"] for item in records)
    manifest = {
        "schema_version": "2.2",
        "account_id": "jianghushuo",
        "status": "full_account_center_snapshot_verified",
        "knowledge_layer": "candidate_knowledge",
        "callable": False,
        "snapshot_at": ingested_at,
        "source_account_dir": FORMAL.as_posix(),
        "snapshot_dir": (DOWNGRADE_ROOT / SNAPSHOT_NAME).as_posix(),
        "file_count": len(records),
        "directory_count": len(state["source_dirs"]),
        "total_size_bytes": sum(item["size_bytes"] for item in records),
        "all_hashes_verified": verified,
        "entries": records,
    }
    write_json(downgrade_root / "account_center_snapshot_manifest.json", manifest)
    old_manifest_path = downgrade_root / "downgrade_manifest.json"
    old_manifest = read_json(old_manifest_path)
    old_manifest.update(
        {
            "status": "downgraded_retained_after_v2_2_formal_promotion",
            "formal_callable": False,
            "formal_write_allowed": False,
            "callable": False,
            "system_pending_item": False,
            "pending_action": "resolved_keep_downgraded",
            "resolution_at": ingested_at,
            "full_account_center_snapshot": {
                "path": manifest["snapshot_dir"],
                "manifest": (DOWNGRADE_ROOT / "account_center_snapshot_manifest.json").as_posix(),
                "file_count": len(records),
                "all_hashes_verified": verified,
            },
        }
    )
    write_json(old_manifest_path, old_manifest)
    readme = (downgrade_root / "README.md").read_text(encoding="utf-8").rstrip()
    readme = readme.replace(
        "- 状态：已按 Skill v2.2 完成重学和 Codex 审计，继续作为系统待处理候选，等待正式晋升决策",
        "- 状态：正式晋升决策已完成；旧卡和旧账号中心继续作为候选历史备份，不恢复调用",
    ).replace(
        "- 调用边界：本备份不可作为正式知识或可调用方法使用；任何正式晋升都需要新的显式批准。",
        "- 调用边界：本备份不可作为正式知识或可调用方法使用；当前正式知识只认新账号中心的 v2.2 入库回执。",
    )
    section = f"""

## 账号中心整体平移快照

- 快照时间：{ingested_at}
- 原账号中心文件：{len(records)} 个；目录：{len(state['source_dirs'])} 个。
- 快照目录：`{manifest['snapshot_dir']}`
- 哈希清单：`{(DOWNGRADE_ROOT / 'account_center_snapshot_manifest.json').as_posix()}`
- 状态：已逐文件校验；继续作为候选历史备份，不进入正式调用。
- 后续：Skill v2.2 新学习内容已写入新的正式账号中心。
"""
    if "## 账号中心整体平移快照" not in readme:
        write_text(downgrade_root / "README.md", readme + section)
    return manifest


def update_workflow_after_promotion(
    root: Path,
    state: dict[str, Any],
    built: dict[str, Any],
    snapshot_manifest: dict[str, Any],
    ingested_at: str,
) -> dict[str, Any]:
    workflow = root / WORKFLOW
    receipt = built["receipt"]
    receipt["snapshot_file_count"] = snapshot_manifest["file_count"]
    receipt["snapshot_all_hashes_verified"] = snapshot_manifest["all_hashes_verified"]
    write_json(root / FORMAL / "FORMAL_INGEST_RECEIPT.json", receipt)
    write_json(workflow / "FORMAL_INGEST_RECEIPT.json", receipt)
    promotion_status = {
        "schema_version": "2.2",
        "workflow_id": "jianghushuo-v2-full",
        "status": "formal_ingested",
        "promoted_at": ingested_at,
        "formal_account_dir": FORMAL.as_posix(),
        "formal_card_count": 546,
        "formal_method_count": 10,
        "callable_method_count": 10,
        "candidate_only_ownership_pending": sorted(state["pending_ids"]),
        "evidence_blocked_count": 50,
        "previous_account_center_snapshot": snapshot_manifest["snapshot_dir"],
        "user_approval": True,
    }
    write_json(workflow / "PROMOTION_STATUS.json", promotion_status)

    pending_path = workflow / "SYSTEM_PENDING_ITEMS.json"
    pending = read_json(pending_path)
    for item in pending.get("items", []):
        if item.get("id") == "legacy_cards_promotion_decision":
            item.update(
                {
                    "status": "resolved_keep_downgraded",
                    "callable": False,
                    "resolved_at": ingested_at,
                    "next_action": "已决定保留旧卡和旧账号中心为候选历史快照；新 v2.2 内容已正式入库。",
                }
            )
    pending["generated_at"] = ingested_at
    pending["status"] = "open_evidence_and_attribution_items_remain_candidate_only"
    write_json(pending_path, pending)
    write_text(
        workflow / "SYSTEM_PENDING_ITEMS.md",
        f"""# 姜胡说 v2.2 系统待处理事项

生成时间：{ingested_at}

## 已解决

- 旧卡与旧账号中心处理：127 张旧卡及原账号中心已保留在候选降级快照；新 v2.2 内容已正式入库。

## 仍待处理

| 事项 | 数量 | 状态 | 调用边界 |
| --- | ---: | --- | --- |
| 缺证据记录补证 | 50 | pending_evidence | 补齐前不可学习、不可调用 |
| 采访/合作归属核验 | 2 | pending_attribution | 核验前保留候选，不进入正式账号中心 |

正式入库回执：`FORMAL_INGEST_RECEIPT.json`；正式晋升状态：`PROMOTION_STATUS.json`。
""",
    )
    audit = {
        "schema_version": "2.2",
        "workflow_id": "jianghushuo-v2-full",
        "generated_at": ingested_at,
        "ok": True,
        "requirements": {
            "old_account_center_moved_to_last_downgrade_folder": snapshot_manifest["all_hashes_verified"],
            "new_v2_2_cards_formally_ingested": 546,
            "new_v2_2_methods_formally_ingested": 10,
            "methods_approved_callable": 10,
            "ownership_pending_kept_candidate_only": 2,
            "evidence_blocked_kept_candidate_only": 50,
        },
        "snapshot_manifest": (DOWNGRADE_ROOT / "account_center_snapshot_manifest.json").as_posix(),
        "formal_receipt": (FORMAL / "FORMAL_INGEST_RECEIPT.json").as_posix(),
    }
    write_json(workflow / "FORMAL_PROMOTION_AUDIT.json", audit)
    write_text(
        workflow / "FORMAL_PROMOTION_AUDIT.md",
        f"""# 姜胡说 Skill v2.2 正式晋升审计

- 时间：{ingested_at}
- 结论：通过。
- 原账号中心：{snapshot_manifest['file_count']} 个文件已整体平移并逐文件哈希校验。
- 正式证据卡：546 张。
- 正式方法：10 个，状态均为 `approved_callable`。
- 候选保留：2 张采访/合作归属待核验卡；50 条缺证据记录。
- 旧卡：127 张继续保留在上次降级目录，不恢复调用。

本次正式晋升由用户明确批准；候选工作流原始阶段产物继续保留，不反向改写为正式状态。
""",
    )
    return audit


def ingest(root: Path, apply: bool = False) -> dict[str, Any]:
    root = root.resolve()
    state = preflight(root)
    records = snapshot_records(root, state)
    preview = {
        "ok": True,
        "apply": apply,
        "workflow_id": "jianghushuo-v2-full",
        "source_account_center": FORMAL.as_posix(),
        "snapshot_target": (DOWNGRADE_ROOT / SNAPSHOT_NAME).as_posix(),
        "source_file_count": len(records),
        "source_directory_count": len(state["source_dirs"]),
        "candidate_card_count": len(state["cards"]),
        "formal_card_count": len(state["cards"]) - len(state["pending_ids"]),
        "ownership_pending_candidate_count": len(state["pending_ids"]),
        "formal_method_count": len(state["methods"]),
    }
    if not apply:
        return preview

    ingested_at = now_iso()
    built = build_staging(root, state, ingested_at)
    staging_validation = validate_staging(state, built)
    if not staging_validation["ok"]:
        raise ValueError(f"staging validation failed: {staging_validation['errors']}")

    formal: Path = state["formal"]
    snapshot: Path = state["snapshot"]
    staging: Path = state["staging"]
    old_index_json = (root / ACCOUNT_INDEX_JSON).read_bytes()
    old_index_md = (root / ACCOUNT_INDEX_MD).read_bytes()
    swapped = False
    try:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        os.replace(formal, snapshot)
        os.replace(staging, formal)
        swapped = True
        snapshot_manifest = update_downgrade_metadata(root, state, records, ingested_at)
        if not snapshot_manifest["all_hashes_verified"]:
            raise RuntimeError("snapshot hash verification failed")
        update_account_indexes(root, built["direction_counts"], len(built["formal_cards"]))
        promotion_audit = update_workflow_after_promotion(
            root, state, built, snapshot_manifest, ingested_at
        )
    except Exception:
        (root / ACCOUNT_INDEX_JSON).write_bytes(old_index_json)
        (root / ACCOUNT_INDEX_MD).write_bytes(old_index_md)
        if swapped and formal.exists() and snapshot.exists():
            failed = formal.parent / f".{formal.name}.v2_2_failed_formal"
            if failed.exists():
                raise RuntimeError(f"rollback target already exists: {failed}")
            os.replace(formal, failed)
            os.replace(snapshot, formal)
        raise

    return {
        **preview,
        "ingested_at": ingested_at,
        "staging_validation": staging_validation,
        "snapshot_all_hashes_verified": snapshot_manifest["all_hashes_verified"],
        "snapshot_manifest": (DOWNGRADE_ROOT / "account_center_snapshot_manifest.json").as_posix(),
        "formal_receipt": (FORMAL / "FORMAL_INGEST_RECEIPT.json").as_posix(),
        "promotion_audit": promotion_audit,
    }


def validate_current(root: Path) -> dict[str, Any]:
    root = root.resolve()
    formal = root / FORMAL
    workflow = root / WORKFLOW
    downgrade_root = root / DOWNGRADE_ROOT
    errors: list[str] = []

    receipt_path = formal / "FORMAL_INGEST_RECEIPT.json"
    snapshot_manifest_path = downgrade_root / "account_center_snapshot_manifest.json"
    promotion_path = workflow / "PROMOTION_STATUS.json"
    for path in (receipt_path, snapshot_manifest_path, promotion_path):
        if not path.is_file():
            errors.append(f"missing:{path.relative_to(root)}")
    if errors:
        return {"ok": False, "errors": errors}

    receipt = read_json(receipt_path)
    snapshot_manifest = read_json(snapshot_manifest_path)
    promotion = read_json(promotion_path)
    formal_cards = sorted(formal.glob("directions/*/cards/*.md"))
    formal_methods = sorted(formal.glob("methods/*/method.json"))
    formal_method_mds = sorted(formal.glob("methods/*/METHOD.md"))
    card_index = read_jsonl(formal / "FORMAL_CARD_INDEX.jsonl")
    pending_ids = pending_ownership_ids(root)
    formal_ids: set[str] = set()

    if len(formal_cards) != 546:
        errors.append(f"formal_card_count:{len(formal_cards)}")
    if len(card_index) != 546:
        errors.append(f"formal_card_index_count:{len(card_index)}")
    for path in formal_cards:
        text = path.read_text(encoding="utf-8")
        source_id = metadata_value(text, "source_id")
        if not source_id:
            errors.append(f"missing_source_id:{path.relative_to(root)}")
            continue
        if source_id in formal_ids:
            errors.append(f"duplicate_formal_source_id:{source_id}")
        formal_ids.add(source_id)
        if "状态：formal_evidence_card" not in text:
            errors.append(f"bad_card_status:{source_id}")
        if "学习卡契约：unified_three_layer_v2" not in text:
            errors.append(f"bad_card_contract:{source_id}")
        if "方法调用：false" not in text:
            errors.append(f"single_card_method_boundary_missing:{source_id}")
    if formal_ids & pending_ids:
        errors.append("ownership_pending_source_entered_formal")

    indexed_ids = {str(item.get("source_id", "")) for item in card_index}
    if indexed_ids != formal_ids:
        errors.append("formal_card_index_ids_mismatch")
    for item in card_index:
        path = root / str(item.get("formal_path", ""))
        if not path.is_file():
            errors.append(f"formal_card_index_path_missing:{item.get('source_id')}")
        if item.get("status") != "formal_evidence_card" or item.get("single_card_method_callable") is not False:
            errors.append(f"formal_card_index_boundary_bad:{item.get('source_id')}")

    if len(formal_methods) != 10 or len(formal_method_mds) != 10:
        errors.append(f"formal_method_count:{len(formal_methods)}/{len(formal_method_mds)}")
    for path in formal_methods:
        payload = read_json(path)
        method_id = str(payload.get("id", path.parent.name))
        if payload.get("status") != "approved_callable" or payload.get("callable") is not True:
            errors.append(f"formal_method_boundary_bad:{method_id}")
        if not set(str(item) for item in payload.get("source_refs", [])) <= formal_ids:
            errors.append(f"formal_method_uses_nonformal_source:{method_id}")
        result_path = path.parent / "test-results.json"
        if not result_path.is_file():
            errors.append(f"method_test_results_missing:{method_id}")
        else:
            result = read_json(result_path)
            if not result.get("all_passed") and result.get("pass_rate") != 1.0:
                errors.append(f"method_pressure_test_not_passed:{method_id}")

    method_index = read_json(formal / "METHOD_INDEX.json")
    if method_index.get("status") != "formal_ingested":
        errors.append("formal_method_index_status_bad")
    if {str(item["id"]) for item in method_index.get("methods", [])} != {path.parent.name for path in formal_methods}:
        errors.append("formal_method_index_ids_mismatch")
    if any(item.get("status") != "approved_callable" or item.get("callable") is not True for item in method_index.get("methods", [])):
        errors.append("formal_method_index_boundary_bad")

    snapshot_entries = snapshot_manifest.get("entries", [])
    snapshot_files = sorted(path for path in (root / snapshot_manifest["snapshot_dir"]).rglob("*") if path.is_file())
    if len(snapshot_entries) != 292 or len(snapshot_files) != 292:
        errors.append(f"snapshot_file_count:{len(snapshot_entries)}/{len(snapshot_files)}")
    for item in snapshot_entries:
        path = root / item["snapshot"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            errors.append(f"snapshot_hash_mismatch:{item['snapshot']}")
    if not snapshot_manifest.get("all_hashes_verified"):
        errors.append("snapshot_manifest_not_verified")

    old_cards = sorted(downgrade_root.glob("directions/*/cards/*.md"))
    if len(old_cards) != 127:
        errors.append(f"old_downgraded_card_count:{len(old_cards)}")
    downgrade_manifest = read_json(downgrade_root / "downgrade_manifest.json")
    if downgrade_manifest.get("pending_action") != "resolved_keep_downgraded" or downgrade_manifest.get("callable") is not False:
        errors.append("old_downgrade_boundary_bad")

    account_index = read_json(root / ACCOUNT_INDEX_JSON)
    accounts = [item for item in account_index.get("accounts", []) if item.get("account_id") == "jianghushuo"]
    if len(accounts) != 1:
        errors.append(f"account_index_entry_count:{len(accounts)}")
    else:
        account = accounts[0]
        if account.get("formal_status") != "formal_ingested_v2_2":
            errors.append("account_index_status_bad")
        if account.get("formal_card_count") != 546 or sum(item.get("card_count", 0) for item in account.get("directions", [])) != 546:
            errors.append("account_index_card_count_bad")
        if account.get("formal_method_count") != 10:
            errors.append("account_index_method_count_bad")

    pending = read_json(workflow / "SYSTEM_PENDING_ITEMS.json")
    statuses = {str(item.get("id")): str(item.get("status")) for item in pending.get("items", [])}
    if statuses.get("legacy_cards_promotion_decision") != "resolved_keep_downgraded":
        errors.append("legacy_pending_item_not_resolved")
    if statuses.get("blocked_evidence_acquisition") != "pending_evidence":
        errors.append("blocked_evidence_item_missing")
    if statuses.get("collaboration_ownership_attribution") != "pending_attribution":
        errors.append("ownership_pending_item_missing")

    if receipt.get("counts", {}).get("formal_evidence_cards") != 546 or receipt.get("counts", {}).get("formal_methods") != 10:
        errors.append("formal_receipt_count_bad")
    if sha256(workflow / "REAL_ACCEPTANCE_SUMMARY.json") != receipt.get("source_acceptance_sha256"):
        errors.append("formal_receipt_acceptance_hash_bad")
    if sha256(workflow / "audit/full_relearning_audit.json") != receipt.get("source_full_audit_sha256"):
        errors.append("formal_receipt_full_audit_hash_bad")
    if promotion.get("status") != "formal_ingested" or promotion.get("formal_card_count") != 546 or promotion.get("callable_method_count") != 10:
        errors.append("promotion_status_bad")

    return {
        "ok": not errors,
        "errors": errors,
        "formal_card_count": len(formal_cards),
        "formal_card_index_count": len(card_index),
        "formal_method_count": len(formal_methods),
        "approved_callable_method_count": sum(1 for path in formal_methods if read_json(path).get("callable") is True),
        "ownership_pending_candidate_count": len(pending_ids),
        "old_downgraded_card_count": len(old_cards),
        "snapshot_file_count": len(snapshot_files),
        "snapshot_hashes_checked": len(snapshot_entries),
        "nas_path_exists": Path("/Volumes/AFK/zhishikushuju/dy/accounts/dy_77700555383").is_dir(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move the current Jianghushuo account center to the previous downgrade snapshot and promote the audited Skill v2.2 delivery."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--validate-current", action="store_true")
    args = parser.parse_args()
    if args.apply and args.validate_current:
        parser.error("--apply and --validate-current are mutually exclusive")
    result = validate_current(Path(args.root)) if args.validate_current else ingest(Path(args.root), apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.validate_current and not result.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
