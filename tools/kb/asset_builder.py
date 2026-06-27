from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import video_learning

from .schemas import SYSTEM_DIR, now_iso
from .candidate_assets import candidate_assets_dir


def assets_dir(root: Path) -> Path:
    return candidate_assets_dir(root)


def topic_candidate(item: video_learning.RankedRecord) -> dict[str, Any]:
    record = item.record
    return {
        "topic_id": f"candidate-{record.platform}-{item.direction}-{record.source_id}",
        "platform": record.platform,
        "领域": item.direction,
        "人群": video_learning.infer_audience(item.direction, record),
        "场景": "从高表现内容或原始资料中提取的待验证场景",
        "痛点": video_learning.first_sentence(record.body or record.title, 80),
        "内容承诺": f"围绕{item.direction}拆出可执行方法或内容角度",
        "爆点": "由互动指标和主题命中共同判断",
        "形式": "口播短视频/图文改写" if record.platform == "douyin" else "图文/短视频均可",
        "参考方法": f"{record.platform}:{record.source_id}",
        "可生成标题": [record.title],
        "正文/脚本方向": video_learning.reusable_template(item.direction, record),
        "证据": record.url,
        "优先级": "high" if item.rank <= 3 else "medium",
        "状态": "candidate",
        "account_name": record.account_name or record.author_name,
        "source_url": record.url,
        "source_file": record.source_file,
        "source_id": record.source_id,
        "score": item.score,
        "rank": item.rank,
        "metrics": record.metrics,
        "has_video_download_url": bool(record.video_download_url),
    }


def build_candidate_assets(root: Path, top_n: int = 10) -> dict[str, Any]:
    root = root.resolve()
    target = assets_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    records, raw_counts, dedupe_stats, failed_files = video_learning.load_unique_records_detailed(root)
    rankings = video_learning.build_direction_rankings(records, limit=top_n)
    candidates = [topic_candidate(item) for ranked in rankings.values() for item in ranked]
    write_jsonl(target / "candidate_topics.jsonl", candidates)
    write_asset_state(root, candidates)
    (target / "candidate_top10_by_category.md").write_text(render_top10(rankings), encoding="utf-8")
    (target / "candidate_viral_structures.md").write_text(render_simple_pool("爆款结构候选", candidates, "正文/脚本方向"), encoding="utf-8")
    (target / "candidate_pain_points.md").write_text(render_simple_pool("人群痛点候选", candidates, "痛点"), encoding="utf-8")
    (target / "candidate_expression_templates.md").write_text(render_simple_pool("表达模板候选", candidates, "正文/脚本方向"), encoding="utf-8")
    (target / "candidate_method_cards.md").write_text(render_method_cards(candidates), encoding="utf-8")
    (target / "candidate_comment_insights.md").write_text("# 评论洞察候选\n\n本版本暂未解析评论正文，等待评论处理器补齐。\n", encoding="utf-8")
    return {
        "generated_at": now_iso(),
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
        "partial_success": bool(failed_files),
        "directions": len(rankings),
        "candidate_topics_count": len(candidates),
        "assets_dir": str(target.relative_to(root)),
    }


def write_asset_state(root: Path, candidates: list[dict[str, Any]]) -> None:
    state_dir = root.resolve() / "00_System" / "runtime" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "generated_at": now_iso(),
        "items": [
            {
                "topic_id": item["topic_id"],
                "content_status": item["状态"],
                "platform": item["platform"],
                "account_name": item["account_name"],
                "source_id": item["source_id"],
                "source_url": item["source_url"],
                "category": item["领域"],
            }
            for item in candidates
        ],
    }
    (state_dir / "asset_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def render_top10(rankings: dict[str, list[video_learning.RankedRecord]]) -> str:
    lines = ["# 候选选题 Top10", "", f"生成时间：{now_iso()}", ""]
    for direction, ranked in rankings.items():
        lines.extend([f"## {direction}", "", "| 排名 | 平台 | 账号 | 标题 | 分数 | 原链接 |", "| ---: | --- | --- | --- | ---: | --- |"])
        for item in ranked:
            record = item.record
            title = record.title.replace("\n", " ")[:80]
            lines.append(f"| {item.rank} | {record.platform} | {record.account_name or record.author_name} | {title} | {item.score} | {record.url} |")
        lines.append("")
    return "\n".join(lines)


def render_simple_pool(title: str, candidates: list[dict[str, Any]], field: str) -> str:
    lines = [f"# {title}", "", "全部内容均为候选，不等于正式知识。", ""]
    seen = set()
    for item in candidates:
        value = str(item.get(field, "")).strip()
        key = (item["领域"], value)
        if not value or key in seen:
            continue
        seen.add(key)
        lines.append(f"- {item['领域']} / {item['account_name']}：{value}（来源：{item['source_url']}）")
    return "\n".join(lines) + "\n"


def render_method_cards(candidates: list[dict[str, Any]]) -> str:
    lines = ["# 方法论候选卡片", "", "全部内容均为候选，需 Codex 审核和用户确认后才能正式沉淀。", ""]
    for item in candidates:
        lines.extend(
            [
                f"## {item['领域']} / {item['account_name']} / {item['source_id']}",
                "",
                f"- 原链接：{item['source_url']}",
                f"- 候选方法：{item['正文/脚本方向']}",
                f"- 证据：{item['证据']}",
                f"- 状态：{item['状态']}",
                "",
            ]
        )
    return "\n".join(lines)
