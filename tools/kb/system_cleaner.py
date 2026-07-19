from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import as_posix, load_layer_map


TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".yaml", ".yml", ".txt"}
SYSTEM_BOUNDARY_FILES = (
    "知识库入口.md",
    "README.md",
    "00_System/shareable/index/controller_routes.json",
    "00_System/shareable/index/task_entry_index.md",
    "00_System/shareable/config/output_contracts.json",
    "00_System/shareable/config/skill_contract.json",
)
SYSTEM_BOUNDARY_DIRS = (
    "00_System/shareable/rules",
    "00_System/shareable/skills/active",
    "00_System/shareable/skill_packages",
)
SYSTEM_BOUNDARY_EXCLUSIONS = (
    "00_System/shareable/config/layer_map.json",
    "00_System/shareable/docs/system_cleaning/",
)


def legacy_path_mapping(root: Path) -> list[tuple[str, str]]:
    layer_map = load_layer_map(root)
    mapping = layer_map.get("legacy_mapping", {})
    if not isinstance(mapping, dict):
        return []
    pairs = [
        (str(source), str(target))
        for source, target in mapping.items()
        if str(source).startswith("01_Case_Cleaning/") and str(source) and str(target)
    ]
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def rewrite_legacy_path_references(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    root = root.resolve()
    mapping = legacy_path_mapping(root)
    scanned_roots = [
        root / "10_Knowledge" / "candidates",
        root / "10_Knowledge" / "evidence" / "index",
    ]
    changed: list[dict[str, Any]] = []
    for base in scanned_roots:
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file() and item.suffix in TEXT_SUFFIXES):
            original = path.read_text(encoding="utf-8", errors="ignore")
            updated = original
            replacements = 0
            for source, target in mapping:
                count = updated.count(source)
                if count:
                    updated = updated.replace(source, target)
                    replacements += count
            if updated == original:
                continue
            changed.append({"path": as_posix(path.relative_to(root)), "replacement_count": replacements})
            if not dry_run:
                path.write_text(updated, encoding="utf-8")
    return {
        "ok": True,
        "dry_run": dry_run,
        "changed_file_count": len(changed),
        "replacement_count": sum(item["replacement_count"] for item in changed),
        "changed": changed,
    }


def audit_system_boundaries(root: Path) -> dict[str, Any]:
    root = root.resolve()
    account_tokens = load_account_tokens(root)
    system_files = list(iter_system_boundary_files(root))
    violations: list[dict[str, str]] = []
    for path in system_files:
        relative = as_posix(path.relative_to(root))
        if any(relative.startswith(prefix) for prefix in SYSTEM_BOUNDARY_EXCLUSIONS):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in account_tokens:
            if token and token in text:
                violations.append({"path": relative, "type": "account_token_in_system_rule", "token": token})
        for forbidden in ("10_Knowledge/candidates/account_assets/content_rough_scan/", "10_Knowledge/candidates/learning_cards/learned_cards/"):
            if forbidden in text:
                violations.append({"path": relative, "type": "candidate_knowledge_link_in_system_rule", "token": forbidden})
    legacy_refs = find_legacy_path_references(root)
    return {
        "ok": not violations and not legacy_refs,
        "system_file_count": len(system_files),
        "account_token_count": len(account_tokens),
        "violations": violations,
        "legacy_path_references": legacy_refs,
    }


def load_account_tokens(root: Path) -> list[str]:
    tokens: set[str] = set()
    profile_path = root / "20_User" / "config" / "content_rough_scan_profiles.json"
    if profile_path.exists():
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
        if isinstance(profiles, dict):
            for profile_id, profile in profiles.items():
                if isinstance(profile_id, str):
                    tokens.add(profile_id)
                if isinstance(profile, dict) and isinstance(profile.get("account_name"), str):
                    tokens.add(profile["account_name"])
        classifier = payload.get("video_learning_classification", {}) if isinstance(payload, dict) else {}
        account_directions = classifier.get("account_directions", {}) if isinstance(classifier, dict) else {}
        if isinstance(account_directions, dict):
            tokens.update(str(account) for account in account_directions if str(account))
    account_cards = root / "10_Knowledge" / "candidates" / "account_assets" / "account_cards"
    if account_cards.exists():
        for path in account_cards.glob("*.md"):
            name = path.stem
            if "_" in name:
                tokens.add(name.rsplit("_", 1)[0])
    return sorted(token for token in tokens if len(token) >= 3)


def iter_system_boundary_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in SYSTEM_BOUNDARY_FILES:
        path = root / relative
        if path.exists() and path.is_file() and path.suffix in TEXT_SUFFIXES:
            files.append(path)
    for relative in SYSTEM_BOUNDARY_DIRS:
        base = root / relative
        if not base.exists():
            continue
        files.extend(sorted(path for path in base.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES))
    return sorted(set(files))


def find_legacy_path_references(root: Path) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for relative in ("10_Knowledge/candidates", "10_Knowledge/evidence/index"):
        base = root / relative
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file() and item.suffix in TEXT_SUFFIXES):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if "01_Case_Cleaning/" in line and "90_Temp/trash_review/ds_store/01_Case_Cleaning" not in line:
                    refs.append({"path": as_posix(path.relative_to(root)), "type": "legacy_path_reference"})
                    break
    return refs
