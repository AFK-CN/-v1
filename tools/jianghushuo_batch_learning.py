from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.jianghushuo_nas import CURRENT_ACCOUNT_DIR
from tools.jianghushuo_v2_audit import audit_batch
from tools.jianghushuo_v2_learning import WORKFLOW_ROOT, evidence_ready_sequence, read_json, run_batch, write_json


def aggregate_gate_status(root: Path, expected_count: int, batch_size: int) -> dict[str, Any]:
    workflow = root.resolve() / WORKFLOW_ROOT
    final_batch = (expected_count + batch_size - 1) // batch_size
    batches: list[dict[str, Any]] = []
    missing: list[str] = []
    for batch_number in range(1, final_batch + 1):
        batch_id = f"batch_{batch_number:02d}"
        path = workflow / "batches" / batch_id / "gate_audit.json"
        if not path.is_file():
            missing.append(batch_id)
            continue
        gate = read_json(path)
        metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
        batches.append(
            {
                "batch_id": batch_id,
                "ok": bool(gate.get("ok")),
                "card_count": int(metrics.get("card_count") or 0),
                "substantive_card_count": int(metrics.get("substantive_card_count") or 0),
                "effective_candidate_count": int(metrics.get("effective_candidate_count") or 0),
                "max_pair_similarity": float(metrics.get("max_pair_similarity") or 0.0),
                "errors": gate.get("errors") or [],
            }
        )
    return {
        "ok": not missing and len(batches) == final_batch and all(item["ok"] for item in batches),
        "expected_batch_count": final_batch,
        "audited_batch_count": len(batches),
        "missing_batches": missing,
        "card_count": sum(item["card_count"] for item in batches),
        "substantive_card_count": sum(item["substantive_card_count"] for item in batches),
        "effective_candidate_count": sum(item["effective_candidate_count"] for item in batches),
        "max_pair_similarity": max((item["max_pair_similarity"] for item in batches), default=0.0),
        "batches": batches,
    }


def run(
    root: Path,
    nas_root: Path,
    *,
    from_batch: int,
    to_batch: int,
    batch_size: int = 10,
    force: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    sequence = evidence_ready_sequence(root, nas_root)
    final_batch = (len(sequence) + batch_size - 1) // batch_size
    start = max(from_batch, 1)
    end = min(max(to_batch, start), final_batch)
    status_path = root / WORKFLOW_ROOT / "BATCH_GATE_STATUS.json"
    summary: dict[str, Any] = {
        "ok": True,
        "workflow_id": "jianghushuo-v2-full",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_ready_count": len(sequence),
        "batch_size": batch_size,
        "batch_range": [start, end],
        "completed_batches": [],
        "failed_batch": "",
        "formal_write_allowed": False,
    }
    write_json(status_path, summary)

    for batch_number in range(start, end + 1):
        learning = run_batch(
            root,
            nas_root,
            batch_number,
            batch_size,
            force=force,
            render_only=True,
            evidence_ready_scope=True,
            scope_sequence=sequence,
        )
        gate = audit_batch(root, nas_root, batch_number)
        item = {
            "batch_id": f"batch_{batch_number:02d}",
            "learning_ok": bool(learning.get("ok")),
            "gate_ok": bool(gate.get("ok")),
            "card_count": gate["metrics"]["card_count"],
            "substantive_card_count": gate["metrics"]["substantive_card_count"],
            "effective_candidate_count": gate["metrics"]["effective_candidate_count"],
            "max_pair_similarity": gate["metrics"]["max_pair_similarity"],
            "errors": gate.get("errors") or [],
        }
        summary["completed_batches"].append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
        if not learning.get("ok") or not gate.get("ok"):
            summary["ok"] = False
            summary["failed_batch"] = item["batch_id"]
            write_json(status_path, summary)
            break
        write_json(status_path, summary)

    summary["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    summary["aggregate_gate_status"] = aggregate_gate_status(root, len(sequence), batch_size)
    summary["ok"] = bool(summary["ok"] and summary["aggregate_gate_status"]["ok"])
    write_json(status_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn Jianghushuo evidence-ready content batch by batch with an automatic audit gate.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default=str(CURRENT_ACCOUNT_DIR))
    parser.add_argument("--from-batch", type=int, default=1)
    parser.add_argument("--to-batch", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--no-force", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    if args.summarize_only:
        root = Path(args.root).resolve()
        sequence = evidence_ready_sequence(root, Path(args.nas_root))
        aggregate = aggregate_gate_status(root, len(sequence), max(args.batch_size, 1))
        result = {
            "ok": aggregate["ok"],
            "workflow_id": "jianghushuo-v2-full",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "evidence_ready_count": len(sequence),
            "batch_size": max(args.batch_size, 1),
            "aggregate_gate_status": aggregate,
            "formal_write_allowed": False,
        }
        write_json(root / WORKFLOW_ROOT / "BATCH_GATE_STATUS.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2
    result = run(
        Path(args.root),
        Path(args.nas_root),
        from_batch=max(args.from_batch, 1),
        to_batch=max(args.to_batch, 1),
        batch_size=max(args.batch_size, 1),
        force=not args.no_force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
