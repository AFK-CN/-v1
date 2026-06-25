from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import SYSTEM_DIR, as_posix, now_iso, validate_task_status


def tasks_root(root: Path) -> Path:
    return runtime_path(root, "tasks")


def task_id_for(task_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task_name).strip("_") or "task"
    return f"kb_task_{now_iso().replace(':', '').replace('-', '').replace('T', '_')}_{safe}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def create_task(root: Path, task_name: str, command: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root.resolve()
    task_id = task_id_for(task_name)
    task_dir = tasks_root(root) / "pending" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "task_id": task_id,
        "task_name": task_name,
        "task_status": "pending",
        "command": command,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_json(task_dir / "status.json", status)
    (task_dir / "task.md").write_text(f"# {task_name}\n\n命令：`{command}`\n", encoding="utf-8")
    (task_dir / "action_log.md").write_text(f"# 行动日志\n\n- {now_iso()} 创建任务。\n", encoding="utf-8")
    (task_dir / "summary_report.md").write_text("# 摘要报告\n\n任务尚未完成。\n", encoding="utf-8")
    (task_dir / "errors.log").write_text("", encoding="utf-8")
    write_json(task_dir / "outputs_manifest.json", {"outputs": []})
    if payload is not None:
        write_json(task_dir / "request.json", payload)
    return {"task_id": task_id, "task_dir": as_posix(task_dir.relative_to(root)), "task_status": "pending"}


def find_task_dir(root: Path, task_id: str) -> Path:
    for status in ("pending", "running", "stale", "done", "failed", "paused"):
        candidate = tasks_root(root) / status / task_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"task not found: {task_id}")


def move_task_dir(root: Path, task_id: str, status: str) -> Path:
    validate_task_status(status)
    current = find_task_dir(root, task_id)
    target = tasks_root(root) / status / task_id
    target.parent.mkdir(parents=True, exist_ok=True)
    if current != target:
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(current), str(target))
    return target


def finish_task(root: Path, task_id: str, status: str, summary: str, outputs: list[str] | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    if status not in {"done", "failed", "paused"}:
        raise ValueError("finish_task status must be done, failed, or paused")
    root = root.resolve()
    task_dir = move_task_dir(root, task_id, status)
    status_path = task_dir / "status.json"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    data["task_status"] = status
    data["updated_at"] = now_iso()
    write_json(status_path, data)
    with (task_dir / "action_log.md").open("a", encoding="utf-8") as handle:
        handle.write(f"- {now_iso()} 任务状态更新为 `{status}`。\n")
    (task_dir / "summary_report.md").write_text(f"# 摘要报告\n\n{summary}\n", encoding="utf-8")
    (task_dir / "errors.log").write_text("\n".join(errors or []), encoding="utf-8")
    write_json(task_dir / "outputs_manifest.json", {"outputs": outputs or [], "updated_at": now_iso()})
    return {"task_id": task_id, "task_status": status, "task_dir": as_posix(task_dir.relative_to(root))}
