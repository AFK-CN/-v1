from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import CONTRACT_ID, validate_unified_text

PROFILE_ID = "lizongheng"
ACCOUNT_ID = "63700340656"
ACCOUNT_NAME = "李宗恒"
LEGACY_NAS_ROOT = Path("/Volumes/AFK/zhishikushuju/dy")
CURRENT_NAS_ROOT = Path("/Volumes/dy")
DEFAULT_INVENTORY = Path(
    "10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/nas_evidence_inventory.jsonl"
)
DEFAULT_OUTPUT = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/batches")

ENUMS = {
    "content_form": {"剧情段子", "唱演/音乐化表达", "口播/独白", "合拍/同框剧情", "其他"},
    "relationship_axis": {
        "恋爱/婚恋", "亲友/家庭", "职场/商务", "同学/校园", "朋友/社交",
        "陌生人/服务消费", "自我表达/舞台表演", "待判定",
    },
    "scene_axis": {
        "家庭/过年节日", "职场/面试/会议", "校园/宿舍/课堂", "餐饮/购物/服务场景",
        "公共空间/交通/街头", "舞台/直播/媒体", "泛生活室内", "待判定",
    },
    "comedy_engine": {
        "误会错位", "身份错位", "语言歧义", "边界拉扯", "情绪升级/重复",
        "身份/地位反转", "最后反转", "金句/价值表达", "待判定",
    },
    "commercial_axis": {"正常内容", "广告植入但剧情完整", "广告强绑定/广告主导", "平台活动/挑战赛", "待判定"},
    "learning_value_axis": {
        "高价值结构样本", "高价值人设/表演样本", "高价值标题文案样本", "广告隔离样本", "低信息样本",
    },
}

BRAND_HINTS = (
    "宁德时代", "麒麟电池", "亚朵", "深睡被", "京东", "天猫", "抖音商城",
    "荣耀", "王者荣耀", "豆包", "伊利", "一粒纯牛奶", "SKII", "SK-II", "sk2", "神仙水", "宝骏云海", "宝军云海", "永异智能撑腰椅", "FLO 5500I", "抖音商城", "双11消费", "AGE面霜", "波色鹰", "茅台1935", "发条总动员", "沃尔沃", "XC70", "立必得", "冰梅见", "魔兽世界", "二十周年", "劲酒", "奥利奥", "舒肤佳", "科大讯飞", "安慕希", "飞科", "马克华菲",
)

