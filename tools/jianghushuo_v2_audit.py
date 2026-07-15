from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from tools.account_learning_card import meaningful_lines, parse_numbered_sections, validate_card_text
from tools.jianghushuo_nas import CURRENT_ACCOUNT_DIR, read_transcript_lines, transcript_path
from tools.jianghushuo_v2_learning import (
    ACCOUNT_NAME,
    LENSES,
    WORKFLOW_ID,
    WORKFLOW_ROOT,
    evidence_ready_sequence,
    full_relearning_sequence,
    read_json,
    relearning_sequence,
    write_json,
)


CORE_SECTIONS = (
    "为什么值得学习",
    "核心观点",
    "内容结构",
    "金句与表达素材",
    "可复用选题与案例",
    "方法候选与可复用方法论",
)
BOILERPLATE_MARKERS = (
    "升级判断",
    "旧卡只提供待复核假设",
    "复用边界",
    "卡片判断",
    "跨卡状态",
    "单卡、旧卡和阶段1观察",
    "单卡、旧卡和阶段 1 观察",
    "来源人物关系只作为本条案例",
    "来源场景只作为a1",
    "单卡与阶段 1 观察不可直接调用",
    "本条来自 NAS 598 条完整计划",
    "本条来自NAS598条完整计划",
    "用独立内容检查既有方法是否稳定",
    "评论正文不参与学习",
    "开头直接给出内容承诺",
    "只复用问题—证据—判断结构",
    "只复用问题证据判断结构",
    "方向评分接近需要人工复核",
    "多个方向并列需要人工复核",
    "发布层缺少明确方向信号",
    "抽帧缺失视觉结论降级",
    "场景切分缺失镜头节奏不作强结论",
    "用一句话提出",
    "回查",
    "先提出",
    "只命中",
)


def normalize(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", value).lower()


def source_id_from_card(text: str) -> str:
    match = re.search(r"^source_id[:：]\s*(\d+)\s*$", text, re.M)
    return match.group(1) if match else ""


def labeled_value(section: str, label: str) -> str:
    match = re.search(rf"(?:^|\n)\s*-\s*{re.escape(label)}(?:（[^）]+）)?[:：]\s*(.+)", section)
    return match.group(1).strip() if match else ""


def distinctive_lines(text: str) -> list[str]:
    sections = parse_numbered_sections(text)[0]
    values: list[str] = []
    for name in CORE_SECTIONS:
        for line in meaningful_lines(sections.get(name, "")):
            normalized_line = normalize(line)
            if any(normalize(marker) in normalized_line for marker in BOILERPLATE_MARKERS):
                continue
            cleaned = re.sub(r"^[^：:]{1,20}[：:]\s*", "", line).strip()
            normalized = normalize(cleaned)
            if len(normalized) >= 12:
                values.append(normalized)
    return values


def bigrams(value: str) -> set[str]:
    return {value[index : index + 2] for index in range(max(len(value) - 1, 0))}


def jaccard(left: str, right: str) -> float:
    left_set = bigrams(left)
    right_set = bigrams(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def jaccard_sets(left_set: set[str], right_set: set[str]) -> float:
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def transcript_text(path: Path) -> str:
    return normalize("".join(read_transcript_lines(path)))


def markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# 姜胡说 2.2 完整重学雷同与偷懒审计",
        "",
        f"- 审计时间：{report['generated_at']}",
        f"- 结论：{'通过' if report['ok'] else '未通过'}",
        f"- 卡片覆盖：{metrics['card_count']}/{metrics['expected_count']}",
        f"- 统一契约通过：{metrics['contract_passed_count']}/{metrics['expected_count']}",
        f"- 原文回查通过：{metrics['quote_supported_count']}/{metrics['expected_count']}",
        f"- 五视角候选：{metrics['candidate_counts']}",
        f"- 正式写入：{str(report['formal_write_allowed']).lower()}",
        "",
        "## 雷同与偷懒检查",
        "",
        f"- 重复 source_id：{len(report['duplicate_source_ids'])}",
        f"- 高相似卡片对：{len(report['high_similarity_pairs'])}",
        f"- 跨卡重复核心句：{len(report['repeated_core_lines'])}",
        f"- 五视角重复摘要：{len(report['duplicate_candidate_summaries'])}",
        f"- 与旧卡近乎整卡复制：{len(report['excessive_legacy_overlap'])}",
        f"- 证据原文无法回查：{len(report['unsupported_quotes'])}",
        "",
        "## 失败项",
        "",
    ]
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- 无。")
    lines.extend(["", "## 最高相似样本", ""])
    for pair in report["top_similarity_pairs"][:20]:
        lines.append(f"- `{pair['left']}` ↔ `{pair['right']}`：{pair['similarity']:.3f}")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本报告只验收候选学习产物，不允许据此恢复正式知识。",
            "- 阶段 2–6 已另行完成三重验证、RIA++ 构造、方法链接、压力测试和候选交付；正式晋升仍需显式批准。",
            "",
        ]
    )
    return "\n".join(lines)


