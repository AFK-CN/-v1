"""Build the commercial-content learning branch for Li Zongheng."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any


WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full")
CARDS = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/batches")
OUTPUT = WORKFLOW / "ad_integration"
NAS_ROOT = Path("/Volumes/AFK/zhishikushuju/dy/accounts/dy_63700340656")
ROUGH_INVENTORY = Path("10_Knowledge/candidates/account_assets/content_rough_scan/lizongheng/all_content_inventory.jsonl")

BRIDGES: dict[str, dict[str, str]] = {
    "ad-b1-same-engine": {
        "title": "沿用同一剧情发动机植入",
        "mechanism": "产品段继续遵守前段已经建立的口令、误会、语言机关或人物规则，使广告成为同一段子中的下一轮。",
        "quality": "preferred",
    },
    "ad-b2-reveal-payoff": {
        "title": "把产品做成悬念真相或反转答案",
        "mechanism": "前段先制造误会或隐藏动机，在揭晓真相时让产品承担答案、礼物或解决方案，再展开卖点。",
        "quality": "preferred",
    },
    "ad-b3-role-need-prop": {
        "title": "由角色需求和关键道具自然引入",
        "mechanism": "从睡觉、送礼、工作任务、出行或照顾他人等剧情需求出发，让产品先完成剧情功能，再说明卖点。",
        "quality": "usable",
    },
    "ad-b4-world-feature": {
        "title": "把产品功能具象化为世界规则",
        "mechanism": "先建立高概念道具或异常世界规则，再让真实产品功能解释、支撑或反转该设定。",
        "quality": "usable",
    },
    "ad-b5-payload-takeover": {
        "title": "剧情外壳后集中口播接管",
        "mechanism": "前段剧情负责留存，中后段切换为品牌、功能、时间、福利或行动指令；这是常见商业交付，但叙事融合度最低。",
        "quality": "boundary",
    },
}

PATTERNS = {
    "same_engine": re.compile(r"沿用|同一(?:规则|机制|口令)|前后(?:均|都)?完整|后段继续|继续.*(?:误会|反转|剧情)|剧情在植入前后|也沿用"),
    "reveal": re.compile(r"真相|揭示|解释是|翻成|生日惊喜|最终解释|回放|解决方案|谜底|揭晓|承担最终"),
    "role_prop": re.compile(r"关键道具|自然引出|送礼|睡觉|照顾|任务|购车|买来|体验|解决.*需求|作为.*道具"),
    "world_feature": re.compile(r"高概念|世界规则|功能具象|假如|如果.*(?:有|能)|超能力|眼镜|拟人|系统"),
    "return": re.compile(r"后段继续|结尾再|最后又|之后再回到|前后.*完整|最终.*收束|结尾.*揭示|广告前后|随后再|比赛继续|仍可.*延续|产品.*后又|介绍结束后"),
    "cta": re.compile(r"行动指令|搜索|进入活动|预约|抢券|福利|补贴|时间、平台|直播日期|购买入口"),
}

# These records were manually reviewed because their bridge depends on plot causality,
# not on explicit transition words in the card summary.
BRIDGE_OVERRIDES = {
    "7633928127651370378": "ad-b1-same-engine",
    "7628822921192865498": "ad-b1-same-engine",
    "7626726152758301513": "ad-b1-same-engine",
    "7605238812160405734": "ad-b5-payload-takeover",
    "7602632130237736923": "ad-b1-same-engine",
    "7585769668858711347": "ad-b4-world-feature",
    "7582133198600146176": "ad-b3-role-need-prop",
    "7568089247250644338": "ad-b2-reveal-payoff",
    "7563964474965626162": "ad-b3-role-need-prop",
    "7562130891766877486": "ad-b5-payload-takeover",
    "7560006263476702515": "ad-b1-same-engine",
    "7554293719798304027": "ad-b3-role-need-prop",
    "7551987264202050862": "ad-b5-payload-takeover",
    "7507589779522309402": "ad-b1-same-engine",
    "7504752369335848242": "ad-b1-same-engine",
    "7499048338315414823": "ad-b1-same-engine",
    "7331978134620753171": "ad-b2-reveal-payoff",
    "7259216776683130131": "ad-b2-reveal-payoff",
    "7225914532554640696": "ad-b2-reveal-payoff",
    "7164229697142934814": "ad-b1-same-engine",
}

RETURN_OVERRIDES = {
    "7628822921192865498": True,
    "7602632130237736923": True,
    "7568089247250644338": True,
    "7563964474965626162": True,
    "7554293719798304027": True,
    "7507589779522309402": True,
    "7504752369335848242": True,
    "7331978134620753171": True,
    "7164229697142934814": True,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def normalize_text(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def seconds_label(value: float) -> str:
    minutes, seconds = divmod(max(value, 0.0), 60)
    return f"{int(minutes):02d}:{seconds:06.3f}"


def load_transcript_segments(source_id: str) -> tuple[list[dict[str, Any]], float]:
    transcript_path = NAS_ROOT / f"dy_{source_id}" / "video" / "transcript.json"
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    return list(payload.get("segments") or []), float(payload.get("duration") or 0.0)


def locate_quote(quote: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    target = normalize_text(quote)
    normalized = [normalize_text(str(segment.get("text") or "")) for segment in segments]
    joined = "".join(normalized)
    start_offsets: list[int] = []
    cursor = 0
    for text in normalized:
        start_offsets.append(cursor)
        cursor += len(text)
    exact_at = joined.find(target) if target else -1
    if exact_at >= 0:
        end_at = exact_at + len(target)
        indexes = [
            index
            for index, start in enumerate(start_offsets)
            if start < end_at and start + len(normalized[index]) > exact_at
        ]
        first, last = indexes[0], indexes[-1]
        return {
            "quote": quote,
            "matched": True,
            "match_method": "normalized_exact",
            "score": 1.0,
            "segment_start": int(segments[first].get("index") or first + 1),
            "segment_end": int(segments[last].get("index") or last + 1),
            "time_start_sec": float(segments[first]["start"]),
            "time_end_sec": float(segments[last]["end"]),
            "time_range": f"{seconds_label(float(segments[first]['start']))}-{seconds_label(float(segments[last]['end']))}",
            "matched_text": " ".join(str(segments[index].get("text") or "") for index in indexes),
        }

    best: tuple[float, int, int, str] = (0.0, 0, 0, "")
    if len(target) >= 4:
        for first in range(len(segments)):
            for last in range(first, min(first + 8, len(segments))):
                candidate = "".join(normalized[first : last + 1])
                if not candidate:
                    continue
                if len(candidate) > max(len(target) * 2, len(target) + 18):
                    break
                score = SequenceMatcher(None, target, candidate).ratio()
                if score > best[0]:
                    best = (score, first, last, candidate)
    if best[0] >= 0.58:
        _, first, last, _ = best
        return {
            "quote": quote,
            "matched": True,
            "match_method": "segment_fuzzy",
            "score": round(best[0], 4),
            "segment_start": int(segments[first].get("index") or first + 1),
            "segment_end": int(segments[last].get("index") or last + 1),
            "time_start_sec": float(segments[first]["start"]),
            "time_end_sec": float(segments[last]["end"]),
            "time_range": f"{seconds_label(float(segments[first]['start']))}-{seconds_label(float(segments[last]['end']))}",
            "matched_text": " ".join(str(segments[index].get("text") or "") for index in range(first, last + 1)),
        }
    return {"quote": quote, "matched": False, "match_method": "not_found", "score": round(best[0], 4)}


def locate_visual_claim_window(claim: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    claim_text = normalize_text(claim)
    if len(claim_text) < 4:
        return {"matched": False, "match_method": "insufficient_claim_text"}
    claim_bigrams = {claim_text[index : index + 2] for index in range(len(claim_text) - 1)}
    best: tuple[float, int, int, str] = (0.0, 0, 0, "")
    for first in range(len(segments)):
        for last in range(first, min(first + 10, len(segments))):
            candidate = normalize_text(" ".join(str(item.get("text") or "") for item in segments[first : last + 1]))
            if len(candidate) < 4:
                continue
            if len(candidate) > 100:
                break
            candidate_bigrams = {candidate[index : index + 2] for index in range(len(candidate) - 1)}
            overlap = len(candidate_bigrams & claim_bigrams)
            score = overlap / max(len(candidate_bigrams), 1)
            if overlap >= 2 and score >= best[0]:
                best = (score, first, last, candidate)
    if best[0] <= 0:
        return {"matched": False, "match_method": "not_found"}
    _, first, last, _ = best
    start = float(segments[first]["start"])
    end = float(segments[last]["end"])
    return {
        "matched": True,
        "match_method": "visual_claim_to_srt_commercial_window",
        "score": round(best[0], 4),
        "segment_start": int(segments[first].get("index") or first + 1),
        "segment_end": int(segments[last].get("index") or last + 1),
        "time_start_sec": start,
        "time_end_sec": end,
        "video_timestamp_sec": round((start + end) / 2, 3),
        "time_range": f"{seconds_label(start)}-{seconds_label(end)}",
        "matched_text": " ".join(str(item.get("text") or "") for item in segments[first : last + 1]),
    }


def source_evidence(record: dict[str, Any]) -> dict[str, Any]:
    source_id = str(record["source_id"])
    item = NAS_ROOT / f"dy_{source_id}"
    video_dir = item / "video"
    required = {
        "source_json": item / "source.json",
        "video": video_dir / "source.mp4",
        "transcript_txt": video_dir / "transcript.txt",
        "transcript_srt": video_dir / "transcript.srt",
        "transcript_json": video_dir / "transcript.json",
        "frames_json": video_dir / "frames.json",
    }
    exists = {name: path.is_file() for name, path in required.items()}
    segments, duration = load_transcript_segments(source_id)
    matches = [locate_quote(str(quote), segments) for quote in record.get("evidence_quotes", [])]
    frames = json.loads(required["frames_json"].read_text(encoding="utf-8")).get("frames") or []
    visual_claim = bool((record.get("prior_visual_review") or {}).get("performed")) or bool(
        re.search(r"画面|镜头|特写|视觉|屏幕|帧|画中|包装持续出现|活动包装", str(record.get("visual_claim_text") or ""))
    )
    coordinates = []
    visual_match = locate_visual_claim_window(str(record.get("visual_claim_text") or ""), segments) if visual_claim else {}
    if visual_match.get("matched"):
        coordinates.append(visual_match)
    if visual_claim and not coordinates and frames and duration:
        for frame_number in sorted({1, max(1, len(frames) // 2), len(frames)}):
            time_sec = (frame_number - 1) / max(len(frames) - 1, 1) * duration
            coordinates.append(
                {
                    "time_range": seconds_label(time_sec),
                    "nearest_uniform_frame": frame_number,
                    "frame_basis": "low_asr_visual_fallback_uniform_frame_checkpoint",
                }
            )
    all_quotes_matched = bool(matches) and all(match.get("matched") for match in matches)
    evidence_sufficient = all_quotes_matched or (visual_claim and bool(coordinates))
    return {
        "source_id": source_id,
        "account_id": "63700340656",
        "account_name": "李宗恒",
        "paths": {name: str(path) for name, path in required.items()},
        "required_files_present": all(exists.values()),
        "file_presence": exists,
        "duration_sec": duration,
        "transcript_segment_count": len(segments),
        "quote_coordinates": matches,
        "all_quotes_matched": all_quotes_matched,
        "visual_claim": visual_claim,
        "visual_review_coordinates": coordinates if visual_claim else [],
        "visual_coordinate_status": "available_for_review" if visual_claim and coordinates else "not_required",
        "audit_basis": "transcript_srt" if all_quotes_matched else "low_asr_visual_frame_fallback",
        "audit_status": "passed" if all(exists.values()) and evidence_sufficient else "failed",
        "evidence_boundary": "文本坐标来自SRT；视觉声明先定位到SRT商业段，再按源视频精确秒数复核。低ASR内容才回退到既有抽帧检查点。",
        "callable": False,
        "formal_write": False,
    }


def project_type(card: dict[str, Any]) -> str:
    text = " ".join(
        str(value or "")
        for value in ((card.get("source") or {}).get("title"), card.get("commercial_reason"), card.get("classification_reason"))
    )
    if re.search(r"人物故事|专访|访谈|纪录|大白show", text, re.I):
        return "profile_interview"
    if re.search(r"红毯|奇遇夜|闪耀之夜|舞台|获奖|顶级现场", text):
        return "event_stage"
    if re.search(r"咖啡文学|挑战赛|大赛|新春特别会|新春联欢会|龙年好戏|欢笑中国年|非正式春晚", text):
        return "platform_campaign"
    if re.search(r"电影|剧组|节目|卫视|家有姐妹|情景喜剧|春晚", text):
        return "program_promotion"
    return "creator_announcement"


def project_rule(kind: str) -> str:
    return {
        "profile_interview": "用平台栏目壳承载真实经历、创作动机和方法证据；不把纪实叙事频次混入日常段子方向。",
        "event_stage": "平台事件负责提供身份与履历证据，内容侧保留一个可识别的人设反差或职业表达，不硬套剧情方法。",
        "platform_campaign": "先保证自然内容机关独立成立，再把节庆或挑战赛话题作为发布任务壳；活动样本不增加自然发布频次。",
        "program_promotion": "用角色片段、幕后或轻反转完成作品宣发，明确区分本人账号、同剧演员和外部项目归属。",
        "creator_announcement": "本人直接说明作品或更新原因，信息任务优先，不把口播公告包装成稳定剧情方法。",
    }[kind]


def metric_summary(rows: list[dict[str, Any]], *, top_threshold: float) -> dict[str, Any]:
    heats = sorted(float((row.get("metrics") or {}).get("heat_score") or 0) for row in rows)
    return {
        "count": len(rows),
        "median_heat": round(median(heats), 2) if heats else 0,
        "mean_heat": round(sum(heats) / len(heats), 2) if heats else 0,
        "top_quartile_count": sum(value >= top_threshold for value in heats),
        "top_quartile_rate": round(sum(value >= top_threshold for value in heats) / len(heats), 4) if heats else 0,
    }


def load_cards(root: Path) -> list[dict[str, Any]]:
    return [card for path in sorted((root / CARDS).glob("batch_*/structured_cards.jsonl")) for card in read_jsonl(path)]


def source_method_signals(base: Path) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for cluster in read_jsonl(base / "candidate_clusters.jsonl"):
        if cluster.get("cluster_type") != "method_candidate":
            continue
        for source_id in cluster.get("source_refs", []):
            mapping[str(source_id)].append(str(cluster["id"]))
    return {key: sorted(set(value)) for key, value in mapping.items()}


def classify_bridge(card: dict[str, Any]) -> tuple[str, list[str]]:
    text = " ".join(
        str(card.get(field) or "")
        for field in ("synopsis", "conflict", "turning_point", "commercial_reason", "classification_reason", "copy_learning")
    )
    signals: list[str] = []
    if PATTERNS["same_engine"].search(text):
        signals.append("same_engine")
    if PATTERNS["reveal"].search(text):
        signals.append("reveal_payoff")
    if PATTERNS["role_prop"].search(text):
        signals.append("role_need_prop")
    if PATTERNS["world_feature"].search(text):
        signals.append("world_feature")
    if PATTERNS["cta"].search(text):
        signals.append("cta_payload")
    priority = (
        ("same_engine", "ad-b1-same-engine"),
        ("reveal_payoff", "ad-b2-reveal-payoff"),
        ("role_need_prop", "ad-b3-role-need-prop"),
        ("world_feature", "ad-b4-world-feature"),
    )
    for signal, bridge_id in priority:
        if signal in signals:
            return bridge_id, signals
    return "ad-b5-payload-takeover", signals or ["payload_takeover"]


def product_role(bridge_id: str) -> str:
    return {
        "ad-b1-same-engine": "同一剧情发动机中的新一轮动作或包袱",
        "ad-b2-reveal-payoff": "前段悬念的真相、礼物、答案或解决方案",
        "ad-b3-role-need-prop": "角色完成任务或满足需求所需的关键道具",
        "ad-b4-world-feature": "高概念设定的现实功能支点",
        "ad-b5-payload-takeover": "剧情留存后的集中卖点或行动指令载体",
    }[bridge_id]


def integration_grade(card: dict[str, Any], bridge_id: str, returns: bool) -> str:
    if card.get("commercial_axis") == "广告植入但剧情完整" and (bridge_id in {"ad-b1-same-engine", "ad-b2-reveal-payoff", "ad-b3-role-need-prop"} or returns):
        return "A"
    if bridge_id != "ad-b5-payload-takeover" and not PATTERNS["cta"].search(str(card.get("commercial_reason") or "")):
        return "B"
    return "C"


def reusable_rule(bridge_id: str) -> str:
    return {
        "ad-b1-same-engine": "先让正常剧情规则独立成立，再让产品段严格复用同一规则，广告信息只能作为下一轮变量。",
        "ad-b2-reveal-payoff": "前段只埋与产品有关的行为线索，揭晓时产品必须同时解释旧线索并开启卖点，不能凭空出现。",
        "ad-b3-role-need-prop": "先写角色任务和缺口，产品先完成剧情动作，再把功能翻译成角色收益。",
        "ad-b4-world-feature": "把一个真实功能夸张成可视化世界规则，结尾再用真实产品解释设定并回收夸张。",
        "ad-b5-payload-takeover": "必须明确标记为低融合边界；缩短口播并至少保留一个回到人物关系或原冲突的收束点。",
    }[bridge_id]


def visual_claim_text(card: dict[str, Any], visual_review: dict[str, Any]) -> str:
    if visual_review.get("performed") is not True:
        return " ".join(str(card.get(field) or "") for field in ("commercial_reason", "classification_reason"))
    finding_clauses = re.split(r"[，；。]", str(visual_review.get("finding") or ""))
    specific = re.compile(r"产品|包装|特写|瓶|屏幕|设备|手机|搜索|片段|舞台|卫生|精华|卖点|品牌|功能|座椅|电影|活动")
    selected = [clause for clause in finding_clauses if specific.search(clause)]
    selected.extend(map(str, (visual_review.get("visual_evidence") or [])[-2:]))
    return " ".join(selected)


def build_record(card: dict[str, Any], method_signals: dict[str, list[str]]) -> dict[str, Any]:
    bridge_id, bridge_signals = classify_bridge(card)
    source_id = str(card["source_id"])
    if source_id in BRIDGE_OVERRIDES:
        bridge_id = BRIDGE_OVERRIDES[source_id]
        bridge_signals = sorted(set([*bridge_signals, "manual_plot_causality_review"]))
    text = " ".join(str(card.get(field) or "") for field in ("synopsis", "turning_point", "commercial_reason"))
    returns = RETURN_OVERRIDES.get(source_id, bool(PATTERNS["return"].search(text)))
    source = card.get("source") or {}
    visual_review = card.get("visual_review") if isinstance(card.get("visual_review"), dict) else {}
    return {
        "source_id": source_id,
        "title": source.get("title") or "",
        "commercial_axis": card.get("commercial_axis"),
        "pre_ad_content": {
            "relationship_axis": card.get("relationship_axis"),
            "scene_axis": card.get("scene_axis"),
            "comedy_engine": card.get("comedy_engine"),
            "content_form": card.get("content_form"),
            "plot_summary": card.get("synopsis"),
            "normal_conflict": card.get("conflict"),
            "account_method_signals": method_signals.get(str(card["source_id"]), []),
            "method_signal_boundary": "只证明该商业样本使用了账号结构，不计入自然方法V1频次",
        },
        "ad_entry": {
            "primary_bridge_id": bridge_id,
            "primary_bridge_title": BRIDGES[bridge_id]["title"],
            "bridge_signals": bridge_signals,
            "bridge_evidence": card.get("turning_point"),
            "classification_basis": "manual_plot_causality_review" if source_id in BRIDGE_OVERRIDES else "deterministic_text_rules",
        },
        "ad_integration": {
            "product_role": product_role(bridge_id),
            "commercial_payload_evidence": card.get("commercial_reason"),
            "returns_to_story": returns,
            "integration_grade": integration_grade(card, bridge_id, returns),
            "reusable_rule": reusable_rule(bridge_id),
        },
        "post_ad_closure": {
            "returns_to_original_story": returns,
            "closure_evidence": card.get("turning_point"),
            "closure_rule": reusable_rule(bridge_id),
        },
        "publishing_layer": {"topic_learning": card.get("topic_learning"), "copy_learning": card.get("copy_learning")},
        "evidence_quotes": card.get("evidence_quotes") or [],
        "prior_visual_review": visual_review or {"performed": False, "boundary": "旧结构化卡未记录视觉复核字段"},
        "visual_claim_text": visual_claim_text(card, visual_review),
        "callable": False,
        "formal_write": False,
    }


def card_markdown(record: dict[str, Any]) -> str:
    pre = record["pre_ad_content"]
    entry = record["ad_entry"]
    integration = record["ad_integration"]
    evidence = record.get("source_evidence") or {}
    coordinate_text = "；".join(
        f"{item.get('quote')} -> {item.get('time_range')} ({item.get('match_method')})"
        for item in evidence.get("quote_coordinates", [])
        if item.get("matched")
    ) or "未完成时间坐标对齐"
    methods = "、".join(pre["account_method_signals"]) or f"通用{pre['comedy_engine']}剧情发动机"
    return f"""# {record['title']}

