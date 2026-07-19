from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .account_skills import default_registry, registry_path, validate_registry
from .production_memory import initialize_database, validate_database
from .schemas import now_iso


USER_DIRS = (
    "20_User/config",
    "20_User/data",
    "20_User/feedback",
    "20_User/private",
    "20_User/local",
)


def write_json_if_missing(path: Path, payload: dict[str, Any]) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def migrate_legacy_local(root: Path) -> list[str]:
    source = root / "80_Local"
    target = root / "20_User" / "local" / "legacy_80_local"
    if not source.exists():
        return []
    moved = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        shutil.copy2(path, destination)
        moved.append(str(relative))
    return moved


def initialize_user_layer(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    root = root.resolve()
    would_create = [relative for relative in USER_DIRS if not (root / relative).exists()]
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would_create": would_create,
            "legacy_local_detected": (root / "80_Local").exists(),
        }
    created = []
    for relative in USER_DIRS:
        path = root / relative
        if path.exists():
            continue
        path.mkdir(parents=True, exist_ok=True)
        created.append(relative)
    classification_defaults_path = root / "00_System/shareable/config/content_classification_defaults.json"
    try:
        classification_defaults = json.loads(classification_defaults_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        classification_defaults = {}
    fallback_directions = classification_defaults.get("fallback_directions", {})
    if not isinstance(fallback_directions, dict):
        fallback_directions = {}
    defaults = {
        "account_skill_registry.json": default_registry(),
        "production_defaults.json": {
            "version": 1,
            "updated_at": now_iso(),
            "topic_novelty": {
                "warning_threshold": 0.62,
                "block_threshold": 0.84,
                "max_conflicts_returned": 5,
                "batch_check": True,
                "never_load_full_database_into_model": True,
            },
        },
        "review_defaults.json": {
            "version": 1,
            "updated_at": now_iso(),
            "single_feedback_is_candidate_only": True,
            "account_skill_update_requires_user_approval": True,
        },
        "content_rough_scan_profiles.json": {
            "version": 1,
            "updated_at": now_iso(),
            "profiles": {},
            "video_learning_classification": {
                "fallback_directions": fallback_directions,
                "account_directions": {},
            },
        },
    }
    written = []
    for name, payload in defaults.items():
        if write_json_if_missing(root / "20_User" / "config" / name, payload):
            written.append(name)
    database = initialize_database(root)
    migrated = migrate_legacy_local(root)
    return {
        "ok": True,
        "dry_run": False,
        "created": created,
        "written_defaults": written,
        "database": database,
        "legacy_local_copied": migrated,
    }


def validate_user_layer(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors = [f"user_layer_missing:{relative}" for relative in USER_DIRS if not (root / relative).exists()]
    for name in (
        "account_skill_registry.json",
        "production_defaults.json",
        "review_defaults.json",
        "content_rough_scan_profiles.json",
    ):
        path = root / "20_User" / "config" / name
        if not path.exists():
            errors.append(f"user_layer_config_missing:{name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"user_layer_config_invalid_json:{name}")
            continue
        if not isinstance(payload, dict) or payload.get("version") != 1:
            errors.append(f"user_layer_config_version_invalid:{name}")
    registry = validate_registry(root)
    errors.extend(registry.get("errors", []))
    database = validate_database(root)
    errors.extend(database.get("errors", []))
    return {
        "ok": not errors,
        "errors": errors,
        "registry": registry,
        "production_memory": database,
        "registry_path": str(registry_path(root).relative_to(root)),
    }