def batch_markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        f"# 姜胡说 {report['batch_id']} 自动审计验收",
        "",
        f"- 审计时间：{report['generated_at']}",
        f"- 结论：{'通过' if report['ok'] else '未通过'}",
        f"- 本批卡片：{metrics['card_count']}/{metrics['expected_count']}",
        f"- 统一契约：{metrics['contract_passed_count']}/{metrics['expected_count']}",
        f"- 原文回查：{metrics['quote_supported_count']}/{metrics['expected_count']}",
        f"- 实质内容卡：{metrics['substantive_card_count']}/{metrics['expected_count']}",
        f"- 五视角候选：{metrics['candidate_counts']}",
        f"- 有效候选产出：{metrics['effective_candidate_count']}/{metrics['expected_effective_candidate_count']}",
        f"- 与已验收批次最高相似度：{metrics['max_pair_similarity']:.3f}",
        "- 正式写入：false",
        "",
        "## 雷同与偷懒检查",
        "",
        f"- 高相似卡片对：{len(report['high_similarity_pairs'])}",
        f"- 跨卡重复核心句：{len(report['repeated_core_lines'])}",
        f"- 五视角重复摘要：{len(report['duplicate_candidate_summaries'])}",
        f"- 旧卡近乎整卡复制：{len(report['excessive_legacy_overlap'])}",
        f"- 原文无法回查：{len(report['unsupported_quotes'])}",
        "",
        "## 失败项",
        "",
    ]
    lines.extend(f"- {value}" for value in report["errors"]) if report["errors"] else lines.append("- 无。")
    lines.extend(["", "## 本批产物", ""])
    lines.extend(f"- `{value}`" for value in report["card_paths"])
    lines.extend(["", "## 边界", "", "- 本批仅验收候选学习产物，不触发正式知识写入。", ""])
    return "\n".join(lines)


