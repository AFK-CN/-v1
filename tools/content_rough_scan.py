from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.publish_content_source import load_publish_content_from_sqlite
from tools.video_learning import NormalizedRecord, deduplicate_records, heat_score, load_unique_records, transcript_covers_video


DEFAULT_PROFILES_PATH = Path("20_User/config/content_rough_scan_profiles.json")
OUTPUT_BASE = Path("10_Knowledge/candidates/account_assets/content_rough_scan")
SQLITE_ACCOUNT_CANDIDATES_PATH = Path("10_Knowledge/candidates/account_assets/sqlite_imports/latest_account_candidates.json")
DEFAULT_COMMERCIAL_DIRECTIONS = {"品牌植入与消费体验"}
DEFAULT_COMMERCIAL_TERMS = (
    "kfc",
    "肯德基",
    "rio",
    "oppo",
    "olay",
    "欧乐b",
    "周黑鸭",
    "滴滴",
    "小度",
    "海澜之家",
    "转转",
    "士力架",
    "元气森林",
    "元气可乐",
    "娇兰",
    "一加",
    "伊利",
    "老村长",
    "永劫无间",
    "梦幻西游",
    "去哪儿",
    "外星人",
    "劲酒",
    "立必得",
    "晓田",
    "荣耀",
    "Magic",
    "冰梅见",
    "马克华菲",
    "奥利奥",
    "舒肤佳",
    "科大讯飞",
    "飞科",
    "安慕希",
    "水星家纺",
    "京东",
    "天猫",
    "抖音商城",
    "爱回收",
    "荣耀Magic",
    "宝骏",
)
COMMERCIAL_HEAVY_TERMS = (
    "品牌活动",
    "好物节",
    "公测",
    "免单",
    "app",
    "双11",
    "618",
    "新品",
    "回收",
    "享美式",
    "想美事",
    "补充电解质",
)
COMMERCIAL_TAG_PATTERNS = (
    r"[A-Za-z]{2,}\s*[A-Za-z0-9]*",
    r"\d+\s*(?:万|元|度|g|G|GB|款|折|代|级)",
    r"(?:手机|电脑|鼠标|剃须刀|口红|精华|白瓶|复原蜜|家纺|夏凉被|商城|电商|出行|酒|可乐|咖啡|乳茶|SUV|体验|推荐|清单)",
)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def load_profiles(root: Path, path: Path | None = None) -> dict[str, dict[str, Any]]:
    profile_path = path or root / DEFAULT_PROFILES_PATH
    payload = read_json(profile_path, {})
    profiles = payload.get("profiles", payload) if isinstance(payload, dict) else {}
    if not isinstance(profiles, dict):
        raise ValueError(f"invalid profiles file: {profile_path}")
    return profiles


def load_profile(root: Path, profile_id: str, path: Path | None = None) -> dict[str, Any]:
    profiles = load_profiles(root, path)
    if profile_id not in profiles:
        raise KeyError(f"unknown rough-scan profile: {profile_id}")
    profile = dict(profiles[profile_id])
    profile.setdefault("profile_id", profile_id)
    return profile


def latest_sqlite_candidate_records_path(root: Path) -> Path | None:
    payload = read_json(root / SQLITE_ACCOUNT_CANDIDATES_PATH, {})
    batch_dir = str(payload.get("source_batch_dir", "")).strip() if isinstance(payload, dict) else ""
    if not batch_dir:
        return None
    path = root / batch_dir / "records.jsonl"
    return path if path.exists() else None


def sqlite_candidate_to_record(row: dict[str, Any]) -> NormalizedRecord:
    metrics = row.get("metrics", {}) if isinstance(row.get("metrics"), dict) else {}
    tags = row.get("tags", []) if isinstance(row.get("tags"), list) else []
    suggested = row.get("suggested_directions", []) if isinstance(row.get("suggested_directions"), list) else []
    source_keyword = str(row.get("source_keyword") or "")
    source_id = str(row.get("source_id") or row.get("stable_id") or "")
    title = str(row.get("title") or "")
    body = str(row.get("summary") or "")
    account_name = str(row.get("account_name") or row.get("source_keyword") or "")
    stable_id = str(row.get("stable_id") or f"{row.get('platform', '')}:{source_id}")
    return NormalizedRecord(
        platform=str(row.get("platform") or ""),
        source_id=source_id,
        source_file=stable_id,
        title=title,
        body=body,
        author_name=account_name,
        published_at="",
        metrics={
            "likes": int(metrics.get("likes", 0) or 0),
            "collects": int(metrics.get("collects", 0) or 0),
            "comments": int(metrics.get("comments", 0) or 0),
            "shares": int(metrics.get("shares", 0) or 0),
        },
        tags=list(dict.fromkeys([str(tag) for tag in [*tags, *suggested, source_keyword] if str(tag)])),
        url=str(row.get("url") or ""),
        video_download_url="",
        text_fingerprint=stable_id,
        account_name=account_name,
    )


