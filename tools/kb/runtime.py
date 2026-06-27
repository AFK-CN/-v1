from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .schemas import FORMAL_KNOWLEDGE_DIRS, SYSTEM_DIR, active_skills_dir, as_posix, now_iso


RUNTIME_SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.0"
MIGRATION_VERSIONS = ("legacy_runtime_v1", "candidate_assets_runtime_v2")
MIGRATION_VERSION = MIGRATION_VERSIONS[-1]
RUNTIME_SECTIONS = ("state", "cache", "reports", "logs", "tasks", "locks", "quarantine")
TASK_STATES = ("pending", "running", "stale", "done", "failed", "paused")
CONTROL_FILES = (
    "知识库入口.md",
    "14_KB_System/index/controller_routes.json",
    "14_KB_System/index/task_entry_index.md",
    "14_KB_System/index/account_knowledge_index.json",
    "14_KB_System/config/output_contracts.json",
    "14_KB_System/config/search_terms.json",
    "14_KB_System/config/skill_contract.json",
    "14_KB_System/config/layer_map.json",
    "14_KB_System/rules/初始化生命周期.md",
    "14_KB_System/skill_packages/知识库/SKILL.md",
    "tools/kb/runtime.py",
    "tools/kb/cli.py",
    "tools/kb/schemas.py",
)
FULL_FINGERPRINT_DIRS = (
    *FORMAL_KNOWLEDGE_DIRS,
    "14_KB_System/config",
)


def runtime_root(root: Path) -> Path:
    return root.resolve() / "00_System" / "runtime"


def runtime_path(root: Path, section: str) -> Path:
    if section not in RUNTIME_SECTIONS:
        raise ValueError(f"unknown runtime section: {section}")
    return runtime_root(root) / section


def manifest_path(root: Path) -> Path:
    return runtime_path(root, "state") / "runtime_manifest.json"


def credential_path(root: Path) -> Path:
    return runtime_path(root, "state") / "health_credential.json"


def dirty_state_path(root: Path) -> Path:
    return runtime_path(root, "state") / "dirty_generation.json"


def maintenance_lock_path(root: Path) -> Path:
    return runtime_path(root, "locks") / "maintenance.lock"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def root_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20]


def local_day() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def ensure_runtime_dirs(root: Path) -> None:
    for section in RUNTIME_SECTIONS:
        runtime_path(root, section).mkdir(parents=True, exist_ok=True)
    for state in TASK_STATES:
        (runtime_path(root, "tasks") / state).mkdir(parents=True, exist_ok=True)


def runtime_layout_complete(root: Path) -> bool:
    return all(runtime_path(root, section).is_dir() for section in RUNTIME_SECTIONS) and all(
        (runtime_path(root, "tasks") / state).is_dir() for state in TASK_STATES
    )