def audit_batch(root: Path, nas_root: Path, batch_number: int) -> dict[str, Any]:
    """Audit one batch against every batch accepted before it."""

    root = root.resolve()
    workflow = root / WORKFLOW_ROOT
    batch_id = f"batch_{batch_number:02d}"
    batch_dir = workflow / "batches" / batch_id
    manifest = read_json(batch_dir / "batch_manifest.json")
    current_items = manifest.get("items") if isinstance(manifest, dict) else []
    if not isinstance(current_items, list):
        current_items = []
    current_by_id = {str(item.get("source_id") or ""): item for item in current_items if isinstance(item, dict)}
    current_ids = {value for value in current_by_id if value}

    card_paths: list[Path] = []
    accepted_items: dict[str, dict[str, Any]] = {}
    prior_gate_failures: list[str] = []
    for number in range(1, batch_number + 1):
        directory = workflow / "batches" / f"batch_{number:02d}"
        payload = read_json(directory / "batch_manifest.json")
        items = payload.get("items") if isinstance(payload, dict) else []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("source_id"):
                    accepted_items[str(item["source_id"])] = item
        card_paths.extend(sorted((directory / "cards").glob("*.md")))
        if number < batch_number:
            gate_path = directory / "gate_audit.json"
            if not gate_path.is_file() or not read_json(gate_path).get("ok"):
                prior_gate_failures.append(f"batch_{number:02d}")

    cards: dict[str, dict[str, Any]] = {}
    duplicate_source_ids: list[str] = []
    contract_errors: dict[str, list[str]] = {}
    unsupported_quotes: list[dict[str, str]] = []
    line_owners: dict[str, set[str]] = defaultdict(set)
    current_card_paths: list[str] = []
    for path in card_paths:
        text = path.read_text(encoding="utf-8")
        source_id = source_id_from_card(text)
        if source_id in cards:
            duplicate_source_ids.append(source_id)
            continue
        validation = validate_card_text(text)
        if source_id in current_ids and not validation.valid:
            contract_errors[source_id or path.name] = list(validation.errors)
        lines = distinctive_lines(text)
        for line in set(lines):
            line_owners[line].add(source_id)
        sections = parse_numbered_sections(text)[0]
        quote = labeled_value(sections.get("金句与表达素材", ""), "原文金句")
        transcript = transcript_text(transcript_path(source_id, nas_root))
        if source_id in current_ids and (not quote or normalize(quote) not in transcript):
            unsupported_quotes.append({"source_id": source_id, "quote": quote})
        relative = path.relative_to(root).as_posix()
        if source_id in current_ids:
            current_card_paths.append(relative)
        cards[source_id] = {
            "path": relative,
            "text": text,
            "sections": sections,
            "lines": lines,
            "signature": "".join(lines),
            "signature_bigrams": bigrams("".join(lines)),
        }

    similarity_pairs: list[dict[str, Any]] = []
    source_ids = sorted(cards)
    for index, left_id in enumerate(source_ids):
        for right_id in source_ids[index + 1 :]:
            if left_id not in current_ids and right_id not in current_ids:
                continue
            score = jaccard_sets(cards[left_id]["signature_bigrams"], cards[right_id]["signature_bigrams"])
            similarity_pairs.append({"left": left_id, "right": right_id, "similarity": round(score, 6)})
    similarity_pairs.sort(key=lambda item: (-item["similarity"], item["left"], item["right"]))
    high_similarity_pairs = [item for item in similarity_pairs if item["similarity"] >= 0.72]

    repeated_core_lines = [
        {"line": line, "source_ids": sorted(owners), "count": len(owners)}
        for line, owners in line_owners.items()
        if len(owners) >= 3 and bool(owners & current_ids)
    ]
    repeated_core_lines.sort(key=lambda item: (-item["count"], item["line"]))

    excessive_legacy_overlap: list[dict[str, Any]] = []
    legacy_overlap_values: list[float] = []
    for source_id in sorted(current_ids):
        item = current_by_id[source_id]
        legacy_path = str(item.get("legacy_candidate_path") or "")
        if not legacy_path or source_id not in cards:
            continue
        legacy_signature = "".join(distinctive_lines((root / legacy_path).read_text(encoding="utf-8")))
        score = SequenceMatcher(None, cards[source_id]["signature"], legacy_signature, autojunk=False).ratio() if legacy_signature else 0.0
        legacy_overlap_values.append(score)
        if score >= 0.92:
            excessive_legacy_overlap.append({"source_id": source_id, "similarity": round(score, 6)})

    substance_errors: dict[str, list[str]] = {}
    for source_id in sorted(current_ids & set(cards)):
        card = cards[source_id]
        card_errors: list[str] = []
        for section_name in CORE_SECTIONS:
            section_text = str(card["sections"].get(section_name, ""))
            section_value = normalize("".join(meaningful_lines(section_text)))
            if len(section_value) < 20:
                card_errors.append(f"thin_core_section:{section_name}:{len(section_value)}")
        if len(str(card["signature"])) < 240:
            card_errors.append(f"thin_distinctive_signature:{len(str(card['signature']))}")
        for marker in ("### R -", "### I -", "### A1 -", "### A2 -", "### E -", "### B -"):
            if marker not in str(card["text"]):
                card_errors.append(f"missing_method_layer:{marker[4:6].strip()}")
        if card_errors:
            substance_errors[source_id] = card_errors

    candidate_counts: dict[str, int] = {}
    duplicate_candidate_summaries: list[dict[str, Any]] = []
    candidate_effectiveness_errors: list[dict[str, Any]] = []
    effective_candidate_count = 0
    for lens in LENSES:
        values: list[dict[str, Any]] = []
        current_values = read_jsonl(batch_dir / "candidates" / f"{lens}.jsonl")
        candidate_counts[lens] = len(current_values)
        current_ref_counts: Counter[str] = Counter()
        for value in current_values:
            refs = [str(ref) for ref in (value.get("source_refs") or []) if str(ref)]
            source_ref = refs[0] if len(refs) == 1 else ""
            if source_ref:
                current_ref_counts[source_ref] += 1
            reasons: list[str] = []
            if source_ref not in current_ids:
                reasons.append("source_ref_not_in_batch")
            if len(refs) != 1:
                reasons.append("source_refs_must_contain_exactly_one_item")
            if len(normalize(str(value.get("title") or ""))) < 6:
                reasons.append("title_too_thin")
            if len(normalize(str(value.get("summary") or ""))) < 24:
                reasons.append("summary_too_thin")
            if value.get("callable") is not False:
                reasons.append("candidate_must_not_be_callable")
            if str(value.get("type") or "") != lens:
                reasons.append("lens_type_mismatch")
            if reasons:
                candidate_effectiveness_errors.append(
                    {"lens": lens, "source_id": source_ref, "id": str(value.get("id") or ""), "reasons": reasons}
                )
            else:
                effective_candidate_count += 1
        for source_id in sorted(current_ids):
            if current_ref_counts[source_id] != 1:
                candidate_effectiveness_errors.append(
                    {
                        "lens": lens,
                        "source_id": source_id,
                        "id": "",
                        "reasons": [f"source_candidate_count:{current_ref_counts[source_id]}/1"],
                    }
                )
        for number in range(1, batch_number + 1):
            values.extend(read_jsonl(workflow / "batches" / f"batch_{number:02d}" / "candidates" / f"{lens}.jsonl"))
        owners: dict[str, list[str]] = defaultdict(list)
        for value in values:
            owners[normalize(str(value.get("summary") or ""))].append(str((value.get("source_refs") or [""])[0]))
        for summary, refs in owners.items():
            distinct_refs = sorted(set(refs))
            if summary and len(distinct_refs) > 1 and bool(set(distinct_refs) & current_ids):
                duplicate_candidate_summaries.append({"lens": lens, "source_ids": distinct_refs, "summary": summary})

    current_cards = current_ids & set(cards)
    unexpected_current = sorted(
        source_id_from_card(path.read_text(encoding="utf-8"))
        for path in (batch_dir / "cards").glob("*.md")
        if source_id_from_card(path.read_text(encoding="utf-8")) not in current_ids
    )
    built_in_audit = read_json(batch_dir / "audit.json")
    errors: list[str] = []
    if current_ids - current_cards:
        errors.append(f"missing_source_ids:{len(current_ids - current_cards)}")
    if unexpected_current:
        errors.append(f"unexpected_source_ids:{len(unexpected_current)}")
    if duplicate_source_ids:
        errors.append(f"duplicate_source_ids:{len(set(duplicate_source_ids))}")
    if contract_errors:
        errors.append(f"contract_failures:{len(contract_errors)}")
    if unsupported_quotes:
        errors.append(f"unsupported_quotes:{len(unsupported_quotes)}")
    if high_similarity_pairs:
        errors.append(f"high_similarity_pairs:{len(high_similarity_pairs)}")
    if repeated_core_lines:
        errors.append(f"repeated_core_lines:{len(repeated_core_lines)}")
    if duplicate_candidate_summaries:
        errors.append(f"duplicate_candidate_summaries:{len(duplicate_candidate_summaries)}")
    if excessive_legacy_overlap:
        errors.append(f"excessive_legacy_overlap:{len(excessive_legacy_overlap)}")
    if substance_errors:
        errors.append(f"substance_failures:{len(substance_errors)}")
    if candidate_effectiveness_errors:
        errors.append(f"candidate_effectiveness_failures:{len(candidate_effectiveness_errors)}")
    if not built_in_audit.get("ok"):
        errors.append("built_in_batch_audit_failed")
    if prior_gate_failures:
        errors.append(f"prior_gate_failures:{len(prior_gate_failures)}")
    for lens, count in candidate_counts.items():
        if count != len(current_ids):
            errors.append(f"candidate_coverage:{lens}:{count}/{len(current_ids)}")

    report: dict[str, Any] = {
        "ok": not errors,
        "workflow_id": WORKFLOW_ID,
        "batch_id": batch_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "formal_write_allowed": False,
        "metrics": {
            "expected_count": len(current_ids),
            "card_count": len(current_cards),
            "contract_passed_count": len(current_cards) - len(contract_errors),
            "quote_supported_count": len(current_cards) - len(unsupported_quotes),
            "candidate_counts": candidate_counts,
            "substantive_card_count": len(current_cards) - len(substance_errors),
            "effective_candidate_count": effective_candidate_count,
            "expected_effective_candidate_count": len(current_ids) * len(LENSES),
            "max_pair_similarity": similarity_pairs[0]["similarity"] if similarity_pairs else 0.0,
            "max_legacy_overlap": round(max(legacy_overlap_values), 6) if legacy_overlap_values else 0.0,
        },
        "errors": errors,
        "card_paths": sorted(current_card_paths),
        "duplicate_source_ids": sorted(set(duplicate_source_ids)),
        "contract_errors": contract_errors,
        "unsupported_quotes": unsupported_quotes,
        "high_similarity_pairs": high_similarity_pairs,
        "top_similarity_pairs": similarity_pairs[:20],
        "repeated_core_lines": repeated_core_lines,
        "duplicate_candidate_summaries": duplicate_candidate_summaries,
        "excessive_legacy_overlap": excessive_legacy_overlap,
        "substance_errors": substance_errors,
        "candidate_effectiveness_errors": candidate_effectiveness_errors,
        "prior_gate_failures": prior_gate_failures,
    }
    write_json(batch_dir / "gate_audit.json", report)
    (batch_dir / "gate_audit.md").write_text(batch_markdown_report(report), encoding="utf-8")
    return report