def load_sqlite_candidate_records(root: Path) -> list[NormalizedRecord]:
    path = latest_sqlite_candidate_records_path(root)
    if path is None:
        return []
    rows = read_jsonl(path)
    records: list[NormalizedRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        platform = str(row.get("platform") or "")
        source_id = str(row.get("source_id") or row.get("stable_id") or "")
        if platform not in {"douyin", "xhs"} or not source_id:
            continue
        records.append(sqlite_candidate_to_record(row))
    return records


def load_rough_scan_records(root: Path) -> list[NormalizedRecord]:
    records, _, _ = load_unique_records(root)
    sqlite_records = load_sqlite_candidate_records(root)
    if sqlite_records:
        records, _ = deduplicate_records([*records, *sqlite_records])
    return records


def enrich_record_from_publish_db(root: Path, record: NormalizedRecord) -> NormalizedRecord:
    publish = load_publish_content_from_sqlite(root, record.platform, record.source_id)
    if publish is None:
        return record
    return replace(
        record,
        title=publish.title or record.title,
        body=publish.body or record.body,
        tags=list(publish.tags) or record.tags,
    )


def manifest_ocr_text(root: Path, record: NormalizedRecord) -> str:
    manifest = read_json(root / "00_System/runtime/state/video_learning/learning_manifest.json", {"items": {}})
    entry = manifest.get("items", {}).get(f"{record.platform}:{record.source_id}", {})
    images = entry.get("image", {}).get("images", [])
    return "\n".join(str(image.get("ocr_text", "")).strip() for image in images if image.get("ocr_text"))


def transcript_text(root: Path, record: NormalizedRecord) -> str:
    path = root / "00_System/runtime/cache/video_learning/video_artifacts" / f"{record.platform}_{record.source_id}" / "transcript.srt"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.isdigit() or "-->" in stripped:
            continue
        lines.append(stripped)
    return " ".join(lines)


def text_evidence(root: Path, record: NormalizedRecord) -> tuple[dict[str, str], list[str]]:
    evidence = {
        "title": record.title,
        "body": record.body,
        "tags": " ".join(record.tags),
        "transcript": transcript_text(root, record) if record.platform == "douyin" else "",
        "ocr": manifest_ocr_text(root, record) if record.platform == "xhs" else "",
    }
    sources = ["metadata"]
    if evidence["transcript"]:
        artifact_dir = root / "00_System/runtime/cache/video_learning/video_artifacts" / f"{record.platform}_{record.source_id}"
        video_path = artifact_dir / "source.mp4"
        transcript_json_path = artifact_dir / "transcript.json"
        if video_path.exists() and transcript_json_path.exists() and not transcript_covers_video(video_path, transcript_json_path):
            sources.append("partial_transcript")
        else:
            sources.append("transcript")
    if evidence["ocr"]:
        sources.append("ocr")
    return evidence, sources


def score_direction(evidence: dict[str, str], keywords: Any) -> int:
    lowered = {key: value.lower() for key, value in evidence.items()}
    score = 0
    if isinstance(keywords, dict):
        weighted_keywords = [
            *((keyword, 3) for keyword in keywords.get("core", [])),
            *((keyword, 1) for keyword in keywords.get("support", [])),
        ]
    else:
        weighted_keywords = [(keyword, 1) for keyword in keywords]
    for keyword, keyword_weight in weighted_keywords:
        needle = str(keyword).lower().strip()
        if not needle:
            continue
        score += lowered["title"].count(needle) * 5 * keyword_weight
        score += lowered["tags"].count(needle) * 3 * keyword_weight
        score += lowered["body"].count(needle) * keyword_weight
        score += lowered["transcript"].count(needle) * keyword_weight
        score += lowered["ocr"].count(needle) * keyword_weight
    return score


def commercial_directions(profile: dict[str, Any]) -> set[str]:
    configured = profile.get("commercial_directions", [])
    return DEFAULT_COMMERCIAL_DIRECTIONS | {str(item) for item in configured if str(item)}


def classification(evidence: dict[str, str], profile: dict[str, Any]) -> dict[str, Any]:
    directions = profile["directions"]
    scores = {direction: score_direction(evidence, keywords) for direction, keywords in directions.items()}
    commercial = commercial_directions(profile)
    topic_scores = {direction: score for direction, score in scores.items() if direction not in commercial}
    ordered_source = topic_scores if any(score > 0 for score in topic_scores.values()) else scores
    ordered = sorted(ordered_source.items(), key=lambda item: (-item[1], list(directions).index(item[0])))
    primary, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0
    margin = (top_score - second_score) / top_score if top_score else 0.0
    threshold = float(profile.get("confidence_margin", 0.2))
    if top_score == 0:
        needs_review = True
        reason = "no_direction_signal"
    elif top_score == second_score:
        needs_review = True
        reason = "top_score_tied"
    elif margin < threshold:
        needs_review = True
        reason = "low_score_margin"
    else:
        needs_review = False
        reason = ""
    secondary = [direction for direction, score in ordered[1:] if score > 0]
    return {
        "primary_direction": primary,
        "secondary_directions": secondary,
        "classification_scores": scores,
        "classification_confidence": round(margin, 4),
        "needs_review": needs_review,
        "review_reason": reason,
        "review_note": "",
    }


def commercial_terms(profile: dict[str, Any]) -> list[str]:
    terms = list(DEFAULT_COMMERCIAL_TERMS)
    configured = profile.get("commercial_terms", [])
    terms.extend(str(item) for item in configured if str(item))
    for direction in commercial_directions(profile):
        terms.extend(keywords_for_direction(profile, direction))
    return list(dict.fromkeys(term for term in terms if term))


def commercial_analysis(evidence: dict[str, str], classified: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    text = normalize_text(" ".join(str(value) for value in evidence.values() if value))
    lower = text.lower()
    terms = [term for term in commercial_terms(profile) if term.lower() in lower]
    tags_text = evidence.get("tags", "")
    inferred_terms = []
    for tag in extract_topic_tags(tags_text) or tags_text.split():
        cleaned = normalize_text(str(tag)).strip("#")
        if cleaned and any(re.search(pattern, cleaned, flags=re.IGNORECASE) for pattern in COMMERCIAL_TAG_PATTERNS):
            inferred_terms.append(cleaned)
    terms = list(dict.fromkeys([*terms, *inferred_terms]))
    scores = classified.get("classification_scores", {})
    primary = str(classified.get("primary_direction", ""))
    topic_score = int(scores.get(primary, 0) or 0)
    commercial_score = max((int(scores.get(direction, 0) or 0) for direction in commercial_directions(profile)), default=0)
    heavy = any(term.lower() in lower for term in COMMERCIAL_HEAVY_TERMS)
    if not terms and commercial_score <= 0:
        commercial_type = "normal_content"
    elif topic_score <= 0 or heavy:
        commercial_type = "ad_heavy"
    else:
        commercial_type = "ad_integrated"
    return {
        "commercial_type": commercial_type,
        "commercial_flag": commercial_type != "normal_content",
        "commercial_terms": terms,
        "commercial_score": commercial_score,
    }


def material_status(root: Path, record: NormalizedRecord) -> str:
    if record.platform == "douyin":
        directory = root / "00_System/runtime/cache/video_learning/video_artifacts" / f"douyin_{record.source_id}"
        video_path = directory / "source.mp4"
        transcript_srt_path = directory / "transcript.srt"
        transcript_json_path = directory / "transcript.json"
        if video_path.is_file() and transcript_srt_path.is_file():
            if transcript_json_path.is_file() and transcript_covers_video(video_path, transcript_json_path):
                return "video_and_transcript"
            return "video_and_partial_transcript"
        if video_path.is_file():
            return "video_only"
        if transcript_srt_path.is_file():
            return "transcript_only"
        return "metadata_only"
    return "ocr_available" if manifest_ocr_text(root, record) else "metadata_only"


def compact_summary(record: NormalizedRecord, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", record.body or record.title).strip()
    return text[:limit]


def extract_topic_tags(*values: str) -> list[str]:
    text = " ".join(value for value in values if value)
    tags: list[str] = []
    for match in re.finditer(r"#\s*([^#\s]+?)(?:\[话题\]#|#|\s|$)", text):
        tag = normalize_text(match.group(1)).strip("#")
        if tag:
            tags.append(tag)
    return list(dict.fromkeys(tags))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u2028", " ")).strip()


def text_fragments(row: dict[str, Any]) -> list[str]:
    text = normalize_text(" ".join([str(row.get("title", "")), str(row.get("topic_summary", ""))]))
    text = re.sub(r"#[^\s#]+", " ", text)
    parts = re.split(r"[。！？!?；;\n\r]+", text)
    return [normalize_text(part) for part in parts if normalize_text(part)]


def opening_fragment(row: dict[str, Any]) -> str:
    fragments = text_fragments(row)
    return fragments[0] if fragments else normalize_text(str(row.get("title", "")))[:80]


def title_pattern(row: dict[str, Any]) -> str:
    title = normalize_text(str(row.get("title", "")))
    if any(marker in title for marker in QUESTION_MARKERS):
        return "问题型标题"
    if re.search(r"\d|一周|几天|多年|分钟|小时|步骤|清单|教程", title):
        return "数字/步骤/周期型标题"
    if any(word in title for word in ("真的", "直接", "不要", "别", "不是", "其实", "反而", "没想到")):
        return "强判断/反常识型标题"
    if any(word in title for word in ("分享", "经验", "方法", "干货", "攻略")):
        return "经验方法型标题"
    return "结果/场景型标题"


def body_pattern(row: dict[str, Any]) -> str:
    text = normalize_text(str(row.get("topic_summary", "")))
    if re.search(r"1[、.．]|2[、.．]|第一|第二|步骤|流程|教程", text):
        return "步骤拆解"
    if any(word in text for word in ("我以前", "我之前", "亲测", "自用", "真实", "坚持")):
        return "个人经历背书"
    if any(word in text for word in ("适合", "不适合", "翻车", "敏感", "风险", "注意")):
        return "适用边界说明"
    if text:
        return "问题到行动"
    return "正文缺失，仅保留标题学习"


def topic_tag_summary(row: dict[str, Any]) -> str:
    tags = row.get("topic_tags") or []
    if tags:
        return "、".join(str(tag) for tag in tags[:8])
    return "未提取到显式话题"


def evidence_level(row: dict[str, Any]) -> str:
    if row.get("confirmed_learned"):
        return "deep_card_confirmed"
    sources = set(row.get("text_sources", []))
    if "partial_transcript" in sources:
        return "needs_video_review"
    if "transcript" in sources or "ocr" in sources:
        return "transcript_available"
    if row.get("candidate_deep_learning") or row.get("rough_scan_value") == "medium":
        return "needs_video_review"
    return "metadata_only"


QUESTION_MARKERS = ("如何", "怎么", "为什么", "什么", "哪些", "有没有", "能不能", "到底", "吗", "？", "?")
CONTRARIAN_PATTERNS = (
    r"不是.+而是",
    r"很多人以为.+其实",
    r"很多人.+搞反",
    r"关键不是",
    r"真正的",
    r"搞反了",
    r"反而",
)


def candidate_short_phrases(row: dict[str, Any], limit: int = 5) -> list[str]:
    phrases: list[str] = []
    for fragment in text_fragments(row):
        cleaned = fragment.strip(" ，,：:")
        if not cleaned or cleaned.startswith("#"):
            continue
        if 8 <= len(cleaned) <= 38 and not re.fullmatch(r"[\w#\s]+", cleaned):
            phrases.append(cleaned)
    return list(dict.fromkeys(phrases))[:limit]


def candidate_question_phrases(row: dict[str, Any], limit: int = 5) -> list[str]:
    questions = [
        fragment
        for fragment in text_fragments(row)
        if any(marker in fragment for marker in QUESTION_MARKERS) and 6 <= len(fragment) <= 60
    ]
    return list(dict.fromkeys(questions))[:limit]


def candidate_contrarian_phrases(row: dict[str, Any], limit: int = 5) -> list[str]:
    phrases = [
        fragment
        for fragment in text_fragments(row)
        if any(re.search(pattern, fragment) for pattern in CONTRARIAN_PATTERNS) and 6 <= len(fragment) <= 80
    ]
    return list(dict.fromkeys(phrases))[:limit]


def keywords_for_direction(profile: dict[str, Any], direction: str) -> list[str]:
    keywords = profile["directions"].get(direction, [])
    if isinstance(keywords, dict):
        return [str(item) for item in [*keywords.get("core", []), *keywords.get("support", [])]]
    return [str(item) for item in keywords]


def topic_clusters(direction: str, rows: list[dict[str, Any]], profile: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    keywords = keywords_for_direction(profile, direction)
    clusters: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        text = normalize_text(f"{row.get('title', '')} {row.get('topic_summary', '')}")
        matched = [keyword for keyword in keywords if keyword and keyword.lower() in text.lower()]
        for keyword in matched[:2] or [direction]:
            if len(clusters[keyword]) >= 5:
                continue
            clusters[keyword].append(
                {
                    "source_id": row["source_id"],
                    "title": normalize_text(str(row.get("title", "")))[:80],
                    "evidence_level": evidence_level(row),
                }
            )
    ranked = sorted(clusters.items(), key=lambda item: (-len(item[1]), keywords.index(item[0]) if item[0] in keywords else 999))
    return [{"topic": topic, "count": len(items), "representative_items": items} for topic, items in ranked[:limit]]


def deep_relation(row: dict[str, Any]) -> str:
    if row.get("confirmed_learned"):
        return "已覆盖"
    if row.get("is_deep_learning_target"):
        return "需复核" if row.get("deep_learning_status") != "selected" else "可补强"
    if row.get("candidate_deep_learning"):
        return "可补强"
    return "低价值暂不学"


def candidate_reason(row: dict[str, Any]) -> str:
    if row.get("confirmed_learned"):
        return "已形成深学单卡，可作为方向总结证据"
    if row.get("is_deep_learning_target"):
        return "权威深学范围内，适合补强方向方法论"
    if row.get("candidate_deep_learning"):
        return "本轮范围外但相关度或热度较高，适合作为候补深学素材"
    return str(row.get("defer_reason") or "相关度或热度较低，暂不进入候补")


def direction_insights(direction: str, rows: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    expression_rows = []
    for row in rows:
        short_phrases = candidate_short_phrases(row)
        question_phrases = candidate_question_phrases(row)
        contrarian_phrases = candidate_contrarian_phrases(row)
        if short_phrases or question_phrases or contrarian_phrases or row.get("candidate_deep_learning") or row.get("is_deep_learning_target"):
            expression_rows.append(
                {
                    "source_id": row["source_id"],
                    "title": normalize_text(str(row.get("title", "")))[:90],
                    "evidence_level": evidence_level(row),
                    "title_pattern": title_pattern(row),
                    "opening_fragment": opening_fragment(row)[:90],
                    "body_pattern": body_pattern(row),
                    "topic_tags": row.get("topic_tags") or extract_topic_tags(
                        str(row.get("title", "")), str(row.get("topic_summary", ""))
                    ),
                    "short_phrases": short_phrases,
                    "question_phrases": question_phrases,
                    "contrarian_phrases": contrarian_phrases,
                    "deep_relation": deep_relation(row),
                    "candidate_reason": candidate_reason(row),
                }
            )
    return {
        "direction": direction,
        "topic_clusters": topic_clusters(direction, rows, profile),
        "expressions": expression_rows,
        "asset_learning_policy": {
            "learn_title": True,
            "learn_body_or_caption": True,
            "learn_topic_tags": True,
            "learn_comment_text": False,
        },
        "candidate_deep_learning": [item for item in expression_rows if item["deep_relation"] in {"可补强", "需复核"}][:20],
        "needs_video_review": [item for item in expression_rows if item["evidence_level"] == "needs_video_review"][:20],
    }


def record_matches_profile(record: NormalizedRecord, profile: dict[str, Any]) -> bool:
    account = profile["account_name"]
    if (record.account_name or record.author_name) == account:
        return True
    match_terms = [str(term) for term in profile.get("account_match_terms", []) if str(term)]
    if not match_terms:
        return False
    text = " ".join(
        [
            record.title,
            record.body,
            " ".join(record.tags),
            record.account_name,
            record.author_name,
        ]
    )
    return any(term in text for term in match_terms)


def build_inventory(
    root: Path,
    records: list[NormalizedRecord],
    profile: dict[str, Any],
    deep_items: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    deep_items = deep_items or {}
    excluded = {str(item) for item in profile.get("excluded_deep_ids", [])}
    platforms = set(profile.get("platforms", []))
    selected = [
        record
        for record in records
        if record_matches_profile(record, profile) and (not platforms or record.platform in platforms)
    ]
    rows: list[dict[str, Any]] = []
    for record in sorted(selected, key=lambda item: (item.platform, item.source_id)):
        record = enrich_record_from_publish_db(root, record)
        evidence, sources = text_evidence(root, record)
        classified = classification(evidence, profile)
        commercial = commercial_analysis(evidence, classified, profile)
        deep = deep_items.get(str(record.source_id))
        if deep:
            classified.update(
                {
                    "primary_direction": deep["primary_direction"],
                    "needs_review": False,
                    "review_reason": "",
                    "review_note": "deep_plan_authoritative",
                }
            )
            classified["secondary_directions"] = [
                direction for direction in classified["secondary_directions"] if direction != classified["primary_direction"]
            ]
        is_excluded = str(record.source_id) in excluded
        is_deep = bool(deep) and not is_excluded
        if is_excluded:
            deep_status = "excluded_missing_media"
        elif is_deep:
            deep_status = str(deep.get("learning_status") or "selected")
        else:
            deep_status = "not_selected"
        url = record.url or (f"https://www.douyin.com/video/{record.source_id}" if record.platform == "douyin" else "")
        row = {
            "profile_id": profile["profile_id"],
            "platform": record.platform,
            "content_type": "video" if record.platform == "douyin" else "image_text",
            "account_name": profile["account_name"],
            "source_id": str(record.source_id),
            "source_url": url,
            "published_at": record.published_at,
            "title": record.title,
            "topic_summary": compact_summary(record),
            "topic_tags": extract_topic_tags(record.title, record.body, " ".join(record.tags)),
            "asset_learning_scope": {
                "title": True,
                "body_or_caption": bool(record.body),
                "topic_tags": bool(record.tags or extract_topic_tags(record.title, record.body)),
                "comment_text": False,
            },
            "text_sources": sources,
            "metrics": record.metrics,
            "heat_score": heat_score(record),
            "material_status": material_status(root, record),
            "is_deep_learning_target": is_deep,
            "deep_learning_status": deep_status,
            "confirmed_learned": bool(deep and deep.get("confirmed_learned")),
            **commercial,
            **classified,
        }
        rows.append(row)

    if overrides:
        rows = apply_overrides(rows, overrides, profile)

    return assign_rough_scan_values(rows, profile)


def assign_rough_scan_values(rows: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    by_direction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not row["is_deep_learning_target"]:
            by_direction[row["primary_direction"]].append(row)
    candidate_ids: set[str] = set()
    candidate_limit = int(profile.get("candidate_limit_per_direction", 20))
    for direction_rows in by_direction.values():
        ranked = sorted(
            direction_rows,
            key=lambda row: (
                int(row["classification_scores"].get(row["primary_direction"], 0)),
                float(row["heat_score"]),
            ),
            reverse=True,
        )
        candidate_ids.update(row["source_id"] for row in ranked[:candidate_limit])
    for row in rows:
        if row["is_deep_learning_target"]:
            row["rough_scan_value"] = "high"
            row["candidate_deep_learning"] = False
            row["defer_reason"] = ""
        elif row.get("commercial_type") == "ad_heavy":
            row["rough_scan_value"] = "low"
            row["candidate_deep_learning"] = False
            row["defer_reason"] = "广告污染较重，仅保留广告植入观察，不进入正常深学候补"
        elif row["deep_learning_status"] == "excluded_missing_media":
            row["rough_scan_value"] = "medium"
            row["candidate_deep_learning"] = False
            row["defer_reason"] = "缺少可用视频与逐字稿，本轮不深学"
        elif row["source_id"] in candidate_ids:
            row["rough_scan_value"] = "medium"
            row["candidate_deep_learning"] = True
            row["defer_reason"] = "本轮深学范围外，保留为方向候补"
        else:
            row["rough_scan_value"] = "low"
            row["candidate_deep_learning"] = False
            row["defer_reason"] = "相关度或热度未进入本轮候补范围"
    return rows


def apply_overrides(
    rows: list[dict[str, Any]], overrides: dict[str, dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    directions = set(profile["directions"])
    by_id = {row["source_id"]: dict(row) for row in rows}
    for source_id, override in overrides.items():
        if source_id not in by_id:
            raise KeyError(f"override source_id not found: {source_id}")
        direction = override.get("primary_direction", "")
        if direction not in directions:
            raise ValueError(f"invalid override direction for {source_id}: {direction}")
        row = by_id[source_id]
        previous = row["primary_direction"]
        row["primary_direction"] = direction
        row["secondary_directions"] = [item for item in row.get("secondary_directions", []) if item != direction]
        if previous != direction and previous not in row["secondary_directions"]:
            row["secondary_directions"].append(previous)
        row["needs_review"] = False
        row["review_reason"] = ""
        row["review_note"] = str(override.get("note", "reviewed"))
        by_id[source_id] = row
    return [by_id[row["source_id"]] for row in rows]


def validate_inventory(
    rows: list[dict[str, Any]], profile: dict[str, Any], expected_deep_count: int | None = None
) -> list[str]:
    errors: list[str] = []
    expected_count = int(profile.get("expected_count", len(rows)))
    if len(rows) != expected_count:
        errors.append(f"count mismatch: expected {expected_count}, got {len(rows)}")
    ids = [str(row.get("source_id", "")) for row in rows]
    duplicates = sorted(source_id for source_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate source_id: {','.join(duplicates)}")
    invalid_accounts = sorted({str(row.get("account_name", "")) for row in rows if row.get("account_name") != profile["account_name"]})
    if invalid_accounts:
        errors.append(f"account contamination: {','.join(invalid_accounts)}")
    allowed_directions = set(profile["directions"])
    invalid_directions = sorted({str(row.get("primary_direction", "")) for row in rows if row.get("primary_direction") not in allowed_directions})
    if invalid_directions:
        errors.append(f"invalid primary direction: {','.join(invalid_directions)}")
    review_count = sum(1 for row in rows if row.get("needs_review"))
    if review_count:
        errors.append(f"needs_review remains: {review_count}")
    if expected_deep_count is not None:
        actual = sum(1 for row in rows if row.get("is_deep_learning_target"))
        if actual != expected_deep_count:
            errors.append(f"deep target mismatch: expected {expected_deep_count}, got {actual}")
    return errors


def inventory_markdown(rows: list[dict[str, Any]], profile: dict[str, Any]) -> str:
    lines = [
        f"# {profile['account_name']}全量粗扫内容清单",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"内容数：{len(rows)}",
        f"待审核：{sum(1 for row in rows if row['needs_review'])}",
        "",
        "| source_id | 平台 | 主方向 | 标题/主题 | 粗扫价值 | 深学状态 | 候补 | 原链接 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        title = re.sub(r"\s+", " ", row["title"])[:60]
        lines.append(
            f"| {row['source_id']} | {row['platform']} | {row['primary_direction']} | {title} | "
            f"{row['rough_scan_value']} | {row['deep_learning_status']} | "
            f"{'是' if row['candidate_deep_learning'] else '否'} | {row['source_url']} |"
        )
    return "\n".join(lines) + "\n"


def direction_markdown(direction: str, rows: list[dict[str, Any]], profile: dict[str, Any]) -> str:
    insights = direction_insights(direction, rows, profile)
    lines = [
        f"# {direction}方向粗学与选题池",
        "",
        f"账号：{profile['account_name']}",
        f"方向：{direction}",
        f"粗学范围：{len(rows)}条",
        "状态：candidate_learning_pool",
        "",
        "## 1. 方向素材总览",
        "",
        f"- 内容总数：{len(rows)}条。",
        f"- 已确认深学卡：{sum(1 for row in rows if row.get('confirmed_learned'))}条。",
        f"- 候补深学：{sum(1 for row in rows if row.get('candidate_deep_learning'))}条。",
        f"- 需视频复核：{len(insights['needs_video_review'])}条。",
        "- 粗学重点：发布内容层，包括标题、正文/文案、话题/标签、内容结构协同。",
        "- 视频边界：粗扫阶段未下载视频，不学习逐字稿、抽帧或分镜；需要进入深度学习后补齐视频内容层。",
        "- 评论处理：不学习评论正文；评论数只作为平台互动指标保留。",
        "",
        "## 2. 全部粗学素材清单",
        "",
        "| source_id | 原视频/笔记链接 | 标题/主题 | 话题/标签 | 辅方向 | 粗学价值 | 深学状态 | 是否候补深学 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        title = re.sub(r"\s+", " ", row["title"])[:72]
        tags = topic_tag_summary(row)
        secondary = "、".join(row["secondary_directions"])
        lines.append(
            f"| {row['source_id']} | {row['source_url']} | {title} | {tags} | {secondary} | {row['rough_scan_value']} | "
            f"{row['deep_learning_status']} | {'是' if row['candidate_deep_learning'] else '否'} |"
        )
    lines.extend(["", "## 3. 标题学习", ""])
    title_count = 0
    for item in insights["expressions"][:40]:
        lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {item['title_pattern']}：{item['title']}")
        title_count += 1
    if not title_count:
        lines.append("- 无。")
    lines.extend(["", "## 4. 正文/文案学习", ""])
    body_count = 0
    for item in insights["expressions"][:40]:
        lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {item['body_pattern']}：{item['opening_fragment']}")
        body_count += 1
    if not body_count:
        lines.append("- 无。")
    lines.extend(["", "## 5. 话题/标签学习", ""])
    topic_tag_count = 0
    for item in insights["expressions"][:40]:
        tags = "、".join(item.get("topic_tags") or [])
        if not tags:
            continue
        lines.append(f"- `{item['source_id']}`：{tags}")
        topic_tag_count += 1
    if not topic_tag_count:
        lines.append("- 无显式话题/标签；保留标题与正文语义学习。")
    lines.extend(["", "## 6. 主题簇", ""])
    for cluster in insights["topic_clusters"]:
        lines.append(f"### {cluster['topic']}（{cluster['count']}条）")
        lines.append("")
        for item in cluster["representative_items"]:
            lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {item['title']}")
        lines.append("")
    if not insights["topic_clusters"]:
        lines.append("- 无。")
    lines.extend(["", "## 7. 候选短句", ""])
    short_count = 0
    for item in insights["expressions"]:
        for phrase in item["short_phrases"][:3]:
            lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {phrase}")
            short_count += 1
            if short_count >= 30:
                break
        if short_count >= 30:
            break
    if not short_count:
        lines.append("- 无。")
    lines.extend(["", "## 8. 候选问题句", ""])
    question_count = 0
    for item in insights["expressions"]:
        for phrase in item["question_phrases"][:3]:
            lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {phrase}")
            question_count += 1
            if question_count >= 30:
                break
        if question_count >= 30:
            break
    if not question_count:
        lines.append("- 无。")
    lines.extend(["", "## 9. 候选反常识表达", ""])
    contrarian_count = 0
    for item in insights["expressions"]:
        for phrase in item["contrarian_phrases"][:3]:
            lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {phrase}")
            contrarian_count += 1
            if contrarian_count >= 30:
                break
        if contrarian_count >= 30:
            break
    if not contrarian_count:
        lines.append("- 无。")
    lines.extend(["", "## 10. 候补深学池", ""])
    for item in insights["candidate_deep_learning"]:
        lines.append(f"- `{item['source_id']}` [{item['evidence_level']}] {item['candidate_reason']}：{item['title']}")
    if not insights["candidate_deep_learning"]:
        lines.append("- 无。")
    lines.extend(["", "## 11. 与已深学卡的关系", ""])
    for item in insights["expressions"][:40]:
        lines.append(f"- `{item['source_id']}`：{item['deep_relation']}。{item['candidate_reason']}")
    if not insights["expressions"]:
        lines.append("- 无。")
    lines.extend(["", "## 12. 需要复核的问题", ""])
    for item in insights["needs_video_review"]:
        lines.append(f"- `{item['source_id']}`：候选素材来自元数据或不完整材料，需要视频/逐字稿复核。")
    if not insights["needs_video_review"]:
        lines.append("- 无。")
    lines.extend(["", "## 13. 评论边界", "", "- 不学习评论正文，不从评论区提炼观点、痛点或话术。"])
    lines.append("- 评论数量只作为平台互动指标，不进入标题、正文、话题或方法论学习。")
    return "\n".join(lines) + "\n"


def write_outputs(
    root: Path,
    profile: dict[str, Any],
    rows: list[dict[str, Any]],
    validation_errors: list[str],
) -> dict[str, Any]:
    output_dir = root / OUTPUT_BASE / profile["profile_id"]
    directions_dir = output_dir / "directions"
    output_dir.mkdir(parents=True, exist_ok=True)
    directions_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (list(profile["directions"]).index(row["primary_direction"]), row["source_id"]))
    write_jsonl(output_dir / "all_content_inventory.jsonl", ordered)
    (output_dir / "all_content_inventory.md").write_text(inventory_markdown(ordered, profile), encoding="utf-8")
    existing_scope = read_json(output_dir / "deep_learning_scope.json", {"items": []})
    existing_items = existing_scope.get("items", existing_scope) if isinstance(existing_scope, dict) else existing_scope
    existing_by_id = {str(item.get("source_id", "")): item for item in existing_items if isinstance(item, dict)}
    write_json(
        output_dir / "deep_learning_scope.json",
        {
            "profile_id": profile["profile_id"],
            "items": [
                {
                    **existing_by_id.get(str(row["source_id"]), {}),
                    "source_id": row["source_id"],
                    "primary_direction": row["primary_direction"],
                    "source_url": row["source_url"],
                    "title": row["title"],
                    "confirmed_learned": bool(
                        existing_by_id.get(str(row["source_id"]), {}).get("confirmed_learned", row.get("confirmed_learned", False))
                    ),
                }
                for row in ordered
                if row["is_deep_learning_target"]
            ],
        },
    )
    review_rows = [row for row in ordered if row["needs_review"]]
    write_jsonl(output_dir / "review_queue.jsonl", review_rows)
    overrides_path = output_dir / "review_overrides.json"
    if not overrides_path.exists():
        write_json(overrides_path, {"items": {}})
    for direction in profile["directions"]:
        direction_rows = [row for row in ordered if row["primary_direction"] == direction]
        insights = direction_insights(direction, direction_rows, profile)
        path = directions_dir / direction / "粗扫内容和选题.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(direction_markdown(direction, direction_rows, profile), encoding="utf-8")
        write_json(path.parent / "rough_scan_insights.json", insights)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile_id": profile["profile_id"],
        "account_name": profile["account_name"],
        "total": len(rows),
        "deep_learning_targets": sum(1 for row in rows if row["is_deep_learning_target"]),
        "non_deep_learning": sum(1 for row in rows if not row["is_deep_learning_target"]),
        "needs_review": len(review_rows),
        "direction_counts": dict(sorted(Counter(row["primary_direction"] for row in rows).items())),
        "errors": validation_errors,
        "valid": not validation_errors,
    }
    write_json(output_dir / "validation_report.json", report)
    return {
        "output_dir": str(output_dir.relative_to(root)),
        "total": len(rows),
        "needs_review": len(review_rows),
        "valid": not validation_errors,
        "errors": validation_errors,
    }


def resolve_deep_items(
    plan_items: list[dict[str, Any]],
    confirmed: dict[str, str],
    direction_limits: dict[str, int],
    excluded_ids: set[str],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in plan_items:
        source_id = str(item["source_id"])
        if source_id in excluded_ids:
            continue
        row = dict(item)
        row["source_id"] = source_id
        row["confirmed_learned"] = source_id in confirmed
        grouped[row["primary_direction"]].append(row)
    existing_ids = {str(item["source_id"]) for items in grouped.values() for item in items}
    for source_id, direction in confirmed.items():
        if source_id in excluded_ids or source_id in existing_ids:
            continue
        grouped[direction].append(
            {
                "source_id": source_id,
                "primary_direction": direction,
                "direction_rank": 0,
                "confirmed_learned": True,
            }
        )
    resolved: dict[str, dict[str, Any]] = {}
    for direction, items in grouped.items():
        limit = int(direction_limits.get(direction, len(items)))
        ranked = sorted(
            items,
            key=lambda item: (
                0 if item.get("confirmed_learned") else 1,
                int(item.get("direction_rank", 999)),
                str(item["source_id"]),
            ),
        )
        for item in ranked[:limit]:
            resolved[str(item["source_id"])] = item
    return resolved


def load_deep_items(root: Path, profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = profile.get("deep_learning_plan", "")
    if not value:
        return {}
    payload = read_json(root / value, {"items": []})
    plan_items = payload.get("items", [])
    confirmed = {str(source_id): str(direction) for source_id, direction in profile.get("confirmed_deep_items", {}).items()}
    limits = {str(direction): int(limit) for direction, limit in profile.get("deep_direction_limits", {}).items()}
    excluded = {str(source_id) for source_id in profile.get("excluded_deep_ids", [])}
    resolved = resolve_deep_items(plan_items, confirmed, limits, excluded)
    existing_scope = read_json(output_dir(root, profile) / "deep_learning_scope.json", {"items": []})
    existing_items = existing_scope.get("items", existing_scope) if isinstance(existing_scope, dict) else existing_scope
    for item in existing_items:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id", ""))
        if not source_id or source_id in excluded:
            continue
        if source_id in resolved:
            resolved[source_id].update(
                {
                    "confirmed_learned": bool(item.get("confirmed_learned")),
                    "learning_status": item.get("learning_status", ""),
                    "card_path": item.get("card_path", ""),
                }
            )
        elif not plan_items:
            resolved[source_id] = {
                "source_id": source_id,
                "primary_direction": item.get("primary_direction", ""),
                "direction_rank": 0,
                "confirmed_learned": bool(item.get("confirmed_learned")),
                "learning_status": item.get("learning_status", ""),
                "card_path": item.get("card_path", ""),
            }
    return resolved


def hydrate_rows_from_deep_scope(root: Path, profile: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scope = read_json(output_dir(root, profile) / "deep_learning_scope.json", {"items": []})
    items = scope.get("items", scope) if isinstance(scope, dict) else scope
    by_id = {str(item.get("source_id", "")): item for item in items if isinstance(item, dict)}
    hydrated: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row.get("source_id", ""))
        item = by_id.get(source_id)
        if not item:
            hydrated.append(row)
            continue
        updated = dict(row)
        updated["is_deep_learning_target"] = True
        updated["confirmed_learned"] = bool(item.get("confirmed_learned", updated.get("confirmed_learned", False)))
        updated["deep_learning_status"] = str(item.get("learning_status") or updated.get("deep_learning_status") or "selected")
        updated["primary_direction"] = str(item.get("primary_direction") or updated.get("primary_direction") or "")
        hydrated.append(updated)
    return hydrated


def output_dir(root: Path, profile: dict[str, Any]) -> Path:
    return root / OUTPUT_BASE / profile["profile_id"]


def build_command(root: Path, profile: dict[str, Any]) -> tuple[dict[str, Any], int]:
    records = load_rough_scan_records(root)
    deep_items = load_deep_items(root, profile)
    rows = build_inventory(root, records, profile, deep_items=deep_items)
    expected_deep = int(profile.get("expected_deep_count", len(deep_items)))
    errors = validate_inventory(rows, profile, expected_deep_count=expected_deep)
    result = write_outputs(root, profile, rows, errors)
    return result, 0


def apply_command(root: Path, profile: dict[str, Any]) -> tuple[dict[str, Any], int]:
    directory = output_dir(root, profile)
    rows = hydrate_rows_from_deep_scope(root, profile, read_jsonl(directory / "all_content_inventory.jsonl"))
    payload = read_json(directory / "review_overrides.json", {"items": {}})
    overrides = payload.get("items", payload)
    reviewed = assign_rough_scan_values(apply_overrides(rows, overrides, profile), profile)
    expected_deep = int(profile.get("expected_deep_count", 0))
    errors = validate_inventory(reviewed, profile, expected_deep_count=expected_deep)
    result = write_outputs(root, profile, reviewed, errors)
    return result, 0 if not errors else 1


def validate_command(root: Path, profile: dict[str, Any]) -> tuple[dict[str, Any], int]:
    rows = hydrate_rows_from_deep_scope(root, profile, read_jsonl(output_dir(root, profile) / "all_content_inventory.jsonl"))
    expected_deep = int(profile.get("expected_deep_count", 0))
    errors = validate_inventory(rows, profile, expected_deep_count=expected_deep)
    result = write_outputs(root, profile, rows, errors)
    return result, 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reusable account-scoped rough-scan knowledge artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "apply-overrides", "validate"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", default=".")
        command.add_argument("--profile", required=True)
        command.add_argument("--profiles-path", default="")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    profiles_path = Path(args.profiles_path).resolve() if args.profiles_path else None
    profile = load_profile(root, args.profile, profiles_path)
    if args.command == "build":
        result, exit_code = build_command(root, profile)
    elif args.command == "apply-overrides":
        result, exit_code = apply_command(root, profile)
    else:
        result, exit_code = validate_command(root, profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