def control_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    root = root.resolve()
    for relative in CONTROL_FILES:
        path = root / relative
        digest.update(relative.encode("utf-8"))
        if path.exists():
            stat = path.stat()
            digest.update(f"{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
        else:
            digest.update(b"missing")
    git_head = root / ".git" / "HEAD"
    git_index = root / ".git" / "index"
    for path in (git_head, git_index):
        if path.exists():
            stat = path.stat()
            digest.update(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
    return digest.hexdigest()


def full_knowledge_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    root = root.resolve()
    files: list[Path] = []
    for relative in FULL_FINGERPRINT_DIRS:
        base = root / relative
        if base.is_file():
            files.append(base)
        elif base.exists():
            files.extend(path for path in base.rglob("*") if path.is_file())
    active = active_skills_dir(root)
    if active.exists():
        files.extend(path for path in active.rglob("*") if path.is_file())
    for path in sorted(set(files)):
        relative = path.relative_to(root)
        if SYSTEM_DIR in relative.parts and "runtime" in relative.parts:
            continue
        stat = path.stat()
        digest.update(as_posix(relative).encode("utf-8"))
        digest.update(f":{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
    return digest.hexdigest()


def dirty_state(root: Path) -> dict[str, Any]:
    return read_json(
        dirty_state_path(root),
        {"dirty_generation": 0, "validated_generation": 0, "events": []},
    )


def mark_dirty(root: Path, reason: str, paths: list[str] | None = None) -> dict[str, Any]:
    state = dirty_state(root)
    state["dirty_generation"] = int(state.get("dirty_generation", 0)) + 1
    events = list(state.get("events", []))
    events.append({"at": now_iso(), "reason": reason, "paths": paths or []})
    state["events"] = events[-100:]
    write_json(dirty_state_path(root), state)
    return state


def issue_health_credential(
    root: Path,
    full_fingerprint: str | None = None,
    status: str = "healthy",
    actions: list[str] | None = None,
) -> dict[str, Any]:
    state = dirty_state(root)
    generation = int(state.get("dirty_generation", 0))
    state["validated_generation"] = generation
    write_json(dirty_state_path(root), state)
    credential = {
        "root_id": root_id(root),
        "root": str(root.resolve()),
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "day": local_day(),
        "issued_at": now_iso(),
        "status": status,
        "control_fingerprint": control_fingerprint(root),
        "full_knowledge_fingerprint": full_fingerprint or full_knowledge_fingerprint(root),
        "validated_generation": generation,
        "actions": actions or [],
    }
    write_json(credential_path(root), credential)
    return credential


def health_gate(root: Path) -> dict[str, Any]:
    started = time.monotonic()
    root = root.resolve()
    manifest = read_json(manifest_path(root), {})
    credential = read_json(credential_path(root), {})
    reasons: list[str] = []
    if not runtime_root(root).exists() or not manifest or not credential:
        return gate_result(root, "requires_init", ["runtime_or_credential_missing"], started)
    if not runtime_layout_complete(root):
        return gate_result(root, "requires_init", ["runtime_layout_incomplete"], started)
    if (
        manifest.get("schema_version") != RUNTIME_SCHEMA_VERSION
        or credential.get("schema_version") != RUNTIME_SCHEMA_VERSION
    ):
        return gate_result(root, "requires_init", ["schema_mismatch"], started)
    if any(version not in manifest.get("applied_migrations", []) for version in MIGRATION_VERSIONS):
        return gate_result(root, "requires_init", ["migration_required"], started)
    if manifest.get("root_id") != root_id(root) or credential.get("root_id") != root_id(root):
        return gate_result(root, "requires_init", ["root_identity_mismatch"], started)
    if credential.get("status") == "blocked":
        return gate_result(root, "blocked", ["credential_blocked"], started)
    lock = maintenance_lock_path(root)
    if lock.exists():
        return gate_result(root, "maintenance_in_progress", ["maintenance_lock_present"], started)
    if credential.get("day") != local_day():
        reasons.append("credential_day_expired")
    if credential.get("control_fingerprint") != control_fingerprint(root):
        reasons.append("control_fingerprint_changed")
    state = dirty_state(root)
    if int(state.get("dirty_generation", 0)) > int(credential.get("validated_generation", 0)):
        reasons.append("dirty_generation_changed")
    status = "requires_doctor" if reasons else "healthy"
    return gate_result(root, status, reasons, started)


def gate_result(root: Path, status: str, reasons: list[str], started: float) -> dict[str, Any]:
    return {
        "status": status,
        "root_id": root_id(root),
        "credential_path": as_posix(credential_path(root)),
        "reasons": reasons,
        "full_scan_performed": False,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
    }


class MaintenanceLock:
    def __init__(self, root: Path, operation: str, stale_after_seconds: int = 1800) -> None:
        self.root = root.resolve()
        self.operation = operation
        self.path = maintenance_lock_path(root)
        self.owner_token = uuid.uuid4().hex
        self.stale_after_seconds = stale_after_seconds
        self.acquired = False

    def __enter__(self) -> "MaintenanceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError as exc:
            if not reclaim_stale_lock(self.path, self.stale_after_seconds):
                raise RuntimeError("maintenance_in_progress") from exc
            self.path.mkdir()
        write_json(
            self.path / "owner.json",
            {
                "operation": self.operation,
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "started_at": now_iso(),
                "heartbeat_at": now_iso(),
                "owner_token": self.owner_token,
            },
        )
        self.acquired = True
        return self

    def heartbeat(self) -> None:
        if not self.acquired:
            return
        owner = read_json(self.path / "owner.json", {})
        if owner.get("owner_token") != self.owner_token:
            raise RuntimeError("maintenance_lock_not_owned")
        owner["heartbeat_at"] = now_iso()
        write_json(self.path / "owner.json", owner)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self.acquired:
            return
        owner = read_json(self.path / "owner.json", {})
        if owner.get("owner_token") == self.owner_token:
            shutil.rmtree(self.path, ignore_errors=True)
        self.acquired = False


def reclaim_stale_lock(path: Path, stale_after_seconds: int) -> bool:
    owner = read_json(path / "owner.json", {})
    if owner.get("hostname") != socket.gethostname():
        return False
    try:
        heartbeat = datetime.fromisoformat(str(owner.get("heartbeat_at", "")))
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.astimezone()
    except ValueError:
        return False
    age = (datetime.now().astimezone() - heartbeat).total_seconds()
    if age <= stale_after_seconds:
        return False
    try:
        pid = int(owner.get("pid"))
    except (TypeError, ValueError):
        return False
    if process_is_alive(pid):
        return False
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def initialize_runtime(
    root: Path,
    rebuild: bool = True,
    migrate: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "root_id": root_id(root),
            "would_create": [f"{SYSTEM_DIR}/runtime/{section}" for section in RUNTIME_SECTIONS],
            "would_migrate": plan_legacy_migration(root) if migrate else [],
            "would_rebuild": ["skill_packages", "indexes", "dashboard"] if rebuild else [],
        }
    ensure_runtime_dirs(root)
    with MaintenanceLock(root, "init") as lock:
        quarantine_corrupt_state(root)
        existing = read_json(manifest_path(root), {})
        initialized_at = existing.get("initialized_at") or now_iso()
        migrations = list(existing.get("applied_migrations", []))
        migration_actions: list[str] = []
        for version in MIGRATION_VERSIONS:
            if version in migrations:
                continue
            if migrate:
                if version == "legacy_runtime_v1":
                    migration_actions.extend(migrate_legacy_runtime(root))
                elif version == "candidate_assets_runtime_v2":
                    migration_actions.extend(migrate_legacy_candidate_assets(root))
                migrations.append(version)
            elif not plan_legacy_migration(root):
                migrations.append(version)
        manifest = {
            "root_id": root_id(root),
            "root": str(root),
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "migration_version": MIGRATION_VERSION,
            "initialized_at": initialized_at,
            "updated_at": now_iso(),
            "applied_migrations": migrations,
        }
        write_json(manifest_path(root), manifest)
        if not dirty_state_path(root).exists():
            write_json(dirty_state_path(root), {"dirty_generation": 0, "validated_generation": 0, "events": []})
        rebuilt: list[str] = []
        if rebuild:
            rebuilt = rebuild_reproducible_outputs(root)
        lock.heartbeat()
        credential_status = "healthy"
        if rebuild:
            diagnosis = diagnose_system(root)
            if diagnosis["status"] != "healthy":
                credential_status = "blocked"
        credential = issue_health_credential(
            root,
            status=credential_status,
            actions=[*migration_actions, *rebuilt],
        )
        receipt = {
            "ok": credential_status == "healthy",
            "status": credential_status,
            "root_id": root_id(root),
            "runtime": as_posix(runtime_root(root).relative_to(root)),
            "applied_migrations": migrations,
            "migration_actions": migration_actions,
            "rebuilt": rebuilt,
            "credential": as_posix(credential_path(root).relative_to(root)),
        }
        write_json(runtime_path(root, "reports") / "latest_initialization_receipt.json", receipt)
        return receipt


def migrate_legacy_runtime(root: Path) -> list[str]:
    actions: list[str] = []
    system = root / SYSTEM_DIR
    mappings = {
        "state": runtime_path(root, "state"),
        "logs": runtime_path(root, "logs"),
    }
    for name, target in mappings.items():
        source = system / name
        if source.exists():
            actions.extend(move_children(source, target, prefix=name))
    reports = system / "reports"
    if reports.exists():
        for path in sorted(reports.glob("latest_*")):
            target = runtime_path(root, "reports") / path.name
            move_if_needed(path, target)
            actions.append(f"migrate:{path.relative_to(root)}->{target.relative_to(root)}")
    legacy_tasks = system / "tasks"
    if legacy_tasks.exists():
        for state in TASK_STATES:
            source_state = legacy_tasks / state
            if not source_state.exists():
                continue
            for task_dir in sorted(path for path in source_state.iterdir() if path.is_dir()):
                if (task_dir / "status.json").exists():
                    target = runtime_path(root, "tasks") / state / task_dir.name
                else:
                    target = system / "plans" / task_dir.name
                move_if_needed(task_dir, target)
                actions.append(f"migrate:{task_dir.relative_to(root)}->{target.relative_to(root)}")
    return actions


def migrate_legacy_candidate_assets(root: Path) -> list[str]:
    actions: list[str] = []
    source = root / SYSTEM_DIR / "assets"
    if not source.exists():
        return actions
    target = root / "10_Knowledge" / "candidates" / "generated_assets"
    target.mkdir(parents=True, exist_ok=True)
    conflict_dir = runtime_path(root, "quarantine") / "legacy_assets_conflicts"
    for path in sorted(source.iterdir()):
        destination = target / path.name
        if destination.exists():
            conflict_dir.mkdir(parents=True, exist_ok=True)
            quarantine_target = unique_destination(conflict_dir / path.name)
            shutil.move(str(path), str(quarantine_target))
            actions.append(f"quarantine_legacy_asset_conflict:{path.relative_to(root)}->{quarantine_target.relative_to(root)}")
            continue
        shutil.move(str(path), str(destination))
        actions.append(f"migrate_candidate_asset:{path.relative_to(root)}->{destination.relative_to(root)}")
    return actions


def plan_legacy_migration(root: Path) -> list[str]:
    actions: list[str] = []
    system = root / SYSTEM_DIR
    for name in ("state", "logs"):
        source = system / name
        if source.exists():
            actions.extend(f"migrate:{path.relative_to(root)}" for path in sorted(source.iterdir()))
    legacy_assets = system / "assets"
    if legacy_assets.exists():
        for path in sorted(legacy_assets.iterdir()):
            target = root / "10_Knowledge" / "candidates" / "generated_assets" / path.name
            prefix = "quarantine_legacy_asset_conflict" if target.exists() else "migrate_candidate_asset"
            actions.append(f"{prefix}:{path.relative_to(root)}")
    reports = system / "reports"
    if reports.exists():
        actions.extend(f"migrate:{path.relative_to(root)}" for path in sorted(reports.glob("latest_*")))
    tasks = system / "tasks"
    if tasks.exists():
        for state in TASK_STATES:
            state_dir = tasks / state
            if state_dir.exists():
                actions.extend(f"migrate:{path.relative_to(root)}" for path in sorted(state_dir.iterdir()) if path.is_dir())
    return actions


def move_children(source: Path, target: Path, prefix: str) -> list[str]:
    actions: list[str] = []
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        destination = target / path.name
        move_if_needed(path, destination)
        actions.append(f"migrate:{prefix}/{path.name}->{destination}")
    return actions


def move_if_needed(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    shutil.move(str(source), str(target))


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def doctor_runtime(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not read_json(manifest_path(root), {}) or not read_json(credential_path(root), {}):
        return {
            "status": "requires_init",
            "checks": {"manifest": manifest_path(root).exists(), "credential": credential_path(root).exists()},
            "repair_actions": ["kb init"],
        }
    with MaintenanceLock(root, "doctor"):
        fingerprint = full_knowledge_fingerprint(root)
        diagnosis = diagnose_system(root)
        credential = read_json(credential_path(root), {})
        status = diagnosis["status"]
        if status == "healthy" and credential.get("full_knowledge_fingerprint") != fingerprint:
            status = "repairable"
            diagnosis["repair_actions"].append("rebuild_reproducible_outputs")
        result = {
            "status": status,
            "checks": diagnosis["checks"],
            "full_knowledge_fingerprint": fingerprint,
            "repair_actions": diagnosis["repair_actions"],
        }
        if status == "healthy":
            result["credential"] = as_posix(
                credential_path(root).relative_to(root)
            )
            issue_health_credential(root, full_fingerprint=fingerprint)
        return result


def diagnose_system(root: Path) -> dict[str, Any]:
    from .validator import validate_system

    validation = validate_system(root, write_report=False)
    failed = list(validation.get("failed", []))
    repairable_prefixes = (
        "missing:14_KB_System/index/knowledge_index",
        "missing:14_KB_System/index/knowledge_index_summary",
        "missing:14_KB_System/index/formal_knowledge_index",
        "missing:14_KB_System/index/candidate_asset_index",
        "missing:14_KB_System/index/raw_blocked_index",
        "missing:14_KB_System/index/file_relation_index",
        "missing:14_KB_System/index/task_entry_index",
    )
    blocked = [item for item in failed if not item.startswith(repairable_prefixes)]
    if blocked:
        status = "blocked"
    elif failed:
        status = "repairable"
    else:
        status = "healthy"
    return {
        "status": status,
        "checks": {
            "system_validation": not failed,
            "failed": failed,
            "blocked": blocked,
        },
        "repair_actions": ["rebuild_reproducible_outputs"] if status == "repairable" else [],
    }


def quarantine_corrupt_state(root: Path) -> list[str]:
    quarantined: list[str] = []
    for path in (manifest_path(root), credential_path(root), dirty_state_path(root)):
        if not path.exists():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            target = runtime_path(root, "quarantine") / f"{path.stem}_{int(time.time())}{path.suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            quarantined.append(as_posix(target.relative_to(root)))
    return quarantined


def repair_runtime(
    root: Path,
    rebuild: bool = True,
    stale_after_seconds: int = 600,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would_rebuild": ["indexes", "dashboard"] if rebuild else [],
            "would_mark_stale": stale_task_candidates(root, stale_after_seconds),
            "rerun_task_count": 0,
        }
    ensure_runtime_dirs(root)
    with MaintenanceLock(root, "repair"):
        stale = mark_stale_tasks(root, stale_after_seconds)
        rebuilt = rebuild_reproducible_outputs(root) if rebuild else []
        diagnosis = diagnose_system(root) if rebuild else {"status": "healthy"}
        credential_status = "healthy" if diagnosis.get("status") == "healthy" else "blocked"
        credential = issue_health_credential(
            root,
            status=credential_status,
            actions=[*rebuilt, *[f"stale:{task}" for task in stale]],
        )
        result = {
            "ok": credential_status == "healthy",
            "status": credential_status,
            "rebuilt": rebuilt,
            "stale_tasks": stale,
            "rerun_task_count": 0,
            "credential": as_posix(credential_path(root).relative_to(root)),
        }
        write_json(runtime_path(root, "reports") / "latest_repair_report.json", result)
        return result


def mark_stale_tasks(root: Path, stale_after_seconds: int) -> list[str]:
    running = runtime_path(root, "tasks") / "running"
    stale_root = runtime_path(root, "tasks") / "stale"
    stale_root.mkdir(parents=True, exist_ok=True)
    if worker_is_active(root, stale_after_seconds):
        return []
    now = datetime.now().astimezone()
    moved: list[str] = []
    for task_dir in sorted(path for path in running.iterdir() if path.is_dir()):
        status_path = task_dir / "status.json"
        status = read_json(status_path, {})
        heartbeat = status.get("heartbeat_at") or status.get("updated_at")
        try:
            heartbeat_time = datetime.fromisoformat(str(heartbeat))
            if heartbeat_time.tzinfo is None:
                heartbeat_time = heartbeat_time.astimezone()
        except (TypeError, ValueError):
            continue
        if (now - heartbeat_time).total_seconds() <= stale_after_seconds:
            continue
        status["task_status"] = "stale"
        status["stale_at"] = now_iso()
        status["stale_reason"] = "heartbeat_timeout"
        write_json(status_path, status)
        target = stale_root / task_dir.name
        if not target.exists():
            shutil.move(str(task_dir), str(target))
        moved.append(task_dir.name)
    return moved


def stale_task_candidates(root: Path, stale_after_seconds: int) -> list[str]:
    running = runtime_path(root, "tasks") / "running"
    if not running.exists() or worker_is_active(root, stale_after_seconds):
        return []
    now = datetime.now().astimezone()
    candidates: list[str] = []
    for task_dir in sorted(path for path in running.iterdir() if path.is_dir()):
        status = read_json(task_dir / "status.json", {})
        heartbeat = status.get("heartbeat_at") or status.get("updated_at")
        try:
            heartbeat_time = datetime.fromisoformat(str(heartbeat))
            if heartbeat_time.tzinfo is None:
                heartbeat_time = heartbeat_time.astimezone()
        except (TypeError, ValueError):
            continue
        if (now - heartbeat_time).total_seconds() > stale_after_seconds:
            candidates.append(task_dir.name)
    return candidates


def worker_is_active(root: Path, stale_after_seconds: int) -> bool:
    state = read_json(runtime_path(root, "state") / "web_console_state.json", {})
    if state.get("worker_status") not in {"running", "idle"}:
        return False
    try:
        heartbeat = datetime.fromisoformat(str(state.get("worker_heartbeat_at", "")))
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.astimezone()
    except ValueError:
        return False
    return (datetime.now().astimezone() - heartbeat).total_seconds() <= stale_after_seconds


def rebuild_reproducible_outputs(root: Path) -> list[str]:
    from .dashboard import write_dashboard
    from .indexer import write_indexes
    from .skill_package import write_skill_packages

    outputs = []
    write_skill_packages(root)
    outputs.append("skill_packages")
    write_indexes(root, include_raw_inputs=False)
    outputs.append("indexes")
    write_dashboard(root)
    outputs.append("dashboard")
    return outputs
