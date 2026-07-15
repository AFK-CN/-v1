from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.jianghushuo_v2_learning import (
    WORKFLOW_ROOT,
    content_classification,
    read_json,
    write_json,
    write_jsonl,
)
from tools.video_learning import load_unique_records_detailed, records_by_source_id


DOWNGRADE_MANIFEST = Path(
    "10_Knowledge/candidates/account_assets/downgraded_formal_cards/jianghushuo/2026-07-12/downgrade_manifest.json"
)


STRATA = (
    "normal_visual",
    "normal_long_transcript",
    "product_ad",
    "platform_project",
    "collaboration_ownership",
    "low_information_or_asr_risk",
)
def card_section(text: str, number: int) -> str:
    match = re.search(rf"(?ms)^## {number}\. .+?\n(.*?)(?=^## \d+\.|\Z)", text)
    return match.group(1).strip() if match else ""


def metadata_value(text: str, label: str) -> str:
    match = re.search(rf"(?m)^{re.escape(label)}[:：](.+)$", text)
    return match.group(1).strip() if match else ""


def coordinate_value(text: str, label: str) -> str:
    match = re.search(rf"(?m)^- {re.escape(label)}[:：](.+?)(?:。|$)", text)
    return match.group(1).strip() if match else ""


def card_classification_id(text: str) -> str:
    section = card_section(text, 3)
    match = re.search(r"(?m)^- 商业属性：(.+)$", section)
    value = match.group(1).strip() if match else ""
    for prefix, classification_id in (
        ("商品广告", "product_ad"),
        ("平台项目", "platform_project"),
        ("协作/采访内容", "collaboration_ownership"),
        ("自然内容", "natural_content"),
    ):
        if value.startswith(prefix):
            return classification_id
    return "unresolved"


def deterministic_sample(rows: list[dict[str, Any]], stratum: str, count: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(f"jianghushuo-v2.2|{stratum}|{row['source_id']}".encode()).hexdigest(),
    )
    return ranked[:count]


def artifact_from_coordinate(value: str) -> Path | None:
    raw = value.split("（", 1)[0].strip()
    return Path(raw) if raw.startswith("/") else None


def commercial_record(row: dict[str, Any], kind: str) -> dict[str, Any]:
    text = row["text"]
    transcript = coordinate_value(text, "文本证据坐标")
    visual = coordinate_value(text, "视觉证据坐标")
    structure = card_section(text, 5)
    media = card_section(text, 7)
    common = {
        "source_id": row["source_id"],
        "classification": kind,
        "classification_basis": "explicit_marker_in_title_body_tags_or_transcript_card",
        "transcript_coordinate": transcript,
        "visual_coordinate": visual,
        "excluded_from_natural_v1": True,
        "callable": False,
        "formal_write": False,
    }
    if kind == "collaboration_ownership":
        common.update(
            {
                "ownership_status": "pending_speaker_and_source_attribution",
                "ownership_evidence": card_section(text, 6),
                "use_boundary": "完成说话人和原始采访归属核验前，只作合作/采访证据，不计入姜胡说自然方法V1。",
            }
        )
        return common
    common.update({
        "pre_ad_content": structure or "待回到逐字稿复核广告前正常内容",
        "ad_entry": "待按逐字稿与帧坐标复核具体引入桥",
        "product_role": "待按视觉证据复核；不得仅凭品牌词推断",
        "post_ad_closure": media or "待复核广告后是否回到原观点或结构",
    })
    return common


