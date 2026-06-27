from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.video_learning import (
    DIRECTION_KEYWORDS,
    NormalizedRecord,
    heat_score,
    load_unique_records,
    media_file_is_usable,
    transcript_covers_video,
    video_artifacts_dir,
)


TARGET_DIRECTIONS = (
    "赚钱",
    "财富策略",
    "创业",
    "商业机会",
    "自媒体",
    "短视频",
    "表达文案",
    "结构化理解",
    "阅读输入",
    "认知升级",
    "个人成长",
    "人生策略",
    "技能沉淀",
)

SKILL_DEPOSITION_KEYWORDS = (
    "技能",
    "积累",
    "资产",
    "产品化",
    "作品",
    "模板",
    "系统",
    "写作",
    "销售",
    "自学",
)


def keywords_for(direction: str) -> tuple[str, ...]:
    if direction == "技能沉淀":
        return SKILL_DEPOSITION_KEYWORDS
    return tuple(DIRECTION_KEYWORDS[direction])


def relevance_score(record: NormalizedRecord, direction: str) -> int:
    title = record.title.lower()
    body = record.body.lower()
    tags = " ".join(record.tags).lower()
    score = 0
    for keyword in keywords_for(direction):
        needle = keyword.lower()
        score += title.count(needle) * 5
        score += tags.count(needle) * 3
        score += body.count(needle)
    return score


def has_complete_material(root: Path, record: NormalizedRecord) -> bool:
    artifact_dir = video_artifacts_dir(root) / f"{record.platform}_{record.source_id}"
    video = artifact_dir / "source.mp4"
    transcript_json = artifact_dir / "transcript.json"
    transcript_srt = artifact_dir / "transcript.srt"
    return (
        media_file_is_usable(video)
        and transcript_srt.is_file()
        and transcript_srt.stat().st_size > 0
        and transcript_covers_video(video, transcript_json)
    )


def build_download_plan(root: Path, records: list[NormalizedRecord], top_n: int = 10) -> dict[str, Any]:
    account_records = [record for record in records if (record.account_name or record.author_name) == "姜胡说"]
    candidates: dict[str, list[NormalizedRecord]] = {direction: [] for direction in TARGET_DIRECTIONS}
    for record in account_records:
        scores = {direction: relevance_score(record, direction) for direction in TARGET_DIRECTIONS}
        best_score = max(scores.values(), default=0)
        if best_score <= 0:
            continue
        primary = next(direction for direction in TARGET_DIRECTIONS if scores[direction] == best_score)
        candidates[primary].append(record)
    used: set[str] = set()
    targets: list[dict[str, Any]] = []

    for direction in TARGET_DIRECTIONS:
        ranked = sorted(
            candidates[direction],
            key=lambda record: (relevance_score(record, direction), heat_score(record), sum(record.metrics.values())),
            reverse=True,
        )
        selected = [record for record in ranked if record.source_id not in used][:top_n]
        for rank, record in enumerate(selected, start=1):
            used.add(record.source_id)
            complete = has_complete_material(root, record)
            secondary = [
                item
                for item in TARGET_DIRECTIONS
                if item != direction and relevance_score(record, item) > 0
            ]
            targets.append(
                {
                    "source_id": record.source_id,
                    "platform": record.platform,
                    "account_name": "姜胡说",
                    "title": record.title,
                    "source_url": record.url,
                    "primary_direction": direction,
                    "secondary_directions": secondary,
                    "direction_rank": rank,
                    "relevance_score": relevance_score(record, direction),
                    "heat_score": heat_score(record),
                    "selection_reason": f"{direction}关键词相关度与内容热度综合排序第 {rank} 名",
                    "material_status": "complete" if complete else "missing",
                    "needs_download": not complete,
                }
            )

    targets.sort(key=lambda item: (TARGET_DIRECTIONS.index(item["primary_direction"]), item["direction_rank"]))
    download_items = [dict(item, status="pending") for item in targets if item["needs_download"]]
    counts = {
        direction: {
            "target": sum(1 for item in targets if item["primary_direction"] == direction),
            "complete": sum(1 for item in targets if item["primary_direction"] == direction and not item["needs_download"]),
            "pending_download": sum(1 for item in download_items if item["primary_direction"] == direction),
        }
        for direction in TARGET_DIRECTIONS
    }
    return {"targets": targets, "download_items": download_items, "direction_counts": counts}


def write_plan(root: Path) -> dict[str, Any]:
    records, raw_counts, dedupe_stats = load_unique_records(root)
    result = build_download_plan(root, records)
    generated_at = datetime.now().isoformat(timespec="seconds")
    plans_dir = root / "10_Knowledge" / "candidates" / "review_registers" / "plans"
    queues_dir = root / "90_Temp" / "scratch" / "video_learning" / "queues"
    plans_dir.mkdir(parents=True, exist_ok=True)
    queues_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / "jianghushuo_primary_top10.json"
    queue_path = queues_dir / "jianghushuo_all_directions_download.json"
    plan_payload = {
        "generated_at": generated_at,
        "account_name": "姜胡说",
        "top_n": 10,
        "directions": list(TARGET_DIRECTIONS),
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "direction_counts": result["direction_counts"],
        "items": result["targets"],
    }
    queue_payload = {"generated_at": generated_at, "status": "pending", "items": result["download_items"]}
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    queue_path.write_text(json.dumps(queue_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "plan": str(plan_path.relative_to(root)),
        "queue": str(queue_path.relative_to(root)),
        "target_count": len(result["targets"]),
        "download_count": len(result["download_items"]),
        "direction_counts": result["direction_counts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan unique Jianghushuo Top10 downloads by primary direction.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = write_plan(Path(args.root).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
