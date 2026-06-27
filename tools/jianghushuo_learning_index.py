from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ACCOUNT_ID = "jianghushuo"
ACCOUNT_NAME = "姜胡说"
BASE_DIR = Path("10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo")
SCOPE_PATH = Path("10_Knowledge/candidates/account_assets/content_rough_scan/jianghushuo/deep_learning_scope.json")
ROUGH_SCAN_DIR = Path("10_Knowledge/candidates/account_assets/content_rough_scan/jianghushuo/directions")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def as_posix(path: Path) -> str:
    return path.as_posix()


def scope_items(root: Path) -> list[dict[str, Any]]:
    payload = read_json(root / SCOPE_PATH, {"items": []})
    return payload.get("items", payload) if isinstance(payload, dict) else payload


def parse_card_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    metadata: dict[str, str] = {}
    for line in text.splitlines()[:40]:
        match = re.match(r"^(source_id|原视频链接|账号|平台|主方向|辅方向|学习批次|状态)[:：]\s*(.*)$", line.strip())
        if match:
            metadata[match.group(1)] = match.group(2).strip()
    title_match = re.search(r"^#\s*视频深度学习卡[:：]\s*(.+)$", text, re.MULTILINE)
    if title_match:
        metadata["标题"] = title_match.group(1).strip()
    return metadata


def card_index(root: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    base = root / BASE_DIR
    for path in sorted(base.glob("*/cards/*.md")):
        metadata = parse_card_metadata(path)
        source_id = metadata.get("source_id", "")
        if not source_id:
            continue
        cards[source_id] = {
            "source_id": source_id,
            "title": metadata.get("标题", ""),
            "primary_direction": metadata.get("主方向", ""),
            "status": metadata.get("状态", ""),
            "card_path": as_posix(path.relative_to(root)),
            "source_url": metadata.get("原视频链接", ""),
        }
    return cards


def direction_paths(root: Path, direction: str) -> dict[str, str]:
    base = root / BASE_DIR / direction
    report = base / "方向验收报告.md"
    return {
        "summary_path": as_posix((base / "方向方法论总结.md").relative_to(root)) if (base / "方向方法论总结.md").exists() else "",
        "rough_scan_path": as_posix((base / "粗扫内容和选题.md").relative_to(root)) if (base / "粗扫内容和选题.md").exists() else "",
        "cards_dir": as_posix((base / "cards").relative_to(root)) if (base / "cards").exists() else "",
        "acceptance_report_path": as_posix(report.relative_to(root)) if report.exists() else "",
    }


def rough_stats(root: Path, direction: str) -> dict[str, int]:
    insights = read_json(root / ROUGH_SCAN_DIR / direction / "rough_scan_insights.json", {})
    return {
        "topic_cluster_count": len(insights.get("topic_clusters", [])),
        "candidate_deep_learning_count": len(insights.get("candidate_deep_learning", [])),
        "needs_video_review_count": len(insights.get("needs_video_review", [])),
    }


def sync_rough_scan_packages(root: Path) -> int:
    synced = 0
    canonical_base = root / ROUGH_SCAN_DIR
    package_base = root / BASE_DIR
    if not canonical_base.exists():
        return synced
    for source_dir in sorted(path for path in canonical_base.iterdir() if path.is_dir()):
        target_dir = package_base / source_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in ("粗扫内容和选题.md", "rough_scan_insights.json"):
            source = source_dir / name
            if not source.exists():
                continue
            shutil.copyfile(source, target_dir / name)
            synced += 1
    return synced


def build_learning_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    scope = scope_items(root)
    cards = card_index(root)
    by_direction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    items: list[dict[str, Any]] = []
    for item in scope:
        source_id = str(item.get("source_id", ""))
        card = cards.get(source_id, {})
        direction = str(item.get("primary_direction", card.get("primary_direction", "")))
        status = str(item.get("learning_status") or card.get("status") or ("confirmed_learned" if item.get("confirmed_learned") else "pending"))
        row = {
            "source_id": source_id,
            "primary_direction": direction,
            "status": status,
            "source_url": item.get("source_url") or card.get("source_url", ""),
            "title": item.get("title") or card.get("title", ""),
            "card_path": item.get("card_path") or card.get("card_path", ""),
        }
        items.append(row)
        by_direction[direction].append(row)
    directions = []
    for direction in sorted(by_direction, key=lambda value: list(by_direction).index(value)):
        rows = by_direction[direction]
        counts = Counter(row["status"] for row in rows)
        directions.append(
            {
                "direction": direction,
                "target_count": len(rows),
                "confirmed_count": counts.get("confirmed_learned", 0),
                "evidence_gap_count": counts.get("evidence_gap", 0),
                "pending_count": len(rows) - counts.get("confirmed_learned", 0) - counts.get("evidence_gap", 0),
                **direction_paths(root, direction),
                "rough_scan": rough_stats(root, direction),
            }
        )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "account_id": ACCOUNT_ID,
        "account_name": ACCOUNT_NAME,
        "scope_count": len(scope),
        "unique_source_id_count": len({item["source_id"] for item in items}),
        "direction_count": len(directions),
        "directions": directions,
        "items": sorted(items, key=lambda item: (item["primary_direction"], item["source_id"])),
        "read_order": [
            "姜胡说学习索引.md",
            "姜胡说整体方法论.md",
            "方向方法论总结.md",
            "cards/*.md",
            "粗扫内容和选题.md",
        ],
    }


