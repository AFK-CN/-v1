from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import video_learning

from .schemas import SYSTEM_DIR, now_iso


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
    rows, skipped_asset_lines = search_asset_topics(root, query, account_name, direction)
    source = "candidate_assets"
    if include_raw:
        raw_rows = search_raw_records(root, query, account_name, direction)
        rows = merge_rows(rows, raw_rows)
        source = "candidate_assets_plus_raw"
    else:
        rows = aggregate_rows(rows)
    rows = rows[: max(limit, 1)]
    report = write_search_report(root, query, account_name, direction, rows, source, skipped_asset_lines)
    return {
        "query": query,
        "account_name": account_name,
        "direction": direction,
        "source": source,
        "count": len(rows),
        "skipped_asset_lines": skipped_asset_lines,
        "report": str(report.relative_to(root)),
        "items": rows,
    }


def search_asset_topics(root: Path, query: str, account_name: str, direction: str) -> tuple[list[dict[str, Any]], int]:
    path = root / SYSTEM_DIR / "assets" / "candidate_topics.jsonl"
    if not path.exists():
        return [], 0
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
        text = json.dumps(item, ensure_ascii=False)
        if query and query not in text:
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
            }
        )
    return sorted(rows, key=lambda row: (float(row.get("score") or 0), -int(row.get("rank") or 999)), reverse=True), skipped


def search_raw_records(root: Path, query: str, account_name: str, direction: str) -> list[dict[str, Any]]:
    records, _, _ = video_learning.load_unique_records(root)
    rows = []
    for record in records:
        text = f"{record.title} {record.body} {' '.join(record.tags)}"
        if query and query not in text:
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
            }
        )
    return sorted(rows, key=lambda row: float(row.get("score") or 0), reverse=True)


def merge_rows(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return aggregate_rows(left + right)


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    merged = []
    for row in sorted(rows, key=lambda item: float(item.get("score") or 0), reverse=True):
        key = (row.get("platform"), row.get("source_id"))
        if key in seen:
            existing = next(item for item in merged if (item.get("platform"), item.get("source_id")) == key)
            add_direction(existing, str(row.get("direction", "")))
            if row.get("source") and row["source"] not in str(existing.get("source", "")):
                existing["source"] = f"{existing.get('source', '')}+{row['source']}"
            continue
        seen.add(key)
        row = dict(row)
        row["directions"] = [str(row.get("direction", ""))] if row.get("direction") else []
        merged.append(row)
    return sorted(merged, key=lambda row: float(row.get("score") or 0), reverse=True)


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
) -> Path:
    reports = root / SYSTEM_DIR / "reports"
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
