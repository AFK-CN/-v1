from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


CONTENT_STATUSES = (
    "new",
    "scanned",
    "cleaned",
    "candidate",
    "review_needed",
    "approved",
    "used",
    "archived",
    "rejected",
)

TASK_STATUSES = ("pending", "running", "stale", "done", "failed", "paused")

RAW_INPUT_DIRS = ("00_Inbox", "数据")
BLOCKED_BY_DEFAULT_DIRS = (
    "00_Inbox",
    "数据",
    "99_Archive",
)
BLOCKED_BY_DEFAULT_PREFIXES = (
    "20_User/private/",
    "20_User/data/",
    "20_User/feedback/",
    "20_User/local/",
    "00_System/runtime/",
)
FORMAL_KNOWLEDGE_DIRS = ("10_Knowledge/formal",)
SYSTEM_DIR = "00_System"
SYSTEM_SHAREABLE_DIR = "00_System/shareable"
SYSTEM_CONFIG_DIR = "00_System/shareable/config"
SYSTEM_RULES_DIR = "00_System/shareable/rules"
SYSTEM_INDEX_DIR = "00_System/shareable/index"
SYSTEM_SKILL_PACKAGES_DIR = "00_System/shareable/skill_packages"
EVIDENCE_INDEX_DIR = "10_Knowledge/evidence/index"
USER_CONFIG_DIR = "20_User/config"
USER_DATA_DIR = "20_User/data"
USER_FEEDBACK_DIR = "20_User/feedback"
USER_LOCAL_DIR = "20_User/local"
LAYER_MAP_PATH = "00_System/shareable/config/layer_map.json"

TARGET_FORMAL_KNOWLEDGE_PREFIXES = ("10_Knowledge/formal/",)
TARGET_CANDIDATE_ASSET_PREFIXES = ("10_Knowledge/candidates/",)
SYSTEM_SKILL_PREFIXES = (
    "00_System/shareable/skills/",
    "13_Evolving_Skills/active/",
)
SYSTEM_SKILLS_DIR = "00_System/shareable/skills"
LEGACY_SKILLS_DIR = "13_Evolving_Skills"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_layer_map(root: Path) -> dict[str, Any]:
    path = root.resolve() / LAYER_MAP_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def layer_prefixes(layer_map: dict[str, Any], key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    values = layer_map.get(key, [])
    if not isinstance(values, list):
        return fallback
    cleaned = tuple(str(value) for value in values if str(value).strip())
    return cleaned or fallback


def skills_root(root: Path) -> Path:
    current = root.resolve() / SYSTEM_SKILLS_DIR
    if current.exists():
        return current
    return root.resolve() / LEGACY_SKILLS_DIR


def active_skills_dir(root: Path) -> Path:
    return skills_root(root) / "active"


def skill_proposals_dir(root: Path) -> Path:
    return skills_root(root) / "proposals"


def skill_history_dir(root: Path) -> Path:
    return skills_root(root) / "history"


def validate_content_status(status: str) -> str:
    if status not in CONTENT_STATUSES:
        raise ValueError(f"invalid content status: {status}")
    return status


def validate_task_status(status: str) -> str:
    if status not in TASK_STATUSES:
        raise ValueError(f"invalid task status: {status}")
    return status


def as_posix(path: Any) -> str:
    return str(path).replace("\\", "/")