def render_learning_index(index: dict[str, Any]) -> str:
    lines = [
        "# 姜胡说学习索引",
        "",
        f"生成时间：{index['generated_at']}",
        f"账号：{index['account_name']}",
        f"权威范围：{index['scope_count']}条",
        f"唯一 source_id：{index['unique_source_id_count']}个",
        "",
        "## AI 读取顺序",
        "",
    ]
    lines.extend(f"{number}. `{item}`" for number, item in enumerate(index["read_order"], start=1))
    lines.extend(
        [
            "",
            "## 方向入口",
            "",
            "| 方向 | 目标 | 已确认 | 证据缺口 | 待处理 | 方向总结 | 粗扫 | cards |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for item in index["directions"]:
        lines.append(
            f"| {item['direction']} | {item['target_count']} | {item['confirmed_count']} | {item['evidence_gap_count']} | "
            f"{item['pending_count']} | {item['summary_path']} | {item['rough_scan_path']} | {item['cards_dir']} |"
        )
    lines.extend(
        [
            "",
            "## 粗扫状态",
            "",
            "| 方向 | 主题簇 | 候补深学 | 需视频复核 |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in index["directions"]:
        rough = item["rough_scan"]
        lines.append(
            f"| {item['direction']} | {rough['topic_cluster_count']} | {rough['candidate_deep_learning_count']} | {rough['needs_video_review_count']} |"
        )
    lines.extend(
        [
            "",
            "## 视频索引",
            "",
            "| source_id | 主方向 | 状态 | 单卡 | 原链接 |",
            "|---|---|---|---|---|",
        ]
    )
    for item in index["items"]:
        lines.append(
            f"| {item['source_id']} | {item['primary_direction']} | {item['status']} | {item['card_path']} | {item['source_url']} |"
        )
    return "\n".join(lines) + "\n"


def write_learning_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    synced_rough_scan_files = sync_rough_scan_packages(root)
    index = build_learning_index(root)
    target_dir = root / BASE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    write_json(target_dir / "jianghushuo_learning_index.json", index)
    (target_dir / "姜胡说学习索引.md").write_text(render_learning_index(index), encoding="utf-8")
    return {
        "account_name": index["account_name"],
        "scope_count": index["scope_count"],
        "unique_source_id_count": index["unique_source_id_count"],
        "direction_count": index["direction_count"],
        "synced_rough_scan_files": synced_rough_scan_files,
        "markdown": as_posix((target_dir / "姜胡说学习索引.md").relative_to(root)),
        "json": as_posix((target_dir / "jianghushuo_learning_index.json").relative_to(root)),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build Jianghushuo learning indexes.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    print(json.dumps(write_learning_index(Path(args.root)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