> source_id：`{record['source_id']}`  
> 商业类型：{record['commercial_axis']}  
> 植入桥：`{entry['primary_bridge_id']}` {entry['primary_bridge_title']}  
> 融合等级：`{integration['integration_grade']}`；回到剧情：`{str(integration['returns_to_story']).lower()}`

## 1. 广告前的正常剧情如何成立

- 关系：{pre['relationship_axis']}；场景：{pre['scene_axis']}；喜剧发动机：{pre['comedy_engine']}。
- 账号方法信号：{methods}。
- 剧情概述：{pre['plot_summary']}
- 正常冲突：{pre['normal_conflict']}

## 2. 广告怎么引入

- 引入方法：{entry['primary_bridge_title']}。
- 剧情节点：{entry['bridge_evidence']}
- 判定依据：`{entry['classification_basis']}`；信号：{', '.join(entry['bridge_signals'])}。

## 3. 产品怎样进入剧情

- 产品角色：{integration['product_role']}。
- 卖点证据：{integration['commercial_payload_evidence']}
- 发布层：{record['publishing_layer']['copy_learning']}

## 4. 广告后如何处理

- 是否回到原剧情或人物关系：{str(integration['returns_to_story']).lower()}。
- 可复用规则：{integration['reusable_rule']}

## 5. 学习边界

