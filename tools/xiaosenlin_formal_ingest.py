from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import validate_card_text


ACCOUNT = "小森林的小世界"
ACCOUNT_ID = "xiaosenlin_xiaoshijie"
WORKFLOW_ID = "xiaosenlin-xiaoshijie-v2-full"
WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows") / WORKFLOW_ID
DEEP_ROOT = WORKFLOW / "v3_deep_relearning"
FORMAL = Path("10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心") / ACCOUNT
DOWNGRADE_ROOT = Path(
    "10_Knowledge/candidates/account_assets/downgraded_formal_cards/"
    "xiaosenlin_xiaoshijie/2026-07-13"
)
SNAPSHOT_NAME = "account_center_snapshot_pre_v2_2_formal_ingest_2026-07-14"
ACCOUNT_INDEX_JSON = Path("10_Knowledge/evidence/index/account_knowledge_index.json")
ACCOUNT_INDEX_MD = Path("10_Knowledge/evidence/index/account_knowledge_index.md")
INGEST_APPROVAL = "2026-07-14 user explicitly requested audited formal ingest after moving the existing account center"
EXPECTED_SOURCE_TOTAL = 428
EXPECTED_FORMAL_CARDS = 379
EXPECTED_PENDING = 49

REQUIRED_TOP_LEVEL = (
    "账号索引.md",
    "账号概述.md",
    "账号方法论总览.md",
    "账号整体方法论.md",
    "内容生产使用说明.md",
    "减少AI味输出规则.md",
    "内容输出标准模板.md",
    "粗学与选题池.md",
    "升级重学状态.md",
    "deep_learning_plan.json",
    "METHOD_INDEX.json",
    "FORMAL_CARD_INDEX.jsonl",
    "FORMAL_INGEST_RECEIPT.json",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}：(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def load_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((root / DEEP_ROOT).glob("batch_*/structured_cards.jsonl")):
        records.extend(read_jsonl(path))
    return records


def candidate_card_path(root: Path, record: dict[str, Any]) -> Path:
    return root / DEEP_ROOT / str(record["batch_id"]) / "cards" / f"xhs_{record['source_id']}.md"


def preflight(root: Path, *, require_snapshot_absent: bool) -> dict[str, Any]:
    root = root.resolve()
    workflow = root / WORKFLOW
    formal = root / FORMAL
    snapshot = root / DOWNGRADE_ROOT / SNAPSHOT_NAME
    if not formal.is_dir():
        raise FileNotFoundError(f"formal account center missing: {formal}")
    if require_snapshot_absent and snapshot.exists():
        raise FileExistsError(f"snapshot already exists: {snapshot}")

    v22 = read_json(workflow / "V22_FINAL_AUDIT.json")
    acceptance = read_json(workflow / "REAL_ACCEPTANCE_SUMMARY.json")
    deep_audit = read_json(workflow / "v3_deep_relearning/FINAL_DEEP_AUDIT.json")
    anti_laziness = read_json(workflow / "v3_deep_relearning/ANTI_LAZINESS_AUDIT.json")
    manifest = read_json(workflow / "promotion_manifest.json")
    state = read_json(workflow / "PIPELINE_STATE.json")
    records = load_records(root)
    pending = read_jsonl(workflow / "v3_deep_relearning/SYSTEM_PENDING_EVIDENCE.jsonl")

    errors: list[str] = []
    if v22.get("gate") != "pass_with_deferred_evidence" or v22.get("errors"):
        errors.append("v22_final_audit_not_passed")
    if acceptance.get("status") != "passed" or acceptance.get("semantic_consistency", {}).get("passed") is not True:
        errors.append("real_acceptance_or_semantic_consistency_not_passed")
    if deep_audit.get("final_gate") != "pass_with_deferred_external_evidence" or deep_audit.get("errors"):
        errors.append("deep_audit_not_passed")
    if anti_laziness.get("gate") != "pass":
        errors.append("anti_laziness_not_passed")
    if len(records) != EXPECTED_FORMAL_CARDS or len(pending) != EXPECTED_PENDING:
        errors.append(f"source_accounting:{len(records)}/{len(pending)}")
    if len(records) + len(pending) != EXPECTED_SOURCE_TOTAL:
        errors.append("source_total_mismatch")
    source_ids = [str(item["source_id"]) for item in records]
    pending_ids = {str(item["source_id"]) for item in pending}
    if len(source_ids) != len(set(source_ids)) or set(source_ids) & pending_ids:
        errors.append("duplicate_or_pending_source_in_learned_set")
    if any(item.get("candidate_boundary") != "not_learned_not_callable" for item in pending):
        errors.append("pending_boundary_mismatch")
    accounting = {
        "source_total": EXPECTED_SOURCE_TOTAL,
        "deep_card_count": EXPECTED_FORMAL_CARDS,
        "deferred_evidence_count": EXPECTED_PENDING,
        "verified_candidate_method_count": int(v22.get("verified_candidate_methods") or 0),
    }
    for key, expected in accounting.items():
        if manifest.get(key) != expected:
            errors.append(f"promotion_manifest_mismatch:{key}")
        if key in state and state.get(key) != expected:
            errors.append(f"pipeline_state_mismatch:{key}")
    if manifest.get("formal_write") is not False or manifest.get("callable") is not False:
        errors.append("candidate_manifest_boundary_broken")

    method_index = read_json(workflow / "METHOD_INDEX.json")
    verified = read_jsonl(workflow / "verified.jsonl")
    verified_ids = {str(item["id"]) for item in verified}
    method_ids = {str(item["id"]) for item in method_index.get("methods", [])}
    if not verified_ids or verified_ids != method_ids or method_ids != set(manifest.get("method_ids", [])):
        errors.append("formal_method_source_mismatch")

    cards: dict[str, dict[str, Any]] = {}
    for record in records:
        source_id = str(record["source_id"])
        path = candidate_card_path(root, record)
        if not path.is_file():
            errors.append(f"missing_candidate_card:{source_id}")
            continue
        text = path.read_text(encoding="utf-8")
        validation = validate_card_text(text)
        if validation.errors:
            errors.append(f"invalid_candidate_card:{source_id}:{','.join(validation.errors)}")
        cards[source_id] = {"record": record, "path": path, "text": text}

    track_by_id = {
        str(item["source_refs"][0]): str(item.get("content_track") or "unknown")
        for item in read_jsonl(workflow / "candidates/positioning.jsonl")
    }
    source_files = sorted(path for path in formal.rglob("*") if path.is_file())
    source_dirs = sorted(path for path in formal.rglob("*") if path.is_dir())
    if not source_files:
        errors.append("existing_account_center_is_empty")
    if errors:
        raise ValueError("preflight failed: " + ";".join(errors[:20]))
    return {
        "root": root,
        "workflow": workflow,
        "formal": formal,
        "snapshot": snapshot,
        "records": records,
        "pending": pending,
        "pending_ids": pending_ids,
        "cards": cards,
        "method_index": method_index,
        "method_ids": method_ids,
        "track_by_id": track_by_id,
        "source_files": source_files,
        "source_dirs": source_dirs,
        "v22": v22,
        "acceptance": acceptance,
        "manifest": manifest,
    }


def formalize_card(text: str, ingested_at: str) -> str:
    if "状态：candidate_learned" not in text:
        raise ValueError("candidate card status missing")
    text = text.replace("状态：candidate_learned", "状态：formal_ingested", 1)
    text = text.replace(
        "## 10. 方法候选与可复用方法论",
        "## 10. 方法候选与可复用方法论\n\n> 正式证据层说明：本节保留单卡方法证据结构，但不独立调用。",
        1,
    )
    text = re.sub(
        r"> 状态：候选，待跨卡三重验证。关联机制：([^\n]+)",
        r"> 状态：正式证据卡；关联机制：\1",
        text,
        count=1,
    )
    text = re.sub(
        r"> 可调用：false。[^\n]+",
        "> 单卡方法调用：false。正式调用仅使用账号级 METHOD_INDEX 中 approved_callable 方法。",
        text,
        count=1,
    )
    text = text.replace("当前不可调用", "单卡不可独立调用")
    text = text.replace(
        "三重验证全部通过后再另建方法卡。",
        "账号级方法已完成三重验证；本卡只提供来源证据。",
    )
    text = text.replace(
        "卡片判断：证据完整，保留为统一十二段深学候选卡；不直接写入正式账号中心。",
        "卡片判断：证据完整，作为正式证据卡进入账号中心；单卡不独立证明方法。",
    )
    text = re.sub(
        r"- 跨卡状态：[^\n]+",
        "- 跨卡状态：本卡已进入正式证据层；账号级正式方法以 METHOD_INDEX 为准，单卡方法不可独立调用。",
        text,
        count=1,
    )
    marker = "状态：formal_ingested"
    text = text.replace(marker, f"{marker}\n正式入库时间：{ingested_at}", 1)
    return text


def formalize_method_md(text: str, ingested_at: str) -> str:
    old = "状态：verified_candidate；可调用：false；Skill：v2.2。"
    if old not in text:
        raise ValueError("candidate method status missing")
    return text.replace(
        old,
        f"状态：approved_callable；可调用：true；Skill：v2.2；正式入库：{ingested_at}。",
        1,
    ).replace("才进入候选调用", "才进入正式调用")


def method_table(method_index: dict[str, Any]) -> str:
    lines = ["| 方法ID | 正式方法 | 角色 |", "|---|---|---|"]
    orchestration = method_index.get("orchestration", {})
    primary = orchestration.get("primary_method")
    progressive = set(orchestration.get("progressive_methods", []))
    support = set(orchestration.get("support_layer", []))
    for method in method_index.get("methods", []):
        method_id = str(method["id"])
        role = "主方法" if method_id == primary else ("递进方法" if method_id in progressive else ("支持层" if method_id in support else "独立方法"))
        lines.append(f"| `{method_id}` | {method['title']} | {role} |")
    return "\n".join(lines)


def direction_table(direction_counts: Counter[str]) -> str:
    lines = ["| 正式方向 | 证据卡 |", "|---|---:|"]
    lines.extend(f"| {direction} | {count} |" for direction, count in sorted(direction_counts.items()))
    return "\n".join(lines)


def top_level_files(
    method_index: dict[str, Any], direction_counts: Counter[str], ingested_at: str
) -> dict[str, str]:
    methods = method_table(method_index)
    directions = direction_table(direction_counts)
    call_order = " → ".join(method_index.get("orchestration", {}).get("fixed_call_order", []))
    return {
        "账号索引.md": f"""# {ACCOUNT}账号索引

用途：调用正式方法、方向证据卡和账号表达规则；不重新扫描 NAS、候选区或49条延期项。

## 固定读取顺序

1. `账号概述.md`
2. `账号方法论总览.md`
3. `账号整体方法论.md`
4. `内容生产使用说明.md`
5. `减少AI味输出规则.md`
6. `内容输出标准模板.md`
7. 按任务读取对应 `directions/{{方向}}/方向正式证据说明.md`
8. 需要核查案例时再读取 `directions/{{方向}}/cards/`
9. 正式方法机器入口为 `METHOD_INDEX.json` 和 `methods/`

## 正式方向

{directions}
""",
        "账号概述.md": f"""# {ACCOUNT}账号概述

- 平台：小红书
- 正式状态：formal_ingested_v2_2
- 正式入库时间：{ingested_at}
- 数据清单：428条
- 正式证据卡：379条
- 系统待处理：49条，未学习、未入库、不可调用
- 五视角候选：1,895条
- 正式方法：{len(method_index.get('methods', []))}个
- 唯一媒体源：`/Volumes/AFK/zhishikushuju/xhs/accounts/xhs_5a201295e8ac2b0dbae9063a`

## 账号定位

以长期油痘肌/敏感状态的自用史为经验身份，把具体皮肤问题转成可感知结果，再通过条件化步骤、时间反馈和产品决策分流提供可执行内容。账号同时包含生活Vlog、社群互动、平台项目和大量商业属性未确认的产品内容，这些内容必须与自然方法证据分轨。

## 证据边界

- 379张卡是正式来源证据；单卡方法不可独立调用。
- 319条商业属性不明内容不能增加自然方法权重，也不能把品牌、功效或购买利益当成已核事实。
- 生活Vlog、社群互动和平台项目只学习信任、任务承载和表达结构，不冒充护肤方法。
- 护肤结果属于账号个人经验，不能改写成医学结论、普遍功效或固定时效承诺。
- 49条证据延期只保留在候选系统待处理区，本轮不继续处理。
""",
        "账号方法论总览.md": f"""# {ACCOUNT}账号方法论总览

## 正式方法

{methods}

## 固定调用顺序

`{call_order}`

先确认账号、方向、内容轨道和证据状态；再选择一个主方法；需要流程推进时叠加递进方法；清单分流只作为支持层。方法组合必须通过消融，删除一个方法后结构没有变化就不应保留。

## 三轨边界

- 自然经验与明确无广自述：可以支持自然方法，但仍是个人经验。
- 商业属性不明、品牌露出和购买节点：独立隔离，不增加自然方法权重。
- 平台项目、生活内容和账号互动：只进入项目、信任或服务证据，不证明护肤方法。
""",
        "账号整体方法论.md": """# 小森林的小世界账号整体方法论

## 内容发动机

从具体皮肤困扰、目标肤态或现实使用场景进入；用可观察结果降低理解成本；用有顺序、有条件和有判停点的步骤承接；再以时间、触感或状态反馈收束。多产品内容必须给出肤质、问题、预算或使用条件的分流，不能只罗列产品。

## 可信度来源

可信度来自长期肤质身份、自用史、空瓶/复测、对失败与不适用情况的说明，而不是来自绝对功效词。正式生产仍必须区分“账号个人经验”“可回查原文”和“外部可核事实”。

## 不能误学

- 不把ASR错字、标题夸张词或单条结果当成可核事实。
- 不把品牌活动、平台项目或商业属性未确认内容计入自然方法频次。
- 不把同题材词、同产品名或同场景当成方法触发条件。
- 不把生活Vlog和社群互动强行套入护肤方法。
""",
        "内容生产使用说明.md": """# 小森林的小世界内容生产使用说明

1. 先确认任务属于自然经验、产品决策、商业内容、平台项目、生活信任或社群互动。
2. 自然经验先选择一个主方法；流程型任务再叠加分步和反馈方法。
3. 多产品内容使用清单决策分流，必须给出选择条件，不做无条件种草。
4. 商业属性不明内容只可学习结构与表达，不可复制功效、品牌判断和购买利益。
5. 生活Vlog、平台项目和互动内容只调用对应证据层，不调用护肤方法。
6. 需要案例时按 FORMAL_CARD_INDEX 定位单卡；不全扫 NAS 或候选工作流。
7. 输出前核对原文/提炼表达、个人经验/事实判断、视觉帧号、风险边界和方法消融。
""",
        "减少AI味输出规则.md": """# 小森林的小世界减少AI味输出规则

- 从具体肤质、当天状态、使用场景或选择难题开场，不用“今天给大家分享几个好东西”的空模板。
- 步骤必须写清先后、用量/频率、观察点和停止条件，不把同义句排成伪步骤。
- 产品清单逐项说明“解决什么、适合谁、为什么保留、什么情况下不用”，不堆形容词。
- 个人体验使用“我自己的状态/感受/复测”，不改写成人人有效或确定疗效。
- 保留账号的具体过程、取舍、翻车和边界，不用百科式成分课替代真实使用史。
- 标题、正文、话题服务同一任务；话题词和品牌词不能反向决定内容方法。
- 原始ASR可能有错字，对外输出只能使用复核过的原文或明确标记的提炼表达。
""",
        "内容输出标准模板.md": """# 小森林的小世界内容输出标准模板

## 发布内容包

- 内容轨道：自然经验 / 产品决策 / 商业内容 / 平台项目 / 生活信任 / 社群互动
- 目标人群与当前状态：
- 具体问题或选择任务：
- 发布标题：
- 发布正文：
- 话题标签：
- 黄金3秒或视觉开场：
- 主方法：仅一个
- 递进方法：可选
- 支持层：可选清单决策分流
- 正文结构：问题/场景 → 条件化步骤或选择 → 状态反馈 → 边界
- 证据参考：正式方法ID + 正式单卡source_id
- 个人经验边界：
- 商业与平台边界：
- 不能复制：来源原句、品牌事实、人物经历、确定功效和固定时效
""",
        "升级重学状态.md": f"""# {ACCOUNT}升级重学状态

- Skill版本：2.2
- 正式入库：完成
- 入库时间：{ingested_at}
- 379条统一十二段正式证据卡：完成
- 4个跨卡正式方法：完成
- 43/43批次审计：通过
- 五视角候选：1,895条，唯一分簇通过
- 压力测试：28/28通过
- 语义冲突：0
- 49条证据延期：保持系统待处理，本轮未继续学习、未进入正式账号中心
- 原账号中心：已整体平移至上次降级文件夹并逐文件哈希校验
""",
    }


def rough_pool(records: list[dict[str, Any]], pending: list[dict[str, Any]]) -> str:
    lines = [
        f"# {ACCOUNT}粗学与选题池",
        "",
        "本文件保留428条完整范围，不是Top清单。379条已形成正式证据卡；49条只登记待处理，不在本轮继续学习。",
        "",
        "| source_id | 标题 | 方向 | 状态 |",
        "|---|---|---|---|",
    ]
    for record in sorted(records, key=lambda item: (str(item.get("topic_family")), str(item["source_id"]))):
        title = str(record.get("title") or "").replace("|", "｜").replace("\n", " ")
        lines.append(f"| {record['source_id']} | {title} | {record.get('topic_family') or '未分类'} | formal_evidence_card |")
    for item in sorted(pending, key=lambda row: str(row["source_id"])):
        title = str(item.get("title") or "证据待补").replace("|", "｜").replace("\n", " ")
        lines.append(f"| {item['source_id']} | {title} | 待补证据 | pending_not_learned |")
    return "\n".join(lines)


def direction_summary(direction: str, records: list[dict[str, Any]], track_by_id: dict[str, str]) -> str:
    mechanisms = Counter(str(item.get("mechanism_key") or "unknown") for item in records)
    tracks = Counter(track_by_id.get(str(item["source_id"]), "unknown") for item in records)
    return f"""# {direction}方向正式证据说明

- 正式证据卡：{len(records)}张
- 主机制分布：{json.dumps(dict(sorted(mechanisms.items())), ensure_ascii=False)}
- 内容轨道分布：{json.dumps(dict(sorted(tracks.items())), ensure_ascii=False)}

## 调用边界

- 本方向卡片用于回查来源证据；单卡方法不可独立调用。
- 账号级方法只从 `METHOD_INDEX.json` 调用，并在生成前完成选择。
- commercial_unknown、platform_project、community_or_aftercare 不增加自然方法权重。
- 个体护肤结果、品牌、商品和固定时效不得改写为普遍事实。
"""


def build_staging(root: Path, state: dict[str, Any], staging: Path, ingested_at: str) -> dict[str, Any]:
    staging.mkdir(parents=True)
    records = state["records"]
    by_direction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_direction[str(record.get("topic_family") or "未分类")].append(record)
    direction_counts = Counter({key: len(value) for key, value in by_direction.items()})

    method_index = json.loads(json.dumps(state["method_index"], ensure_ascii=False))
    method_index.update({"status": "formal_ingested", "formal_ingested_at": ingested_at})
    method_index["methods"] = [dict(item, status="approved_callable", callable=True) for item in method_index["methods"]]

    for name, content in top_level_files(method_index, direction_counts, ingested_at).items():
        write_text(staging / name, content)
    write_text(staging / "粗学与选题池.md", rough_pool(records, state["pending"]))

    card_index: list[dict[str, Any]] = []
    for direction, direction_records in sorted(by_direction.items()):
        write_text(
            staging / "directions" / direction / "方向正式证据说明.md",
            direction_summary(direction, direction_records, state["track_by_id"]),
        )
        for record in sorted(direction_records, key=lambda item: str(item["source_id"])):
            source_id = str(record["source_id"])
            source = state["cards"][source_id]
            target = staging / "directions" / direction / "cards" / f"xhs_{source_id}.md"
            formal_text = formalize_card(source["text"], ingested_at)
            write_text(target, formal_text)
            card_index.append(
                {
                    "source_id": source_id,
                    "direction": direction,
                    "content_track": state["track_by_id"].get(source_id, "unknown"),
                    "status": "formal_evidence_card",
                    "callable_as_evidence": True,
                    "single_card_method_callable": False,
                    "source_url": metadata_value(source["text"], "原内容链接"),
                    "formal_path": (FORMAL / target.relative_to(staging)).as_posix(),
                    "candidate_source": source["path"].relative_to(root).as_posix(),
                }
            )
    write_jsonl(staging / "FORMAL_CARD_INDEX.jsonl", card_index)

    write_json(staging / "METHOD_INDEX.json", method_index)
    for method_id in sorted(state["method_ids"]):
        source_dir = root / WORKFLOW / "methods" / method_id
        target_dir = staging / "methods" / method_id
        write_text(target_dir / "METHOD.md", formalize_method_md((source_dir / "METHOD.md").read_text(encoding="utf-8"), ingested_at))
        payload = read_json(source_dir / "method.json")
        payload.update(
            {
                "status": "approved_callable",
                "callable": True,
                "knowledge_layer": "formal",
                "formal_ingested_at": ingested_at,
                "approval_basis": INGEST_APPROVAL,
            }
        )
        write_json(target_dir / "method.json", payload)
        shutil.copy2(source_dir / "test-prompts.json", target_dir / "test-prompts.json")
        shutil.copy2(source_dir / "test-results.json", target_dir / "test-results.json")

    glossary = (root / WORKFLOW / "GLOSSARY.md").read_text(encoding="utf-8")
    write_text(staging / "GLOSSARY.md", glossary.replace("候选方法术语", "正式方法术语", 1))
    evidence_dir = staging / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_files = (
        "ACCOUNT_OVERVIEW.json",
        "ACCOUNT_OVERVIEW.md",
        "REAL_ACCEPTANCE_SUMMARY.json",
        "REAL_ACCEPTANCE_REPORT_2026-07-14.md",
        "V22_FINAL_AUDIT.json",
        "V22_FINAL_AUDIT.md",
        "v3_deep_relearning/FINAL_DEEP_AUDIT.json",
        "v3_deep_relearning/FINAL_DEEP_AUDIT.md",
        "v3_deep_relearning/ANTI_LAZINESS_AUDIT.json",
        "v3_deep_relearning/ANTI_LAZINESS_AUDIT.md",
    )
    for relative in evidence_files:
        source = root / WORKFLOW / relative
        shutil.copy2(source, evidence_dir / source.name)

    plan = {
        "schema_version": "2.2",
        "status": "formal_ingested_with_deferred_evidence",
        "account_name": ACCOUNT,
        "account_id": "xhs_5a201295e8ac2b0dbae9063a",
        "source_total": EXPECTED_SOURCE_TOTAL,
        "formal_evidence_card_count": EXPECTED_FORMAL_CARDS,
        "system_pending_not_learned_count": EXPECTED_PENDING,
        "formal_method_count": len(state["method_ids"]),
        "formal_ingested_at": ingested_at,
        "source_workflow": WORKFLOW.as_posix(),
        "authoritative_nas": "/Volumes/AFK/zhishikushuju/xhs/accounts/xhs_5a201295e8ac2b0dbae9063a",
        "pending_policy": "keep_candidate_only_do_not_continue_until_user_reopens",
    }
    write_json(staging / "deep_learning_plan.json", plan)
    receipt = {
        "ok": True,
        "schema_version": "2.2",
        "status": "formal_ingested",
        "account_name": ACCOUNT,
        "formal_account_dir": FORMAL.as_posix(),
        "ingested_at": ingested_at,
        "counts": {
            "source_total": EXPECTED_SOURCE_TOTAL,
            "formal_evidence_cards": EXPECTED_FORMAL_CARDS,
            "system_pending_not_learned": EXPECTED_PENDING,
            "formal_methods": len(state["method_ids"]),
            "directions": len(direction_counts),
        },
        "pending_source_ids": sorted(state["pending_ids"]),
        "source_v22_audit_sha256": sha256(root / WORKFLOW / "V22_FINAL_AUDIT.json"),
        "source_real_acceptance_sha256": sha256(root / WORKFLOW / "REAL_ACCEPTANCE_SUMMARY.json"),
        "previous_account_center_snapshot": (DOWNGRADE_ROOT / SNAPSHOT_NAME).as_posix(),
        "user_confirmation": INGEST_APPROVAL,
    }
    write_json(staging / "FORMAL_INGEST_RECEIPT.json", receipt)
    return {"direction_counts": direction_counts, "method_index": method_index, "receipt": receipt}


def validate_staging(staging: Path, state: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    missing = [name for name in REQUIRED_TOP_LEVEL if not (staging / name).is_file()]
    if missing:
        errors.append("missing_top_level:" + ",".join(missing))
    cards = sorted(staging.glob("directions/*/cards/xhs_*.md"))
    methods = sorted(staging.glob("methods/*/method.json"))
    if len(cards) != EXPECTED_FORMAL_CARDS:
        errors.append(f"formal_card_count:{len(cards)}")
    if len(methods) != len(state["method_ids"]):
        errors.append(f"formal_method_count:{len(methods)}")
    staged_ids: set[str] = set()
    for path in cards:
        text = path.read_text(encoding="utf-8")
        source_id = metadata_value(text, "source_id")
        staged_ids.add(source_id)
        if "状态：formal_ingested" not in text or "> 单卡方法调用：false" not in text:
            errors.append(f"bad_formal_card_status:{path.name}")
        validation = validate_card_text(text)
        if validation.errors:
            errors.append(f"invalid_formal_card:{path.name}:{','.join(validation.errors)}")
        if "主证据：NAS原始视频、完整SRT与转写" in text and "无有效语音转写" in text:
            errors.append(f"silent_transcript_contradiction:{path.name}")
    if len(staged_ids) != len(cards) or staged_ids & state["pending_ids"]:
        errors.append("duplicate_or_pending_formal_source")
    for path in methods:
        payload = read_json(path)
        if payload.get("status") != "approved_callable" or payload.get("callable") is not True:
            errors.append(f"bad_formal_method:{path.parent.name}")
    index_rows = read_jsonl(staging / "FORMAL_CARD_INDEX.jsonl")
    if len(index_rows) != EXPECTED_FORMAL_CARDS or {str(item["source_id"]) for item in index_rows} != staged_ids:
        errors.append("formal_card_index_mismatch")
    pool = (staging / "粗学与选题池.md").read_text(encoding="utf-8")
    if pool.count("| formal_evidence_card |") != EXPECTED_FORMAL_CARDS or pool.count("| pending_not_learned |") != EXPECTED_PENDING:
        errors.append("rough_pool_accounting_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "formal_card_count": len(cards),
        "formal_method_count": len(methods),
        "direction_count": len(list(staging.glob("directions/*/方向正式证据说明.md"))),
    }


def snapshot_records(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source": path.relative_to(root).as_posix(),
            "snapshot": (DOWNGRADE_ROOT / SNAPSHOT_NAME / path.relative_to(state["formal"])).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in state["source_files"]
    ]


def update_downgrade_metadata(root: Path, state: dict[str, Any], records: list[dict[str, Any]], ingested_at: str) -> dict[str, Any]:
    verified = all((root / item["snapshot"]).is_file() and sha256(root / item["snapshot"]) == item["sha256"] for item in records)
    manifest = {
        "schema_version": "2.2",
        "account_id": ACCOUNT_ID,
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
    write_json(root / DOWNGRADE_ROOT / "account_center_snapshot_manifest.json", manifest)
    old_manifest_path = root / DOWNGRADE_ROOT / "downgrade_manifest.json"
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
    readme_path = root / DOWNGRADE_ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8").rstrip()
    if "## 账号中心整体平移快照" not in readme:
        readme += f"""

## 账号中心整体平移快照

- 快照时间：{ingested_at}
- 原账号中心文件：{len(records)}个；目录：{len(state['source_dirs'])}个
- 快照目录：`{manifest['snapshot_dir']}`
- 哈希清单：`{(DOWNGRADE_ROOT / 'account_center_snapshot_manifest.json').as_posix()}`
- 状态：逐文件哈希校验通过；继续作为不可调用的候选历史备份
"""
        write_text(readme_path, readme)
    return manifest


def account_index_entry(direction_counts: Counter[str], method_count: int) -> dict[str, Any]:
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
        {"layer": "account_status_overview", "path": f"{base}/账号概述.md", "description": "Skill v2.2正式状态、范围和证据边界。"},
        {"layer": "account_overview", "path": f"{base}/账号方法论总览.md", "description": f"{method_count}个正式可调用方法入口。"},
        {"layer": "account_summary", "path": f"{base}/账号整体方法论.md", "description": "账号内容发动机、可信度和误学边界。"},
        {"layer": "content_usage", "path": f"{base}/内容生产使用说明.md", "description": "内容生产固定读取顺序。"},
        {"layer": "anti_ai_style", "path": f"{base}/减少AI味输出规则.md", "description": "本账号证据导出的表达约束。"},
        {"layer": "account_content_template", "path": f"{base}/内容输出标准模板.md", "description": "正式内容交付模板。"},
        {"layer": "method_index", "path": f"{base}/METHOD_INDEX.json", "description": "正式方法和关系机器索引。"},
        {"layer": "formal_card_index", "path": f"{base}/FORMAL_CARD_INDEX.jsonl", "description": f"{EXPECTED_FORMAL_CARDS}张正式证据卡机器索引。"},
    ]
    for direction in directions:
        name = direction["direction"]
        layers.extend(
            [
                {"layer": "direction_method", "direction": name, "path": f"{base}/directions/{name}/方向正式证据说明.md", "description": "方向证据路由与方法边界。"},
                {"layer": "single_cards", "direction": name, "path": f"{base}/directions/{name}/cards", "description": "Skill v2.2正式证据卡。"},
            ]
        )
    return {
        "account_id": ACCOUNT_ID,
        "account_name": ACCOUNT,
        "platform": "小红书",
        "formal_account_dir": base,
        "formal_status": "formal_ingested_v2_2",
        "formal_card_count": EXPECTED_FORMAL_CARDS,
        "formal_method_count": method_count,
        "system_pending_not_learned_count": EXPECTED_PENDING,
        "directions": directions,
        "knowledge_layers": layers,
    }


def render_account_index_md(payload: dict[str, Any]) -> str:
    lines = ["# 账号知识总索引", "", "| 账号 | 平台 | 正式目录 | 已入库方向 |", "|---|---|---|---|"]
    for account in payload.get("accounts", []):
        directions = "、".join(item["direction"] for item in account.get("directions", []))
        lines.append(f"| {account['account_name']} | {account['platform']} | {account['formal_account_dir']} | {directions} |")
    return "\n".join(lines) + "\n"


def update_indexes(root: Path, direction_counts: Counter[str], method_count: int) -> None:
    path = root / ACCOUNT_INDEX_JSON
    payload = read_json(path)
    accounts = [item for item in payload.get("accounts", []) if item.get("account_id") != ACCOUNT_ID]
    accounts.append(account_index_entry(direction_counts, method_count))
    accounts.sort(key=lambda item: item.get("account_name", ""))
    payload["generated_at"] = now_iso()
    payload["accounts"] = accounts
    write_json(path, payload)
    write_text(root / ACCOUNT_INDEX_MD, render_account_index_md(payload))


def update_workflow(root: Path, built: dict[str, Any], snapshot_manifest: dict[str, Any], ingested_at: str) -> None:
    receipt = built["receipt"]
    receipt["snapshot_file_count"] = snapshot_manifest["file_count"]
    receipt["snapshot_all_hashes_verified"] = snapshot_manifest["all_hashes_verified"]
    write_json(root / FORMAL / "FORMAL_INGEST_RECEIPT.json", receipt)
    write_json(root / WORKFLOW / "FORMAL_INGEST_RECEIPT.json", receipt)
    promotion = {
        "schema_version": "2.2",
        "workflow_id": WORKFLOW_ID,
        "status": "formal_ingested_with_deferred_evidence",
        "promoted_at": ingested_at,
        "formal_account_dir": FORMAL.as_posix(),
        "formal_card_count": EXPECTED_FORMAL_CARDS,
        "formal_method_count": len(built["method_index"].get("methods", [])),
        "callable_method_count": len(built["method_index"].get("methods", [])),
        "candidate_only_system_pending_count": EXPECTED_PENDING,
        "previous_account_center_snapshot": snapshot_manifest["snapshot_dir"],
        "user_approval": True,
    }
    write_json(root / WORKFLOW / "PROMOTION_STATUS.json", promotion)
    state_path = root / WORKFLOW / "PIPELINE_STATE.json"
    state = read_json(state_path)
    state["formal_promotion"] = promotion
    state["updated_at"] = ingested_at
    write_json(state_path, state)


def audit_formal(root: Path) -> dict[str, Any]:
    formal = root / FORMAL
    workflow = root / WORKFLOW
    snapshot_manifest = read_json(root / DOWNGRADE_ROOT / "account_center_snapshot_manifest.json")
    promotion = read_json(workflow / "PROMOTION_STATUS.json")
    cards = sorted(formal.glob("directions/*/cards/xhs_*.md"))
    methods = sorted(formal.glob("methods/*/method.json"))
    pending = read_jsonl(workflow / "v3_deep_relearning/SYSTEM_PENDING_EVIDENCE.jsonl")
    pending_ids = {str(item["source_id"]) for item in pending}
    errors: list[str] = []
    formal_ids: set[str] = set()
    for path in cards:
        text = path.read_text(encoding="utf-8")
        source_id = metadata_value(text, "source_id")
        formal_ids.add(source_id)
        if "状态：formal_ingested" not in text or "状态：candidate_learned" in text:
            errors.append(f"bad_card_status:{path.name}")
        if "主证据：NAS原始视频、完整SRT与转写" in text and "无有效语音转写" in text:
            errors.append(f"semantic_conflict:{path.name}")
    if len(cards) != EXPECTED_FORMAL_CARDS or len(formal_ids) != EXPECTED_FORMAL_CARDS:
        errors.append(f"formal_card_count:{len(cards)}/{len(formal_ids)}")
    if formal_ids & pending_ids or len(pending) != EXPECTED_PENDING:
        errors.append("pending_entered_formal_or_count_changed")
    if len(methods) != 4:
        errors.append(f"formal_method_count:{len(methods)}")
    for path in methods:
        payload = read_json(path)
        if payload.get("status") != "approved_callable" or payload.get("callable") is not True:
            errors.append(f"method_not_callable:{path.parent.name}")
    snapshot_entries = snapshot_manifest.get("entries", [])
    if not snapshot_manifest.get("all_hashes_verified"):
        errors.append("snapshot_manifest_not_verified")
    for item in snapshot_entries:
        path = root / item["snapshot"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            errors.append(f"snapshot_hash_mismatch:{item['snapshot']}")
    account_index = read_json(root / ACCOUNT_INDEX_JSON)
    entry = next((item for item in account_index.get("accounts", []) if item.get("account_id") == ACCOUNT_ID), None)
    if not entry or entry.get("formal_card_count") != EXPECTED_FORMAL_CARDS or entry.get("formal_method_count") != 4:
        errors.append("account_index_not_updated")
    if promotion.get("status") != "formal_ingested_with_deferred_evidence":
        errors.append("promotion_status_missing")
    for name in REQUIRED_TOP_LEVEL:
        if not (formal / name).is_file():
            errors.append(f"missing_formal_top_level:{name}")
    audit = {
        "ok": not errors,
        "schema_version": "2.2",
        "account": ACCOUNT,
        "audited_at": now_iso(),
        "formal_status": "formal_ingested" if not errors else "audit_failed",
        "formal_card_count": len(cards),
        "formal_method_count": len(methods),
        "pending_not_learned_count": len(pending),
        "snapshot_file_count": len(snapshot_entries),
        "snapshot_hashes_verified": len(snapshot_entries) if not any(error.startswith("snapshot_hash") for error in errors) else 0,
        "semantic_conflict_count": sum(error.startswith("semantic_conflict") for error in errors),
        "errors": errors,
    }
    write_json(workflow / "FORMAL_PROMOTION_AUDIT.json", audit)
    write_text(
        workflow / "FORMAL_PROMOTION_AUDIT.md",
        f"""# {ACCOUNT}正式晋升审计

- 状态：`{'pass' if audit['ok'] else 'fail'}`
- 正式证据卡：{audit['formal_card_count']}
- 正式可调用方法：{audit['formal_method_count']}
- 系统待处理且未学习：{audit['pending_not_learned_count']}
- 原账号中心整体平移：{audit['snapshot_file_count']}个文件逐项哈希验证
- 语义冲突：{audit['semantic_conflict_count']}
- 账号索引：已更新

## 边界

- 49条延期项未继续学习、未进入正式卡、未进入正式方法。
- 正式证据卡可用于回查；单卡方法不可独立调用。
- 仅4个账号级方法标记为 `approved_callable`。
""",
    )
    return audit


def ingest(root: Path, *, apply: bool) -> dict[str, Any]:
    root = root.resolve()
    state = preflight(root, require_snapshot_absent=apply)
    ingested_at = now_iso()
    if not apply:
        temp_parent = root / "90_Temp"
        temp_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="xiaosenlin_formal_ingest_", dir=temp_parent) as temp:
            staging = Path(temp) / ACCOUNT
            built = build_staging(root, state, staging, ingested_at)
            validation = validate_staging(staging, state)
            return {
                "ok": validation["ok"],
                "mode": "dry_run",
                "preflight": "passed",
                "staging_validation": validation,
                "source_account_center_files_to_move": len(state["source_files"]),
                "snapshot_target": (DOWNGRADE_ROOT / SNAPSHOT_NAME).as_posix(),
                "formal_cards": len(state["records"]),
                "pending_untouched": len(state["pending"]),
                "formal_methods": len(state["method_ids"]),
            }

    staging = root / "90_Temp" / "xiaosenlin_formal_ingest_staging_2026-07-14"
    if staging.exists():
        raise FileExistsError(f"staging exists: {staging}")
    built = build_staging(root, state, staging, ingested_at)
    validation = validate_staging(staging, state)
    if not validation["ok"]:
        raise ValueError("staging validation failed: " + ";".join(validation["errors"][:20]))
    records = snapshot_records(root, state)
    snapshot = state["snapshot"]
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    swapped = False
    try:
        os.replace(state["formal"], snapshot)
        os.replace(staging, state["formal"])
        swapped = True
        snapshot_manifest = update_downgrade_metadata(root, state, records, ingested_at)
        if not snapshot_manifest["all_hashes_verified"]:
            raise RuntimeError("snapshot hash verification failed")
        update_indexes(root, built["direction_counts"], len(state["method_ids"]))
        update_workflow(root, built, snapshot_manifest, ingested_at)
        audit = audit_formal(root)
        if not audit["ok"]:
            raise RuntimeError("formal audit failed: " + ";".join(audit["errors"][:20]))
    except Exception:
        if swapped and state["formal"].exists() and snapshot.exists():
            failed = root / "90_Temp" / f"xiaosenlin_failed_formal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.replace(state["formal"], failed)
            os.replace(snapshot, state["formal"])
        raise
    return {
        "ok": True,
        "mode": "apply",
        "formal_account_dir": FORMAL.as_posix(),
        "formal_cards": EXPECTED_FORMAL_CARDS,
        "formal_methods": len(state["method_ids"]),
        "pending_untouched": EXPECTED_PENDING,
        "snapshot_manifest": (DOWNGRADE_ROOT / "account_center_snapshot_manifest.json").as_posix(),
        "formal_receipt": (FORMAL / "FORMAL_INGEST_RECEIPT.json").as_posix(),
        "formal_audit": (WORKFLOW / "FORMAL_PROMOTION_AUDIT.json").as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit, move the old Xiaosenlin account center to its downgrade folder, and formally ingest the Skill v2.2 delivery."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.audit_only:
        result = audit_formal(root)
    else:
        result = ingest(root, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
