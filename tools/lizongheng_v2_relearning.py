from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import CONTRACT_ID, UNIFIED_SECTIONS, validate_card_text
from tools.lizongheng_nas_learning import resolve_evidence_path


PROFILE_ID = "lizongheng"
BATCH_SIZE = 10
TOTAL_ITEMS = 430
CARD_CONTRACT_VERSION = "2.1"
METHOD_REVISION = "cluster_ready_noncallable_v2_3"
LENSES = ("positioning", "topics", "structures", "expression", "counterexamples")
DECISIONS = {
    "supports_candidate",
    "contradicts_candidate",
    "boundary_evidence",
    "insufficient_evidence",
}
LEGACY_ROOT = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/batches")
ANNOTATION_ROOT = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/v2_annotations")
OUTPUT_ROOT = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/v2_relearning")
WORKFLOW_ROOT = Path("10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full")


def is_current_audit(audit: dict[str, Any]) -> bool:
    return (
        audit.get("batch_gate") == "pass"
        and audit.get("unified_card_contract") == CONTRACT_ID
        and audit.get("card_contract_version") == CARD_CONTRACT_VERSION
        and audit.get("learning_method_revision") == METHOD_REVISION
        and int(audit.get("unified_card_passed_count") or 0) == BATCH_SIZE
    )


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    values: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        values.append(value)
    return values


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batch_id(batch_number: int) -> str:
    return f"batch_{batch_number:02d}"


def legacy_cards(root: Path, batch_number: int) -> list[dict[str, Any]]:
    return read_jsonl(root / LEGACY_ROOT / batch_id(batch_number) / "structured_cards.jsonl")


def audit_assessment(assessment: dict[str, Any], card: dict[str, Any]) -> list[str]:
    source_id = str(card.get("source_id") or "")
    errors: list[str] = []
    if str(assessment.get("source_id") or "") != source_id:
        errors.append("source_id_mismatch")
    if assessment.get("schema_version") != "2.0":
        errors.append("invalid_schema_version")
    if assessment.get("reviewer_mode") != "independent_five_lens":
        errors.append("reviewer_mode_not_independent")
    if assessment.get("legacy_card_used_as_evidence") is not True:
        errors.append("legacy_evidence_not_declared")
    lenses = assessment.get("professional_lenses")
    if not isinstance(lenses, dict):
        return errors + ["missing_professional_lenses"]
    if set(lenses) != set(LENSES):
        errors.append("five_lens_scope_mismatch")
    non_empty = 0
    for lens in LENSES:
        value = lenses.get(lens)
        if not isinstance(value, dict):
            errors.append(f"{lens}:missing_assessment")
            continue
        decision = str(value.get("decision") or "")
        if decision not in DECISIONS:
            errors.append(f"{lens}:invalid_decision")
        if decision != "insufficient_evidence":
            non_empty += 1
        if len(normalize(str(value.get("finding") or ""))) < 18:
            errors.append(f"{lens}:shallow_finding")
        evidence_points = value.get("evidence_points")
        if not isinstance(evidence_points, list) or not evidence_points:
            errors.append(f"{lens}:missing_evidence_points")
        elif any(len(normalize(str(point))) < 6 for point in evidence_points):
            errors.append(f"{lens}:shallow_evidence_point")
        candidate_ids = value.get("candidate_ids")
        if not isinstance(candidate_ids, list):
            errors.append(f"{lens}:candidate_ids_not_list")
        elif decision == "insufficient_evidence" and candidate_ids:
            errors.append(f"{lens}:insufficient_evidence_linked_candidate")
        elif decision != "insufficient_evidence" and not candidate_ids:
            errors.append(f"{lens}:missing_candidate_link")
    if non_empty == 0:
        errors.append("all_lenses_insufficient")
    if card.get("commercial_axis") != "正常内容":
        counterexample = lenses.get("counterexamples") or {}
        if counterexample.get("decision") not in {"boundary_evidence", "contradicts_candidate"}:
            errors.append("commercial_content_not_isolated_in_counterexamples")
    return sorted(set(errors))