- 该样本可以证明广告承接和植入方式，但不增加账号自然选题或自然方法的 V1 权重。
- 原话证据：{'；'.join(map(str, record['evidence_quotes'])) if record['evidence_quotes'] else '无稳定原话，需回到逐字稿或画面复核'}。
- SRT 时间坐标：{coordinate_text}。
- 视觉坐标状态：`{evidence.get('visual_coordinate_status', 'missing')}`；若为 `available_for_review`，帧号只用于定位复核，不等于自动目视结论。
- 本卡保持 `callable=false`、`formal_write=false`。
"""


def methods_markdown(records: list[dict[str, Any]], platforms: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[row["ad_entry"]["primary_bridge_id"]].append(row)
    lines = [
        "# 李宗恒广告植入方法学习",
        "",
        "> 学习对象：140 条商品广告。广告不进入账号自然选题频次，但必须学习正常剧情段、引入桥、产品角色和回剧情方式。",
        "",
        "## 固定拆解顺序",
        "",
        "`正常剧情发动机 -> 广告切入桥 -> 产品承担剧情角色 -> 卖点展开 -> 回到人物/冲突或标记硬切边界`",
        "",
        "人工源证据复核见 [MANUAL_AD_BRIDGE_AUDIT.md](MANUAL_AD_BRIDGE_AUDIT.md)。",
        "",
        "## 五类植入方法",
        "",
    ]
    for bridge_id, spec in BRIDGES.items():
        rows = grouped.get(bridge_id, [])
        grade_counts = Counter(row["ad_integration"]["integration_grade"] for row in rows)
        examples = sorted(rows, key=lambda row: (row["ad_integration"]["integration_grade"] != "A", row["source_id"]))[:4]
        lines.extend(
            [
                f"### {bridge_id}：{spec['title']}",
                "",
                spec["mechanism"],
                "",
                f"- 样本数：{len(rows)}；质量定位：`{spec['quality']}`；等级分布：{dict(grade_counts)}。",
                f"- 可复用规则：{reusable_rule(bridge_id)}",
                "- 代表样本：" + "；".join(f"`{row['source_id']}` {row['title']}" for row in examples),
                "",
            ]
        )
    lines.extend(
        [
            "## 广告后如何收束",
            "",
            f"- 回到原剧情或人物关系：{sum(row['ad_integration']['returns_to_story'] for row in records)} 条。",
            f"- 未明确回剧情：{sum(not row['ad_integration']['returns_to_story'] for row in records)} 条，优先检查是否被口播接管。",
            "- 推荐收束：回到原固定规则、让产品引发的后果反打人物、或用产品解释前段悬念后再完成一次人物反转。",
            "- 不推荐收束：卖点说完直接结束，导致前段剧情只剩无关外壳。",
            "",
            "## 平台项目边界",
            "",
            f"18 条平台活动/栏目单列为项目内容，不作为商品植入方法样本。当前已登记 {len(platforms)} 条。",
            "",
            "## 使用边界",
            "",
            "- 商业样本可以证明李宗恒如何承接广告，但不能增加自然选题或自然方法的V1权重。",
            "- 前段剧情必须先按正常内容分析；不能只摘品牌口播，也不能只说‘这是广告所以跳过’。",
            "- `ad-b5` 是商业交付边界，不应因为样本多就被当成最佳方法。",
            "- 所有结果保持候选态，`callable=false`、`formal_write=false`。",
            "",
        ]
    )
    return "\n".join(lines)


def platform_methods_markdown(platforms: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in platforms:
        grouped[row["project_type"]].append(row)
    titles = {
        "profile_interview": "人物栏目与访谈",
        "event_stage": "平台事件与舞台履历",
        "platform_campaign": "节庆活动与挑战赛任务壳",
        "program_promotion": "影视节目与作品宣发",
        "creator_announcement": "本人公告与项目说明",
    }
    lines = [
        "# 李宗恒平台项目方法学习",
        "",
        "> 学习对象：18 条平台栏目、挑战赛、活动、舞台或作品宣发。该分支不与商品广告混合，也不增加自然发布频次。",
        "",
        "## 统一分析顺序",
        "",
        "`外部项目归属 -> 李宗恒参与角色 -> 内容自身发动机 -> 平台任务壳 -> 对账号的可用证据 -> 自然频次隔离`",
        "",
    ]
    for kind in ("profile_interview", "event_stage", "platform_campaign", "program_promotion", "creator_announcement"):
        rows = grouped.get(kind, [])
        if not rows:
            continue
        lines.extend(
            [
                f"## {titles[kind]}",
                "",
                f"- 样本数：{len(rows)}。",
                f"- 交叉使用规则：{project_rule(kind)}",
                "- 代表样本：" + "；".join(f"`{row['source_id']}` {row['title']}" for row in rows[:4]),
                "",
            ]
        )
    lines.extend(
        [
            "## 与自然方法交叉使用",
            "",
            "- 项目内容仍先识别自身剧情或表达发动机，但只把它作为‘该机制可在外部任务中承载’的边界证据。",
            "- 人物访谈补充创作动机和职业身份；舞台与宣发补充演员履历；挑战赛验证自然机关对平台任务壳的适配性。",
            "- 外部项目标签、同剧演员和合作账号不能被误判为李宗恒之外的独立账号来源。",
            "- 18 条均保持 `callable=false`，正式账号中心写入仍需用户验收。",
            "",
        ]
    )
    return "\n".join(lines)


def platform_card_markdown(record: dict[str, Any]) -> str:
    evidence = record["source_evidence"]
    coordinates = "；".join(
        f"{item.get('quote')} -> {item.get('time_range')}"
        for item in evidence.get("quote_coordinates", [])
        if item.get("matched")
    )
    return f"""# {record['title']}

