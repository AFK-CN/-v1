from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.jianghushuo_v2_learning import (
    WORKFLOW_ID,
    WORKFLOW_ROOT,
    evidence_ready_sequence,
    full_relearning_sequence,
    relearning_sequence,
    write_json,
)
from tools.jianghushuo_nas import CURRENT_ACCOUNT_DIR, evidence_status


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def build_report(root: Path, nas_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    full = full_relearning_sequence(root)
    ready = evidence_ready_sequence(root, nas_root)
    priority_ids = {item["source_id"] for item in relearning_sequence(root)}
    ready_ids = {item["source_id"] for item in ready}
    blocked: list[dict[str, Any]] = []
    for item in full:
        source_id = item["source_id"]
        if source_id in ready_ids:
            continue
        status = evidence_status(source_id, nas_root)
        missing = [
            name
            for name, field in (
                ("video", "has_video"),
                ("transcript", "has_transcript"),
                ("keyframes", "has_keyframes"),
                ("scenes", "has_scenes"),
            )
            if not status.get(field)
        ]
        blocked.append(
            {
                "source_id": source_id,
                "direction": item.get("direction"),
                "status": "blocked_missing_evidence",
                "missing": missing,
                "artifact_dir": status.get("artifact_dir"),
            }
        )
    counts_by_missing: dict[str, int] = {}
    for item in blocked:
        key = "+".join(item["missing"]) or "unknown"
        counts_by_missing[key] = counts_by_missing.get(key, 0) + 1
    report = {
        "ok": True,
        "workflow_id": WORKFLOW_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "nas_plan_count": len(full),
        "evidence_ready_count": len(ready),
        "priority_relearned_count": len(priority_ids),
        "additional_evidence_ready_count": len(ready_ids - priority_ids),
        "blocked_count": len(blocked),
        "counts_by_missing": counts_by_missing,
        "blocked_items": blocked,
        "formal_write_allowed": False,
    }
    workflow = root / WORKFLOW_ROOT
    write_json(workflow / "EVIDENCE_GAP_STATUS.json", report)
    lines = [
        "# 姜胡说 NAS 全量证据缺口",
        "",
        f"- NAS 计划：{len(full)} 条",
        f"- 有完整逐字稿、可进入重学：{len(ready)} 条",
        f"- 其中原正式卡优先范围：{len(priority_ids)} 条",
        f"- 新增证据可用扩展：{len(ready_ids - priority_ids)} 条",
        f"- 缺证据阻断：{len(blocked)} 条",
        "- 处理边界：阻断项不生成正式学习结论，不进入阶段 2 方法验证。",
        "",
        "## 缺失组合",
        "",
    ]
    lines.extend(f"- `{key}`：{count} 条" for key, count in sorted(counts_by_missing.items()))
    lines.extend(["", "## 待补证据清单", "", "| source_id | 方向 | 缺失 | NAS 目录 |", "| --- | --- | --- | --- |"])
    lines.extend(
        f"| {item['source_id']} | {item['direction']} | {', '.join(item['missing']) or 'unknown'} | {item['artifact_dir']} |"
        for item in blocked
    )
    lines.append("")
    (workflow / "EVIDENCE_GAP_STATUS.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Jianghushuo NAS evidence-gap report.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default=str(CURRENT_ACCOUNT_DIR))
    args = parser.parse_args()
    report = build_report(Path(args.root), Path(args.nas_root))
    print(json.dumps({key: value for key, value in report.items() if key != "blocked_items"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