def audit(root: Path, nas_root: Path, scope: str = "priority") -> dict[str, Any]:
    root = root.resolve()
    workflow = root / WORKFLOW_ROOT
    if scope == "full":
        expected = full_relearning_sequence(root)
    elif scope == "evidence_ready":
        expected = evidence_ready_sequence(root, nas_root)
    else:
        expected = relearning_sequence(root)
    expected_by_id = {item["source_id"]: item for item in expected}
    card_paths = sorted((workflow / "batches").glob("batch_*/cards/*.md"))
    cards: dict[str, dict[str, Any]] = {}
    duplicate_source_ids: list[str] = []
    contract_errors: dict[str, list[str]] = {}
    unsupported_quotes: list[dict[str, str]] = []
    line_owners: dict[str, set[str]] = defaultdict(set)

    for path in card_paths:
        text = path.read_text(encoding="utf-8")
        source_id = source_id_from_card(text)
        if source_id in cards:
            duplicate_source_ids.append(source_id)
            continue
        validation = validate_card_text(text)
        if not validation.valid:
            contract_errors[source_id or path.name] = list(validation.errors)
        lines = distinctive_lines(text)
        for line in set(lines):
            line_owners[line].add(source_id)
        sections = parse_numbered_sections(text)[0]
        quote = labeled_value(sections.get("金句与表达素材", ""), "原文金句")
        transcript = transcript_text(transcript_path(source_id, nas_root))
        if not quote or normalize(quote) not in transcript:
            unsupported_quotes.append({"source_id": source_id, "quote": quote})
        cards[source_id] = {
            "path": path.relative_to(root).as_posix(),
            "text": text,
            "lines": lines,
            "signature": "".join(lines),
            "signature_bigrams": bigrams("".join(lines)),
        }

    repeated_core_lines = [
        {"line": line, "source_ids": sorted(owners), "count": len(owners)}
        for line, owners in line_owners.items()
        if len(owners) >= 3
    ]
    repeated_core_lines.sort(key=lambda item: (-item["count"], item["line"]))

    similarity_pairs: list[dict[str, Any]] = []
    source_ids = sorted(cards)
    for index, left_id in enumerate(source_ids):
        for right_id in source_ids[index + 1 :]:
            score = jaccard_sets(cards[left_id]["signature_bigrams"], cards[right_id]["signature_bigrams"])
            similarity_pairs.append({"left": left_id, "right": right_id, "similarity": round(score, 6)})
    similarity_pairs.sort(key=lambda item: (-item["similarity"], item["left"], item["right"]))
    high_similarity_pairs = [item for item in similarity_pairs if item["similarity"] >= 0.72]

    excessive_legacy_overlap: list[dict[str, Any]] = []
    legacy_overlap_values: list[float] = []
    for source_id, card in cards.items():
        item = expected_by_id.get(source_id)
        if not item:
            continue
        legacy_path = str(item.get("legacy_candidate_path") or "")
        if not legacy_path:
            continue
        legacy_text = (root / legacy_path).read_text(encoding="utf-8")
        legacy_signature = "".join(distinctive_lines(legacy_text))
        score = SequenceMatcher(None, card["signature"], legacy_signature, autojunk=False).ratio() if legacy_signature else 0.0
        legacy_overlap_values.append(score)
        if score >= 0.92:
            excessive_legacy_overlap.append({"source_id": source_id, "similarity": round(score, 6)})

    candidate_counts: dict[str, int] = {}
    duplicate_candidate_summaries: list[dict[str, Any]] = []
    for lens in LENSES:
        values = read_jsonl(workflow / "candidates" / f"{lens}.jsonl")
        candidate_counts[lens] = len(values)
        owners: dict[str, list[str]] = defaultdict(list)
        for value in values:
            owners[normalize(str(value.get("summary") or ""))].append(str((value.get("source_refs") or [""])[0]))
        for summary, refs in owners.items():
            if summary and len(set(refs)) > 1:
                duplicate_candidate_summaries.append({"lens": lens, "source_ids": sorted(set(refs)), "summary": summary})

    missing_source_ids = sorted(set(expected_by_id) - set(cards))
    unexpected_source_ids = sorted(set(cards) - set(expected_by_id))
    failed_batch_audits: list[str] = []
    final_batch = (len(expected) + 9) // 10
    for batch_number in range(1, final_batch + 1):
        path = workflow / "batches" / f"batch_{batch_number:02d}" / "audit.json"
        if not path.exists() or not read_json(path).get("ok"):
            failed_batch_audits.append(f"batch_{batch_number:02d}")

    errors: list[str] = []
    if missing_source_ids:
        errors.append(f"missing_source_ids:{len(missing_source_ids)}")
    if unexpected_source_ids:
        errors.append(f"unexpected_source_ids:{len(unexpected_source_ids)}")
    if duplicate_source_ids:
        errors.append(f"duplicate_source_ids:{len(duplicate_source_ids)}")
    if contract_errors:
        errors.append(f"contract_failures:{len(contract_errors)}")
    if unsupported_quotes:
        errors.append(f"unsupported_quotes:{len(unsupported_quotes)}")
    if high_similarity_pairs:
        errors.append(f"high_similarity_pairs:{len(high_similarity_pairs)}")
    if repeated_core_lines:
        errors.append(f"repeated_core_lines:{len(repeated_core_lines)}")
    if duplicate_candidate_summaries:
        errors.append(f"duplicate_candidate_summaries:{len(duplicate_candidate_summaries)}")
    if excessive_legacy_overlap:
        errors.append(f"excessive_legacy_overlap:{len(excessive_legacy_overlap)}")
    if failed_batch_audits:
        errors.append(f"failed_batch_audits:{len(failed_batch_audits)}")
    for lens, count in candidate_counts.items():
        if count != len(expected):
            errors.append(f"candidate_coverage:{lens}:{count}/{len(expected)}")

    report: dict[str, Any] = {
        "ok": not errors,
        "workflow_id": WORKFLOW_ID,
        "scope": scope,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "formal_write_allowed": False,
        "metrics": {
            "expected_count": len(expected),
            "card_count": len(cards),
            "contract_passed_count": len(cards) - len(contract_errors),
            "quote_supported_count": len(cards) - len(unsupported_quotes),
            "candidate_counts": candidate_counts,
            "max_pair_similarity": similarity_pairs[0]["similarity"] if similarity_pairs else 0.0,
            "max_legacy_overlap": round(max(legacy_overlap_values), 6) if legacy_overlap_values else 0.0,
            "average_legacy_overlap": round(sum(legacy_overlap_values) / len(legacy_overlap_values), 6) if legacy_overlap_values else 0.0,
        },
        "errors": errors,
        "missing_source_ids": missing_source_ids,
        "unexpected_source_ids": unexpected_source_ids,
        "duplicate_source_ids": sorted(set(duplicate_source_ids)),
        "contract_errors": contract_errors,
        "unsupported_quotes": unsupported_quotes,
        "high_similarity_pairs": high_similarity_pairs,
        "top_similarity_pairs": similarity_pairs[:100],
        "repeated_core_lines": repeated_core_lines,
        "duplicate_candidate_summaries": duplicate_candidate_summaries,
        "excessive_legacy_overlap": excessive_legacy_overlap,
        "failed_batch_audits": failed_batch_audits,
    }
    output = workflow / "audit"
    write_json(output / "full_relearning_audit.json", report)
    (output / "full_relearning_audit.md").write_text(markdown_report(report), encoding="utf-8")
    if report["ok"] and scope == "evidence_ready":
        status_path = workflow / "LEARNING_STATUS.json"
        status = read_json(status_path)
        status.update(
            {
                "workflow_id": WORKFLOW_ID,
                "status": "stage1_evidence_ready_completed",
                "completed_cards": len(expected),
                "latest_batch": f"batch_{(len(expected) + 9) // 10:02d}",
                "latest_batch_ok": True,
                "full_audit_ok": True,
                "formal_write_allowed": False,
                "updated_at": report["generated_at"],
            }
        )
        write_json(status_path, status)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Jianghushuo v2.2 relearning for duplication, shortcuts and evidence support.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default=str(CURRENT_ACCOUNT_DIR))
    parser.add_argument("--scope", choices=["priority", "evidence_ready", "full"], default="priority")
    parser.add_argument("--batch", type=int, default=0, help="Audit one completed batch against all earlier accepted batches.")
    args = parser.parse_args()
    if args.batch:
        report = audit_batch(Path(args.root), Path(args.nas_root), max(args.batch, 1))
    else:
        report = audit(Path(args.root), Path(args.nas_root), scope=args.scope)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