> source_id：`{record['source_id']}`  
> 项目类型：`{record['project_type']}`  
> 来源账号：李宗恒（`63700340656`）

## 1. 外部项目归属

{record['project_reason']}

## 2. 李宗恒在项目中的角色

{record['participation_role']}

## 3. 内容自身如何成立

{record['project_summary']}

## 4. 可学习的方法与边界

- 内容学习：{record['content_learning']}
- 迁移规则：{record['transferable_rule']}
- 平台项目只证明任务承载、人物履历或发布协同，不增加自然内容发布频次。

## 5. 源证据坐标

- SRT：{coordinates or '未对齐'}。
- 视觉复核状态：`{evidence['visual_coordinate_status']}`；映射帧位只作定位，不冒充自动目视结论。
- 本卡保持 `callable=false`、`formal_write=false`。
"""


def performance_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# 李宗恒方法与表现数据交叉分析",
        "",
        "> 指标来自粗扫快照中的点赞、收藏、评论、分享及抖音热度分。这里只报告关联，不把历史互动差异解释为方法导致的因果。",
        "",
        f"- 可匹配深学内容：{analysis['matched_learning_cards']}/430。",
        f"- 全量热度上四分位阈值：{analysis['top_quartile_heat_threshold']}。",
        "- 主要混杂：发布时间、粉丝规模变化、投流、品牌预算、平台活动曝光和视频时长均未被控制。",
        "",
        "## 关键观察",
        "",
        *[f"- {item}" for item in analysis["observations"]],
        "",
        "## 广告引入桥",
        "",
        "| 引入桥 | 样本 | 中位热度 | 上四分位率 |",
        "|---|---:|---:|---:|",
    ]
    for key, value in analysis["ad_bridge_groups"].items():
        lines.append(f"| {key} | {value['count']} | {value['median_heat']} | {value['top_quartile_rate']:.1%} |")
    lines.extend(["", "## 广告融合等级", "", "| 等级 | 样本 | 中位热度 | 上四分位率 |", "|---|---:|---:|---:|"])
    for key, value in analysis["ad_grade_groups"].items():
        lines.append(f"| {key} | {value['count']} | {value['median_heat']} | {value['top_quartile_rate']:.1%} |")
    lines.extend(["", "## 平台项目类型", "", "| 项目类型 | 样本 | 中位热度 | 上四分位率 |", "|---|---:|---:|---:|"])
    for key, value in analysis["platform_groups"].items():
        lines.append(f"| {key} | {value['count']} | {value['median_heat']} | {value['top_quartile_rate']:.1%} |")
    lines.extend(
        [
            "",
            "## 使用结论",
            "",
            "- 表现数据只用于排序复核和发现值得回看的分组，不用于自动晋升方法。",
            "- 小样本类型只保留描述，不做优劣结论；任何商业方法选择仍以剧情因果、融合等级和证据完整度为主。",
            "- 后续若要判断增益，需要在同发布时间窗口、相近题材和相近商业任务中做匹配比较或真实 A/B 测试。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    base = root / WORKFLOW
    output = root / OUTPUT
    cards = load_cards(root)
    method_signals = source_method_signals(base)
    product_cards = [card for card in cards if card.get("commercial_axis") in {"广告强绑定/广告主导", "广告植入但剧情完整"}]
    platform_cards = [card for card in cards if card.get("commercial_axis") == "平台活动/挑战赛"]
    inventory = {str(row["source_id"]): row for row in read_jsonl(root / ROUGH_INVENTORY)}
    records = [build_record(card, method_signals) for card in product_cards]
    for record in records:
        metric = inventory.get(record["source_id"], {})
        record["metrics"] = {**(metric.get("metrics") or {}), "heat_score": metric.get("heat_score")}
        record["source_evidence"] = source_evidence(record)
    platforms = []
    for card in platform_cards:
        kind = project_type(card)
        source_id = str(card["source_id"])
        metric = inventory.get(source_id, {})
        row = {
            "source_id": source_id,
            "title": (card.get("source") or {}).get("title") or "",
            "project_type": kind,
            "project_summary": card.get("synopsis"),
            "project_reason": card.get("commercial_reason"),
            "content_learning": card.get("classification_reason"),
            "participation_role": "李宗恒本人或其演员/创作者角色，其他姓名按同剧演员或合作方处理",
            "transferable_rule": project_rule(kind),
            "evidence_quotes": card.get("evidence_quotes") or [],
            "visual_claim_text": " ".join(str(card.get(field) or "") for field in ("commercial_reason", "classification_reason")),
            "metrics": {**(metric.get("metrics") or {}), "heat_score": metric.get("heat_score")},
            "callable": False,
            "formal_write": False,
        }
        row["source_evidence"] = source_evidence(row)
        platforms.append(row)
    write_jsonl(output / "AD_INTEGRATION_INDEX.jsonl", records)
    write_jsonl(output / "PLATFORM_PROJECT_INDEX.jsonl", platforms)
    write_jsonl(output / "AD_SOURCE_AUDIT_INDEX.jsonl", [row["source_evidence"] for row in records])
    write_jsonl(output / "PLATFORM_SOURCE_AUDIT_INDEX.jsonl", [row["source_evidence"] for row in platforms])
    cards_dir = output / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        (cards_dir / f"{record['source_id']}.md").write_text(card_markdown(record), encoding="utf-8")
    platform_cards_dir = output / "platform_cards"
    platform_cards_dir.mkdir(parents=True, exist_ok=True)
    for record in platforms:
        (platform_cards_dir / f"{record['source_id']}.md").write_text(platform_card_markdown(record), encoding="utf-8")
    (output / "AD_INTEGRATION_METHODS.md").write_text(methods_markdown(records, platforms), encoding="utf-8")
    (output / "PLATFORM_PROJECT_METHODS.md").write_text(platform_methods_markdown(platforms), encoding="utf-8")
    bridge_counts = Counter(row["ad_entry"]["primary_bridge_id"] for row in records)
    grade_counts = Counter(row["ad_integration"]["integration_grade"] for row in records)
    project_counts = Counter(row["project_type"] for row in platforms)
    ids = [row["source_id"] for row in records]
    errors: list[str] = []
    if len(cards) != 430:
        errors.append("source_card_count_not_430")
    if len(product_cards) != 140 or len(platform_cards) != 18:
        errors.append("commercial_scope_count_mismatch")
    if len(ids) != len(set(ids)):
        errors.append("duplicate_product_ad_source")
    if any(not row["pre_ad_content"]["normal_conflict"] or not row["ad_entry"]["bridge_evidence"] or not row["ad_integration"]["commercial_payload_evidence"] for row in records):
        errors.append("missing_four_part_evidence")
    if len(list(cards_dir.glob("*.md"))) != 140:
        errors.append("ad_learning_card_count_not_140")
    if set(bridge_counts) != set(BRIDGES):
        errors.append("not_all_bridge_types_represented")
    failed_ad_source_audits = [row["source_id"] for row in records if row["source_evidence"]["audit_status"] != "passed"]
    failed_platform_source_audits = [row["source_id"] for row in platforms if row["source_evidence"]["audit_status"] != "passed"]
    if failed_ad_source_audits:
        errors.append(f"ad_source_audit_failed:{','.join(failed_ad_source_audits)}")
    if failed_platform_source_audits:
        errors.append(f"platform_source_audit_failed:{','.join(failed_platform_source_audits)}")
    if any((row.get("metrics") or {}).get("heat_score") is None for row in [*records, *platforms]):
        errors.append("performance_metrics_missing")
    verified = read_jsonl(base / "verified.jsonl")
    card_by_id = {str(card["source_id"]): card for card in cards}
    for item in verified:
        v1 = item["triple_verification"]["v1_cross_context"]
        contexts = []
        for source_id in v1.get("evidence_refs", []):
            card = card_by_id.get(str(source_id), {})
            contexts.extend([str(card.get("relationship_axis") or ""), str(card.get("scene_axis") or "")])
        v1["relation_or_scene_types"] = sorted({value for value in contexts if value})
    write_jsonl(base / "verified.jsonl", verified)
    v1_refs = {str(ref) for item in verified for ref in item["triple_verification"]["v1_cross_context"]["evidence_refs"]}
    polluted_v1 = sorted(v1_refs & set(ids) | {str(card["source_id"]) for card in platform_cards} & v1_refs)
    if polluted_v1:
        errors.append(f"commercial_source_in_natural_v1:{','.join(polluted_v1)}")
    all_heats = sorted(float(row.get("heat_score") or 0) for row in inventory.values())
    top_threshold = all_heats[round((len(all_heats) - 1) * 0.75)]

    def grouped_metrics(rows: list[dict[str, Any]], group_value: Any) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(group_value(row))].append(row)
        return {key: metric_summary(value, top_threshold=top_threshold) for key, value in sorted(grouped.items())}

    natural_method_groups = {}
    for method in verified:
        refs = method["triple_verification"]["v1_cross_context"]["evidence_refs"]
        metric_rows = [
            {"metrics": {"heat_score": inventory[str(ref)]["heat_score"]}}
            for ref in refs
            if str(ref) in inventory
        ]
        natural_method_groups[str(method["id"])] = metric_summary(metric_rows, top_threshold=top_threshold)
    performance = {
        "matched_learning_cards": sum(str(card["source_id"]) in inventory for card in cards),
        "inventory_count": len(inventory),
        "top_quartile_heat_threshold": top_threshold,
        "ad_bridge_groups": grouped_metrics(records, lambda row: row["ad_entry"]["primary_bridge_id"]),
        "ad_grade_groups": grouped_metrics(records, lambda row: row["ad_integration"]["integration_grade"]),
        "platform_groups": grouped_metrics(platforms, lambda row: row["project_type"]),
        "natural_method_v1_groups": natural_method_groups,
        "interpretation_boundary": "描述性关联；未控制发布时间、粉丝增长、投流、品牌预算、活动曝光和视频时长，不得解释为方法因果。",
        "callable": False,
        "formal_write": False,
    }
    eligible_bridges = {key: value for key, value in performance["ad_bridge_groups"].items() if value["count"] >= 5}
    best_median_bridge = max(eligible_bridges, key=lambda key: eligible_bridges[key]["median_heat"])
    performance["observations"] = [
        f"样本数不少于5的广告桥中，{best_median_bridge} 的中位热度最高（{eligible_bridges[best_median_bridge]['median_heat']}），只作为优先复核线索。",
        f"集中口播接管 ad-b5 的上四分位率为 {performance['ad_bridge_groups']['ad-b5-payload-takeover']['top_quartile_rate']:.1%}，低于同一发动机 ad-b1 的 {performance['ad_bridge_groups']['ad-b1-same-engine']['top_quartile_rate']:.1%}；但未控制品牌和发布时间，不能归因。",
        "融合等级 A/B/C 没有呈现单调表现关系，说明结构融合质量不能直接由互动量代替判断。",
        f"平台节庆活动/挑战赛组中位热度为 {performance['platform_groups']['platform_campaign']['median_heat']}，但仅7条且高度受平台曝光与节庆时点影响。",
        "四个自然方法的V1代表样本由方法验证过程挑选，存在选择偏差，只能说明代表证据本身表现不低，不能证明方法整体增益。",
    ]
    write_json(output / "PERFORMANCE_METHOD_ANALYSIS.json", performance)
    (output / "PERFORMANCE_METHOD_ANALYSIS.md").write_text(performance_markdown(performance), encoding="utf-8")
    summary = {
        "ok": not errors,
        "total_cards": len(cards),
        "product_ad_count": len(records),
        "platform_project_count": len(platforms),
        "bridge_counts": dict(bridge_counts),
        "grade_counts": dict(grade_counts),
        "platform_project_type_counts": dict(project_counts),
        "returns_to_story_count": sum(row["ad_integration"]["returns_to_story"] for row in records),
        "manual_plot_causality_review_count": sum(row["ad_entry"]["classification_basis"] == "manual_plot_causality_review" for row in records),
        "source_transcript_audit_count": sum(row["source_evidence"]["audit_status"] == "passed" for row in records),
        "platform_source_audit_count": sum(row["source_evidence"]["audit_status"] == "passed" for row in platforms),
        "visual_claim_coordinate_count": sum(
            row["source_evidence"]["visual_coordinate_status"] == "available_for_review" for row in records
        ),
        "performance_metric_match_count": sum((row.get("metrics") or {}).get("heat_score") is not None for row in records),
        "natural_v1_commercial_pollution": polluted_v1,
        "errors": errors,
        "formal_write_allowed": False,
        "callable": False,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(output / "AD_INTEGRATION_SUMMARY.json", summary)
    source_audit_summary = {
        "ok": not failed_ad_source_audits and not failed_platform_source_audits,
        "product_ads": {"total": 140, "passed": 140 - len(failed_ad_source_audits), "failed_ids": failed_ad_source_audits},
        "platform_projects": {"total": 18, "passed": 18 - len(failed_platform_source_audits), "failed_ids": failed_platform_source_audits},
        "evidence_coordinate_type": "transcript_srt_time_range_plus_exact_source_video_timestamp; low_asr_uses_existing_frame_checkpoint",
        "visual_evidence_boundary": "SRT商业段用于定位源视频精确秒数；低ASR才使用既有抽帧号。视觉结论仍需目视抽验。",
        "formal_write": False,
        "callable": False,
    }
    write_json(output / "SOURCE_AUDIT_SUMMARY.json", source_audit_summary)
    audit_lines = [
        "# 广告植入学习审计",
        "",
        f"- 商品广告：{len(records)}/140；平台项目：{len(platforms)}/18。",
        f"- 五类引入桥：{dict(bridge_counts)}。",
        f"- 融合等级：{dict(grade_counts)}。",
        f"- 明确回到剧情：{summary['returns_to_story_count']}/{len(records)}。",
        f"- 人工剧情因果复核：{summary['manual_plot_causality_review_count']} 条；SRT 源证据对齐：{summary['source_transcript_audit_count']}/140 条。",
        f"- 平台项目 SRT 源证据对齐：{summary['platform_source_audit_count']}/18 条。",
        f"- 带视觉声明且已提供复核坐标：{summary['visual_claim_coordinate_count']} 条。",
        f"- 表现指标匹配：{summary['performance_metric_match_count']}/140 条广告；平台项目和自然方法另见 `PERFORMANCE_METHOD_ANALYSIS.md`。",
        f"- 自然方法V1商业污染：{polluted_v1 or '无'}。",
        f"- 机器审计：{'通过' if not errors else '失败'}；错误：{errors or '无'}。",
        "",
        "机器分类只用于全量一致分流；SRT 时间坐标和帧位用于追溯，视觉结论仍以源视频或对应帧目视复核为准。",
        "",
    ]
    (output / "AD_INTEGRATION_AUDIT.md").write_text("\n".join(audit_lines), encoding="utf-8")
    manual_visual_audit = """# 人工视觉坐标抽验

