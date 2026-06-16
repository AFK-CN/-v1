from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .schemas import RAW_INPUT_DIRS, SYSTEM_DIR, as_posix, now_iso


CLEANUP_NAMES = {".DS_Store", "feishu-auth-qrcode.png"}
CLEANUP_SUFFIXES = {".pyc", ".tmp", ".log"}
CLEANUP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
RAW_SUFFIXES = {".json", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}


def is_under(path: Path, names: tuple[str, ...]) -> bool:
    return any(part in names for part in path.parts)


def cleanup_reason(relative: Path) -> str:
    if relative.name in CLEANUP_NAMES:
        return "system_or_auth_artifact"
    if relative.suffix in CLEANUP_SUFFIXES:
        return "cache_or_temporary_file"
    if any(part in CLEANUP_PARTS for part in relative.parts):
        return "cache_directory"
    if "video_artifacts" in relative.parts:
        return "large_generated_media_artifact"
    return ""


def file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_file(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root)
    stat = path.stat()
    reason = cleanup_reason(relative)
    is_raw = is_under(relative, RAW_INPUT_DIRS) and path.suffix.lower() in RAW_SUFFIXES
    return {
        "path": as_posix(relative),
        "name": path.name,
        "suffix": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified_at": now_iso(),
        "is_raw_input": is_raw,
        "is_system_file": SYSTEM_DIR in relative.parts,
        "cleanup_candidate": bool(reason),
        "cleanup_reason": reason,
        "sha1": file_sha1(path) if stat.st_size <= 2_000_000 else "",
    }


def scan_files(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        files.append(classify_file(root, path))
    cleanup = [item for item in files if item["cleanup_candidate"]]
    return {
        "generated_at": now_iso(),
        "root": str(root),
        "file_count": len(files),
        "cleanup_candidate_count": len(cleanup),
        "files": files,
        "cleanup_candidates": cleanup,
    }


def write_scan_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    result = scan_files(root)
    report_dir = root / SYSTEM_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest_file_inventory_report.md"
    lines = [
        "# 文件盘点与清理候选报告",
        "",
        f"生成时间：{result['generated_at']}",
        f"文件数量：{result['file_count']}",
        f"清理候选：{result['cleanup_candidate_count']}",
        "",
        "## 清理候选",
        "",
        "| 路径 | 原因 |",
        "| --- | --- |",
    ]
    for item in result["cleanup_candidates"]:
        lines.append(f"| {item['path']} | {item['cleanup_reason']} |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "file_count": result["file_count"],
        "cleanup_candidate_count": result["cleanup_candidate_count"],
        "report": as_posix(report_path.relative_to(root)),
    }
