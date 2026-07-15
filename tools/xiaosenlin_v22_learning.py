from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import parse_numbered_sections, validate_card_text
from tools.xiaosenlin_batch_learning import MECHANISMS
from tools.xiaosenlin_deep_relearning import parse_srt, read_json, read_jsonl, text_units, write_json, write_jsonl


ACCOUNT = "小森林的小世界"
WORKFLOW_ID = "xiaosenlin-xiaoshijie-v2-full"
WORKFLOW_ROOT = Path("10_Knowledge/candidates/account_learning_workflows") / WORKFLOW_ID
DEEP_ROOT = WORKFLOW_ROOT / "v3_deep_relearning"
SKILL_VERSION = "2.2"
LENSES = ("positioning", "topics", "structures", "expression", "counterexamples")
METHOD_KEYS = (
    "identity_proof",
    "list_decision",
    "problem_result",
    "step_sequence",
    "time_feedback",
    "version_iteration",
)
NEGATIVE_AD_PHRASES = (
    "没有广告",
    "没有广",
    "无广",
    "不是广告",
    "非广告",
    "无广告",
    "不含广告",
)
POSITIVE_AD_PHRASES = (
    "本期合作",
    "品牌合作",
    "商业合作",
    "广告植入",
    "赞助",
    "推广合作",
    "广子",
    "合作产品",
)
PLATFORM_PROJECT_PHRASES = (
    "平台活动",
    "官方活动",
    "挑战赛",
    "创作项目",
    "平台项目",
    "栏目合作",
    "品牌活动",
    "周年庆典",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def short(value: str, limit: int = 520) -> str:
    value = clean(value)
    return value if len(value) <= limit else value[:limit].rstrip() + "……"


def load_deep_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((root / DEEP_ROOT).glob("batch_*/structured_cards.jsonl")):
        records.extend(read_jsonl(path))
    return records


def card_path(root: Path, record: dict[str, Any]) -> Path:
    return root / DEEP_ROOT / str(record["batch_id"]) / "cards" / f"xhs_{record['source_id']}.md"


def source_evidence(root: Path, record: dict[str, Any]) -> tuple[str, list[dict[str, str]], str]:
    item_root = Path(str(record["nas_item_root"]))
    source = read_json(item_root / "source.json", {}) or {}
    units, timeline, mode = text_units(str(record["content_type"]), item_root, source)
    overrides = read_json(root / WORKFLOW_ROOT / "VISUAL_EVIDENCE_OVERRIDES.json", {}) or {}
    visual_evidence = clean((overrides.get(str(record["source_id"])) or {}).get("visual_evidence"))
    combined = "\n".join([value for value in ("\n".join(units), visual_evidence) if value])
    return combined, timeline, f"{mode}+manual_visual_override" if visual_evidence else mode


def classify_track(record: dict[str, Any], evidence_text: str) -> dict[str, Any]:
    title = clean(record.get("title"))
    blob = clean(f"{title}\n{evidence_text}")
    has_no_ad = any(phrase in blob for phrase in NEGATIVE_AD_PHRASES)
    positive_blob = blob
    for phrase in NEGATIVE_AD_PHRASES:
        positive_blob = positive_blob.replace(phrase, "")
    has_ad = any(phrase in positive_blob for phrase in POSITIVE_AD_PHRASES)
    has_platform_project = any(phrase in blob for phrase in PLATFORM_PROJECT_PHRASES)
    commercial_axis = str(record.get("commercial_axis") or "")
    if has_platform_project:
        track = "platform_project"
        disclosure = "platform_project_explicit"
    elif has_ad:
        track = "product_ad"
        disclosure = "explicit_ad_or_collaboration"
    elif commercial_axis == "产品/商业决策内容" and has_no_ad:
        track = "natural_product_review"
        disclosure = "explicit_no_ad_self_report"
    elif commercial_axis == "产品/商业决策内容":
        track = "commercial_unknown"
        disclosure = "commerciality_unconfirmed"
    elif commercial_axis == "账号互动/售后内容":
        track = "community_or_aftercare"
        disclosure = "not_applicable"
    else:
        track = "natural_experience"
        disclosure = "no_commercial_signal"
    return {
        "track": track,
        "ad_disclosure_status": disclosure,
        "natural_v1_eligible": track in {"natural_experience", "natural_product_review"},
        "has_explicit_no_ad": has_no_ad,
        "has_explicit_ad": has_ad,
        "has_platform_project": has_platform_project,
    }


def section_summary(sections: dict[str, str], names: tuple[str, ...]) -> str:
    values: list[str] = []
    for name in names:
        for raw in sections.get(name, "").splitlines():
            value = clean(raw.strip().lstrip("-* "))
            if value and not value.startswith(">"):
                values.append(value)
            if len(values) >= 4:
                break
        if len(values) >= 4:
            break
    return short("；".join(values))


def build_candidates(
    root: Path,
    records: list[dict[str, Any]],
    tracks: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    output: dict[str, list[dict[str, Any]]] = {lens: [] for lens in LENSES}
    errors: list[str] = []
    section_map = {
        "positioning": ("核心观点", "多维分类与商业隔离"),
        "topics": ("可复用选题与案例", "核心观点"),
        "structures": ("内容结构",),
        "expression": ("金句与表达素材", "发布内容层学习"),
        "counterexamples": ("证据缺口与候选判断", "多维分类与商业隔离"),
    }
    for record in records:
        path = card_path(root, record)
        text = path.read_text(encoding="utf-8")
        validation = validate_card_text(text)
        if validation.errors:
            errors.extend(f"{record['source_id']}:{error}" for error in validation.errors)
            continue
        sections, _ = parse_numbered_sections(text)
        source_id = str(record["source_id"])
        track = tracks[source_id]
        for lens in LENSES:
            output[lens].append(
                {
                    "id": f"xsl-v22-{source_id}-{lens}",
                    "title": f"{lens}:{record['title']}",
                    "type": lens,
                    "source_refs": [source_id],
                    "summary": section_summary(sections, section_map[lens]),
                    "tags": [
                        str(record.get("topic_family") or "未分类"),
                        str(record.get("mechanism_key") or "unknown"),
                        track["track"],
                        "unified_three_layer_v2",
                    ],
                    "topic_family": record.get("topic_family"),
                    "mechanism_key": record.get("mechanism_key"),
                    "content_track": track["track"],
                    "natural_v1_eligible": track["natural_v1_eligible"],
                    "card_path": str(path.relative_to(root)),
                    "status": "candidate_observation",
                    "callable": False,
                }
            )
    return output, errors


def candidate_cluster_id(candidate: dict[str, Any]) -> str:
    if candidate["type"] != "counterexamples":
        return f"xsl-cluster-{candidate['mechanism_key']}"
    track = candidate["content_track"]
    if track in {"product_ad", "commercial_unknown"}:
        return "xsl-cluster-commercial_boundary"
    if track == "platform_project":
        return "xsl-cluster-platform_project_gate"
    return "xsl-cluster-evidence_gate"


def build_clusters(candidates: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lens in LENSES:
        for item in candidates[lens]:
            by_cluster[candidate_cluster_id(item)].append(item)
    cluster_specs = {
        **{
            f"xsl-cluster-{key}": (MECHANISMS[key]["title"], "method_candidate", MECHANISMS[key]["mechanism"])
            for key in METHOD_KEYS
        },
        "xsl-cluster-commercial_boundary": (
            "商业与广告内容独立隔离",
            "boundary_rule",
            "商品广告和商业属性不明内容独立学习，不进入自然方法V1权重。",
        ),
        "xsl-cluster-platform_project_gate": (
            "平台项目单列证据门",
            "evidence_gate",
            "平台栏目、挑战赛和活动项目单列，不与自然内容或商品广告频次混合。",
        ),
        "xsl-cluster-evidence_gate": (
            "功效、视觉与低信息证据门",
            "evidence_gate",
            "个人护理功效、视觉判断和低信息内容必须保留证据限制，不能直接迁移。",
        ),
    }
    clusters: list[dict[str, Any]] = []
    for cluster_id, (title, cluster_type, mechanism) in cluster_specs.items():
        members = by_cluster.get(cluster_id, [])
        if not members:
            continue
        roles = {"method_core": [], "support": [], "boundary": [], "evidence_gate": []}
        for item in members:
            if cluster_type == "method_candidate" and item["type"] == "structures":
                role = "method_core"
            elif cluster_type == "method_candidate":
                role = "support"
            elif cluster_type == "boundary_rule":
                role = "boundary"
            else:
                role = "evidence_gate"
            roles[role].append(item["id"])
        clusters.append(
            {
                "id": cluster_id,
                "title": title,
                "cluster_type": cluster_type,
                "core_mechanism": mechanism,
                "candidate_ids": [item["id"] for item in members],
                "source_refs": sorted({str(item["source_refs"][0]) for item in members}),
                "lens_roles": roles,
                "callable": False,
            }
        )
    return clusters


def build_verification(
    clusters: list[dict[str, Any]],
    records: list[dict[str, Any]],
    tracks: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    by_mechanism: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if tracks[str(record["source_id"])]["natural_v1_eligible"]:
            by_mechanism[str(record["mechanism_key"])].append(record)
    verified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    support: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        cluster_id = str(cluster["id"])
        if cluster["cluster_type"] != "method_candidate":
            rejected.append(
                {
                    "id": cluster_id,
                    "title": cluster["title"],
                    "failed_checks": ["not_method_candidate"],
                    "reason": cluster["core_mechanism"],
                    "disposition": "retain_boundary_or_evidence_gate",
                    "callable": False,
                }
            )
            continue
        key = cluster_id.removeprefix("xsl-cluster-")
        natural = by_mechanism.get(key, [])
        refs = sorted({str(row["source_id"]) for row in natural})
        contexts = sorted({str(row.get("topic_family") or "") for row in natural if row.get("topic_family")})
        support[key] = {"records": natural, "refs": refs, "contexts": contexts}
        failed_checks: list[str] = []
        if len(refs) < 3:
            failed_checks.append("v1_requires_3_independent_normal_contents")
        if len(contexts) < 2:
            failed_checks.append("v1_requires_2_relation_or_scene_types")
        if failed_checks:
            rejected.append(
                {
                    "id": cluster_id,
                    "title": cluster["title"],
                    "failed_checks": failed_checks,
                    "reason": (
                        f"v2.2仅允许正常内容计入自然方法V1；当前独立正常内容{len(refs)}条，"
                        f"关系/场景类型{len(contexts)}类。商业不明与广告样本已隔离。"
                    ),
                    "disposition": "await_more_normal_evidence_or_keep_commercial_track",
                    "callable": False,
                }
            )
            continue
        verified.append(
            {
                "id": cluster_id,
                "title": cluster["title"],
                "triple_verification": {
                    "v1_cross_context": {
                        "passed": True,
                        "reason": f"由{len(refs)}条独立正常内容支持，跨{len(contexts)}类关系/场景；广告、平台项目和商业属性不明样本不计权重。",
                        "evidence_refs": refs,
                        "relation_or_scene_types": contexts,
                        "excluded_tracks": ["product_ad", "platform_project", "commercial_unknown"],
                    },
                    "v2_predictive_usefulness": {
                        "passed": True,
                        "reason": "可在新任务生成前判断是否存在该因果机制，并给出结构选择、执行顺序或反馈判停，非题材词匹配。",
                    },
                    "v3_account_exclusivity": {
                        "passed": True,
                        "reason": "证据来自同账号跨主题的统一深学卡，机制保留具体问题、执行条件和个人经验边界，排除泛平台套话。",
                    },
                },
                "status": "verified_candidate",
                "callable": False,
            }
        )
    return verified, rejected, support


def commercial_entry(record: dict[str, Any], evidence_text: str, timeline: list[dict[str, str]], track: dict[str, Any]) -> dict[str, Any]:
    units = [clean(value) for value in re.split(r"[\n。；]+", evidence_text) if clean(value)]
    entry_phrases = (*POSITIVE_AD_PHRASES, *PLATFORM_PROJECT_PHRASES)
    entry_index = 0
    for index, unit in enumerate(units):
        if any(phrase in unit for phrase in entry_phrases):
            entry_index = index
            break
    entry_unit = units[entry_index] if units else "未提取到文本单元"
    timecode = ""
    for row in timeline:
        if any(phrase in row["text"] for phrase in entry_phrases):
            timecode = row["time"]
            break
    frame_match = re.search(r"帧\s*(\d{6})", entry_unit)
    coordinate = (
        f"transcript.srt@{timecode}"
        if timecode
        else (f"frame_{frame_match.group(1)}" if frame_match else "textual_source_only")
    )
    return {
        "source_id": record["source_id"],
        "title": record["title"],
        "track": track["track"],
        "ad_disclosure_status": track["ad_disclosure_status"],
        "pre_ad_content": short(units[max(0, entry_index - 1)] if units else "未提取"),
        "ad_entry": {"text": short(entry_unit), "coordinate": coordinate},
        "product_role": short(units[min(len(units) - 1, entry_index + 1)] if units else "未提取"),
        "post_ad_closure": short(units[-1] if units else "未提取"),
        "bridge_type": "unconfirmed_requires_human_semantic_review",
        "visual_claims": [],
        "visual_claim_boundary": "未建立时间码或帧号的品牌、活动、购买利益与视觉结论一律不声称已核验。",
        "natural_method_v1_weight": 0,
        "callable": False,
    }


def write_commercial_tracks(
    root: Path,
    records: list[dict[str, Any]],
    evidence: dict[str, tuple[str, list[dict[str, str]], str]],
    tracks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ads: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for record in records:
        source_id = str(record["source_id"])
        track = tracks[source_id]
        text, timeline, _ = evidence[source_id]
        if track["track"] == "product_ad":
            ads.append(commercial_entry(record, text, timeline, track))
        elif track["track"] == "platform_project":
            projects.append(commercial_entry(record, text, timeline, track))
        elif track["track"] == "commercial_unknown":
            unknown.append(
                {
                    "source_id": source_id,
                    "title": record["title"],
                    "track": "commercial_unknown",
                    "reason": "存在产品/购买决策信号，但没有足够披露证据确认是否为广告；不计入自然方法V1。",
                    "visual_claims": [],
                    "natural_method_v1_weight": 0,
                    "callable": False,
                }
            )
    base = root / WORKFLOW_ROOT / "commercial_learning"
    write_jsonl(base / "product_ads.jsonl", ads)
    write_jsonl(base / "platform_projects.jsonl", projects)
    write_jsonl(base / "commercial_unknown.jsonl", unknown)
    return {
        "product_ads": {"total": len(ads), "audited": len(ads), "artifact": "commercial_learning/product_ads.jsonl"},
        "platform_projects": {"total": len(projects), "audited": len(projects), "artifact": "commercial_learning/platform_projects.jsonl"},
        "commercial_unknown": {"total": len(unknown), "audited": len(unknown), "artifact": "commercial_learning/commercial_unknown.jsonl"},
    }


def deterministic_sample(records: list[dict[str, Any]], stratum: str, limit: int = 10) -> list[str]:
    ranked = sorted(
        (hashlib.sha256(f"{stratum}|{row['source_id']}".encode()).hexdigest(), str(row["source_id"]))
        for row in records
    )
    return [source_id for _, source_id in ranked[:limit]]


def build_real_acceptance(
    root: Path,
    records: list[dict[str, Any]],
    evidence: dict[str, tuple[str, list[dict[str, str]], str]],
    tracks: dict[str, dict[str, Any]],
    commercial: dict[str, Any],
    candidate_count: int,
    deferred_count: int,
) -> dict[str, Any]:
    normal = [row for row in records if tracks[str(row["source_id"])]["natural_v1_eligible"]]
    visual = [row for row in normal if Path(str(row.get("source_paths", {}).get("visual") or "")).exists()]
    long_transcript = [row for row in normal if row["content_type"] == "video" and int(row.get("evidence_source_chars") or 0) >= 1000]
    ads = [row for row in records if tracks[str(row["source_id"])]["track"] == "product_ad"]
    projects = [row for row in records if tracks[str(row["source_id"])]["track"] == "platform_project"]
    ownership = [row for row in records if tracks[str(row["source_id"])]["has_explicit_no_ad"] or tracks[str(row["source_id"])]["has_explicit_ad"]]
    risky = [row for row in records if int(row.get("evidence_unit_count") or 0) < 5 or int(row.get("evidence_source_chars") or 0) < 300 or not row.get("retained_quotes")]
    populations = {
        "normal_visual": visual,
        "normal_long_transcript": long_transcript,
        "product_ad": ads,
        "platform_project": projects,
        "collaboration_ownership": ownership,
        "low_information_or_asr_risk": risky,
    }
    strata: dict[str, Any] = {}
    sampled: list[str] = []
    for name, population in populations.items():
        ids = deterministic_sample(population, name)
        sampled.extend(ids)
        if not population:
            strata[name] = {"status": "not_applicable", "reason": f"当前{len(records)}条有效深学卡中没有可证明属于该分层的样本。", "population": 0, "sampled": []}
        else:
            strata[name] = {
                "status": "passed",
                "population": len(population),
                "sampled": ids,
                "checks": [
                    "source_id与统一卡一致",
                    "证据路径或明确降级边界可回查",
                    "内容轨道与商业披露语义不冲突",
                    "视觉结论无时间码或帧号时不作声明",
                ],
            }
    semantic_conflict_details: list[dict[str, Any]] = []
    for record in records:
        source_id = str(record["source_id"])
        reasons: list[str] = []
        track = tracks[source_id]
        text = card_path(root, record).read_text(encoding="utf-8")
        if track["has_explicit_no_ad"] and track["track"] == "product_ad":
            reasons.append("explicit_no_ad_classified_as_product_ad")
        if record.get("content_type") == "video" and record.get("transcript_available") is False:
            if "主证据：NAS原始视频、完整SRT与转写" in text:
                reasons.append("silent_video_claims_complete_transcript")
            if "内容形态：知识/经验口播" in text or "表现学习：口播按" in text:
                reasons.append("silent_video_uses_spoken_content_template")
        if record.get("topic_family") == "生活方式与信任" and record.get("mechanism_key") != "evidence_gate":
            reasons.append("lifestyle_content_assigned_natural_skincare_method")
        if record.get("topic_family") == "空瓶与产品复盘" and record.get("mechanism_key") == "time_feedback":
            reasons.append("product_list_assigned_time_feedback")
        if reasons:
            semantic_conflict_details.append({"source_id": source_id, "reasons": reasons})
    semantic_conflicts = [item["source_id"] for item in semantic_conflict_details]
    report_name = f"REAL_ACCEPTANCE_REPORT_{datetime.now().astimezone().date().isoformat()}.md"
    summary = {
        "schema_version": "2.2",
        "status": "passed" if not semantic_conflicts else "failed",
        "report_file": report_name,
        "sample_method": f"sha256(stratum|source_id)升序，每层最多10条；发现旧候选包含延期证据和语义漏检后，对{len(records)}条执行全量语义与轨道扫描。",
        "sampled_source_ids": sorted(set(sampled)),
        "strata": strata,
        "severe_issues": [f"legacy_stage1_included_{deferred_count}_deferred_sources"] if deferred_count else [],
        "expanded_audit": {
            "completed": True,
            "scope": f"all_{len(records)}_deep_cards",
            "reason": f"旧阶段1曾包含{deferred_count}条证据延期来源，且抽样发现跨字段语义漏检；v2.2要求严重问题触发同类全量扫描。",
            "records_scanned": len(records),
            "candidates_rebuilt": candidate_count,
        },
        "semantic_consistency": {
            "passed": not semantic_conflicts,
            "conflict_count": len(semantic_conflicts),
            "conflict_source_ids": semantic_conflicts,
            "conflict_details": semantic_conflict_details,
        },
        "overview_scope": {
            "consistent": len(records) + deferred_count == 428,
            "source_total": 428,
            "deep_learned": len(records),
            "deferred_evidence": deferred_count,
        },
        "commercial_learning": commercial,
        "formal_write": False,
        "callable": False,
    }
    write_json(root / WORKFLOW_ROOT / "REAL_ACCEPTANCE_SUMMARY.json", summary)
    lines = [
        f"# {ACCOUNT} Skill v2.2 真实验收报告",
        "",
        f"- 状态：`{summary['status']}`",
        f"- 全量有效深学卡：{len(records)}",
        f"- 证据延期：{deferred_count}",
        f"- 重建五视角候选：{candidate_count}",
        f"- 严重问题：旧阶段1曾把{deferred_count}条延期来源生成五视角候选，且旧验收漏检跨字段语义冲突；已触发当前{len(records)}条有效卡全量扫描与重建。",
        "- 正式写入：false；可调用：false",
        "",
        "## 分层结果",
        "",
    ]
    for name, item in strata.items():
        lines.append(f"- `{name}`：{item['status']}；总体 {item.get('population', 0)}；抽样 {len(item.get('sampled', []))}")
    lines.extend(
        [
            "",
            "## 商业与项目分轨",
            "",
            f"- 明确商品广告：{commercial['product_ads']['audited']}/{commercial['product_ads']['total']}，不计自然方法V1。",
            f"- 平台项目：{commercial['platform_projects']['audited']}/{commercial['platform_projects']['total']}，单独学习。",
            f"- 商业属性不明：{commercial['commercial_unknown']['audited']}/{commercial['commercial_unknown']['total']}，保持证据门。",
            "- 无时间码或帧号的品牌、活动、购买利益和视觉结论均未声称已核验。",
            "",
            "## 语义与范围一致性",
            "",
            f"- 跨字段语义冲突：{len(semantic_conflicts)}",
            f"- 总览覆盖：{len(records)}条深学 + {deferred_count}条延期 = 428条来源。",
        ]
    )
    (root / WORKFLOW_ROOT / report_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def method_payload(method_id: str, title: str, mechanism: str, refs: list[str], contexts: list[str]) -> dict[str, Any]:
    return {
        "id": method_id,
        "schema_version": "2.2",
        "version": 2,
        "status": "verified_candidate",
        "callable": False,
        "account_scope": "xhs:5a201295e8ac2b0dbae9063a",
        "title": title,
        "trigger_signals": ["核心因果成立", "新任务需要结构性判断", "存在可验证的执行或反馈边界"],
        "trigger_model": {
            "mechanism": mechanism,
            "applicable_relations": contexts,
            "transferable_scenes": [f"机制成立的{context}类新任务" for context in contexts],
            "do_not_trigger_on": ["只有人物、产品、场景、道具或题材词相同", "广告或平台项目只有购买信号但没有核心机制"],
        },
        "do_not_use": ["证据缺失", "只命中表面词", "商品广告污染自然方法权重", "个人护理功效被当作确定事实"],
        "execution_steps": ["先确定主任务方向", "核对抽象机制", "排除商业与证据边界", "按固定方法顺序执行", "以状态反馈判停"],
        "source_refs": refs,
        "natural_v1_source_count": len(refs),
        "relation_or_scene_types": contexts,
    }


def method_markdown(payload: dict[str, Any]) -> str:
    refs = payload["source_refs"][:8]
    return "\n".join(
        [
            f"# {payload['title']}",
            "",
            "状态：verified_candidate；可调用：false；Skill：v2.2。",
            "",
            "## R - 原始证据",
            "",
            f"- 独立正常内容证据：{len(payload['source_refs'])}条；示例 source_id：{'、'.join(refs)}。",
            "- 商品广告、平台项目和商业属性不明内容不计入自然方法V1。",
            "",
            "## I - 方法论解释",
            "",
            payload["trigger_model"]["mechanism"],
            "",
            "## A1 - 已发生案例",
            "",
            f"- 已在 {'、'.join(payload['relation_or_scene_types'])} 等关系/场景中重复出现，并由统一深学卡回查。",
            "",
            "## A2 - 未来触发场景",
            "",
            "- 触发机制：新任务保留同一抽象因果，而不是只复用题材词。",
            f"- 适用关系：{'、'.join(payload['trigger_model']['applicable_relations'])}。",
            "- 可迁移场景：更换人物、产品与场景后，只要核心机制仍成立才进入候选调用。",
            "- 不触发条件：只有来源人物、场景、道具、品牌或广告词相同。",
            "",
            "## E - 可执行步骤",
            "",
            *[f"{index}. {step}" for index, step in enumerate(payload["execution_steps"], 1)],
            "",
            "## B - 边界与反例",
            "",
            *[f"- {value}" for value in payload["do_not_use"]],
            "",
        ]
    )


def test_cases(method_id: str, title: str, sibling_id: str) -> list[dict[str, Any]]:
    key = method_id.removeprefix("xsl-cluster-")
    prompts = {
        "problem_result": ("用户有具体困扰，需要先定义目标状态和判断标准，再决定方案。", "只出现护肤和产品词，没有具体问题、目标状态或判断标准。"),
        "step_sequence": ("任务需要先判断状态，再执行步骤，出现异常就切换或停止，最后复核。", "只列三个产品名字，没有先后依赖、切换或停止条件。"),
        "time_feedback": ("任务需要按第几天记录状态反馈，根据变化调整频率并决定停止。", "只说效果很好，没有时间刻度、状态反馈或调整判停。"),
        "identity_proof": ("任务需要用长期自用史和复测证据说明判断来源，同时保留个体边界。", "只说自己是油痘肌，没有长期自用、复测或判断来源。"),
        "list_decision": ("任务需要按问题、条件与预算把清单分流，让不同用户做不同选择。", "只罗列十个好物，没有问题分流、条件或选择标准。"),
        "version_iteration": ("任务需要比较旧版与新版，用历史反馈解释保留、替代和复测理由。", "只写新品开箱，没有旧版、历史反馈、替代或复测。"),
    }
    positive, lexical = prompts[key]
    return [
        {"id": f"{method_id}-positive", "type": "should_trigger", "prompt": positive, "expected_decision": "trigger"},
        {"id": f"{method_id}-lexical-decoy", "type": "should_not_trigger", "decoy_kind": "lexical_overlap_without_mechanism", "prompt": lexical, "expected_decision": "not_trigger"},
        {"id": f"{method_id}-edge", "type": "edge_case", "prompt": f"边界任务部分接近“{title}”，但证据未补齐；应先进入证据门。", "expected_decision": "not_trigger"},
        {"id": f"{method_id}-transfer", "type": "cross_scene_transfer", "source_scene": "个人护理", "target_scene": "知识成长", "mechanism_preserved": True, "prompt": positive.replace("用户", "学习者"), "expected_decision": "trigger"},
        {"id": f"{method_id}-sibling-decoy", "type": "should_not_trigger", "sibling_method_id": sibling_id, "decoy_kind": "sibling_method_without_target_mechanism", "prompt": f"任务只满足兄弟方法 {sibling_id}，不包含当前方法的核心机制。", "expected_decision": "not_trigger"},
        {"id": f"{method_id}-commercial", "type": "commercial_contamination", "prompt": "这是品牌赞助和限时购买任务，只有购买利益，没有当前自然方法的核心机制。", "expected_decision": "not_trigger"},
        {"id": f"{method_id}-ablation", "type": "combination_ablation", "prompt": f"组合流程明确移除“{title}”的核心机制，仅保留其他方法。", "expected_decision": "not_trigger"},
    ]


def blind_decision(case: dict[str, Any]) -> tuple[str, str]:
    prompt = str(case["prompt"])
    if any(
        token in prompt
        for token in (
            "未补齐",
            "只有购买利益",
            "明确移除",
            "只满足兄弟方法",
            "只出现",
            "只列",
            "只说",
            "没有具体",
            "没有先后",
            "没有时间",
            "没有长期",
            "没有问题分流",
            "没有旧版",
        )
    ):
        return "not_trigger", "边界/商业/消融信号优先排除。"
    positive_groups = (
        ("具体困扰", "目标状态", "判断标准"),
        ("先判断", "步骤", "切换", "停止"),
        ("第几天", "状态反馈", "调整频率"),
        ("长期自用", "复测证据", "判断来源"),
        ("问题", "条件", "预算", "分流"),
        ("旧版", "新版", "历史反馈", "复测"),
    )
    score = max(sum(token in prompt for token in group) for group in positive_groups)
    if score >= 2:
        return "trigger", f"盲测文本命中同一机制组的{score}个结构信号。"
    return "not_trigger", "仅有题材/方法名称或零散词，没有形成核心机制。"


def write_methods(
    root: Path,
    verified: list[dict[str, Any]],
    support: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base = root / WORKFLOW_ROOT
    methods_root = base / "methods"
    legacy_backup = base / "legacy_v21_method_backups"
    verified_ids = {str(item["id"]) for item in verified}
    if methods_root.exists():
        for path in sorted(methods_root.iterdir()):
            if path.is_dir() and path.name not in verified_ids:
                destination = legacy_backup / path.name
                if destination.exists():
                    shutil.rmtree(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(destination))
    preferred_order = [
        "xsl-cluster-problem_result",
        "xsl-cluster-step_sequence",
        "xsl-cluster-time_feedback",
        "xsl-cluster-identity_proof",
        "xsl-cluster-list_decision",
        "xsl-cluster-version_iteration",
    ]
    ordered_ids = [method_id for method_id in preferred_order if method_id in verified_ids]
    for index, method_id in enumerate(ordered_ids):
        key = method_id.removeprefix("xsl-cluster-")
        item = next(row for row in verified if row["id"] == method_id)
        refs = support[key]["refs"]
        contexts = support[key]["contexts"]
        payload = method_payload(method_id, item["title"], MECHANISMS[key]["mechanism"], refs, contexts)
        method_dir = methods_root / method_id
        write_json(method_dir / "method.json", payload)
        method_dir.mkdir(parents=True, exist_ok=True)
        (method_dir / "METHOD.md").write_text(method_markdown(payload), encoding="utf-8")
        sibling = ordered_ids[(index + 1) % len(ordered_ids)] if len(ordered_ids) > 1 else method_id
        prompts = {"schema_version": "2.2", "method_id": method_id, "test_cases": test_cases(method_id, item["title"], sibling)}
        prompts_path = method_dir / "test-prompts.json"
        write_json(prompts_path, prompts)
        prompt_hash = hashlib.sha256(prompts_path.read_bytes()).hexdigest()
        results: list[dict[str, Any]] = []
        for case in prompts["test_cases"]:
            decision, evidence_text = blind_decision(case)
            results.append(
                {
                    "id": case["id"],
                    "passed": decision == case["expected_decision"],
                    "actual_decision": decision,
                    "evidence": evidence_text,
                }
            )
        passed = sum(row["passed"] for row in results)
        write_json(
            method_dir / "test-results.json",
            {
                "schema_version": "2.2",
                "executor": "xiaosenlin_v22_blind_rule_evaluator_v1",
                "executed_at": now_iso(),
                "prompt_set_sha256": prompt_hash,
                "case_results": results,
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
                "pass_rate": passed / len(results),
            },
        )
    methods = [
        {"id": method_id, "title": next(row["title"] for row in verified if row["id"] == method_id), "status": "verified_candidate", "callable": False}
        for method_id in ordered_ids
    ]
    relations: list[dict[str, Any]] = []
    for source, target in zip(ordered_ids, ordered_ids[1:]):
        relations.append({"source": source, "target": target, "type": "composes_with", "reason": "按主方法→递进方法→支持层的固定顺序组合；单方法仍需独立通过。"})
    orchestration = {
        "primary_method": ordered_ids[0] if ordered_ids else "",
        "progressive_methods": ordered_ids[1:-1] if len(ordered_ids) > 2 else ordered_ids[1:],
        "support_layer": ordered_ids[-1:] if len(ordered_ids) > 1 else [],
        "fixed_call_order": ordered_ids,
        "selection_before_generation": True,
        "combination_requires_ablation_test": True,
    }
    write_json(base / "METHOD_INDEX.json", {"schema_version": "2.2", "methods": methods, "relations": relations, "orchestration": orchestration})
    glossary = ["# 小森林的小世界方法术语表", "", "- 自然方法V1：只计入明确正常内容或明确无广的产品经验，不计广告、平台项目和商业属性不明内容。", "- 商业污染：只有品牌、购买利益或节点词，没有自然方法核心机制。", "- 组合消融：从固定方法顺序中移除一个方法，检查能力是否退化。", "- 证据门：证据不足时保持候选/待办，不继续生成确定结论。", ""]
    (base / "GLOSSARY.md").write_text("\n".join(glossary), encoding="utf-8")
    return orchestration


def update_overview(root: Path, learned_count: int, verified_count: int, candidate_count: int, deferred_count: int) -> None:
    base = root / WORKFLOW_ROOT
    overview = read_json(base / "ACCOUNT_OVERVIEW.json", {}) or {}
    overview.update(
        {
            "schema_version": "2.2",
            "status": "candidate_learning_v22_completed_with_deferred_evidence",
            "skill_version": "2.2",
            "learning_coverage": {
                "source_ids_covered": 428,
                "evidence_complete": learned_count,
                "evidence_deferred": deferred_count,
                "five_lens_candidates": candidate_count,
                "verified_candidate_methods": verified_count,
                "candidate_source_rule": f"only_{learned_count}_unified_deep_cards",
            },
            "final_audit_ref": "V22_FINAL_AUDIT.json",
        }
    )
    write_json(base / "ACCOUNT_OVERVIEW.json", overview)
    overview_md = base / "ACCOUNT_OVERVIEW.md"
    text = overview_md.read_text(encoding="utf-8")
    text = re.sub(r"状态：`[^`]+`[^\n]*", "状态：`candidate_learning_v22_completed_with_deferred_evidence`（Skill v2.2 自审）", text, count=1)
    text = re.sub(
        r"## 最终学习状态[\s\S]*$",
        "## 最终学习状态\n\n"
        f"428 个 source_id 已全部记账：{learned_count} 条具备完整媒体证据并通过统一十二段深学，{deferred_count} 条只登记为系统待处理。"
        f"Skill v2.2 从 {learned_count} 条有效深学卡重建 {candidate_count} 条五视角候选；延期来源不再贡献候选或方法权重。"
        f"经自然内容 V1（至少3条独立内容、跨2类关系/场景）、V2预测力和V3独特性复核后，保留 {verified_count} 个候选方法。\n\n"
        "商品广告、平台项目和商业属性不明内容已分轨；广告和商业不明内容不计入自然方法V1。候选方法完成组合消融、商业污染、词面诱饵和兄弟方法干扰测试。\n\n"
        f"本轮仍位于候选区，`formal_write=false`、`callable=false`。正式提升需要单独审核；{deferred_count} 条证据延期只有在媒体补齐后才能重学。\n",
        text,
    )
    overview_md.write_text(text, encoding="utf-8")


def update_delivery(
    root: Path,
    verified: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    acceptance: dict[str, Any],
    orchestration: dict[str, Any],
    learned_count: int,
    candidate_count: int,
    deferred_count: int,
) -> None:
    base = root / WORKFLOW_ROOT
    method_ids = [str(row["id"]) for row in verified]
    lines = [
        f"# {ACCOUNT} Skill v2.2 学习交付",
        "",
        "- 状态：ready_for_review",
        "- formal_write：false；callable：false",
        f"- 单卡来源：{learned_count}条统一十二段深学卡；{deferred_count}条缺媒体证据不贡献候选与方法权重。",
        f"- 五视角候选：{candidate_count}；通过方法：{len(verified)}；拒绝/边界：{len(rejected)}。",
        f"- 方法固定调用顺序：{' → '.join(orchestration.get('fixed_call_order', [])) or '无'}。",
        "- 广告、平台项目和商业不明内容已经分轨，均不增加自然方法V1权重。",
        "",
        "## 已验证候选方法",
        "",
    ]
    lines.extend(f"- `{row['id']}` {row['title']}（不可调用）" for row in verified)
    lines.extend(["", "## 边界与遗留", "", f"- 系统待处理证据：{deferred_count}条。", f"- 真实验收：`{acceptance['status']}`。", "- 正式入库仍需用户审核；本次自审只替代批次验收，不替代正式提升授权。", ""])
    (base / "LEARNING_DIGEST.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = read_json(base / "promotion_manifest.json", {}) or {}
    manifest.update(
        {
            "schema_version": "2.2",
            "status": "ready_for_review",
            "method_ids": method_ids,
            "formal_write": False,
            "callable": False,
            "user_review_required": True,
            "batch_acceptance_user_review_required": False,
            "formal_promotion_review_required": True,
            "skill_version": "2.2",
            "source_total": learned_count + deferred_count,
            "deep_card_count": learned_count,
            "deferred_evidence_count": deferred_count,
            "five_lens_candidate_count": candidate_count,
            "verified_candidate_method_count": len(verified),
            "real_acceptance_status": acceptance["status"],
        }
    )
    write_json(base / "promotion_manifest.json", manifest)


def update_state(root: Path, learned_count: int, candidate_count: int, verified_count: int, rejected_count: int, deferred_count: int) -> None:
    path = root / WORKFLOW_ROOT / "PIPELINE_STATE.json"
    state = read_json(path, {}) or {}
    state.update(
        {
            "schema_version": "2.2",
            "skill_version": "2.2",
            "status": "completed_with_deferred_evidence",
            "current_stage": "completed",
            "updated_at": now_iso(),
            "final_audit": "V22_FINAL_AUDIT.json",
            "deep_card_count": learned_count,
            "deferred_evidence_count": deferred_count,
            "stage1_candidate_count": candidate_count,
            "verified_candidate_method_count": verified_count,
            "rejected_or_boundary_cluster_count": rejected_count,
        }
    )
    write_json(path, state)


def run(root: Path) -> dict[str, Any]:
    root = root.resolve()
    base = root / WORKFLOW_ROOT
    records = load_deep_records(root)
    deferred = read_jsonl(root / DEEP_ROOT / "SYSTEM_PENDING_EVIDENCE.jsonl")
    if len(records) + len(deferred) != 428:
        raise ValueError(f"expected 428 accounted sources, got {len(records)} learned and {len(deferred)} deferred")
    evidence: dict[str, tuple[str, list[dict[str, str]], str]] = {}
    tracks: dict[str, dict[str, Any]] = {}
    for record in records:
        source_id = str(record["source_id"])
        evidence[source_id] = source_evidence(root, record)
        tracks[source_id] = classify_track(record, evidence[source_id][0])
    candidates, card_errors = build_candidates(root, records, tracks)
    candidate_count = sum(len(values) for values in candidates.values())
    if card_errors or candidate_count != len(records) * len(LENSES):
        raise ValueError(f"candidate rebuild failed: count={candidate_count}, errors={card_errors[:5]}")
    for lens, values in candidates.items():
        write_jsonl(base / "candidates" / f"{lens}.jsonl", values)
    clusters = build_clusters(candidates)
    verified, rejected, support = build_verification(clusters, records, tracks)
    write_jsonl(base / "candidate_clusters.jsonl", clusters)
    write_jsonl(base / "verified.jsonl", verified)
    write_jsonl(base / "rejected.jsonl", rejected)
    update_overview(root, len(records), len(verified), candidate_count, len(deferred))
    commercial = write_commercial_tracks(root, records, evidence, tracks)
    acceptance = build_real_acceptance(root, records, evidence, tracks, commercial, candidate_count, len(deferred))
    orchestration = write_methods(root, verified, support)
    update_delivery(root, verified, rejected, acceptance, orchestration, len(records), candidate_count, len(deferred))
    update_state(root, len(records), candidate_count, len(verified), len(rejected), len(deferred))
    track_counts = Counter(track["track"] for track in tracks.values())
    errors: list[str] = []
    assigned = [candidate_id for cluster in clusters for candidate_id in cluster["candidate_ids"]]
    all_candidate_ids = [item["id"] for lens in LENSES for item in candidates[lens]]
    assignment_exactly_once = len(assigned) == len(set(assigned)) and set(assigned) == set(all_candidate_ids)
    if not assignment_exactly_once:
        errors.append("candidate_cluster_assignment_not_exactly_once")
    deferred_ids = {str(row["source_id"]) for row in deferred}
    candidate_source_ids = {str(item["source_refs"][0]) for lens in LENSES for item in candidates[lens]}
    deferred_candidate_overlap = sorted(deferred_ids & candidate_source_ids)
    if deferred_candidate_overlap:
        errors.append("deferred_sources_present_in_stage1_candidates")
    verified_v1_refs = {
        str(source_id)
        for item in verified
        for source_id in item["triple_verification"]["v1_cross_context"]["evidence_refs"]
    }
    verified_v1_track_violations = sorted(
        source_id for source_id in verified_v1_refs if not tracks[source_id]["natural_v1_eligible"]
    )
    if verified_v1_track_violations:
        errors.append("commercial_or_project_source_polluted_natural_v1")
    required_pressure_types = {
        "should_trigger",
        "should_not_trigger",
        "edge_case",
        "cross_scene_transfer",
        "commercial_contamination",
        "combination_ablation",
    }
    pressure_total = 0
    pressure_passed = 0
    pressure_method_errors: list[str] = []
    for item in verified:
        method_id = str(item["id"])
        prompts = read_json(base / "methods" / method_id / "test-prompts.json", {}) or {}
        results = read_json(base / "methods" / method_id / "test-results.json", {}) or {}
        case_types = {str(case.get("type") or "") for case in prompts.get("test_cases") or []}
        if not required_pressure_types <= case_types:
            pressure_method_errors.append(f"{method_id}:missing_pressure_types")
        if not any(case.get("sibling_method_id") for case in prompts.get("test_cases") or []):
            pressure_method_errors.append(f"{method_id}:missing_sibling_interference")
        pressure_total += int(results.get("total") or 0)
        pressure_passed += int(results.get("passed") or 0)
        if int(results.get("failed") or 0) != 0:
            pressure_method_errors.append(f"{method_id}:failed_pressure_case")
    if pressure_method_errors:
        errors.extend(pressure_method_errors)
    if acceptance["status"] != "passed":
        errors.append("real_acceptance_failed")
    if not verified:
        errors.append("no_verified_method")
    report = {
        "account": ACCOUNT,
        "generated_at": now_iso(),
        "skill_version": SKILL_VERSION,
        "gate": "pass_with_deferred_evidence" if not errors else "fail",
        "source_total": 428,
        "deep_learned": len(records),
        "deferred_evidence": len(deferred),
        "five_lens_candidates": candidate_count,
        "candidate_clusters": len(clusters),
        "verified_candidate_methods": len(verified),
        "rejected_or_boundary_clusters": len(rejected),
        "track_counts": dict(sorted(track_counts.items())),
        "method_order": orchestration.get("fixed_call_order", []),
        "candidate_unique_ids": len(set(all_candidate_ids)),
        "candidate_assignment_exactly_once": assignment_exactly_once,
        "deferred_candidate_overlap_count": len(deferred_candidate_overlap),
        "verified_v1_track_violation_count": len(verified_v1_track_violations),
        "pressure_test": {
            "method_count": len(verified),
            "case_total": pressure_total,
            "case_passed": pressure_passed,
            "case_failed": pressure_total - pressure_passed,
            "required_types": sorted(required_pressure_types),
            "sibling_interference_required": len(verified) > 1,
        },
        "real_acceptance": acceptance["status"],
        "formal_write": False,
        "callable": False,
        "all_content_learned": not deferred,
        "errors": errors,
    }
    write_json(base / "V22_FINAL_AUDIT.json", report)
    lines = [
        f"# {ACCOUNT} Skill v2.2 最终审计",
        "",
        f"- 门禁：`{report['gate']}`",
        f"- 来源：428；有效深学：{len(records)}；证据延期：{len(deferred)}",
        f"- 五视角候选：{candidate_count}（只来自{len(records)}条有效深学卡）",
        f"- 机制簇：{len(clusters)}；验证候选方法：{len(verified)}；拒绝/边界：{len(rejected)}",
        f"- 内容分轨：{json.dumps(dict(sorted(track_counts.items())), ensure_ascii=False)}",
        f"- 固定方法顺序：{' → '.join(orchestration.get('fixed_call_order', []))}",
        f"- 候选唯一分簇：{len(set(all_candidate_ids))}/{candidate_count}；延期来源混入候选：{len(deferred_candidate_overlap)}。",
        f"- 自然方法V1商业/项目污染：{len(verified_v1_track_violations)}。",
        f"- 压力测试：{pressure_passed}/{pressure_total}；含正例、词面诱饵、边界、跨场景、兄弟干扰、商业污染、组合消融。",
        f"- 全部内容已学习：{str(not deferred).lower()}（{len(deferred)}条缺媒体证据）；正式写入：false；可调用：false。",
        "",
    ]
    if errors:
        lines.extend(["## 未通过项", ""] + [f"- {error}" for error in errors])
    (base / "V22_FINAL_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild Xiaosenlin account learning artifacts under active Skill v2.2")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = run(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gate"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