REQUIRED_TEXT = (
    "synopsis", "conflict", "turning_point", "reusable_topic", "copy_learning",
    "topic_learning", "commercial_reason", "classification_reason",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_evidence_path(value: str | Path) -> Path:
    path = Path(value)
    if path.exists():
        return path
    try:
        relative = path.relative_to(LEGACY_NAS_ROOT)
    except ValueError:
        return path
    remapped = CURRENT_NAS_ROOT / relative
    return remapped if remapped.exists() else path


def source_metadata(item: dict[str, Any]) -> dict[str, Any]:
    source_path = resolve_evidence_path(item["evidence"]["source_json"])
    value = json.loads(source_path.read_text(encoding="utf-8", errors="ignore"))
    return {
        "source_path": source_path.as_posix(),
        "source_url": value.get("source_url") or value.get("raw", {}).get("source_url", ""),
        "title": value.get("title") or value.get("desc") or "",
        "desc": value.get("desc") or "",
        "publish_time": value.get("publish_time"),
        "account_id": str(value.get("account_id") or ""),
        "account_name": value.get("account_name") or "",
    }


def evidence_record(item: dict[str, Any]) -> dict[str, Any]:
    transcript_path = resolve_evidence_path(item["evidence"]["transcript_txt"])
    transcript = transcript_path.read_text(encoding="utf-8", errors="ignore").strip()
    metadata = source_metadata(item)
    frames_path = resolve_evidence_path(item["evidence"]["frames_json"])
    video_path = resolve_evidence_path(item["evidence"]["video_mp4"])
    return {
        "source_id": str(item["source_id"]),
        **metadata,
        "transcript_path": transcript_path.as_posix(),
        "transcript": transcript,
        "transcript_sha256": sha256_text(transcript),
        "transcript_chars": len(normalize(transcript)),
        "frames_path": frames_path.as_posix(),
        "frames_available": frames_path.is_file() and frames_path.stat().st_size > 0,
        "video_path": video_path.as_posix(),
        "video_available": video_path.is_file() and video_path.stat().st_size > 0,
    }


def batch_items(inventory: list[dict[str, Any]], batch_number: int, batch_size: int) -> list[dict[str, Any]]:
    start = (batch_number - 1) * batch_size
    return inventory[start : start + batch_size]


def audit_card(card: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if card.get("source_id") != evidence.get("source_id"):
        errors.append("source_id_mismatch")
    if evidence.get("account_id") != ACCOUNT_ID or evidence.get("account_name") != ACCOUNT_NAME:
        errors.append("account_ownership_mismatch")
    transcript_chars = int(evidence.get("transcript_chars", 0))
    visual_only = transcript_chars < 20
    if transcript_chars < 80:
        visual_review = card.get("visual_review") or {}
        if not visual_review.get("performed"):
            errors.append("short_transcript_without_visual_review")
        required_frames = 5 if visual_only else 3
        if int(visual_review.get("frames_inspected") or 0) < required_frames:
            errors.append("insufficient_visual_frames")
        if len(normalize(str(visual_review.get("finding") or ""))) < 12:
            errors.append("shallow_visual_finding")
        if visual_only and len(visual_review.get("visual_evidence") or []) < 3:
            errors.append("insufficient_visual_evidence")
    if not evidence.get("video_available"):
        errors.append("video_missing")
    if not evidence.get("frames_available"):
        errors.append("frames_missing")
    for field, choices in ENUMS.items():
        if card.get(field) not in choices:
            errors.append(f"invalid_enum:{field}")
    for field in REQUIRED_TEXT:
        if len(normalize(str(card.get(field, "")))) < 12:
            errors.append(f"shallow_field:{field}")
    quotes = card.get("evidence_quotes") or []
    if not visual_only:
        if len(quotes) < 2:
            errors.append("insufficient_evidence_quotes")
        transcript_norm = normalize(evidence.get("transcript", ""))
        for quote in quotes:
            if len(normalize(str(quote))) < 4 or normalize(str(quote)) not in transcript_norm:
                errors.append("unsupported_evidence_quote")
                break
    title_and_transcript = f"{evidence.get('title', '')} {evidence.get('desc', '')} {evidence.get('transcript', '')}"
    brand_hits = sorted({term for term in BRAND_HINTS if term in title_and_transcript})
    commercial = card.get("commercial_axis")
    if brand_hits and commercial == "正常内容":
        errors.append("brand_signal_marked_normal")
    if commercial in {"广告植入但剧情完整", "广告强绑定/广告主导"}:
        if card.get("learning_value_axis") != "广告隔离样本":
            errors.append("commercial_not_isolated")
    if commercial not in {"正常内容", "待判定"} and card.get("core_direction_eligible") is not False:
        errors.append("commercial_entered_core_direction")
    classification_reason = str(card.get("classification_reason") or "")
    if commercial not in {"正常内容", "待判定"} and re.search(r"保留核心方向|进入核心方向", classification_reason):
        errors.append("commercial_core_language_conflict")
    if commercial == "广告强绑定/广告主导" and card.get("core_direction_eligible") is not False:
        errors.append("ad_heavy_entered_core_direction")
    if commercial == "平台活动/挑战赛" and card.get("core_direction_eligible") is not False:
        errors.append("platform_event_entered_core_direction")
    if "待判定" in {card.get("relationship_axis"), card.get("scene_axis"), card.get("comedy_engine"), commercial}:
        errors.append("unresolved_classification")
    return sorted(set(errors))


def card_markdown(card: dict[str, Any], evidence: dict[str, Any]) -> str:
    evidence_quotes = [str(value) for value in card.get("evidence_quotes") or []]
    quotes = "\n".join(f"- {quote}" for quote in evidence_quotes)
    original_quote = "；".join(evidence_quotes[:2]) if evidence_quotes else "无；本条以视觉证据为主，不编造原话"
    visual = card.get("visual_review") or {}
    visual_section = "- 无需额外视觉复核；逐字稿信息量达到门禁要求。"
    if visual.get("performed"):
        visual_evidence = "\n".join(f"  - {item}" for item in visual.get("visual_evidence") or [])
        visual_section = (
            f"- 已执行短逐字稿视觉复核：抽查 {visual.get('frames_inspected')} 帧。\n"
            f"- 视觉结论：{visual.get('finding')}"
            + (f"\n- 视觉证据：\n{visual_evidence}" if visual_evidence else "")
        )
    primary_direction = str(card.get("primary_direction") or card.get("content_form") or "待复核")
    media_status = (
        f"逐字稿 {evidence['transcript_chars']} 字符；视频 {'可用' if evidence.get('video_available') else '缺失'}；"
        f"抽帧 {'可用' if evidence.get('frames_available') else '缺失'}"
    )
    performance_learning = str(
        card.get("performance_learning")
        or f"围绕“{card['comedy_engine']}”观察人物反应、节奏推进和转折落点；没有帧级证据的细节不写入。"
    )
    distilled_expression = str(card.get("distilled_expression") or card["turning_point"])
    reusable_sentence = str(card.get("reusable_sentence") or "先给一个看似合理的设定，再让冲突结果反向证明这个设定失效。")
    reusable_template = str(
        card.get("reusable_template")
        or "当【人物关系】试图用【看似合理的办法】解决【具体冲突】，先让办法短暂成立，再通过【升级动作】把结果推向【反转或笑点】。"
    )
    evidence_gap = str(
        card.get("evidence_gaps")
        or "本卡只能证明这一条内容中的结构与表达；是否属于稳定账号规律，仍需跨卡三重验证。"
    )
    candidate_decision = "支持进入跨卡候选池" if card.get("core_direction_eligible") else "仅保留为边界或商业隔离证据"
    content_form = str(card.get("content_form") or "")
    if any(token in content_form for token in ("剧情", "合拍", "唱演", "故事")):
        structure_block = "\n".join(
            (
                f"- 开头设定：{evidence['title']}；{card['copy_learning']}",
                f"- 核心冲突：{card['conflict']}",
                f"- 升级：{card['synopsis']}",
                f"- 转折或笑点：{card['turning_point']}",
                "- 收尾：让转折后的关系或结果成为最终落点，不额外拔高。",
            )
        )
    else:
        structure_block = "\n".join(
            (
                f"- 黄金3秒：{evidence['title']}；{card['copy_learning']}",
                f"- 观点提出：{card['conflict']}",
                f"- 证据或案例：{card['synopsis']}",
                f"- 推演：{card['classification_reason']}",
                f"- 收尾：{card['turning_point']}",
            )
        )
    return f"""# 视频深度学习卡：{card['source_id']}

学习卡契约：{CONTRACT_ID}
状态：candidate_learned
学习批次：{card['batch_id']}
账号：{ACCOUNT_NAME}
平台：抖音
source_id：{card['source_id']}
原内容链接：{evidence['source_url']}
主方向：{primary_direction}
标题：{evidence['title']}

## 1. 证据边界

- 主证据：完整逐字稿、原视频、抽帧索引。
- 辅助证据：发布标题、发布文案、话题标签。
- 证据状态：{media_status}。
- 逐字稿校验：`{evidence['transcript_sha256']}`，{evidence['transcript_chars']} 字符。
{visual_section}

## 2. 为什么值得学习

- 学习价值：{card['learning_value_axis']}。
- 结构价值：{card['classification_reason']}
- 表达价值：{card['copy_learning']}

## 3. 多维分类与商业隔离

- 内容形态：{card['content_form']}
- 人物关系：{card['relationship_axis']}
- 场景：{card['scene_axis']}
- 喜剧机制：{card['comedy_engine']}
- 商业属性：{card['commercial_axis']}
- 学习价值：{card['learning_value_axis']}
- 核心方向统计：{'纳入' if card['core_direction_eligible'] else '不纳入'}
- 分类依据：{card['classification_reason']}
- 隔离判断：{card['commercial_reason']}

## 4. 核心观点

- 内容层观点：{card['conflict']}
- 表达层观点：{card['turning_point']}
- 传播层判断：{card['copy_learning']}

## 5. 内容结构

{structure_block}

## 6. 发布内容层学习

- 标题：{evidence['title']}
- 正文或文案：{card['copy_learning']}
- 话题或标签：{card['topic_learning']}
- 协同判断：标题先承诺冲突或解决方案，正文和话题负责限定人物、场景与表达机制。

## 7. 视频/图文表现层学习

- 媒体类型：视频。
- 分析状态：{media_status}。
- 表现学习：{performance_learning}
{visual_section}

## 8. 金句与表达素材

- 原文金句：{original_quote}
- 提炼表达（非原话）：{distilled_expression}
- 可复用句式：{reusable_sentence}
- 逐字稿证据：
{quotes or '  - 无有效逐字稿；本卡依据视觉证据生成，不补造原话。'}

## 9. 可复用选题与案例

- 可复用选题：{card['reusable_topic']}
- 可复用案例：{card['synopsis']}
- 复用边界：只复用冲突和转折机制，不复制来源人物、故事事实和原句。

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。
> 可调用：false。单卡候选必须聚合并通过后续验证后才可能进入正式审核。

### R - 原始证据

{original_quote}

### I - 初步解释

{card['classification_reason']} 其可复用价值来自“{card['comedy_engine']}”，不是来自具体人物或台词本身。

### A1 - 本条案例

{card['synopsis']}

### A2 - 未来触发场景

- 触发机制：新任务需要复用“{card['comedy_engine']}”的冲突因果或结构机制时，调用本候选。
- 适用关系：来源人物关系只作为本条案例；目标关系能够承载同类冲突时可以迁移。
- 可迁移场景：来源场景只作为本条案例；更换场景后“{card['comedy_engine']}”仍成立时可以迁移。
- 不触发条件：只出现本条人物、场景、道具或“{card['reusable_topic']}”中的题材词，但没有“{card['comedy_engine']}”机制时不得调用。
- 来源选题示例：{card['reusable_topic']}

### E - 初步执行步骤

1. 先按账号、内容形态和主任务方向建立基础召回范围。
2. 再按“{card['comedy_engine']}”匹配结构机制，不因偶然题材词触发。
3. 将来源人物和场景替换为目标关系与目标场景，同时保留核心因果。
4. 用具体动作持续放大核心冲突，让“{card['turning_point']}”承担转折或笑点。
5. 检查标题、文案和视频表现是否共同服务同一个冲突。

### B - 边界与反例

- 商业边界：{card['commercial_reason']}
- 证据边界：单卡不能证明稳定规律；必须跨卡验证。

## 11. 可复用模板

```text
路由：先确定【主任务方向】和【内容形态】，再匹配【核心结构机制】。
触发检查：只命中来源人物、场景、道具或题材词时不调用。
{reusable_template}
替换【目标人物关系】【目标场景】【解决办法】【具体冲突】【升级动作】【反转或笑点】，保留证据和适用边界。
```

## 12. 证据缺口与候选判断

- 证据缺口：{evidence_gap}
- 卡片判断：{candidate_decision}。
- 跨卡状态：待验证；进入五视角候选池后再决定支持、反驳或边界证据。
"""


def summary_markdown(batch_id: str, cards: list[dict[str, Any]], audit: dict[str, Any]) -> str:
    axes = {
        field: Counter(str(card[field]) for card in cards)
        for field in ("content_form", "relationship_axis", "scene_axis", "comedy_engine", "commercial_axis")
    }
    lines = [
        f"# 李宗恒全量深学 {batch_id} 批次总结", "",
        f"- 批次条数：{len(cards)}", f"- 审核通过：{audit['passed_count']}",
        f"- 审核退回：{audit['failed_count']}", f"- 批次门禁：{audit['batch_gate']}", "",
        "## 分类分布", "",
    ]
    for field, counts in axes.items():
        lines.append(f"- {field}：" + "；".join(f"{name} {count}" for name, count in counts.items()))
    lines.extend(["", "## 批次结论", "", "- 本批仅进入结构化候选知识区；正式账号中心需全量完成后统一审核。"])
    return "\n".join(lines) + "\n"


def update_cumulative_status(root: Path, output_root: Path, total_items: int, batch_size: int) -> dict[str, Any]:
    batches_root = root / output_root
    passed_batches: list[str] = []
    completed_ids: list[str] = []
    all_cards: list[dict[str, Any]] = []
    for audit_path in sorted(batches_root.glob("batch_*/audit.json")):
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("batch_gate") != "pass":
            continue
        batch_id = str(audit["batch_id"])
        cards_path = audit_path.parent / "structured_cards.jsonl"
        batch_cards = read_jsonl(cards_path)
        passed_batches.append(batch_id)
        completed_ids.extend(str(card["source_id"]) for card in batch_cards)
        all_cards.extend(batch_cards)
    status = {
        "profile_id": PROFILE_ID,
        "account_id": ACCOUNT_ID,
        "account_name": ACCOUNT_NAME,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total_items": total_items,
        "batch_size": batch_size,
        "total_batches": (total_items + batch_size - 1) // batch_size,
        "passed_batches": passed_batches,
        "completed_items": len(set(completed_ids)),
        "remaining_items": total_items - len(set(completed_ids)),
        "completion_ratio": round(len(set(completed_ids)) / total_items, 4) if total_items else 0,
        # Completion is an evidence state, not authorization. Formal ingest stays
        # closed until the user explicitly confirms the reviewed deliverables.
        "formal_ingest_allowed": False,
    }
    aggregates = {
        "status": status,
        "classification_counts": {
            field: dict(Counter(str(card[field]) for card in all_cards))
            for field in ENUMS
        },
        "core_direction_eligible": dict(Counter(str(card["core_direction_eligible"]).lower() for card in all_cards)),
        "source_ids": completed_ids,
    }
    write_json(batches_root / "learning_status.json", status)
    write_json(batches_root / "cumulative_knowledge.json", aggregates)
    return status


def run_batch(root: Path, inventory_path: Path, annotations_path: Path, output_root: Path, batch_number: int, batch_size: int) -> dict[str, Any]:
    inventory = read_jsonl(root / inventory_path)
    selected = batch_items(inventory, batch_number, batch_size)
    annotations = read_jsonl(root / annotations_path)
    expected_ids = [str(item["source_id"]) for item in selected]
    by_id = {str(item["source_id"]): item for item in annotations}
    if len(by_id) != len(annotations):
        raise ValueError("duplicate annotation source_id")
    if set(by_id) != set(expected_ids):
        raise ValueError(f"annotation scope mismatch: expected={expected_ids}, actual={sorted(by_id)}")

    batch_id = f"batch_{batch_number:02d}"
    output_dir = root / output_root / batch_id
    previous_titles: dict[str, list[str]] = {}
    for cards_path in sorted((root / output_root).glob("batch_*/structured_cards.jsonl")):
        if cards_path.parent.name == batch_id:
            continue
        audit_path = cards_path.parent / "audit.json"
        if not audit_path.is_file() or json.loads(audit_path.read_text(encoding="utf-8")).get("batch_gate") != "pass":
            continue
        for previous in read_jsonl(cards_path):
            title_key = normalize(str(previous.get("source", {}).get("title") or ""))
            if title_key:
                previous_titles.setdefault(title_key, []).append(str(previous.get("source_id")))
    evidence_rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for item in selected:
        source_id = str(item["source_id"])
        evidence = evidence_record(item)
        annotation = {**by_id[source_id], "source_id": source_id, "batch_id": batch_id}
        errors = audit_card(annotation, evidence)
        rendered_card = card_markdown(annotation, evidence)
        errors.extend(f"card_contract:{error}" for error in validate_unified_text(rendered_card).errors)
        title_matches = previous_titles.get(normalize(evidence.get("title", "")), [])
        related_ids = {str(value) for value in annotation.get("related_source_ids") or []}
        if title_matches and not related_ids.intersection(title_matches):
            errors.append("duplicate_title_unlinked")
        if title_matches and len(normalize(str(annotation.get("version_relation") or ""))) < 4:
            errors.append("duplicate_version_relation_missing")
        evidence_rows.append({key: value for key, value in evidence.items() if key != "transcript"})
        cards.append({
            **annotation,
            "source": {
                "title": evidence["title"],
                "desc": evidence["desc"],
                "source_url": evidence["source_url"],
                "publish_time": evidence["publish_time"],
                "transcript_sha256": evidence["transcript_sha256"],
                "transcript_path": evidence["transcript_path"],
                "video_path": evidence["video_path"],
                "frames_path": evidence["frames_path"],
            },
        })
        audits.append({"source_id": source_id, "decision": "pass" if not errors else "reject", "errors": errors})
        if not errors:
            card_path = output_dir / "cards" / f"{source_id}.md"
            card_path.parent.mkdir(parents=True, exist_ok=True)
            card_path.write_text(rendered_card, encoding="utf-8")

    synopsis_hashes = Counter(normalize(card["synopsis"]) for card in cards)
    for audit in audits:
        card = by_id[audit["source_id"]]
        if synopsis_hashes[normalize(card["synopsis"])] > 1:
            audit["errors"].append("duplicated_synopsis")
            audit["decision"] = "reject"

    passed_count = sum(item["decision"] == "pass" for item in audits)
    audit_payload = {
        "batch_id": batch_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "expected_count": len(selected),
        "annotation_count": len(annotations),
        "evidence_count": len(evidence_rows),
        "passed_count": passed_count,
        "failed_count": len(audits) - passed_count,
        "batch_gate": "pass" if passed_count == len(selected) and len(selected) > 0 else "reject",
        "gate_rule": "全量逐条通过；任一条证据、分类、广告隔离或内容深度失败，整批不得晋级。",
        "cards": audits,
    }
    write_jsonl(output_dir / "evidence_manifest.jsonl", evidence_rows)
    write_jsonl(output_dir / "structured_cards.jsonl", cards)
    write_json(output_dir / "audit.json", audit_payload)
    (output_dir / "batch_summary.md").write_text(summary_markdown(batch_id, cards, audit_payload), encoding="utf-8")
    audit_payload["cumulative_status"] = update_cumulative_status(root, output_root, len(inventory), batch_size)
    return audit_payload


def prepare_batch(root: Path, inventory_path: Path, batch_number: int, batch_size: int) -> dict[str, Any]:
    inventory = read_jsonl(root / inventory_path)
    selected = batch_items(inventory, batch_number, batch_size)
    return {
        "batch_id": f"batch_{batch_number:02d}",
        "expected_count": len(selected),
        "account_id": ACCOUNT_ID,
        "account_name": ACCOUNT_NAME,
        "items": [evidence_record(item) for item in selected],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run auditable NAS deep-learning batches for 李宗恒.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--annotations")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only:
        result = prepare_batch(Path(args.root).resolve(), Path(args.inventory), args.batch, args.batch_size)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.annotations:
        parser.error("--annotations is required unless --prepare-only is used")
    result = run_batch(
        Path(args.root).resolve(), Path(args.inventory), Path(args.annotations), Path(args.output),
        args.batch, args.batch_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["batch_gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
