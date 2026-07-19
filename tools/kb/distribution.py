from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .system_cleaner import load_account_tokens


MANIFEST_PATH = Path("00_System/shareable/share_manifest.json")
TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".yaml", ".yml", ".txt", ".py", ".sh", ".cjs", ".js", ".ts"}
FORBIDDEN_PREFIXES = (
    "00_System/runtime/",
    "10_Knowledge/",
    "20_User/",
    "90_Temp/",
    "99_Archive/",
    "数据/",
    "00_Inbox/",
    ".venv/",
    ".git/",
)
ABSOLUTE_MACHINE_PATH = re.compile(
    r"(?:/" + r"Users/|/" + r"Volumes/|[A-Za-z]:\\" + r"Users\\)[^\s`\"']+"
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:app[_-]?secret|client[_-]?secret|access[_-]?token|refresh[_-]?token|api[_-]?key)\s*[:=]\s*[\"'][^\"']{8,}[\"']"
)


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _excluded(relative: str, excludes: list[str]) -> bool:
    return any(relative == item.rstrip("/") or relative.startswith(item if item.endswith("/") else f"{item}/") for item in excludes)


def distribution_files(root: Path) -> tuple[list[Path], list[str]]:
    root = root.resolve()
    manifest = _load_manifest(root)
    includes = manifest.get("include", []) if isinstance(manifest.get("include"), list) else []
    excludes = [str(item) for item in manifest.get("exclude", []) if str(item)] if isinstance(manifest.get("exclude"), list) else []
    errors: list[str] = []
    files: set[Path] = set()
    for item in includes:
        relative = str(item).rstrip("/")
        source = root / relative
        if not source.exists():
            errors.append(f"distribution_include_missing:{item}")
            continue
        if source.is_file():
            candidates = [source]
        else:
            candidates = [path for path in source.rglob("*") if path.is_file()]
        for path in candidates:
            rel = path.relative_to(root).as_posix()
            if path.name == ".DS_Store" or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if not _excluded(rel, excludes):
                files.add(path)
    return sorted(files), errors


def audit_distribution(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files, errors = distribution_files(root)
    machine_paths: list[dict[str, str]] = []
    secrets: list[str] = []
    account_leaks: list[dict[str, str]] = []
    forbidden_files: list[str] = []
    account_tokens = load_account_tokens(root)
    for path in files:
        relative = path.relative_to(root).as_posix()
        if any(relative.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            forbidden_files.append(relative)
        if path.name == ".DS_Store" or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            forbidden_files.append(relative)
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not relative.startswith("tests/"):
            for match in ABSOLUTE_MACHINE_PATH.finditer(text):
                machine_paths.append({"path": relative, "token": match.group(0)})
        if SECRET_ASSIGNMENT.search(text):
            secrets.append(relative)
        if not relative.startswith("tests/"):
            for token in account_tokens:
                if token and token in text:
                    account_leaks.append({"path": relative, "token": token})
                    break
    errors.extend(f"distribution_forbidden_file:{item}" for item in sorted(set(forbidden_files)))
    errors.extend(f"distribution_machine_path:{item['path']}:{item['token']}" for item in machine_paths)
    errors.extend(f"distribution_secret_assignment:{item}" for item in secrets)
    errors.extend(f"distribution_account_leak:{item['path']}:{item['token']}" for item in account_leaks)
    license_files = [name for name in ("LICENSE", "LICENSE.md", "COPYING") if (root / name).exists()]
    license_text = ""
    if license_files:
        license_text = (root / license_files[0]).read_text(encoding="utf-8", errors="ignore")
    scope_path = root / "LICENSE_SCOPE.md"
    notice_path = root / "NOTICE"
    scope_text = scope_path.read_text(encoding="utf-8", errors="ignore") if scope_path.exists() else ""
    apache_2 = "Apache License" in license_text and "Version 2.0" in license_text
    scoped_system_only = (
        "SPDX-License-Identifier: Apache-2.0" in scope_text
        and "00_System/shareable/share_manifest.json" in scope_text
        and "10_Knowledge/" in scope_text
        and "不在 Apache-2.0 授权范围内" in scope_text
    )
    license_ready = bool(license_files) and apache_2 and scoped_system_only and notice_path.exists()
    if not license_files:
        legal_release_blocker = "missing_license"
    elif not license_ready:
        legal_release_blocker = "invalid_or_unscoped_license"
    else:
        legal_release_blocker = ""
    return {
        "ok": not errors,
        "portable": not errors,
        "open_source_ready": not errors and license_ready,
        "file_count": len(files),
        "license_files": license_files,
        "license_id": "Apache-2.0" if apache_2 else "",
        "license_scope": "portable_system_package_only" if scoped_system_only else "",
        "license_scope_file": "LICENSE_SCOPE.md" if scope_path.exists() else "",
        "notice_files": ["NOTICE"] if notice_path.exists() else [],
        "legal_release_blocker": legal_release_blocker,
        "errors": errors,
        "machine_paths": machine_paths,
        "secret_files": secrets,
        "account_leaks": account_leaks,
    }


def export_system_package(root: Path, output: Path, *, force: bool = False) -> dict[str, Any]:
    root = root.resolve()
    output = output.expanduser().resolve()
    audit = audit_distribution(root)
    if not audit["ok"]:
        return {"ok": False, "status": "distribution_audit_failed", "audit": audit}
    if output == root or root in output.parents:
        return {"ok": False, "status": "output_must_be_outside_source_root", "output": str(output)}
    if output.exists() and any(output.iterdir()):
        if not force:
            return {"ok": False, "status": "output_not_empty", "output": str(output)}
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    files, errors = distribution_files(root)
    if errors:
        return {"ok": False, "status": "manifest_invalid", "errors": errors}
    for source in files:
        relative = source.relative_to(root)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return {
        "ok": True,
        "status": "exported",
        "output": str(output),
        "file_count": len(files),
        "open_source_ready": audit["open_source_ready"],
        "license_id": audit["license_id"],
        "license_scope": audit["license_scope"],
        "legal_release_blocker": audit["legal_release_blocker"],
    }