def audit_candidates(
    batch_cards: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    candidates_by_lens: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    batch_source_ids = {str(card.get("source_id") or "") for card in batch_cards}
    assessment_by_id = {str(item.get("source_id") or ""): item for item in assessments}
    candidate_index: dict[str, dict[str, Any]] = {}
    for lens in LENSES:
        records = candidates_by_lens.get(lens) or []
        if not records:
            errors.append(f"empty_candidate_lens:{lens}")
        for record in records:
            candidate_id = str(record.get("id") or "")
            if not candidate_id:
                errors.append(f"{lens}:candidate_missing_id")
                continue
            if candidate_id in candidate_index:
                errors.append(f"duplicate_candidate_id:{candidate_id}")
            candidate_index[candidate_id] = record
            if record.get("callable") is not False:
                errors.append(f"{candidate_id}:candidate_must_not_be_callable")
            if record.get("type") != lens:
                errors.append(f"{candidate_id}:type_mismatch")
            for field in ("title", "summary"):
                if len(normalize(str(record.get(field) or ""))) < 12:
                    errors.append(f"{candidate_id}:shallow_{field}")
            tags = record.get("tags")
            if not isinstance(tags, list) or not tags:
                errors.append(f"{candidate_id}:missing_tags")
            refs = [str(value) for value in record.get("source_refs") or []]
            if not refs:
                errors.append(f"{candidate_id}:missing_source_refs")
            unknown_refs = sorted(set(refs) - batch_source_ids)
            if unknown_refs:
                errors.append(f"{candidate_id}:unknown_source_refs:{','.join(unknown_refs)}")
            for source_id in refs:
                assessment = assessment_by_id.get(source_id, {})
                lens_value = (assessment.get("professional_lenses") or {}).get(lens) or {}
                if candidate_id not in (lens_value.get("candidate_ids") or []):
                    errors.append(f"{candidate_id}:unbacked_source_ref:{source_id}")
    for source_id, assessment in assessment_by_id.items():
        for lens in LENSES:
            value = (assessment.get("professional_lenses") or {}).get(lens) or {}
            for candidate_id in value.get("candidate_ids") or []:
                candidate = candidate_index.get(str(candidate_id))
                if candidate is None:
                    errors.append(f"{source_id}:{lens}:unknown_candidate:{candidate_id}")
                    continue
                if candidate.get("type") != lens:
                    errors.append(f"{source_id}:{lens}:candidate_lens_mismatch:{candidate_id}")
                if source_id not in {str(ref) for ref in candidate.get("source_refs") or []}:
                    errors.append(f"{source_id}:{lens}:candidate_missing_backref:{candidate_id}")
    return sorted(set(errors)), candidate_index


def audit_quote_review(review: dict[str, Any], card: dict[str, Any]) -> list[str]:
    source_id = str(card.get("source_id") or "")
    errors: list[str] = []
    if str(review.get("source_id") or "") != source_id:
        errors.append("quote_review_source_id_mismatch")
    if review.get("review_mode") != "asr_quality_screened":
        errors.append("quote_review_mode_invalid")
    retained = [str(value) for value in review.get("retained_quotes") or []]
    rejected_records = review.get("rejected_quotes") or []
    if not isinstance(rejected_records, list):
        return errors + ["rejected_quotes_not_list"]
    rejected: list[str] = []
    for record in rejected_records:
        if not isinstance(record, dict) or not str(record.get("text") or ""):
            errors.append("invalid_rejected_quote")
            continue
        rejected.append(str(record["text"]))
        if len(normalize(str(record.get("reason") or ""))) < 6:
            errors.append("rejected_quote_missing_reason")
    originals = [str(value) for value in card.get("evidence_quotes") or []]
    if set(retained) & set(rejected):
        errors.append("quote_review_overlap")
    if set(retained) | set(rejected) != set(originals):
        errors.append("quote_review_scope_mismatch")
    return sorted(set(errors))


def audit_legacy(root: Path) -> dict[str, Any]:
    root = root.resolve()
    legacy_batches: list[dict[str, Any]] = []
    for audit_path in sorted((root / LEGACY_ROOT).glob("batch_*/audit.json")):
        legacy_audit = read_json(audit_path)
        legacy_batch_id = str(legacy_audit.get("batch_id") or audit_path.parent.name)
        v2_audit_path = root / OUTPUT_ROOT / legacy_batch_id / "audit.json"
        v2_audit = read_json(v2_audit_path) if v2_audit_path.exists() else {}
        v2_pass = is_current_audit(v2_audit)
        legacy_batches.append(
            {
                "batch_id": legacy_batch_id,
                "legacy_gate": legacy_audit.get("batch_gate"),
                "legacy_item_count": legacy_audit.get("expected_count"),
                "v2_compatible": v2_pass,
                "decision": "retain_as_v2_evidence" if v2_pass else "relearn_required",
                "reason": (
                    "已补齐统一十二段单卡、逐条五视角评估、候选双向引用和v2批次审核。"
                    if v2_pass
                    else "缺少统一十二段单卡或逐条五视角与候选双向引用，不能计入新方法完成进度。"
                ),
            }
        )
    report = {
        "profile_id": PROFILE_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "legacy_batches": legacy_batches,
        "legacy_items": sum(int(item.get("legacy_item_count") or 0) for item in legacy_batches),
        "v2_compatible_batches": [item["batch_id"] for item in legacy_batches if item["v2_compatible"]],
        "relearn_required_batches": [item["batch_id"] for item in legacy_batches if not item["v2_compatible"]],
        "formal_ingest_allowed": False,
    }
    write_json(root / OUTPUT_ROOT / "compatibility_report.json", report)
    update_status(root)
    return report


def update_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    passed_batches: list[str] = []
    completed_ids: list[str] = []
    for audit_path in sorted((root / OUTPUT_ROOT).glob("batch_*/audit.json")):
        audit = read_json(audit_path)
        if not is_current_audit(audit):
            continue
        passed_batches.append(str(audit.get("batch_id") or audit_path.parent.name))
        completed_ids.extend(str(value) for value in audit.get("source_ids") or [])
    status = {
        "profile_id": PROFILE_ID,
        "schema_version": "2.0",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total_items": TOTAL_ITEMS,
        "batch_size": BATCH_SIZE,
        "total_batches": (TOTAL_ITEMS + BATCH_SIZE - 1) // BATCH_SIZE,
        "v2_passed_batches": passed_batches,
        "v2_completed_items": len(set(completed_ids)),
        "v2_remaining_items": TOTAL_ITEMS - len(set(completed_ids)),
        "v2_completion_ratio": round(len(set(completed_ids)) / TOTAL_ITEMS, 4),
        "learning_method_revision": METHOD_REVISION,
        "user_review_pending_batches": passed_batches,
        "legacy_passes_do_not_count": True,
        "formal_ingest_allowed": False,
    }
    write_json(root / OUTPUT_ROOT / "status.json", status)
    return status


def sync_workflow_candidates(root: Path) -> None:
    root = root.resolve()
    for lens in LENSES:
        records: list[dict[str, Any]] = []
        for audit_path in sorted((root / OUTPUT_ROOT).glob("batch_*/audit.json")):
            audit = read_json(audit_path)
            if not is_current_audit(audit):
                continue
            records.extend(read_jsonl(audit_path.parent / "candidates" / f"{lens}.jsonl"))
        write_jsonl(root / WORKFLOW_ROOT / "candidates" / f"{lens}.jsonl", records)


def render_review_packet(
    name: str,
    cards: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    candidates_by_lens: dict[str, list[dict[str, Any]]],
    audit: dict[str, Any],
) -> str:
    assessment_by_id = {str(item.get("source_id") or ""): item for item in assessments}
    lines = [
        f"# 李宗恒 {name} v2重学成果审核包",
        "",
        "## 审核结论",
        "",
        f"- 批次门禁：`{audit['batch_gate']}`",
        f"- 学习方法版本：`{audit['learning_method_revision']}`",
        "- 用户审核：`pending`（机器门禁通过不等于用户确认）",
        f"- 视频条数：{len(cards)}",
        f"- 逐条五视角通过：{audit['passed_card_count']}/{len(cards)}",
        f"- ASR引用质量筛查：{len(cards)}/{len(cards)}",
        f"- 批次错误：{len(audit['batch_errors'])}",
        "- 旧版卡片：只作为来源证据，不自动继承完成状态。",
        "- 正式入库：锁定。",
        "",
        "## 核心成果：统一十二段学习卡",
        "",
    ]
    card_audit_by_id = {
        str(item.get("source_id") or ""): item for item in audit.get("unified_card_audits") or []
    }
    for card in cards:
        source_id = str(card.get("source_id") or "")
        title = str((card.get("source") or {}).get("title") or source_id)
        card_audit = card_audit_by_id.get(source_id, {})
        lines.append(
            f"- [{title}](cards/{source_id}.md) - 契约 `{audit.get('unified_card_contract', '')}`，"
            f"验证 `{card_audit.get('decision', 'unknown')}`"
        )
    lines.extend(["", "## 逐条五视角学习", ""])
    for index, card in enumerate(cards, 1):
        source_id = str(card.get("source_id") or "")
        title = str((card.get("source") or {}).get("title") or source_id)
        assessment = assessment_by_id.get(source_id, {})
        lines.extend(
            [
                f"### {index}. {title}",
                "",
                f"- source_id：`{source_id}`",
                f"- 原分类：{card.get('content_form')} / {card.get('relationship_axis')} / {card.get('commercial_axis')}",
                "",
            ]
        )
        for lens in LENSES:
            value = (assessment.get("professional_lenses") or {}).get(lens) or {}
            points = "；".join(str(point) for point in value.get("evidence_points") or [])
            candidate_ids = "、".join(f"`{item}`" for item in value.get("candidate_ids") or []) or "无"
            lines.extend(
                [
                    f"#### {lens}",
                    "",
                    f"- 判断：`{value.get('decision', '')}`",
                    f"- 结论：{value.get('finding', '')}",
                    f"- 证据点：{points}",
                    f"- 关联候选：{candidate_ids}",
                    "",
                ]
            )
    lines.extend(["## 五类候选池", ""])
    for lens in LENSES:
        lines.extend([f"### {lens}", ""])
        for candidate in candidates_by_lens.get(lens) or []:
            refs = "、".join(f"`{item}`" for item in candidate.get("source_refs") or [])
            lines.extend(
                [
                    f"- **{candidate.get('title')}**（`{candidate.get('id')}`）",
                    f"  - 摘要：{candidate.get('summary')}",
                    f"  - 证据：{refs}",
                ]
            )
        lines.append("")
    if audit["batch_errors"]:
        lines.extend(["## 退回原因", ""])
        lines.extend(f"- {error}" for error in audit["batch_errors"])
        lines.append("")
    return "\n".join(lines)


def _lens(assessment: dict[str, Any], lens: str) -> dict[str, Any]:
    return (assessment.get("professional_lenses") or {}).get(lens) or {}


def _candidate_records_for_assessment(
    assessment: dict[str, Any], candidate_index: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lens in LENSES:
        for candidate_id in _lens(assessment, lens).get("candidate_ids") or []:
            candidate_id = str(candidate_id)
            if candidate_id in candidate_index and candidate_id not in seen:
                seen.add(candidate_id)
                records.append(candidate_index[candidate_id])
    return records


def _hashtags(title: str) -> str:
    tags = [item.strip("，。！？!?；;：:") for item in re.findall(r"#([^#@\s]+)", title)]
    return "、".join(tag for tag in tags if tag) or "未提取到显式话题或标签；不补造。"


def _opening_setting(synopsis: str) -> str:
    value = str(synopsis or "").strip()
    parts = re.split(r"[；;。]", value, maxsplit=1)
    first = parts[0].strip("，,。；; ")
    if len(normalize(first)) > 12:
        return first
    comma_parts = re.split(r"[，,]", value, maxsplit=2)
    return "，".join(comma_parts[:2]).strip("，,。；; ") or value


def render_unified_card(
    card: dict[str, Any],
    assessment: dict[str, Any],
    candidate_index: dict[str, dict[str, Any]],
    quote_review: dict[str, Any] | None = None,
) -> str:
    source_id = str(card.get("source_id") or "")
    source = card.get("source") or {}
    transcript_path = resolve_evidence_path(str(source.get("transcript_path") or ""))
    video_path = resolve_evidence_path(str(source.get("video_path") or ""))
    frames_path = resolve_evidence_path(str(source.get("frames_path") or ""))
    title = str(source.get("title") or source_id)
    positioning = _lens(assessment, "positioning")
    topics = _lens(assessment, "topics")
    structures = _lens(assessment, "structures")
    expression = _lens(assessment, "expression")
    counterexamples = _lens(assessment, "counterexamples")
    linked_candidates = _candidate_records_for_assessment(assessment, candidate_index)
    primary_candidate = next(
        (item for item in linked_candidates if item.get("type") == "structures"),
        next((item for item in linked_candidates if item.get("type") == "topics"), {}),
    )
    candidate_title = str(primary_candidate.get("title") or "本条结构候选")
    candidate_summary = str(primary_candidate.get("summary") or structures.get("finding") or "")
    topic_candidate = next((item for item in linked_candidates if item.get("type") == "topics"), {})
    expression_candidate = next((item for item in linked_candidates if item.get("type") == "expression"), {})
    counter_candidate = next((item for item in linked_candidates if item.get("type") == "counterexamples"), {})
    topic_title = str(topic_candidate.get("title") or "本条选题机制")
    expression_title = str(expression_candidate.get("title") or "本条表达机制")
    counter_title = str(counter_candidate.get("title") or "单卡证据边界")
    quote_review = quote_review or {
        "retained_quotes": card.get("evidence_quotes") or [],
        "rejected_quotes": [],
    }
    quotes = [str(item) for item in quote_review.get("retained_quotes") or []]
    rejected_quotes = [str(item.get("text") or "") for item in quote_review.get("rejected_quotes") or []]
    quote_text = "；".join(f"“{item}”" for item in quotes) or "未保留；现有ASR句子均未通过语义质量筛查。"
    if rejected_quotes:
        quote_quality_note = f"疑似ASR错字已退回：{'；'.join(f'“{item}”' for item in rejected_quotes)}。"
    elif not quotes:
        quote_quality_note = "未保留可引用原句；短音轨、歌词或低信息ASR不作为事实证据。"
    else:
        quote_quality_note = "未发现需要退回的明显ASR错字。"
    quote_follow_up = " 保留句仍须在正式对外引用前回看原视频。" if quotes else ""
    visual = card.get("visual_review") or {}
    if visual.get("performed"):
        media_status = (
            f"完整逐字稿或短音轨状态已记录；已人工复核 {visual.get('frames_inspected')} 帧；"
            f"视觉结论：{visual.get('finding')}"
        )
        media_learning = str(visual.get("finding") or expression.get("finding") or "")
    else:
        media_status = "原视频、完整逐字稿和抽帧索引均可用；逐字稿已通过引用回查，未触发短文本强制视觉复核。"
        media_learning = (
            f"场景与表演按已审逐字稿和抽帧索引学习：{expression.get('finding', '')}；"
            "未做逐镜头语言标注，不补造景别、机位或剪辑动作。"
        )
    commercial = str(card.get("commercial_axis") or "待判定")
    if commercial == "正常内容" and card.get("core_direction_eligible") is not False:
        isolation = "无品牌卖点、购买行动或平台任务；允许作为核心方向候选证据，仍需跨卡验证。"
        cross_status = "支持候选"
        card_decision = "保留为内容拆解候选卡，进入五视角候选池。"
    elif commercial == "正常内容":
        isolation = "无商业信号，但本条只保留定位、表达或边界证据，不进入自然选题与核心方向频次。"
        cross_status = "边界证据（可支持定位）"
        card_decision = "保留为定位或边界卡，不作为正常选题方向的独立证明。"
    else:
        isolation = f"按“{commercial}”隔离；只保留结构、表达或边界证据，不进入正常内容方向频次。"
        cross_status = "边界证据"
        card_decision = "保留为商业或平台边界卡，不作为正常方向方法的独立证明。"
    candidate_titles = "、".join(f"{item.get('title')}（{item.get('id')}）" for item in linked_candidates)
    evidence_gap = (
        "已完成短文本视觉复核，但未形成逐镜头时间码，视觉结论仅限已检查帧。"
        if visual.get("performed")
        else "逐字稿和抽帧索引可用，但未完成逐镜头时间码标注；媒体表现只写已证实部分。"
    )
    direction = f"{card.get('relationship_axis')} / {card.get('comedy_engine')}"
    opening_setting = _opening_setting(str(card.get("synopsis") or ""))
    reusable_sentence = (
        f"当【目标关系中的人物】遇到【可迁移冲突】，先引入【{topic_title}】，"
        f"再按【{candidate_title}】升级，最后用【动作、台词或真相】改变前文含义。"
    )
    commercial_template_boundary = (
        "把【品牌/平台任务段】与【自然剧情段】分开标注；如果产品接管解决方案，只保留商业边界证据。"
        if commercial != "正常内容"
        else "不主动添加品牌或购买动作；发现商业信号时立即退出正常方向统计。"
    )
    content_form = str(card.get("content_form") or "")
    if any(token in content_form for token in ("剧情", "合拍", "唱演", "故事")):
        structure_block = "\n".join(
            (
                f"- 开头设定：{opening_setting}。",
                f"- 核心冲突：{card.get('conflict')}",
                f"- 升级：{structures.get('finding', '')}",
                f"- 转折或笑点：{card.get('turning_point')}",
                "- 收尾：停在上述关系变化、行动结果或真相揭示上；本卡不把剧情结果额外拔高为价值结论。",
            )
        )
    else:
        structure_block = "\n".join(
            (
                f"- 黄金3秒：{title}；用标题中的人物矛盾或核心判断建立观看问题。",
                f"- 观点提出：{topics.get('finding', '')}",
                f"- 证据或案例：{card.get('synopsis')}",
                f"- 推演：{structures.get('finding', '')}",
                f"- 收尾：{card.get('turning_point')}",
            )
        )
    return f"""# 李宗恒统一账号发布资产学习卡：{title}

学习卡契约：{CONTRACT_ID}
学习方法版本：{METHOD_REVISION}
source_id：{source_id}
原内容链接：{source.get('source_url', '')}
账号：李宗恒
平台：抖音
主方向：{direction}
学习批次：{card.get('batch_id')}-mechanism-routed-relearn
状态：candidate_learned

## 1. 证据边界

- 主证据：原视频、完整逐字稿、抽帧索引及可回查 source_id `{source_id}`。
- 辅助证据：发布标题、正文或文案、显式话题标签、旧版证据卡与本批五视角评估；这些不重复计算为独立来源。
- 证据状态：{media_status}
- 原始路径状态：逐字稿 `{transcript_path}`；视频 `{video_path}`；抽帧 `{frames_path}`。

## 2. 为什么值得学习

- 学习价值：{card.get('learning_value_axis')}；本条不是因指标入选，而是因为其内容机制和边界可被证据解释。
- 定位价值：{positioning.get('finding', '')}
- 结构价值：{structures.get('finding', '')}
- 表达价值：{expression.get('finding', '')}

## 3. 多维分类与商业隔离

- 内容形态：{card.get('content_form')}
- 人物关系：{card.get('relationship_axis')}
- 场景：{card.get('scene_axis')}
- 喜剧或表达机制：{card.get('comedy_engine')}
- 商业属性：{commercial}
- 学习价值：{card.get('learning_value_axis')}
- 分类依据：{card.get('classification_reason')}
- 隔离判断：{isolation}
- 商业判断依据：{card.get('commercial_reason')}

## 4. 核心观点

- 内容层观点：{topics.get('finding', '')}
- 结构层观点：{structures.get('finding', '')}
- 表达层观点：{expression.get('finding', '')}
- 边界判断：{counterexamples.get('finding', '')}

## 5. 内容结构

{structure_block}

## 6. 发布内容层学习

- 标题：{title}
- 正文或文案：{source.get('desc') or '未提取到独立正文；当前发布文案与标题相同。'}
- 话题或标签：{_hashtags(title)}
- 标题学习：{card.get('copy_learning')}
- 话题学习：{card.get('topic_learning')}
- 协同判断：发布层只负责设定、情绪或分发入口；完整分类以视频、逐字稿和视觉证据为准。

## 7. 视频/图文表现层学习

- 媒体类型：视频。
- 分析状态：{media_status}
- 表现学习：{media_learning}
- 节奏学习：{structures.get('finding', '')}
- 表演与场景：以 `{card.get('relationship_axis')}` 关系和 `{card.get('scene_axis')}` 场景承载冲突；未证实的镜头语言不补写。

## 8. 金句与表达素材

- 原文金句：{quote_text}
- 引用质量：{quote_quality_note}{quote_follow_up}
- 提炼表达（非原话）：{expression.get('finding', '')}
- 可复用句式：{reusable_sentence}
- 引用边界：只有“原文金句”来自逐字稿；提炼表达和可复用句式均为学习总结，不得冒充原话。

## 9. 可复用选题与案例

- 可复用选题：{card.get('reusable_topic')}
- 跨场景选题候选：{topics.get('finding', '')}
- 可复用案例：`{source_id}` 中，{card.get('synopsis')}
- 复用边界：{counterexamples.get('finding', '')}

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。关联候选：{candidate_titles or '无；本条仅保留边界证据。'}
> 可调用：false。单卡审核通过也不代表方法可调用，必须先聚合为机制簇并完成后续验证。

### R - 原始证据

- source_id：`{source_id}`。
- 可回查原句：{quote_text}
- 剧情证据：{card.get('synopsis')}

### I - 初步解释

候选“{candidate_title}”：{candidate_summary}

### A1 - 本条案例

本条在 `{card.get('scene_axis')}` 中，以 `{card.get('relationship_axis')}` 关系建立“{card.get('conflict')}”，并通过“{card.get('turning_point')}”完成结果。

### A2 - 未来触发场景

- 触发机制：只有候选完成跨卡三重验证，且新任务确实需要“{candidate_title}”与“{candidate_summary}”的核心因果时，才可另行晋级；当前不可调用。
- 适用关系：`{card.get('relationship_axis')}` 只是本条已证实关系；其他人物关系能否承载同类冲突，属于后续验证问题，不在本卡中直接迁移。
- 可迁移场景：`{card.get('scene_axis')}` 只是本条已证实场景；更换场景后能否同时保留“{topic_title}”与“{candidate_title}”，仅作为待验证假设，当前不可用于生成任务。
- 不触发条件：只出现本条人物关系、场景、道具或“{card.get('reusable_topic')}”中的题材词，但没有“{candidate_title}”的结构因果时，不得调用。
- 来源选题示例：{card.get('reusable_topic')}

### E - 初步执行步骤

> 本小节执行的是候选验证，不是内容生成。

1. 先在已审核历史卡中按账号、内容形态和主任务方向建立验证样本，不使用待生成草稿反向寻找方法。
2. 再按“{candidate_title}”核对至少三条独立内容；只有核心因果重复成立，才进入机制簇验证。
3. 为 `{card.get('relationship_axis')}` 和 `{card.get('scene_axis')}` 各寻找一个同机制正例与一个题材相似但机制不同的反例，检验是否只是名词共现。
4. 对照“{expression_title}”检查标题、对白或视觉信息是否稳定承担同一表达作用，不把一次性措辞提升为方法。
5. 用“{counter_title}”复核广告、平台活动、合拍归属和证据质量；V1、V2、V3全部通过后，另行生成正式可调用方法。

### B - 边界与反例

- {counterexamples.get('finding', '')}
- {isolation}
- 单卡只能支持候选，未经过V1跨内容证据、V2预测指导力和V3账号独特性验证，不得写成稳定方法。

## 11. 可复用模板

> 以下仅为候选验证模板，当前不可用于生成发布内容。

```text
验证范围：在【同账号已审核内容】中确认【主任务方向】与【内容形态】。
正例检查：至少三条独立内容均命中【{candidate_title}】的核心因果，而非只共享人物、场景或道具。
选题检查：确认【{topic_title}】在每条正例中承担同一种冲突作用。
结构检查：确认【{candidate_title}】在不同事实中仍保留相同因果和升级方向。
表达检查：确认【{expression_title}】稳定组织标题、对白或视觉信息，而非一次性措辞。
反例检查：用【{counter_title}】排除题材相似但机制不同的内容；{commercial_template_boundary}
晋级条件：V1跨内容证据、V2预测指导力、V3账号独特性全部通过后，另建正式方法卡；此前保持不可调用。
```

- 可验证变量：人物关系、场景、冲突规则、升级方向和表达作用。
- 适用边界：本模板只验证候选，不指导生成；商业内容必须独立隔离。

## 12. 证据缺口与候选判断

- 证据缺口：{evidence_gap} 此外，ASR逐字稿可能包含错字，正式对外引用需回看原视频；本条仍缺少跨内容独立证据和发布表现数据，不能证明方法稳定或必然有效。
- 卡片判断：{card_decision}
- 跨卡状态：{cross_status}；后续进入五视角合并和三重验证，不直接写正式账号中心。
"""


def audit_unified_card_text(text: str, source_id: str) -> list[str]:
    result = validate_card_text(text)
    errors = list(result.errors)
    if result.schema != CONTRACT_ID:
        errors.append("unified_card_wrong_schema")
    if len(result.sections) != len(UNIFIED_SECTIONS):
        errors.append("unified_card_section_count_mismatch")
    if f"source_id：{source_id}" not in text:
        errors.append("unified_card_source_id_mismatch")
    if f"学习方法版本：{METHOD_REVISION}" not in text:
        errors.append("learning_method_revision_mismatch")
    if "状态：candidate_learned" not in text:
        errors.append("card_status_must_wait_for_user_review")
    if "可调用：false" not in text:
        errors.append("single_card_method_must_not_be_callable")
    if "当前不可调用" not in text:
        errors.append("single_card_missing_current_noncallable_boundary")
    for forbidden in ("可调用本候选", "可以跨场景调用"):
        if forbidden in text:
            errors.append(f"single_card_callability_contradiction:{forbidden}")
    a2 = result.sections.get("方法候选与可复用方法论", "")
    if "先在已审核历史卡中按账号、内容形态和主任务方向建立验证样本" not in a2:
        errors.append("a2_missing_evidence_first_validation_route")
    if "只出现本条人物关系、场景、道具" not in a2:
        errors.append("a2_missing_noun_match_exclusion")
    if len(normalize(text)) < 1800:
        errors.append("unified_card_too_shallow")
    return sorted(set(errors))


def review_batch(root: Path, batch_number: int) -> dict[str, Any]:
    root = root.resolve()
    name = batch_id(batch_number)
    cards = legacy_cards(root, batch_number)
    input_dir = root / ANNOTATION_ROOT / name
    assessments_path = input_dir / "assessments.jsonl"
    assessments = read_jsonl(assessments_path)
    candidates_by_lens = {
        lens: read_jsonl(input_dir / "candidates" / f"{lens}.jsonl") for lens in LENSES
    }
    quote_reviews_path = input_dir / "quote_reviews.jsonl"
    quote_reviews = read_jsonl(quote_reviews_path)
    expected_ids = [str(card.get("source_id") or "") for card in cards]
    assessment_ids = [str(item.get("source_id") or "") for item in assessments]
    batch_errors: list[str] = []
    if len(cards) != BATCH_SIZE:
        batch_errors.append(f"legacy_batch_size_mismatch:{len(cards)}")
    if len(assessment_ids) != len(set(assessment_ids)):
        batch_errors.append("duplicate_assessment_source_id")
    if set(assessment_ids) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(assessment_ids))
        extra = sorted(set(assessment_ids) - set(expected_ids))
        if missing:
            batch_errors.append(f"missing_assessments:{','.join(missing)}")
        if extra:
            batch_errors.append(f"unexpected_assessments:{','.join(extra)}")
    assessment_by_id = {str(item.get("source_id") or ""): item for item in assessments}
    quote_review_by_id = {str(item.get("source_id") or ""): item for item in quote_reviews}
    if set(quote_review_by_id) != set(expected_ids):
        batch_errors.append("quote_review_scope_mismatch")
    card_audits: list[dict[str, Any]] = []
    for card in cards:
        source_id = str(card.get("source_id") or "")
        assessment = assessment_by_id.get(source_id)
        errors = ["missing_assessment"] if assessment is None else audit_assessment(assessment, card)
        quote_review = quote_review_by_id.get(source_id)
        errors.extend(["missing_quote_review"] if quote_review is None else audit_quote_review(quote_review, card))
        card_audits.append(
            {"source_id": source_id, "decision": "pass" if not errors else "reject", "errors": errors}
        )
    candidate_errors, candidate_index = audit_candidates(cards, assessments, candidates_by_lens)
    batch_errors.extend(candidate_errors)
    passed_cards = sum(item["decision"] == "pass" for item in card_audits)
    output_dir = root / OUTPUT_ROOT / name
    output_dir.mkdir(parents=True, exist_ok=True)
    if assessments_path.exists():
        write_jsonl(output_dir / "assessments.jsonl", assessments)
    if quote_reviews_path.exists():
        write_jsonl(output_dir / "quote_reviews.jsonl", quote_reviews)
    for lens, records in candidates_by_lens.items():
        write_jsonl(output_dir / "candidates" / f"{lens}.jsonl", records)
    unified_card_audits: list[dict[str, Any]] = []
    for card in cards:
        source_id = str(card.get("source_id") or "")
        assessment = assessment_by_id.get(source_id)
        if assessment is None:
            unified_card_audits.append(
                {"source_id": source_id, "decision": "reject", "errors": ["missing_assessment"]}
            )
            continue
        card_text = render_unified_card(card, assessment, candidate_index, quote_review_by_id.get(source_id))
        card_path = output_dir / "cards" / f"{source_id}.md"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(card_text, encoding="utf-8")
        errors = audit_unified_card_text(card_text, source_id)
        unified_card_audits.append(
            {"source_id": source_id, "decision": "pass" if not errors else "reject", "errors": errors}
        )
    unified_card_passed_count = sum(item["decision"] == "pass" for item in unified_card_audits)
    if unified_card_passed_count != BATCH_SIZE:
        batch_errors.append(f"unified_card_gate_failed:{unified_card_passed_count}/{BATCH_SIZE}")
    gate_pass = passed_cards == len(cards) == BATCH_SIZE and not batch_errors
    audit = {
        "batch_id": name,
        "schema_version": "2.1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "expected_count": BATCH_SIZE,
        "assessment_count": len(assessments),
        "passed_card_count": passed_cards,
        "failed_card_count": len(cards) - passed_cards,
        "candidate_counts": {lens: len(records) for lens, records in candidates_by_lens.items()},
        "batch_errors": sorted(set(batch_errors)),
        "batch_gate": "pass" if gate_pass else "reject",
        "gate_rule": "10张统一十二段学习卡、10条逐条五视角、逐条ASR引用质量筛查、五类候选非空且双向引用一致；任一项失败整批退回。",
        "unified_card_contract": CONTRACT_ID,
        "card_contract_version": CARD_CONTRACT_VERSION,
        "learning_method_revision": METHOD_REVISION,
        "user_review_status": "pending",
        "unified_card_count": len(unified_card_audits),
        "unified_card_passed_count": unified_card_passed_count,
        "unified_card_audits": unified_card_audits,
        "source_ids": expected_ids,
        "input_hashes": {
            "legacy_cards": sha256_file(root / LEGACY_ROOT / name / "structured_cards.jsonl"),
            "assessments": sha256_file(assessments_path) if assessments_path.exists() else "",
            "quote_reviews": sha256_file(quote_reviews_path) if quote_reviews_path.exists() else "",
        },
        "cards": card_audits,
        "formal_ingest_allowed": False,
    }
    write_json(output_dir / "audit.json", audit)
    summary_lines = [
        f"# 李宗恒 {name} v2重学审核",
        "",
        f"- 批次门禁：{audit['batch_gate']}",
        f"- 逐条五视角：{passed_cards}/{len(cards)}",
        f"- 统一十二段单卡：{unified_card_passed_count}/{len(cards)}",
        f"- ASR引用质量筛查：{len(quote_reviews)}/{len(cards)}",
        f"- 批次错误：{len(audit['batch_errors'])}",
        "- 旧卡用途：仅作来源证据，不自动继承旧版完成状态。",
        "- 正式入库：锁定。",
        "",
        "## 五视角候选数量",
        "",
    ]
    summary_lines.extend(f"- {lens}: {len(candidates_by_lens[lens])}" for lens in LENSES)
    if audit["batch_errors"]:
        summary_lines.extend(["", "## 退回原因", ""])
        summary_lines.extend(f"- {error}" for error in audit["batch_errors"])
    write_json(output_dir / "audit.json", audit)
    (output_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    (output_dir / "review_packet.md").write_text(
        render_review_packet(name, cards, assessments, candidates_by_lens, audit), encoding="utf-8"
    )
    status = update_status(root)
    if gate_pass:
        sync_workflow_candidates(root)
    audit["v2_status"] = status
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and relearn 李宗恒 batches against account-learning v2.")
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit-legacy")
    review = subparsers.add_parser("review-batch")
    review.add_argument("--batch", type=int, required=True)
    args = parser.parse_args()
    root = Path(args.root)
    if args.command == "audit-legacy":
        result = audit_legacy(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = review_batch(root, args.batch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["batch_gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
