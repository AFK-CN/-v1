from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .distribution import audit_distribution
from .formal_search import index_status, search_formal
from .runtime import doctor_runtime
from .system_cleaner import audit_system_boundaries
from .user_layer import validate_user_layer
from .validator import validate_system


DEFAULT_SMOKE_QUERY = "角色"
DEFAULT_MAX_SEARCH_MS = 5000.0
NONEXISTENT_ACCOUNT = "__kb_release_gate_nonexistent_account__"


def _version_check(root: Path) -> dict[str, Any]:
    version_path = root / "VERSION"
    system_path = root / "00_System/shareable/config/system_version.json"
    if not version_path.exists() or not system_path.exists():
        return {"ok": False, "reason": "version_file_missing"}
    release_version = version_path.read_text(encoding="utf-8").strip()
    try:
        payload = json.loads(system_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"ok": False, "reason": "system_version_invalid"}
    configured_release = str(payload.get("release_version") or "").strip()
    system_version = str(payload.get("system_version") or "").strip()
    expected_prefix = ".".join(release_version.split(".")[:2])
    ok = bool(release_version) and configured_release == release_version and expected_prefix == system_version
    return {
        "ok": ok,
        "release_version": release_version,
        "configured_release_version": configured_release,
        "system_version": system_version,
        "reason": "" if ok else "version_mismatch",
    }


def _git_clean_check(root: Path) -> dict[str, Any]:
    try:
        process = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {"ok": False, "reason": f"git_unavailable:{type(exc).__name__}"}
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    return {
        "ok": process.returncode == 0 and not lines,
        "returncode": process.returncode,
        "change_count": len(lines),
        "reason": "" if process.returncode == 0 and not lines else "git_worktree_not_clean",
    }


def run_release_gate(
    root: Path,
    *,
    query: str = DEFAULT_SMOKE_QUERY,
    max_search_ms: float = DEFAULT_MAX_SEARCH_MS,
    require_clean_git: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    checks: dict[str, dict[str, Any]] = {}

    validation = validate_system(root)
    checks["system_validation"] = {
        "ok": bool(validation.get("ok")),
        "failure_count": len(validation.get("failed", [])),
    }

    doctor = doctor_runtime(root)
    checks["runtime_doctor"] = {
        "ok": doctor.get("status") == "healthy",
        "status": doctor.get("status", "unknown"),
        "repair_action_count": len(doctor.get("repair_actions", [])),
    }

    user_layer = validate_user_layer(root)
    checks["user_layer"] = {
        "ok": bool(user_layer.get("ok")),
        "error_count": len(user_layer.get("errors", [])),
    }

    boundary = audit_system_boundaries(root)
    checks["system_boundary"] = {
        "ok": bool(boundary.get("ok")),
        "violation_count": len(boundary.get("violations", [])),
        "legacy_reference_count": len(boundary.get("legacy_path_references", [])),
    }

    distribution = audit_distribution(root)
    checks["distribution"] = {
        "ok": bool(distribution.get("ok")) and bool(distribution.get("license_files")),
        "portable": bool(distribution.get("portable")),
        "license_files": distribution.get("license_files", []),
        "legal_release_blocker": distribution.get("legal_release_blocker", ""),
        "error_count": len(distribution.get("errors", [])),
    }

    status = index_status(root)
    meta = status.get("meta", {}) if isinstance(status.get("meta"), dict) else {}
    checks["formal_index"] = {
        "ok": bool(status.get("ok")) and not bool(meta.get("forbidden_layers_indexed")),
        "status": status.get("status", "unknown"),
        "source_count": int(meta.get("source_count", 0) or 0),
        "chunk_count": int(meta.get("chunk_count", 0) or 0),
        "forbidden_layers_indexed": bool(meta.get("forbidden_layers_indexed")),
    }

    started = time.perf_counter()
    search = search_formal(root, query=query, limit=3)
    elapsed_ms = (time.perf_counter() - started) * 1000
    items = search.get("items", []) if isinstance(search.get("items"), list) else []
    formal_only = all(str(item.get("path", "")).startswith("10_Knowledge/formal/") for item in items)
    traceable = all(
        bool(item.get("evidence_coordinate"))
        and int(item.get("line_start", 0) or 0) > 0
        and bool(item.get("chunk_sha256"))
        for item in items
        if isinstance(item, dict)
    )
    checks["formal_search_smoke"] = {
        "ok": bool(search.get("ok")) and len(items) > 0 and formal_only and traceable,
        "count": len(items),
        "formal_only": formal_only,
        "traceable": traceable,
        "query": query,
    }
    checks["formal_search_performance"] = {
        "ok": elapsed_ms <= float(max_search_ms),
        "elapsed_ms": round(elapsed_ms, 3),
        "max_ms": float(max_search_ms),
    }

    strict = search_formal(root, query=query, account=NONEXISTENT_ACCOUNT, limit=3)
    strict_items = strict.get("items", []) if isinstance(strict.get("items"), list) else []
    checks["strict_account_filter"] = {
        "ok": bool(strict.get("ok")) and not strict_items,
        "count": len(strict_items),
        "cross_account_fallback": bool(strict_items),
    }

    checks["version"] = _version_check(root)
    if require_clean_git:
        checks["git_clean"] = _git_clean_check(root)

    failed = [name for name, item in checks.items() if not bool(item.get("ok"))]
    return {
        "ok": not failed,
        "status": "passed" if not failed else "failed",
        "release_version": checks["version"].get("release_version", ""),
        "failed": failed,
        "checks": checks,
    }
