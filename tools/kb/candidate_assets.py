from __future__ import annotations

from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import SYSTEM_DIR


def candidate_assets_dir(root: Path) -> Path:
    return runtime_path(root, "cache") / "assets"


def candidate_asset_path(root: Path, filename: str = "candidate_topics.jsonl") -> Path:
    return candidate_assets_dir(root) / filename


def legacy_candidate_asset_path(root: Path, filename: str = "candidate_topics.jsonl") -> Path:
    return root.resolve() / SYSTEM_DIR / "assets" / filename


def candidate_asset_status(root: Path, filename: str = "candidate_topics.jsonl") -> dict[str, Any]:
    runtime_file = candidate_asset_path(root, filename)
    legacy_file = legacy_candidate_asset_path(root, filename)
    if runtime_file.exists():
        return {"status": "ready", "path": runtime_file, "reasons": [], "next_action": ""}
    if legacy_file.exists():
        return {
            "status": "requires_init",
            "path": runtime_file,
            "legacy_path": legacy_file,
            "reasons": ["runtime_candidate_assets_missing"],
            "next_action": "kb init",
        }
    return {
        "status": "empty",
        "path": runtime_file,
        "reasons": [],
        "next_action": "",
    }
