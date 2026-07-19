from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ACCOUNT_CONFIGS = {
    "姜胡说": {
        "workflow": "jianghushuo-v2-full",
        "nas": "dy/accounts/dy_77700555383",
        "prefix": "dy_",
    },
    "李宗恒": {
        "workflow": "lizongheng-v2-full",
        "nas": "dy/accounts/dy_63700340656",
        "prefix": "dy_",
        "required_direction": "自然短剧情",
    },
    "小森林的小世界": {
        "workflow": "xiaosenlin-xiaoshijie-v2-full",
        "nas": "xhs/accounts/xhs_5a201295e8ac2b0dbae9063a",
        "prefix": "xhs_",
        "mechanism_map": {
            "xsl-cluster-list_decision": "list_decision",
            "xsl-cluster-problem_result": "problem_result",
            "xsl-cluster-step_sequence": "step_sequence",
            "xsl-cluster-time_feedback": "time_feedback",
        },
    },
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def source_id_from_card(text: str, path: Path) -> str | None:
    match = re.search(r"(?m)^source_id[：:]\s*`?([^`\s]+)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:douyin_|xhs_)?([0-9a-f]{16,24})", path.stem, re.I)
    return match.group(1) if match else None


def extract_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def extract_relevant_card_text(text: str) -> str:
    wanted = {"4", "5", "7", "8", "9", "10", "11", "12"}
    chunks: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(\d+)[.、]?", line)
        if heading:
            current = heading.group(1)
        if current in wanted:
            chunks.append(line)
    return "\n".join(chunks) if chunks else text


def load_cards(account_root: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in account_root.glob("directions/*/cards/*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        source_id = source_id_from_card(text, path)
        if not source_id:
            continue
        direction = path.parents[1].name
        cards[source_id] = {
            "source_id": source_id,
            "path": str(path),
            "direction": direction,
            "title": extract_title(text, path),
            "text": extract_relevant_card_text(text),
        }
    return cards


def ngrams(text: str, size: int = 2) -> Counter[str]:
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text.lower())
    return Counter(compact[index : index + size] for index in range(max(0, len(compact) - size + 1)))


def cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = left.keys() & right.keys()
    numerator = sum(left[key] * right[key] for key in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def transcript_path(nas_root: Path, config: dict[str, Any], source_id: str) -> Path:
    return nas_root / config["nas"] / f"{config['prefix']}{source_id}" / "video" / "transcript.txt"


def source_path(nas_root: Path, config: dict[str, Any], source_id: str) -> Path:
    return nas_root / config["nas"] / f"{config['prefix']}{source_id}" / "source.json"


def compact_excerpt(text: str, start: int, width: int = 220) -> str:
    excerpt = re.sub(r"\s+", " ", text[start : start + width]).strip()
    return excerpt


def transcript_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path)}
    text = path.read_text(encoding="utf-8", errors="replace")
    compact = re.sub(r"\s+", " ", text).strip()
    middle = max(0, len(text) // 2 - 100)
    signals = {
        "audience_terms": len(re.findall(r"大家|各位|你们|姐妹|宝宝|观众|朋友", text)),
        "first_person_terms": len(re.findall(r"我|我们|咱", text)),
        "causal_terms": len(re.findall(r"因为|所以|但是|后来|于是|结果|发现|为什么", text)),
        "time_or_sequence_terms": len(re.findall(r"第一|第二|第三|首先|然后|接着|最后|分钟|小时|天|周|月", text)),
        "boundary_terms": len(re.findall(r"如果|除非|不适合|不要|停止|别|不能|不一定|情况下", text)),
        "feedback_terms": len(re.findall(r"反馈|效果|变化|结果|发现|看起来|感觉|完成|失败", text)),
        "question_marks": text.count("?") + text.count("？"),
        "line_count": len([line for line in text.splitlines() if line.strip()]),
    }
    return {
        "available": True,
        "path": str(path),
        "chars": len(compact),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "opening_excerpt": compact_excerpt(text, 0),
        "middle_excerpt": compact_excerpt(text, middle),
        "closing_excerpt": compact_excerpt(text, max(0, len(text) - 240)),
        "signals": signals,
    }


def published_at(source_file: Path) -> int:
    if not source_file.exists():
        return 0
    try:
        return int(read_json(source_file).get("publish_time") or 0)
    except (ValueError, TypeError, json.JSONDecodeError):
        return 0


def load_structured_xiaosenlin(workflow_root: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    base = workflow_root / "v3_deep_relearning"
    for path in base.glob("batch_*/structured_cards.jsonl"):
        for row in read_jsonl(path):
            source_id = str(row.get("source_id", ""))
            if source_id:
                records[source_id] = row
    return records


def cluster_map(workflow_root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in read_jsonl(workflow_root / "candidate_clusters.jsonl")
        if row.get("cluster_type") == "method_candidate"
    }


def method_summary(method: dict[str, Any], cluster: dict[str, Any]) -> str:
    trigger = method.get("trigger_model") or {}
    parts: list[str] = [
        str(method.get("title", "")),
        str(cluster.get("core_mechanism", "")),
        str(trigger.get("mechanism", "")),
    ]
    for key in ("trigger_signals", "execution_steps", "do_not_use"):
        value = method.get(key, [])
        if isinstance(value, list):
            parts.extend(map(str, value))
    return "\n".join(parts)


def unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def candidate_score(
    source_id: str,
    cards: dict[str, dict[str, Any]],
    seed_vectors: list[Counter[str]],
    method_vector: Counter[str],
) -> float:
    card = cards.get(source_id)
    if not card:
        return 0.0
    vector = ngrams(card["text"])
    seed_score = max((cosine(vector, seed) for seed in seed_vectors), default=0.0)
    method_score = cosine(vector, method_vector)
    return round(seed_score * 0.72 + method_score * 0.28, 6)


def choose_diverse(
    candidates: list[dict[str, Any]],
    preferred_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    by_id = {row["source_id"]: row for row in candidates}
    selected: list[dict[str, Any]] = []
    directions: Counter[str] = Counter()
    length_bands: Counter[str] = Counter()

    def band(chars: int) -> str:
        if chars < 700:
            return "short"
        if chars < 2200:
            return "medium"
        return "long"

    def add(row: dict[str, Any]) -> None:
        selected.append(row)
        directions[row.get("direction", "unknown")] += 1
        length_bands[band(int(row.get("transcript", {}).get("chars", 0)))] += 1

    for source_id in preferred_ids:
        row = by_id.get(source_id)
        if row and row not in selected and len(selected) < limit:
            add(row)

    remaining = [row for row in candidates if row not in selected]
    while remaining and len(selected) < limit:
        best = max(
            remaining,
            key=lambda row: (
                float(row.get("similarity", 0.0))
                + (0.12 if directions[row.get("direction", "unknown")] == 0 else 0.0)
                + (0.06 if length_bands[band(int(row.get("transcript", {}).get("chars", 0)))] == 0 else 0.0),
                int(row.get("publish_time", 0)),
            ),
        )
        add(best)
        remaining.remove(best)
    return selected


def median(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2)


def aggregate_selected(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [int(row.get("transcript", {}).get("chars", 0)) for row in rows]
    signal_names = sorted(
        {
            name
            for row in rows
            for name in row.get("transcript", {}).get("signals", {})
        }
    )
    signal_medians = {
        name: median(
            [int(row.get("transcript", {}).get("signals", {}).get(name, 0)) for row in rows]
        )
        for name in signal_names
    }
    direction_counts = Counter(row.get("direction", "unknown") for row in rows)
    status_counts = Counter(row.get("status", "unknown") for row in rows)
    return {
        "unique_source_count": len({row["source_id"] for row in rows}),
        "direction_count": len(direction_counts),
        "direction_distribution": dict(direction_counts),
        "selection_status_distribution": dict(status_counts),
        "transcript_chars": {
            "min": min(lengths, default=0),
            "median": median(lengths),
            "max": max(lengths, default=0),
        },
        "signal_medians": signal_medians,
    }


def audit_account(
    root: Path,
    nas_root: Path,
    account_name: str,
    config: dict[str, Any],
    manual_reviews: dict[str, Any],
    minimum: int,
    limit: int,
) -> dict[str, Any]:
    account_root = root / "10_Knowledge/formal/accounts" / account_name
    workflow_root = root / "10_Knowledge/candidates/account_learning_workflows" / config["workflow"]
    cards = load_cards(account_root)
    clusters = cluster_map(workflow_root)
    structured = load_structured_xiaosenlin(workflow_root) if config.get("mechanism_map") else {}
    all_cluster_refs: dict[str, set[str]] = {
        method_id: set(map(str, cluster.get("source_refs", [])))
        for method_id, cluster in clusters.items()
    }
    transcript_cache: dict[str, dict[str, Any]] = {}

    def transcript(source_id: str) -> dict[str, Any]:
        if source_id not in transcript_cache:
            transcript_cache[source_id] = transcript_record(transcript_path(nas_root, config, source_id))
        return transcript_cache[source_id]

    results: list[dict[str, Any]] = []
    for method_file in sorted((account_root / "methods").glob("*/method.json")):
        method = read_json(method_file)
        method_id = str(method.get("id") or method_file.parent.name)
        cluster = clusters.get(method_id, {})
        strong_refs = unique(cluster.get("source_refs", []) or method.get("source_refs", []))
        if config.get("mechanism_map"):
            key = config["mechanism_map"].get(method_id)
            if key:
                strong_refs = unique(
                    source_id
                    for source_id, row in structured.items()
                    if row.get("mechanism_key") == key and row.get("evidence_status") == "complete"
                )

        excluded_direction_refs: list[str] = []
        required_direction = config.get("required_direction")
        if required_direction:
            excluded_direction_refs = [
                source_id
                for source_id in strong_refs
                if cards.get(source_id, {}).get("direction") != required_direction
            ]
            strong_refs = [
                source_id
                for source_id in strong_refs
                if cards.get(source_id, {}).get("direction") == required_direction
            ]

        unavailable_strong_refs = [
            source_id
            for source_id in strong_refs
            if source_id not in cards or not transcript(source_id).get("available")
        ]
        strong_refs = [
            source_id
            for source_id in strong_refs
            if source_id in cards and transcript(source_id).get("available")
        ]

        formal_refs = unique(method.get("source_refs", []))
        seed_ids = [source_id for source_id in formal_refs if source_id in cards]
        seed_vectors = [ngrams(cards[source_id]["text"]) for source_id in seed_ids]
        method_vector = ngrams(method_summary(method, cluster))

        candidate_ids = list(strong_refs)
        expansion_rows: list[dict[str, Any]] = []
        if len(candidate_ids) < minimum:
            sibling_refs = set().union(
                *(refs for sibling_id, refs in all_cluster_refs.items() if sibling_id != method_id)
            )
            expansion_ids = [
                source_id
                for source_id, card in cards.items()
                if source_id not in set(candidate_ids)
                and source_id not in sibling_refs
                and (not config.get("required_direction") or card["direction"] == config["required_direction"])
                and transcript(source_id).get("available")
            ]
            ranked = sorted(
                expansion_ids,
                key=lambda source_id: candidate_score(source_id, cards, seed_vectors, method_vector),
                reverse=True,
            )[: max(30, minimum * 3)]
            for source_id in ranked:
                card = cards[source_id]
                expansion_rows.append(
                    {
                        "source_id": source_id,
                        "status": "provisional_expansion",
                        "direction": card["direction"],
                        "title": card["title"],
                        "card_path": card["path"],
                        "similarity": candidate_score(source_id, cards, seed_vectors, method_vector),
                        "publish_time": published_at(source_path(nas_root, config, source_id)),
                        "transcript": transcript(source_id),
                    }
                )
            candidate_ids.extend(row["source_id"] for row in expansion_rows)

        rows: list[dict[str, Any]] = []
        expansion_by_id = {row["source_id"]: row for row in expansion_rows}
        for source_id in unique(candidate_ids):
            card = cards.get(source_id)
            if not card:
                continue
            transcript_data = transcript(source_id)
            if not transcript_data.get("available"):
                continue
            row = expansion_by_id.get(source_id) or {
                "source_id": source_id,
                "status": "formal_seed" if source_id in formal_refs else "cluster_support",
                "direction": card["direction"],
                "title": card["title"],
                "card_path": card["path"],
                "similarity": candidate_score(source_id, cards, seed_vectors, method_vector),
                "publish_time": published_at(source_path(nas_root, config, source_id)),
                "transcript": transcript_data,
            }
            if source_id in structured:
                row["structured_metadata"] = {
                    key: structured[source_id].get(key)
                    for key in ("topic_family", "mechanism_key", "commercial_axis", "evidence_basis", "traceable_anchors")
                }
            rows.append(row)

        target = min(limit, max(minimum, len(strong_refs)))
        review = manual_reviews.get(account_name, {}).get(method_id)
        if review:
            accepted_ids = unique(review.get("accepted_source_ids", []))
            accepted_rows = [row for row in rows if row["source_id"] in accepted_ids]
            for row in accepted_rows:
                row["status"] = "manual_validated_expansion"
            strong_rows = [row for row in rows if row["source_id"] in strong_refs]
            selected = choose_diverse(
                strong_rows,
                [source_id for source_id in formal_refs if source_id in strong_refs],
                min(limit, len(strong_rows)),
            )
            selected.extend(row for row in accepted_rows if row not in selected)
            selected = selected[:limit]
        else:
            selected = choose_diverse(rows, [source_id for source_id in formal_refs if source_id in strong_refs], target)
        provisional_count = sum(1 for row in selected if row["status"] == "provisional_expansion")
        manual_validated_count = sum(1 for row in selected if row["status"] == "manual_validated_expansion")
        results.append(
            {
                "method_id": method_id,
                "title": method.get("title", method_id),
                "core_mechanism": cluster.get("core_mechanism") or (method.get("trigger_model") or {}).get("mechanism"),
                "formal_source_count": len(formal_refs),
                "cluster_or_classified_source_count": len(strong_refs),
                "unavailable_strong_source_count": len(unavailable_strong_refs),
                "unavailable_strong_source_refs": unavailable_strong_refs,
                "excluded_direction_source_count": len(excluded_direction_refs),
                "excluded_direction_source_refs": excluded_direction_refs,
                "direct_transcript_available_count": sum(1 for row in rows if row["transcript"].get("available")),
                "selected_count": len(selected),
                "selected": selected,
                "aggregate": aggregate_selected(selected),
                "provisional_expansion_candidates": expansion_rows,
                "manual_review": review,
                "evidence_status": (
                    "provisional_review_required"
                    if provisional_count
                    else "sufficient_transcript_validated"
                    if manual_validated_count and len(selected) >= minimum
                    else "sufficient_for_review"
                    if len(selected) >= minimum
                    else "insufficient_after_expansion"
                ),
            }
        )

    return {
        "account": account_name,
        "formal_card_count": len(cards),
        "method_count": len(results),
        "methods": results,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 账号 Skill 逐字稿证据复核候选",
        "",
        f"目标：每个正式方法分层抽取 {payload['minimum_per_method']}–{payload['target_per_method']} 条可回查逐字稿；弱相关扩展不自动晋升。",
        "",
    ]
    for account in payload["accounts"]:
        lines.extend([f"## {account['account']}", ""])
        for method in account["methods"]:
            lines.extend(
                [
                    f"### {method['title']} (`{method['method_id']}`)",
                    "",
                    f"- 正式方法原有证据：{method['formal_source_count']} 条。",
                    f"- 聚类或全量分类候选：{method['cluster_or_classified_source_count']} 条。",
                    f"- 聚类证据中逐字稿不可用：{method['unavailable_strong_source_count']} 条。",
                    f"- 因轨道隔离未计入核心证据：{method['excluded_direction_source_count']} 条。",
                    f"- 本轮逐字稿抽样：{method['selected_count']} 条；状态：`{method['evidence_status']}`。",
                    f"- 核心机制：{method.get('core_mechanism') or '未记录'}",
                    f"- 方向覆盖：{method['aggregate']['direction_count']} 类；逐字稿字数范围：{method['aggregate']['transcript_chars']['min']}–{method['aggregate']['transcript_chars']['max']}，中位数 {method['aggregate']['transcript_chars']['median']}。",
                    "",
                    "| source_id | 身份 | 方向 | 逐字稿字数 | 相似度 | 标题 |",
                    "| --- | --- | --- | ---: | ---: | --- |",
                ]
            )
            for row in method["selected"]:
                title = str(row.get("title", "")).replace("|", "／").replace("\n", " ")[:72]
                lines.append(
                    f"| `{row['source_id']}` | {row['status']} | {row.get('direction', '')} | "
                    f"{row['transcript'].get('chars', 0)} | {row.get('similarity', 0):.3f} | {title} |"
                )
            provisional = [row for row in method["selected"] if row["status"] == "provisional_expansion"]
            if provisional:
                lines.extend(
                    [
                        "",
                        "> 本表含待人工确认的扩展候选；只有逐字稿结构与核心机制一致、且不是兄弟方法或题材词重合时才能计入强证据。",
                    ]
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_formal_evidence(root: Path, payload: dict[str, Any]) -> list[str]:
    written: list[str] = []
    for account in payload["accounts"]:
        target = (
            root
            / "10_Knowledge/formal/accounts"
            / account["account"]
            / "evidence/ACCOUNT_SKILL_TRANSCRIPT_VALIDATION.json"
        )
        formal_payload = {
            "schema_version": "account_skill_transcript_validation_v1",
            "validated_at": "2026-07-16",
            "account": account["account"],
            "minimum_per_method": payload["minimum_per_method"],
            "maximum_per_method": payload["target_per_method"],
            "selection_rule": payload["selection_rule"],
            "candidate_audit_path": "10_Knowledge/candidates/account_skill_upgrades/2026-07-16/evidence_revalidation/evidence_matrix.json",
            "method_count": account["method_count"],
            "validated_source_total": sum(method["selected_count"] for method in account["methods"]),
            "methods": [
                {
                    "method_id": method["method_id"],
                    "title": method["title"],
                    "evidence_status": method["evidence_status"],
                    "selected_count": method["selected_count"],
                    "source_refs": [row["source_id"] for row in method["selected"]],
                    "transcript_sha256": {
                        row["source_id"]: row["transcript"].get("sha256") for row in method["selected"]
                    },
                    "aggregate": method["aggregate"],
                    "manual_review": method.get("manual_review"),
                    "excluded_direction_source_refs": method.get("excluded_direction_source_refs", []),
                }
                for method in account["methods"]
            ],
            "formal_skill_update_allowed": True,
        }
        target.write_text(json.dumps(formal_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(str(target))
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a transcript-backed evidence audit for formal account Skills.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default="/Volumes/AFK/zhishikushuju")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manual-review")
    parser.add_argument("--write-formal-evidence", action="store_true")
    parser.add_argument("--minimum", type=int, default=10)
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    nas_root = Path(args.nas_root)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manual_reviews: dict[str, Any] = {}
    if args.manual_review:
        review_path = Path(args.manual_review)
        if not review_path.is_absolute():
            review_path = root / review_path
        manual_reviews = read_json(review_path).get("accounts", {})

    payload = {
        "schema_version": "account_skill_transcript_evidence_audit_v1",
        "minimum_per_method": args.minimum,
        "target_per_method": args.limit,
        "selection_rule": "formal seeds first, then cluster/classified support with direction and length diversity; low-evidence expansion remains provisional",
        "accounts": [
            audit_account(root, nas_root, account_name, config, manual_reviews, args.minimum, args.limit)
            for account_name, config in ACCOUNT_CONFIGS.items()
        ],
    }
    (output_dir / "evidence_matrix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "EVIDENCE_REVIEW.md").write_text(render_markdown(payload), encoding="utf-8")
    formal_evidence = write_formal_evidence(root, payload) if args.write_formal_evidence else []
    print(json.dumps({
        "ok": True,
        "output_dir": str(output_dir),
        "accounts": len(payload["accounts"]),
        "methods": sum(len(account["methods"]) for account in payload["accounts"]),
        "selected": sum(method["selected_count"] for account in payload["accounts"] for method in account["methods"]),
        "formal_evidence": formal_evidence,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