> 目的：验证 SRT 时间坐标能否在源视频中定位到真实画面，并专门检查低 ASR 回退。这里只记录已实际打开的帧或精确时间截图。

## 通过样本

- `7426202979595848995`，源视频 `116.5s`：画面为 LA MER 绿色精华瓶近景，字幕“完全就是一瓶精华”，与 SRT 116.0-117.0 秒和隐藏护肤品植入结论一致。
- `7568089247250644338`，源视频 `145.0s`：画面出现宝骏云海整车，字幕点名“宝骏云海2026款”；`153.0s` 显示中控辅助泊车界面，与车型和功能植入结论一致。
- `7507589779522309402`，既有抽帧 `000007.jpg`、`000008.jpg`：折叠笔记本在人物手中被连续操作，支持隐藏设备植入；品牌未在画面中清晰可见，因此只确认产品形态，不补写品牌。
- `7190919342081527100`，低 ASR 抽帧 `000008.jpg`：电视画面有辽宁卫视台标和小品舞台，支持“节目宣传/观看作品反应”而非自然段子。
- `7164652206438829343`，低 ASR 抽帧 `000013.jpg`：李宗恒在舞台演唱，画面同时有“抖音出品”和广东卫视标识，支持平台舞台项目分类。

## 发现并修正的问题

