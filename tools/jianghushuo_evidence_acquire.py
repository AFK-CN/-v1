from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.video_learning import (
    NormalizedRecord,
    artifact_bundle_status,
    load_unique_records_detailed,
    media_file_is_usable,
    run_selected_deep_learning,
)


ACCOUNT_NAME = "姜胡说"
WORKFLOW_REL = Path("10_Knowledge/candidates/account_learning_workflows/jianghushuo-v2-full")


def read_plan(account_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads((account_dir / "_learning_plan.json").read_text(encoding="utf-8"))
    items = payload.get("items", {}) if isinstance(payload, dict) else {}
    if not isinstance(items, dict):
        raise ValueError("NAS learning plan items must be an object")
    return [item for item in items.values() if isinstance(item, dict)]


def bundle_ready(account_dir: Path, source_id: str) -> bool:
    state = artifact_bundle_status(account_dir / f"douyin_{source_id}")
    return all(state.get(key) for key in ("has_video", "has_transcript", "has_keyframes", "has_scenes"))


def acquisition_inventory(
    plan: list[dict[str, Any]],
    by_id: dict[str, NormalizedRecord],
    account_dir: Path,
) -> dict[str, Any]:
    ready: list[str] = []
    eligible: list[str] = []
    unavailable: list[str] = []
    missing_record: list[str] = []
    for item in plan:
        source_id = str(item.get("source_id") or "")
        if not source_id:
            continue
        if bundle_ready(account_dir, source_id):
            ready.append(source_id)
            continue
        record = by_id.get(source_id)
        if record is None:
            missing_record.append(source_id)
            continue
        local_video = account_dir / f"douyin_{source_id}" / "source.mp4"
        if record.video_download_url or media_file_is_usable(local_video):
            eligible.append(source_id)
        else:
            unavailable.append(source_id)
    def chronological_key(source_id: str) -> tuple[int, str]:
        return (int(source_id), source_id) if source_id.isdigit() else (10**30, source_id)

    return {
        "plan_count": len(plan),
        "ready_ids": ready,
        "eligible_ids": sorted(eligible, key=chronological_key),
        "unavailable_video_url_ids": sorted(unavailable, key=chronological_key),
        "missing_record_ids": sorted(missing_record, key=chronological_key),
    }


def write_status(root: Path, status: dict[str, Any]) -> None:
    workflow = root / WORKFLOW_REL
    workflow.mkdir(parents=True, exist_ok=True)
    status_path = workflow / "EVIDENCE_ACQUISITION_STATUS.json"
    history_path = workflow / "EVIDENCE_ACQUISITION_HISTORY.jsonl"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(status, ensure_ascii=False) + "\n")


def run_batch(root: Path, nas_root: Path, batch_size: int) -> dict[str, Any]:
    account_dir = nas_root / ACCOUNT_NAME
    plan = read_plan(account_dir)
    records, raw_counts, dedupe_stats, failed_files = load_unique_records_detailed(root)
    by_id = {
        record.source_id: record
        for record in records
        if (record.account_name or record.author_name) == ACCOUNT_NAME and record.source_id
    }
    before = acquisition_inventory(plan, by_id, account_dir)
    selected = before["eligible_ids"][: max(batch_size, 0)]
    learning_result: dict[str, Any] = {}
    if selected:
        learning_result = run_selected_deep_learning(
            root,
            source_ids=set(selected),
            analyze_video=True,
            video_limit=len(selected),
            force=True,
            artifacts_dir=nas_root,
            artifact_layout="account",
            account_name=ACCOUNT_NAME,
            mirror_nas_state=True,
        )
    after = acquisition_inventory(plan, by_id, account_dir)
    status = {
        "ok": True,
        "account_name": ACCOUNT_NAME,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_size": batch_size,
        "selected_ids": selected,
        "plan_count": after["plan_count"],
        "complete_bundle_count": len(after["ready_ids"]),
        "remaining_eligible_count": len(after["eligible_ids"]),
        "unavailable_video_url_count": len(after["unavailable_video_url_ids"]),
        "unavailable_video_url_ids": after["unavailable_video_url_ids"],
        "missing_record_count": len(after["missing_record_ids"]),
        "newly_completed_count": len(after["ready_ids"]) - len(before["ready_ids"]),
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
        "learning_result": learning_result,
    }
    write_status(root, status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire complete NAS evidence bundles for Jianghushuo relearning.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default="/Volumes/AFK/zhishikushuju")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    result = run_batch(Path(args.root).resolve(), Path(args.nas_root).expanduser().resolve(), max(args.batch_size, 0))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
