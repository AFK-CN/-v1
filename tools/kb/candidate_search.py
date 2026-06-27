from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools import video_learning

from .candidate_assets import candidate_asset_path, candidate_asset_status
from .runtime import runtime_path
from .schemas import SYSTEM_CONFIG_DIR, now_iso


DEFAULT_SYNONYM_GROUPS = [
    ["赚钱", "挣钱", "收入", "变现", "副业", "财富"],
    ["创业", "一人公司", "做项目", "生意"],
    ["自媒体", "内容创作", "做账号", "个人IP", "个人ip"],
    ["短视频", "口播", "视频脚本", "拍视频"],
    ["个人成长", "成长", "自我提升", "进步"],
]

SEARCH_FIELDS = {
    "title": ("可生成标题", "title"),
    "direction": ("领域",),
    "pain_point": ("痛点",),
    "promise": ("内容承诺",),
    "script_direction": ("正文/脚本方向",),
    "account_name": ("account_name",),
}

FIELD_WEIGHTS = {
    "title": 12.0,
    "direction": 10.0,
    "pain_point": 7.0,
    "promise": 6.0,
    "script_direction": 5.0,
    "account_name": 2.0,
}


def search_candidates(
    root: Path,
    query: str,
    account_name: str = "",
    direction: str = "",
    limit: int = 10,
    include_raw: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    query = query.strip()
    account_name = account_name.strip()
    direction = direction.strip()
    query_terms = expand_query(root, query)
    status = candidate_asset_status(root)
    if status["status"] == "requires_init" and not include_raw:
        return {
            "status": "requires_init",
            "reasons": status["reasons"],
            "next_action": status["next_action"],
            "query": query,
            "account_name": account_name,
            "direction": direction,
            "query_expansions": query_terms,
            "backend": "weighted_jsonl_v1",
            "source": "candidate_assets",
            "count": 0,
            "skipped_asset_lines": 0,
            "failed_files": [],
            "partial_success": False,
            "report": "",
            "items": [],
        }
    backend_result = run_search_backend(
        root,
        query,
        account_name,
        direction,
        query_terms,
        include_raw=include_raw,
    )
    rows = backend_result["rows"][: max(limit, 1)]
    skipped_asset_lines = backend_result["skipped_asset_lines"]
    failed_files = backend_result["failed_files"]
    source = backend_result["source"]
    backend = backend_result["backend"]
    report = write_search_report(
        root,
        query,
        account_name,
        direction,
        rows,
        source,
        skipped_asset_lines,
        failed_files,
    )
    return {
        "status": "ok",
        "query": query,
        "account_name": account_name,
        "direction": direction,
        "query_expansions": query_terms,
        "backend": backend,
        "source": source,
        "count": len(rows),
        "skipped_asset_lines": skipped_asset_lines,
        "failed_files": failed_files,
        "partial_success": bool(failed_files),
        "report": str(report.relative_to(root)),
        "items": rows,
    }


def run_search_backend(
    root: Path,
    query: str,
    account_name: str,
    direction: str,
    query_terms: list[str],
    include_raw: bool,
) -> dict[str, Any]:
    rows, skipped_asset_lines = search_asset_topics(root, query, account_name, direction, query_terms)
    source = "candidate_assets"
    failed_files: list[dict[str, str]] = []
    if include_raw:
        raw_rows, failed_files = search_raw_records(root, query, account_name, direction, query_terms)
        rows = merge_rows(rows, raw_rows)
        source = "candidate_assets_plus_raw"
    else:
        rows = aggregate_rows(rows)
    return {
        "backend": "weighted_jsonl_v1",
        "rows": rows,
        "source": source,
        "skipped_asset_lines": skipped_asset_lines,
        "failed_files": failed_files,
    }


def search_asset_topics(
    root: Path,
    query: str,
    account_name: str,
    direction: str,
    query_terms: list[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    path = candidate_asset_path(root)
    if not path.exists():
        return [], 0
    query_terms = query_terms if query_terms is not None else expand_query(root, query)
    rows = []
    skipped = 0
    with path.open("r", encoding="utf-8") as handle:
        lines = list(handle)
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        match = score_item(item, query, query_terms)
        if query and not match["matched_terms"]:
            continue
        if account_name and account_name not in str(item.get("account_name", "")):
            continue
        if direction and direction not in str(item.get("领域", "")):
            continue
        rows.append(
            {
                "source": "candidate_assets",
                "platform": item.get("platform", ""),
                "account_name": item.get("account_name", ""),
                "direction": item.get("领域", ""),
                "title": first_title(item),
                "score": item.get("score", 0),
                "rank": item.get("rank", 0),
                "source_url": item.get("source_url", ""),
                "source_id": item.get("source_id", ""),
                "match_score": match["match_score"],
                "matched_terms": match["matched_terms"],
                "matched_fields": match["matched_fields"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("match_score") or 0),
            float(row.get("score") or 0),
            -int(row.get("rank") or 999),
        ),
        reverse=True,
    ), skipped


def search_raw_records(
    root: Path,
    query: str,
    account_name: str,
    direction: str,
    query_terms: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records, _, _, failed_files = video_learning.load_unique_records_detailed(root)
    query_terms = query_terms if query_terms is not None else expand_query(root, query)
    rows = []
    for record in records:
        text = f"{record.title} {record.body} {' '.join(record.tags)}"
        matched_terms = [term for term in query_terms if normalize_text(term) in normalize_text(text)]
        if query and not matched_terms:
            continue
        if account_name and account_name not in {record.account_name, record.author_name}:
            continue
        directions = video_learning.detect_directions(record)
        if direction and direction not in directions:
            continue
        best_direction = direction or first_non_unknown(directions)
        rows.append(
            {
                "source": "raw_dynamic",
                "platform": record.platform,
                "account_name": record.account_name or record.author_name,
                "direction": best_direction,
                "title": record.title,
                "score": video_learning.heat_score(record),
                "rank": "",
                "source_url": record.url,
                "source_id": record.source_id,
                "match_score": raw_match_score(record.title, record.body, query, matched_terms),
                "matched_terms": matched_terms,
                "matched_fields": raw_matched_fields(record.title, record.body, record.tags, matched_terms),
            }
        )
    return sorted(
        rows,
        key=lambda row: (float(row.get("match_score") or 0), float(row.get("score") or 0)),
        reverse=True,
    ), failed_files


def merge_rows(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return aggregate_rows(left + right)


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    merged = []
    for row in sorted(
        rows,
        key=lambda item: (float(item.get("match_score") or 0), float(item.get("score") or 0)),
        reverse=True,
    ):
        key = (row.get("platform"), row.get("source_id"))
        if key in seen:
            existing = next(item for item in merged if (item.get("platform"), item.get("source_id")) == key)
            add_direction(existing, str(row.get("direction", "")))
            if row.get("source") and row["source"] not in str(existing.get("source", "")):
                existing["source"] = f"{existing.get('source', '')}+{row['source']}"
            existing["matched_terms"] = merge_unique(existing.get("matched_terms", []), row.get("matched_terms", []))
            existing["matched_fields"] = merge_unique(existing.get("matched_fields", []), row.get("matched_fields", []))
            continue
        seen.add(key)
        row = dict(row)
        row["directions"] = [str(row.get("direction", ""))] if row.get("direction") else []
        merged.append(row)
    return sorted(
        merged,
        key=lambda row: (float(row.get("match_score") or 0), float(row.get("score") or 0)),
        reverse=True,
    )


def load_search_terms(root: Path) -> tuple[list[list[str]], dict[str, list[str]]]:
    path = root / SYSTEM_CONFIG_DIR / "search_terms.json"
    if not path.exists():
        return DEFAULT_SYNONYM_GROUPS, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return DEFAULT_SYNONYM_GROUPS, {}
    groups = payload.get("synonym_groups", []) if isinstance(payload, dict) else []
    valid = [
        [str(term).strip() for term in group if str(term).strip()]
        for group in groups
        if isinstance(group, list)
    ]
    configured_directions = payload.get("direction_terms", {}) if isinstance(payload, dict) else {}
    direction_terms = {
        str(direction): [str(term).strip() for term in terms if str(term).strip()]
        for direction, terms in configured_directions.items()
        if isinstance(terms, list)
    } if isinstance(configured_directions, dict) else {}
    return valid or DEFAULT_SYNONYM_GROUPS, direction_terms


def expand_query(root: Path, query: str) -> list[str]:
    query = query.strip()
    if not query:
        return []
    expanded = [query]
    normalized_query = normalize_text(query)
    synonym_groups, configured_directions = load_search_terms(root)
    for group in synonym_groups:
        normalized_group = [normalize_text(term) for term in group]
        if any(term and (term in normalized_query or normalized_query in term) for term in normalized_group):
            expanded.extend(group)
    direction_terms = {
        direction: merge_unique(list(keywords), configured_directions.get(direction, []))
        for direction, keywords in video_learning.DIRECTION_KEYWORDS.items()
    }
    for direction, aliases in configured_directions.items():
        direction_terms.setdefault(direction, list(aliases))
    for direction, keywords in direction_terms.items():
        terms = [direction, *keywords]
        normalized_terms = [normalize_text(term) for term in terms]
        if any(direction_term_matches_query(term, normalized_query) for term in normalized_terms):
            expanded.extend(terms)
    return merge_unique([], [term for term in expanded if term])


def direction_term_matches_query(term: str, query: str) -> bool:
    if not term or not query:
        return False
    if term == query:
        return True
    if len(term) < 2:
        return False
    return term in query or (len(query) >= 2 and query in term)


def normalize_text(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return re.sub(r"[\W_]+", "", str(value).lower(), flags=re.UNICODE)


def field_text(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    values = []
    for key in keys:
        value = item.get(key, "")
        if isinstance(value, list):
            values.extend(str(entry) for entry in value)
        elif value:
            values.append(str(value))
    return " ".join(values)


def score_item(item: dict[str, Any], query: str, query_terms: list[str]) -> dict[str, Any]:
    if not query:
        return {"match_score": 0.0, "matched_terms": [], "matched_fields": []}
    normalized_query = normalize_text(query)
    matched_terms: list[str] = []
    matched_fields: list[str] = []
    score = 0.0
    for field, keys in SEARCH_FIELDS.items():
        text = normalize_text(field_text(item, keys))
        if not text:
            continue
        field_matches = []
        for term in query_terms:
            normalized_term = normalize_text(term)
            if normalized_term and normalized_term in text:
                field_matches.append(term)
        if not field_matches:
            continue
        matched_fields.append(field)
        matched_terms.extend(field_matches)
        score += FIELD_WEIGHTS[field] * len(set(field_matches))
        if normalized_query and normalized_query in text:
            score += FIELD_WEIGHTS[field] * 10
    return {
        "match_score": round(score, 2),
        "matched_terms": merge_unique([], matched_terms),
        "matched_fields": matched_fields,
    }


def raw_match_score(title: str, body: str, query: str, matched_terms: list[str]) -> float:
    score = len(set(matched_terms)) * 5.0
    normalized_query = normalize_text(query)
    if normalized_query and normalized_query in normalize_text(title):
        score += 120.0
    elif normalized_query and normalized_query in normalize_text(body):
        score += 70.0
    return score


def raw_matched_fields(title: str, body: str, tags: list[str], terms: list[str]) -> list[str]:
    fields = []
    for name, value in (("title", title), ("body", body), ("tags", tags)):
        text = normalize_text(value)
        if any(normalize_text(term) in text for term in terms):
            fields.append(name)
    return fields


def merge_unique(left: list[Any], right: list[Any]) -> list[Any]:
    merged = list(left)
    for item in right:
        if item not in merged:
            merged.append(item)
    return merged


def add_direction(row: dict[str, Any], direction: str) -> None:
    if not direction:
        return
    directions = row.setdefault("directions", [])
    if direction not in directions:
        directions.append(direction)
    row["direction"] = "、".join(directions)


def first_title(item: dict[str, Any]) -> str:
    titles = item.get("可生成标题") or []
    if isinstance(titles, list) and titles:
        return str(titles[0])
    return str(item.get("title") or "")


def first_non_unknown(directions: list[str]) -> str:
    for value in directions:
        if value != "未归类":
            return value
    return directions[0] if directions else "未归类"


def write_search_report(
    root: Path,
    query: str,
    account_name: str,
    direction: str,
    rows: list[dict[str, Any]],
    source: str,
    skipped_asset_lines: int,
    failed_files: list[dict[str, str]],
) -> Path:
    reports = runtime_path(root, "reports")
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "latest_candidate_search_report.md"
    lines = [
        "# 候选资产检索报告",
        "",
        f"生成时间：{now_iso()}",
        f"检索词：{query or '未指定'}",
        f"账号：{account_name or '未指定'}",
        f"方向：{direction or '未指定'}",
        f"来源：{source}",
        f"跳过损坏候选行：{skipped_asset_lines}",
        "",
        "| 序号 | 来源 | 账号 | 方向 | 标题 | 分数 | 原链接 |",
        "| ---: | --- | --- | --- | --- | ---: | --- |",
    ]
    for index, row in enumerate(rows, 1):
        title = str(row.get("title", "")).replace("\n", " ")[:80]
        direction = row.get("direction", "")
        if isinstance(row.get("directions"), list) and row["directions"]:
            direction = "、".join(row["directions"])
        lines.append(f"| {index} | {row.get('source', '')} | {row.get('account_name', '')} | {direction} | {title} | {row.get('score', '')} | {row.get('source_url', '')} |")
    if failed_files:
        lines.extend(
            [
                "",
                "## 损坏原始文件",
                "",
                "| 文件 | 阶段 | 错误类型 | 错误摘要 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for failure in failed_files:
            message = str(failure.get("message", "")).replace("\n", " ")[:160]
            lines.append(
                f"| {failure.get('path', '')} | {failure.get('stage', '')} | "
                f"{failure.get('error_type', '')} | {message} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