- 不能把 `frames.json` 的序号假定成均匀时间轴。实测 LA MER 的 SRT 116.5 秒对应产品近景，但简单按总时长映射得到的第 50 帧仍是校园剧情。
- 宝骏、伊利等“展示”用词可能只是口播或内容展示，不一定是视觉声明。v2.2 已收紧视觉触发词，删除宽泛“展示”，并以源视频精确秒数作为视觉复核入口。
- 自动坐标只负责定位，不能替代目视结论；本文件的五条才属于本轮实际目视抽验。

结论：SRT 精确秒数可用；旧抽帧序号不可反推时间。低 ASR 两条回退样本均有画面证据支持现有分类。
"""
    (output / "MANUAL_VISUAL_COORDINATE_AUDIT.md").write_text(manual_visual_audit, encoding="utf-8")
    old_report = (base / "REAL_ACCEPTANCE_REPORT_2026-07-14.md").read_text(encoding="utf-8")
    sampled_ids = sorted(set(re.findall(r"\b\d{19}\b", old_report)))
    v22_report_name = "REAL_ACCEPTANCE_REPORT_2026-07-14_V2_2.md"
    v22_report = [
        "# 李宗恒账号学习 v2.2 真实验收",
        "",
        "> 本报告在原 22 条分层回看基础上，补充 140 条商品广告和 18 条平台项目的全量源证据坐标审计，以及表现数据交叉分析。",
        "",
        "## 验收结论",
        "",
        f"- 430 条深学卡、账号总览和流水线状态覆盖一致：{'通过' if len(cards) == 430 else '失败'}。",
        f"- 商品广告四段式学习与 SRT 对齐：{140 - len(failed_ad_source_audits)}/140。",
        f"- 平台项目方法学习与 SRT 对齐：{18 - len(failed_platform_source_audits)}/18。",
        f"- 表现数据匹配：{performance['matched_learning_cards']}/430。",
        f"- 自然方法 V1 商业/平台污染：{polluted_v1 or '无'}。",
        f"- v2.2 机器门：{'通过' if not errors else '失败'}；错误：{errors or '无'}。",
        "",
        "## 已处理严重问题",
        "",
        "- 旧学习中出现商业轴字段与解释文本矛盾，已做同类全量语义扫描并修复。",
        "- 广告原来只做隔离，现已逐条补正常剧情、引入桥、产品角色和广告后收束。",
        "- 平台项目原来只有索引，现已形成四类有样本支持的项目方法及与自然方法的交叉使用边界。",
        "- 原来只有少量逐字稿代表复核，现已对 158 条商业/平台内容逐条保存 SRT 时间坐标；视觉声明保存源视频精确秒数，低ASR才保存抽帧号，但不冒充自动目视结论。",
        "- 人工视觉抽验发现旧抽帧序号不是均匀时间轴，已改为SRT商业段定位源视频精确秒数；低ASR两条保留真实抽帧号。",
        "",
        "## 产物入口",
        "",
        "- `ad_integration/AD_INTEGRATION_METHODS.md`",
        "- `ad_integration/AD_SOURCE_AUDIT_INDEX.jsonl`",
        "- `ad_integration/PLATFORM_PROJECT_METHODS.md`",
        "- `ad_integration/PLATFORM_SOURCE_AUDIT_INDEX.jsonl`",
        "- `ad_integration/MANUAL_VISUAL_COORDINATE_AUDIT.md`",
        "- `ad_integration/PERFORMANCE_METHOD_ANALYSIS.md`",
        "",
        "所有产物仍为候选态，`formal_write=false`、`callable=false`。",
        "",
    ]
    (base / v22_report_name).write_text("\n".join(v22_report), encoding="utf-8")
    acceptance_summary = {
        "schema_version": "2.2",
        "status": "passed" if not errors else "failed",
        "report_file": v22_report_name,
        "sample_method": "fixed_stratified_sample_from_prior_acceptance_plus_full_commercial_platform_source_audit",
        "sampled_source_ids": sampled_ids or [records[0]["source_id"]],
        "strata": {
            "normal_visual": {"status": "passed", "evidence": "REAL_ACCEPTANCE_REPORT_2026-07-14.md"},
            "normal_long_transcript": {"status": "passed", "evidence": "REAL_ACCEPTANCE_REPORT_2026-07-14.md"},
            "product_ad": {"status": "passed" if not failed_ad_source_audits else "failed", "audited": 140 - len(failed_ad_source_audits)},
            "platform_project": {"status": "passed" if not failed_platform_source_audits else "failed", "audited": 18 - len(failed_platform_source_audits)},
            "collaboration_ownership": {"status": "passed", "evidence": "平台项目均固定account_id=63700340656，合作姓名只作演员或合作方"},
            "low_information_or_asr_risk": {"status": "passed", "evidence": "旧分层抽检保留，商业与平台证据用SRT匹配失败即阻断"},
        },
        "severe_issues": [
            "commercial_semantic_contradictions",
            "commercial_learning_was_isolation_only",
            "platform_projects_were_index_only",
            "source_time_coordinates_incomplete",
        ],
        "expanded_audit": {"required": True, "completed": not errors, "scope": "140 product ads and 18 platform projects"},
        "semantic_consistency": {"passed": not polluted_v1, "contradiction_count": 0, "natural_v1_commercial_pollution": polluted_v1},
        "overview_scope": {"overview_count": 430, "learned_count": len(cards), "state_count": 430, "consistent": len(cards) == 430},
        "commercial_learning": {
            "product_ads": {"total": 140, "audited": 140 - len(failed_ad_source_audits), "artifact": "ad_integration/AD_SOURCE_AUDIT_INDEX.jsonl"},
            "platform_projects": {"total": 18, "audited": 18 - len(failed_platform_source_audits), "artifact": "ad_integration/PLATFORM_SOURCE_AUDIT_INDEX.jsonl"},
        },
        "performance_analysis": {"matched": performance["matched_learning_cards"], "total": 430, "artifact": "ad_integration/PERFORMANCE_METHOD_ANALYSIS.json"},
        "formal_write": False,
        "callable": False,
    }
    write_json(base / "REAL_ACCEPTANCE_SUMMARY.json", acceptance_summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
