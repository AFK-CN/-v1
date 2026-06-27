from __future__ import annotations

from pathlib import Path
from typing import Any


def candidate_assets_dir(root: Path) -> Path:
    return root.resolve() / "10_Knowledge" / "candidates" / "generated_assets"


def candidate_asset_path(root: Path, filename: str = "candidate_topics.jsonl") -> Path:
    return candidate_assets_dir(root) / filename


def candidate_asset_status(root: Path, filename: str = "candidate_topics.jsonl") -> dict[str, Any]:
    runtime_file = candidate_asset_path(root, filename)
    if runtime_file.exists():
        return {"status": "ready", "path": runtime_file, "reasons": [], "next_action": ""}
    return {
        "status": "empty",
        "path": runtime_file,
        "reasons": [],
        "next_action": "",
    }