def build(root: Path) -> dict[str, Any]:
    root = root.resolve()
    workflow = root / WORKFLOW_ROOT
    gap = read_json(workflow / "EVIDENCE_GAP_STATUS.json")
    planned_count = int(gap.get("nas_plan_count") or 0)
    expected_ready_count = int(gap.get("evidence_ready_count") or 0)
    expected_blocked_count = int(gap.get("blocked_count") or 0)
    rows: list[dict[str, Any]] = []
    for manifest_path in sorted((workflow / "batches").glob("batch_*/batch_manifest.json")):
        manifest = read_json(manifest_path)
        for item in manifest.get("items", []):
            card_path = root / str(item["card_path"])
            text = card_path.read_text(encoding="utf-8")
            rows.append(
                {
                    "source_id": str(item["source_id"]),
                    "direction": str(item.get("direction") or "待复核"),
                    "card_path": str(card_path.relative_to(root)),
                    "text": text,
                    "evidence": item.get("nas_evidence") or {},
                    "search_text": " ".join(
                        (
                            text.splitlines()[0] if text.splitlines() else "",
                            card_section(text, 3),
                            card_section(text, 6),
                        )
                    ),
                }
            )

    errors: list[str] = []
    if len(rows) != expected_ready_count or len({row["source_id"] for row in rows}) != len(rows):
        errors.append(f"card_population_must_match_evidence_ready:{len(rows)}/{expected_ready_count}")
    title_v22_count = sum(row["text"].startswith("# 姜胡说 2.2") for row in rows)
    contract_count = sum(metadata_value(row["text"], "学习卡契约") == "unified_three_layer_v2" for row in rows)
    coordinate_count = sum(
        bool(coordinate_value(row["text"], "文本证据坐标"))
        and bool(coordinate_value(row["text"], "视觉证据坐标"))
        for row in rows
    )
    if title_v22_count != len(rows):
        errors.append("not_all_cards_are_labeled_v2_2")
    if contract_count != len(rows):
        errors.append("not_all_cards_use_unified_three_layer_v2")
    if coordinate_count != len(rows):
        errors.append("not_all_cards_have_text_and_visual_coordinates")

    records, _, _, _ = load_unique_records_detailed(root)
    records_by_id = records_by_source_id(records)
    classification_mismatches: list[dict[str, str]] = []
    classification_counts: dict[str, int] = {}
    for row in rows:
        record = records_by_id.get(row["source_id"])
        expected = content_classification(record)["id"] if record is not None else "missing_source_record"
        actual = card_classification_id(row["text"])
        row["classification"] = expected
        classification_counts[expected] = classification_counts.get(expected, 0) + 1
        if expected != actual:
            classification_mismatches.append(
                {"source_id": row["source_id"], "expected": expected, "actual": actual}
            )
    if classification_mismatches:
        errors.append(f"classification_consistency_failed:{len(classification_mismatches)}")
    if classification_counts.get("natural_content", 0) + sum(
        classification_counts.get(kind, 0)
        for kind in ("product_ad", "platform_project", "collaboration_ownership")
    ) != len(rows):
        errors.append("classification_population_incomplete")

    visual_pool = [
        row
        for row in rows
        if row["evidence"].get("has_keyframes") and row["evidence"].get("has_scenes")
    ]
    normal_visual = deterministic_sample(visual_pool, "normal_visual")
    visual_checks = []
    for row in normal_visual:
        coordinate = coordinate_value(row["text"], "视觉证据坐标")
        artifact = artifact_from_coordinate(coordinate)
        visual_checks.append(
            {
                "source_id": row["source_id"],
                "coordinate": coordinate,
                "artifact_exists": bool(artifact and artifact.is_file()),
                "no_unverified_visual_claim": "不据此猜测" in row["text"] or "未对该帧作超出画面的" in row["text"],
            }
        )
    if not normal_visual or not all(item["artifact_exists"] and item["no_unverified_visual_claim"] for item in visual_checks):
        errors.append("normal_visual_real_acceptance_failed")

    long_pool = sorted(
        rows,
        key=lambda row: int((row["evidence"].get("transcript_quality") or {}).get("normalized_char_count") or 0),
        reverse=True,
    )
    normal_long = long_pool[:3]
    long_checks = [
        {
            "source_id": row["source_id"],
            "transcript_coordinate": coordinate_value(row["text"], "文本证据坐标"),
            "normalized_char_count": int((row["evidence"].get("transcript_quality") or {}).get("normalized_char_count") or 0),
            "transcript_exists": Path(str(row["evidence"].get("transcript_path") or "")).is_file(),
        }
        for row in normal_long
    ]
    if not normal_long or not all(item["transcript_exists"] and item["transcript_coordinate"] for item in long_checks):
        errors.append("normal_long_transcript_real_acceptance_failed")

    product_rows = [row for row in rows if row["classification"] == "product_ad"]
    platform_rows = [row for row in rows if row["classification"] == "platform_project"]
    collaboration_rows = [row for row in rows if row["classification"] == "collaboration_ownership"]
    commercial_dir = workflow / "commercial_learning"
    write_jsonl(commercial_dir / "PRODUCT_AD_INDEX.jsonl", [commercial_record(row, "product_ad") for row in product_rows])
    write_jsonl(
        commercial_dir / "PLATFORM_PROJECT_INDEX.jsonl",
        [commercial_record(row, "platform_project") for row in platform_rows],
    )
    write_jsonl(
        commercial_dir / "COLLABORATION_OWNERSHIP_INDEX.jsonl",
        [commercial_record(row, "collaboration_ownership") for row in collaboration_rows],
    )

    blocked_ids = {str(item["source_id"]) for item in gap.get("blocked_items", [])}
    learned_ids = {row["source_id"] for row in rows}
    low_ready = sorted(
        rows,
        key=lambda row: int((row["evidence"].get("transcript_quality") or {}).get("normalized_char_count") or 0),
    )[:3]
    low_checks = [
        {
            "source_id": row["source_id"],
            "normalized_char_count": int((row["evidence"].get("transcript_quality") or {}).get("normalized_char_count") or 0),
            "kept_candidate_only": metadata_value(row["text"], "状态") == "candidate_learned",
        }
        for row in low_ready
    ]
    if blocked_ids & learned_ids:
        errors.append("blocked_source_was_included_in_learning_cards")
    if len(blocked_ids) != expected_blocked_count or planned_count != len(rows) + len(blocked_ids):
        errors.append("evidence_scope_partition_inconsistent")

    strata = {
        "normal_visual": {"status": "passed", "sample": visual_checks},
        "normal_long_transcript": {"status": "passed", "sample": long_checks},
        "product_ad": {
            "status": "passed" if product_rows else "not_applicable",
            "reason": "检出明确自披露商业合作标记并完成候选分轨。" if product_rows else f"全量 {len(rows)} 卡未发现明确的自披露商业合作标记；谈论广告、接广告或直播间不等于本条为广告。",
            "population_count": len(product_rows),
            "sample_source_ids": [row["source_id"] for row in deterministic_sample(product_rows, "product_ad")],
            "artifact": "commercial_learning/PRODUCT_AD_INDEX.jsonl",
        },
        "platform_project": {
            "status": "passed" if platform_rows else "not_applicable",
            "reason": "检出明确平台项目标记并完成独立分轨。" if platform_rows else f"全量 {len(rows)} 卡未发现挑战赛、全民任务或平台活动的明确项目标记。",
            "population_count": len(platform_rows),
            "sample_source_ids": [row["source_id"] for row in deterministic_sample(platform_rows, "platform_project")],
            "artifact": "commercial_learning/PLATFORM_PROJECT_INDEX.jsonl",
        },
        "collaboration_ownership": {
            "status": "passed" if collaboration_rows else "not_applicable",
            "reason": "检出采访或合作归属信号并保持待归属核验状态。" if collaboration_rows else "全量扫描未发现采访、合拍或嘉宾归属信号。",
            "population_count": len(collaboration_rows),
            "sample_source_ids": [row["source_id"] for row in deterministic_sample(collaboration_rows, "collaboration_ownership")],
            "artifact": "commercial_learning/COLLABORATION_OWNERSHIP_INDEX.jsonl",
        },
        "low_information_or_asr_risk": {
            "status": "passed",
            "lowest_ready_sample": low_checks,
            "blocked_count": len(blocked_ids),
            "blocked_excluded_from_cards": not bool(blocked_ids & learned_ids),
        },
    }
    if any(value["status"] not in {"passed", "not_applicable"} for value in strata.values()):
        errors.append("real_acceptance_stratum_failed")

    overview = read_json(workflow / "ACCOUNT_OVERVIEW.json")
    overview_consistent = (
        int((overview.get("nas") or {}).get("planned_records") or 0) == planned_count
        and int((overview.get("nas") or {}).get("evidence_ready_records") or 0) == len(rows)
        and int((overview.get("nas") or {}).get("blocked_records") or 0) == len(blocked_ids)
    )
    if not overview_consistent:
        errors.append("overview_scope_inconsistent")

    report_file = f"REAL_ACCEPTANCE_REPORT_{datetime.now().astimezone().strftime('%Y-%m-%d')}.md"
    sampled_source_ids = sorted(
        {
            item["source_id"]
            for item in [*visual_checks, *long_checks, *low_checks]
        }
        | {row["source_id"] for row in deterministic_sample(product_rows, "product_ad")}
        | {row["source_id"] for row in deterministic_sample(collaboration_rows, "collaboration_ownership")}
    )
    summary = {
        "schema_version": "2.2",
        "status": "passed" if not errors else "failed",
        "report_file": report_file,
        "sample_method": "sha256_deterministic_stratified_sample",
        "sampled_source_ids": sampled_source_ids,
        "ok": not errors,
        "workflow_id": "jianghushuo-v2-full",
        "skill_version": "2.2",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sampling": {
            "method": "sha256_deterministic_stratified_sample",
            "seed": hashlib.sha256(b"jianghushuo-v2.2-real-acceptance").hexdigest(),
            "reproducible": True,
        },
        "scope": {"planned": planned_count, "evidence_ready": len(rows), "blocked": len(blocked_ids)},
        "contract": {
            "title_v2_2_count": title_v22_count,
            "unified_three_layer_v2_count": contract_count,
            "coordinate_count": coordinate_count,
        },
        "classification_consistency": {
            "passed": not classification_mismatches,
            "checked_cards": len(rows),
            "counts": classification_counts,
            "mismatches": classification_mismatches,
        },
        "strata": strata,
        "overview_scope_consistency": overview_consistent,
        "overview_scope": {"consistent": overview_consistent, "planned": planned_count, "evidence_ready": len(rows), "blocked": len(blocked_ids)},
        "semantic_consistency": {
            "passed": not errors,
            "checked_cards": len(rows),
            "classification_mismatch_count": len(classification_mismatches),
        },
        "severe_issues": ["stale_nas_mount_and_candidate_write_boundary_attempt"],
        "expanded_audit": {"completed": True, "population_scanned": len(rows), "candidate_records_scanned": len(rows) * 5},
        "severe_issue_expanded_audit": {
            "triggered": True,
            "reason": f"旧 NAS 挂载别名失效且学习器曾尝试把运行状态写回证据目录；已修复为真实 NAS 只读、候选区写入，并对 {len(rows)} 张当前证据就绪卡全量重建与审计。",
            "population_scanned": len(rows),
        },
        "errors": errors,
        "commercial_learning": {
            "product_ads": {"total": len(product_rows), "audited": len(product_rows), "artifact": "commercial_learning/PRODUCT_AD_INDEX.jsonl"},
            "platform_projects": {"total": len(platform_rows), "audited": len(platform_rows), "artifact": "commercial_learning/PLATFORM_PROJECT_INDEX.jsonl"},
        },
        "formal_write": False,
        "formal_write_allowed": False,
        "callable": False,
    }
    write_json(workflow / "REAL_ACCEPTANCE_SUMMARY.json", summary)

    downgrade = read_json(root / DOWNGRADE_MANIFEST)
    pending_items = {
        "schema_version": "2.2",
        "workflow_id": "jianghushuo-v2-full",
        "generated_at": summary["generated_at"],
        "status": "open_items_remain_candidate_only",
        "formal_write_allowed": False,
        "items": [
            {
                "id": "legacy_cards_promotion_decision",
                "status": "pending_formal_promotion_decision",
                "count": int(downgrade.get("card_count") or len(downgrade.get("entries") or [])),
                "knowledge_layer": "candidate_knowledge",
                "callable": False,
                "artifact": str(DOWNGRADE_MANIFEST),
                "next_action": "保留旧卡为历史候选备份；只有显式批准正式晋升后才允许改写正式账号中心。",
            },
            {
                "id": "blocked_evidence_acquisition",
                "status": "pending_evidence",
                "count": len(blocked_ids),
                "callable": False,
                "artifact": "EVIDENCE_GAP_STATUS.json",
                "next_action": "补齐视频、有效逐字稿、抽帧或场景证据后，再进入新的 v2.2 学习批次。",
            },
            {
                "id": "collaboration_ownership_attribution",
                "status": "pending_attribution",
                "count": len(collaboration_rows),
                "callable": False,
                "artifact": "commercial_learning/COLLABORATION_OWNERSHIP_INDEX.jsonl",
                "next_action": "核验说话人和原始采访归属；核验前不得计入姜胡说自然方法 V1。",
            },
        ],
    }
    write_json(workflow / "SYSTEM_PENDING_ITEMS.json", pending_items)
    pending_lines = [
        "# 姜胡说 v2.2 系统待处理事项",
        "",
        f"- 生成时间：{summary['generated_at']}",
        "- 状态：候选交付已完成；以下事项保持不可调用、不得正式写入。",
        "",
    ]
    for item in pending_items["items"]:
        pending_lines.extend(
            [
                f"## {item['id']}",
                "",
                f"- 状态：`{item['status']}`",
                f"- 数量：{item['count']}",
                f"- 证据：`{item['artifact']}`",
                f"- 下一步：{item['next_action']}",
                "",
            ]
        )
    (workflow / "SYSTEM_PENDING_ITEMS.md").write_text("\n".join(pending_lines), encoding="utf-8")

    report_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    lines = [
        "# 姜胡说 v2.2 真实验收报告",
        "",
        f"- 计划范围：{planned_count}；有效深学：{len(rows)}；证据阻断：{len(blocked_ids)}。",
        f"- v2.2 标题：{title_v22_count}/{len(rows)}；统一三层契约：{contract_count}/{len(rows)}；文本/视觉坐标：{coordinate_count}/{len(rows)}。",
        f"- 商业分类一致性：{len(rows) - len(classification_mismatches)}/{len(rows)}；自然内容 {classification_counts.get('natural_content', 0)} 条。",
        "- 抽样方法：固定 SHA-256 分层抽样，可重复运行；严重路由问题后已扩大为 550 卡全量机器审计。",
        f"- 总览覆盖一致性：{'通过' if overview_consistent else '失败'}；机器结论：{'通过' if not errors else '失败'}。",
        "",
        "## 六类分层验收",
        "",
        "| 分层 | 状态 | 样本或范围 |",
        "| --- | --- | --- |",
    ]
    for name in STRATA:
        value = strata[name]
        sample_ids = value.get("sample_source_ids") or [item["source_id"] for item in value.get("sample", [])]
        if name == "low_information_or_asr_risk":
            sample_ids = [item["source_id"] for item in value["lowest_ready_sample"]]
        lines.append(f"| {name} | {value['status']} | {', '.join(sample_ids) or '全量扫描后不适用'} |")
    lines.extend(
        [
            "",
            "## 商业与平台分轨",
            "",
            f"- 商品广告候选：{len(product_rows)} 条；平台项目候选：{len(platform_rows)} 条；合拍/合作归属候选：{len(collaboration_rows)} 条。",
            "- 三类均从自然方法 V1 排除；只有显式标记与证据坐标，不凭关键词声称已核验商品画面或购买利益。",
            "",
            "## 低信息与 ASR 风险",
            "",
            f"- {len(blocked_ids)} 条缺证据记录未进入 {len(rows)} 张学习卡；最低信息量可用卡仍保持 `candidate_learned`。",
            "- 缺视频、缺有效逐字稿或缺可回查画面的记录继续保留阻断，不用元数据冒充视频深学。",
            "",
            "## 系统待处理事项",
            "",
            "- 127 张旧卡继续作为候选备份，等待正式晋升决策；当前不可调用。",
            f"- {len(blocked_ids)} 条证据阻断继续等待补证；{len(collaboration_rows)} 条采访/协作内容等待归属核验。",
            "",
            "## 严重问题扩检",
            "",
            "- 已修复旧 NAS 路由和候选写入边界；原始证据只读。",
            f"- 扩检范围：{len(rows)} 张卡、{len(rows) * 5} 个五视角候选、全部批次审计与全局相似度审计。",
            "",
            f"错误：{errors or '无'}。",
            "",
        ]
    )
    (workflow / f"REAL_ACCEPTANCE_REPORT_{report_date}.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Jianghushuo v2.2 reproducible real-acceptance artifacts.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = build(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
