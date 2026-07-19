from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REGISTRY_PATH = Path("20_User/config/account_skill_registry.json")
OUTPUT_DIR_NAME = "轻量数据源"
PLATFORM_PREFIXES = {
    "抖音": "dy",
    "douyin": "dy",
    "dy": "dy",
    "小红书": "xhs",
    "xiaohongshu": "xhs",
    "xhs": "xhs",
}
MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
SOURCE_ID_PATTERNS = (
    re.compile(r"source_id\s*[：:]\s*`?([A-Za-z0-9_-]+)`?", re.IGNORECASE),
    re.compile(r"(?:douyin|dy|xhs)_([A-Za-z0-9_-]{12,})", re.IGNORECASE),
)


@dataclass(frozen=True)
class SourceCandidate:
    account_name: str
    platform: str
    prefix: str
    direction: str
    source_id: str
    title: str
    card_path: Path
    source_dir: Path
    content_type: str
    byte_count: int
    file_count: int
    quality_score: int
    portable_ready: bool
    missing_core: tuple[str, ...]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _source_id(card_path: Path, text: str) -> str:
    for pattern in SOURCE_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip("` ")
            if value:
                return value
    stem = card_path.stem
    stem = re.sub(r"^(?:douyin|dy|xhs)_", "", stem, flags=re.IGNORECASE)
    exact = re.fullmatch(r"[A-Za-z0-9_-]{12,}", stem)
    if exact:
        return stem
    matches = re.findall(r"[A-Za-z0-9]{16,}", stem)
    return max(matches, key=len) if matches else ""


def _title(text: str, source_id: str) -> str:
    for line in text.splitlines():
        value = line.strip()
        if value.startswith("# "):
            return value[2:].strip()
    return source_id


def _iter_files(directory: Path) -> Iterable[Path]:
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name not in IGNORED_NAMES and not path.name.startswith("._"):
            yield path


def _directory_stats(directory: Path) -> tuple[int, int]:
    files = list(_iter_files(directory))
    return len(files), sum(path.stat().st_size for path in files)


def _inspect_source(directory: Path) -> dict[str, Any]:
    root_files = {path.name: path for path in directory.iterdir() if path.is_file()}
    video_dir = directory / "video"
    image_dir = directory / "images"
    video_entries = list(video_dir.iterdir()) if video_dir.is_dir() else []
    image_entries = list(image_dir.iterdir()) if image_dir.is_dir() else []
    video_files = [path for path in video_entries if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".m4v"}]
    source_video_files = [path for path in video_files if path.name.lower().startswith("source")]
    image_files = [path for path in image_entries if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
    transcript_files = [
        path
        for path in video_entries
        if path.is_file()
        and "transcript" in path.name.lower()
        and path.suffix.lower() in {".srt", ".txt", ".json"}
    ]
    frames_dir = video_dir / "frames"
    frame_files = []
    if frames_dir.is_dir():
        frame_files = [
            path
            for path in frames_dir.iterdir()
            if path.suffix.lower() in IMAGE_SUFFIXES
        ]
    analysis_files = [
        path
        for path in image_entries
        if path.is_file()
        and path.name.lower() in {"ocr.json", "image_analysis.json", "visual_summary.json", "vision_analysis.json"}
    ]
    content_type = "video" if video_files else "image_text" if image_files else "unknown"
    missing: list[str] = []
    for name in ("source.json", "status.json", "manifest_item.json"):
        if name not in root_files:
            missing.append(name)
    if content_type == "video":
        if not source_video_files:
            missing.append("video/source*.mp4")
        if not transcript_files:
            missing.append("video/transcript.*")
        if not frame_files:
            missing.append("video/frames/*")
    elif content_type == "image_text":
        if not image_files:
            missing.append("images/*")
    else:
        missing.append("media")

    score = 0
    score += 100 if not missing else 0
    score += len({"source.json", "status.json", "manifest_item.json"} & set(root_files)) * 5
    score += 30 if video_files else 0
    score += 20 if transcript_files else 0
    score += 20 if frame_files else 0
    score += 25 if analysis_files else 0
    score += min(len(analysis_files), 4)
    size_basis = list(root_files.values()) + [
        path for path in video_entries + image_entries if path.is_file()
    ]
    return {
        "content_type": content_type,
        "file_count": len(root_files) + len(video_entries) + len(image_entries) + len(frame_files),
        "byte_count": sum(path.stat().st_size for path in size_basis),
        "quality_score": score,
        "portable_ready": not missing,
        "missing_core": tuple(missing),
        "media_suffixes": sorted({path.suffix.lower() for path in size_basis} & MEDIA_SUFFIXES),
    }


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def _fast_inspect_source(directory: Path) -> dict[str, Any]:
    """Inspect fixed artifact coordinates without listing a remote directory."""
    video_dir = directory / "video"
    image_dir = directory / "images"
    source_video = _first_existing(
        (video_dir / "source.mp4", video_dir / "source.codex.mp4", video_dir / "source.mov")
    )
    transcript = _first_existing(
        (
            video_dir / "transcript.srt",
            video_dir / "transcript.txt",
            video_dir / "transcript.json",
            video_dir / "transcript.codex.srt",
        )
    )
    first_frame = _first_existing((video_dir / "frames/000001.jpg", video_dir / "frames/000000.jpg"))
    cover_image = _first_existing(
        (
            image_dir / "000_cover.jpg",
            image_dir / "000_cover.png",
            image_dir / "cover.jpg",
            video_dir / "cover.jpg",
        )
    )
    metadata = [directory / "source.json", directory / "status.json", directory / "manifest_item.json"]
    missing = [path.name for path in metadata if not path.is_file()]
    content_type = "video" if source_video else "image_text" if cover_image else "unknown"
    if content_type == "video":
        if transcript is None:
            missing.append("video/transcript.*")
        if first_frame is None:
            missing.append("video/frames/000001.jpg")
    elif content_type == "unknown":
        missing.append("media")
    size_paths = [path for path in metadata if path.is_file()]
    if source_video:
        size_paths.append(source_video)
        audio = video_dir / "audio.wav"
        if audio.is_file():
            size_paths.append(audio)
    if cover_image and cover_image not in size_paths:
        size_paths.append(cover_image)
    analysis_count = sum(
        path.is_file()
        for path in (
            image_dir / "ocr.json",
            image_dir / "image_analysis.json",
            image_dir / "visual_summary.json",
            image_dir / "vision_analysis.json",
        )
    )
    quality_score = (100 if not missing else 0) + (20 if transcript else 0) + (20 if first_frame else 0) + analysis_count
    return {
        "content_type": content_type,
        "file_count": len(size_paths),
        "byte_count": sum(path.stat().st_size for path in size_paths),
        "quality_score": quality_score,
        "portable_ready": not missing,
        "missing_core": tuple(missing),
    }


def _platform_prefix(platform: str) -> str:
    prefix = PLATFORM_PREFIXES.get(platform.strip().lower()) or PLATFORM_PREFIXES.get(platform.strip())
    if not prefix:
        raise ValueError(f"unsupported account platform: {platform}")
    return prefix


def _load_accounts(root: Path, requested_accounts: list[str] | None) -> list[dict[str, Any]]:
    registry = _read_json(root / REGISTRY_PATH)
    accounts = [item for item in registry.get("accounts", []) if item.get("status") == "active"]
    if requested_accounts:
        wanted = set(requested_accounts)
        accounts = [item for item in accounts if str(item.get("account_name")) in wanted]
        missing = wanted - {str(item.get("account_name")) for item in accounts}
        if missing:
            raise ValueError(f"active account not found: {', '.join(sorted(missing))}")
    if not accounts:
        raise ValueError("no active account Skills found")
    return accounts


def _resolve_nas_root(root: Path, accounts: list[dict[str, Any]], provided: Path | None) -> Path | None:
    if provided is not None:
        return provided.expanduser().resolve()
    environment_value = os.environ.get("KB_NAS_ROOT", "").strip()
    if environment_value:
        return Path(environment_value).expanduser().resolve()
    for account in accounts:
        account_center = (root / str(account["skill_path"])).parent.parent
        manifest_path = account_center / OUTPUT_DIR_NAME / "manifest.json"
        if not manifest_path.is_file():
            continue
        source_root = str(_read_json(manifest_path).get("discovery", {}).get("source_root") or "")
        source_path = Path(source_root)
        if len(source_path.parents) >= 3:
            return source_path.parents[2].resolve()
    return None


def _existing_manifest(account_center: Path) -> dict[str, Any] | None:
    manifest_path = account_center / OUTPUT_DIR_NAME / "manifest.json"
    return _read_json(manifest_path) if manifest_path.is_file() else None


def _selection_diff(
    existing_manifest: dict[str, Any] | None,
    selected: list[SourceCandidate],
) -> dict[str, Any]:
    existing_keys = {
        (str(item.get("direction") or ""), str(item.get("source_id") or ""))
        for item in (existing_manifest or {}).get("items", [])
    }
    selected_keys = {(item.direction, item.source_id) for item in selected}

    def rows(keys: set[tuple[str, str]]) -> list[dict[str, str]]:
        return [
            {"direction": direction, "source_id": source_id}
            for direction, source_id in sorted(keys)
        ]

    added = selected_keys - existing_keys
    removed = existing_keys - selected_keys
    unchanged = selected_keys & existing_keys
    return {
        "status": "changes_detected" if added or removed else "unchanged",
        "existing_count": len(existing_keys),
        "planned_count": len(selected_keys),
        "added": rows(added),
        "removed": rows(removed),
        "unchanged_count": len(unchanged),
    }


def _card_inventory(account_center: Path) -> dict[str, list[tuple[Path, str, str]]]:
    directions_root = account_center / "directions"
    inventory: dict[str, list[tuple[Path, str, str]]] = {}
    if not directions_root.is_dir():
        return inventory
    for direction_dir in sorted(path for path in directions_root.iterdir() if path.is_dir()):
        cards_dir = direction_dir / "cards"
        cards: list[tuple[Path, str, str]] = []
        if cards_dir.is_dir():
            for card_path in sorted(cards_dir.glob("*.md")):
                text = card_path.read_text(encoding="utf-8", errors="replace")
                source_id = _source_id(card_path, text)
                if source_id:
                    cards.append((card_path, source_id, _title(text, source_id)))
        if cards:
            inventory[direction_dir.name] = cards
    return inventory


def _discover_account_source_root(
    nas_root: Path,
    prefix: str,
    source_ids: list[str],
) -> tuple[Path | None, dict[str, int]]:
    accounts_root = nas_root / prefix / "accounts"
    if not accounts_root.is_dir():
        return None, {}
    roots = sorted(path for path in accounts_root.iterdir() if path.is_dir())
    sample = source_ids[: min(len(source_ids), 40)]
    scores = {
        str(candidate): sum((candidate / f"{prefix}_{source_id}").is_dir() for source_id in sample)
        for candidate in roots
    }
    matched = [(score, Path(path)) for path, score in scores.items() if score > 0]
    if not matched:
        return None, scores
    matched.sort(key=lambda item: (-item[0], str(item[1])))
    return matched[0][1], scores


def _build_candidates(
    *,
    root: Path,
    account: dict[str, Any],
    nas_root: Path,
    candidate_limit: int,
) -> tuple[Path, dict[str, list[SourceCandidate]], dict[str, Any]]:
    account_name = str(account["account_name"])
    platform = str(account.get("platform") or "")
    prefix = _platform_prefix(platform)
    skill_path = root / str(account["skill_path"])
    account_center = skill_path.parent.parent
    inventory = _card_inventory(account_center)
    source_ids = [source_id for cards in inventory.values() for _, source_id, _ in cards]
    source_root, root_scores = _discover_account_source_root(nas_root, prefix, source_ids)
    candidates: dict[str, list[SourceCandidate]] = defaultdict(list)
    if source_root is not None:
        for direction, cards in inventory.items():
            for card_path, source_id, title in cards[:candidate_limit]:
                source_dir = source_root / f"{prefix}_{source_id}"
                if not source_dir.is_dir():
                    continue
                inspection = _fast_inspect_source(source_dir)
                candidates[direction].append(
                    SourceCandidate(
                        account_name=account_name,
                        platform=platform,
                        prefix=prefix,
                        direction=direction,
                        source_id=source_id,
                        title=title,
                        card_path=card_path,
                        source_dir=source_dir,
                        content_type=str(inspection["content_type"]),
                        byte_count=int(inspection["byte_count"]),
                        file_count=int(inspection["file_count"]),
                        quality_score=int(inspection["quality_score"]),
                        portable_ready=bool(inspection["portable_ready"]),
                        missing_core=tuple(inspection["missing_core"]),
                    )
                )
    for items in candidates.values():
        items.sort(key=lambda item: (-int(item.portable_ready), -item.quality_score, item.byte_count, item.source_id))
    discovery = {
        "account_center": _relative(account_center, root),
        "formal_direction_count": len(inventory),
        "formal_card_count": sum(len(items) for items in inventory.values()),
        "source_root": str(source_root) if source_root else "",
        "source_root_match_scores": root_scores,
        "matched_direction_count": len(candidates),
        "matched_card_count": sum(len(items) for items in candidates.values()),
    }
    return account_center, dict(candidates), discovery


def _select_candidates(
    candidates: dict[str, list[SourceCandidate]],
    *,
    min_total: int,
    max_total: int,
    per_direction_max: int,
) -> tuple[list[SourceCandidate], list[str]]:
    directions = sorted(candidates)
    errors: list[str] = []
    if len(directions) > max_total:
        errors.append(f"direction_count_exceeds_max_total:{len(directions)}>{max_total}")
        return [], errors
    ready = {
        direction: [candidate for candidate in candidates[direction] if candidate.portable_ready]
        for direction in directions
    }
    empty = [direction for direction, items in ready.items() if not items]
    errors.extend(f"no_portable_source:{direction}" for direction in empty)
    if errors:
        return [], errors

    target = max(min_total, len(directions))
    target = min(target, max_total)
    selected: dict[str, list[SourceCandidate]] = {direction: [ready[direction][0]] for direction in directions}
    while sum(len(items) for items in selected.values()) < target:
        progressed = False
        for direction in directions:
            current = selected[direction]
            if len(current) >= per_direction_max or len(current) >= len(ready[direction]):
                continue
            current.append(ready[direction][len(current)])
            progressed = True
            if sum(len(items) for items in selected.values()) >= target:
                break
        if not progressed:
            break
    flat = [candidate for direction in directions for candidate in selected[direction]]
    if len(flat) < min_total:
        errors.append(f"insufficient_portable_sources:{len(flat)}<{min_total}")
    return flat, errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_source_tree(source: Path, destination: Path) -> None:
    # SMB/NAS files can carry ownership, flags or extended attributes that macOS
    # refuses to apply inside the local workspace. Preserve bytes and layout;
    # integrity is checked separately with SHA-256 instead of NAS metadata.
    destination.mkdir(parents=True)
    for source_path in _iter_files(source):
        destination_path = destination / source_path.relative_to(source)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)


def _file_manifest(directory: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(directory).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in _iter_files(directory)
    ]


def _human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{value} B"


def _account_readme(account_name: str, manifest: dict[str, Any]) -> str:
    lines = [
        f"# {account_name}轻量数据源",
        "",
        "这是为 NAS 断开时的查看、复查与证据回溯准备的自包含离线样本。",
        "",
        f"- 内容数：{manifest['selected_count']}",
        f"- 方向数：{manifest['direction_count']}",
        f"- 总体积：{_human_size(manifest['total_bytes'])}",
        "- 每条内容包含 `学习卡.md`、`bundle_manifest.json` 与 `完整产出物/`。",
        "- `完整产出物/` 保留源条目的视频/图片、逐字稿、抽帧、OCR/视觉分析、元数据、状态和 manifest；仅排除 `.DS_Store` 等系统垃圾。",
        "- 原始 NAS 资料只读，本目录是本地副本，不替代原始资料。",
        "",
        "## 快速复查",
        "",
        "| 方向 | source_id | 类型 | 体积 | 离线入口 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in manifest["items"]:
        lines.append(
            f"| {item['direction']} | `{item['source_id']}` | {item['content_type']} | "
            f"{_human_size(item['bytes'])} | `{item['bundle_path']}/学习卡.md` |"
        )
    lines.extend(
        [
            "",
            "## 更新方式",
            "",
            "NAS 连接时，在知识库根目录运行：",
            "",
            "```bash",
            f".venv/bin/python -m tools.account_offline_source --root . --account \"{account_name}\" --apply",
            "```",
            "",
            "如果目录已存在，使用 `--force` 明确覆盖旧的离线包。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_account_bundle(
    *,
    root: Path,
    account_center: Path,
    account_name: str,
    platform: str,
    selected: list[SourceCandidate],
    discovery: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    output_dir = account_center / OUTPUT_DIR_NAME
    if output_dir.exists() and not force:
        raise FileExistsError(f"offline source already exists: {output_dir}; rerun with --force")
    stage_dir = account_center / f".{OUTPUT_DIR_NAME}.building"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    items: list[dict[str, Any]] = []
    try:
        for candidate in selected:
            bundle_rel = Path("directions") / candidate.direction / f"{candidate.prefix}_{candidate.source_id}"
            bundle_dir = stage_dir / bundle_rel
            bundle_dir.mkdir(parents=True)
            shutil.copy2(candidate.card_path, bundle_dir / "学习卡.md")
            artifact_dir = bundle_dir / "完整产出物"
            _copy_source_tree(candidate.source_dir, artifact_dir)
            copied_files = _file_manifest(artifact_dir)
            copied_bytes = sum(int(item["bytes"]) for item in copied_files)
            bundle_manifest = {
                "schema_version": 1,
                "account_name": account_name,
                "platform": platform,
                "direction": candidate.direction,
                "source_id": candidate.source_id,
                "title": candidate.title,
                "content_type": candidate.content_type,
                "formal_card": _relative(candidate.card_path, root),
                "original_source_dir": str(candidate.source_dir),
                "copied_file_count": len(copied_files),
                "copied_bytes": copied_bytes,
                "files": copied_files,
            }
            _write_json(bundle_dir / "bundle_manifest.json", bundle_manifest)
            items.append(
                {
                    "direction": candidate.direction,
                    "source_id": candidate.source_id,
                    "title": candidate.title,
                    "content_type": candidate.content_type,
                    "bytes": copied_bytes,
                    "file_count": len(copied_files),
                    "quality_score": candidate.quality_score,
                    "bundle_path": bundle_rel.as_posix(),
                    "formal_card": _relative(candidate.card_path, root),
                    "original_source_dir": str(candidate.source_dir),
                }
            )

        direction_counts: dict[str, int] = defaultdict(int)
        for item in items:
            direction_counts[str(item["direction"])] += 1
        manifest = {
            "schema_version": 1,
            "status": "ready_offline",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "account_name": account_name,
            "platform": platform,
            "purpose": "NAS 断开时的账号 Skill 查看、复查和证据回溯",
            "source_policy": "原始资料只读；离线包仅复制已有产出物",
            "selected_count": len(items),
            "direction_count": len(direction_counts),
            "direction_counts": dict(sorted(direction_counts.items())),
            "total_bytes": sum(int(item["bytes"]) for item in items),
            "discovery": discovery,
            "items": items,
        }
        _write_json(stage_dir / "manifest.json", manifest)
        (stage_dir / "README.md").write_text(_account_readme(account_name, manifest), encoding="utf-8")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        stage_dir.rename(output_dir)
        return {
            "ok": True,
            "account_name": account_name,
            "output_dir": _relative(output_dir, root),
            "manifest": _relative(output_dir / "manifest.json", root),
            "selected_count": len(items),
            "direction_count": len(direction_counts),
            "direction_counts": dict(sorted(direction_counts.items())),
            "total_bytes": manifest["total_bytes"],
        }
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        raise


def _write_pending_bundle(
    *,
    root: Path,
    account_center: Path,
    account_name: str,
    platform: str,
) -> dict[str, Any]:
    output_dir = account_center / OUTPUT_DIR_NAME
    if output_dir.exists():
        return {
            "ok": True,
            "status": "existing_bundle_preserved",
            "output_dir": _relative(output_dir, root),
        }
    output_dir.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "status": "pending_nas_sync",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "account_name": account_name,
        "platform": platform,
        "purpose": "NAS 断开时的账号 Skill 查看、复查和证据回溯",
        "source_policy": "原始资料只读；NAS 恢复后再组建离线包",
        "selected_count": 0,
        "direction_count": 0,
        "direction_counts": {},
        "total_bytes": 0,
        "gaps": ["nas_unavailable"],
        "items": [],
    }
    _write_json(output_dir / "manifest.json", manifest)
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                f"# {account_name}轻量数据源",
                "",
                "- 状态：`pending_nas_sync`",
                "- 原因：NAS 当前不可用，尚未复制媒体与处理产出物。",
                "- 边界：正式账号 Skill 可继续使用；不使用候选资产填充本目录。",
                "- 下一步：NAS 恢复后重新执行轻量数据源组建。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "status": "pending_nas_sync",
        "output_dir": _relative(output_dir, root),
        "manifest": _relative(output_dir / "manifest.json", root),
    }


def verify_account_bundle(root: Path, output_dir: Path) -> dict[str, Any]:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return {"ok": False, "output_dir": _relative(output_dir, root), "errors": ["missing:manifest.json"]}
    manifest = _read_json(manifest_path)
    manifest_status = str(manifest.get("status") or "")
    if manifest_status != "ready_offline":
        return {
            "ok": True,
            "status": manifest_status or "pending_nas_sync",
            "account_name": manifest.get("account_name", output_dir.parent.name),
            "output_dir": _relative(output_dir, root),
            "selected_count": manifest.get("selected_count", 0),
            "direction_count": manifest.get("direction_count", 0),
            "verified_bytes": 0,
            "gaps": manifest.get("gaps", []),
            "errors": [],
        }
    errors: list[str] = []
    counted_bytes = 0
    for item in manifest.get("items", []):
        bundle_dir = output_dir / str(item["bundle_path"])
        card_path = bundle_dir / "学习卡.md"
        bundle_manifest_path = bundle_dir / "bundle_manifest.json"
        artifact_dir = bundle_dir / "完整产出物"
        if not card_path.is_file():
            errors.append(f"missing:{card_path.relative_to(output_dir)}")
        if not bundle_manifest_path.is_file():
            errors.append(f"missing:{bundle_manifest_path.relative_to(output_dir)}")
            continue
        bundle_manifest = _read_json(bundle_manifest_path)
        for file_info in bundle_manifest.get("files", []):
            path = artifact_dir / str(file_info["path"])
            if not path.is_file():
                errors.append(f"missing:{path.relative_to(output_dir)}")
                continue
            actual_size = path.stat().st_size
            if actual_size != int(file_info["bytes"]):
                errors.append(f"size_mismatch:{path.relative_to(output_dir)}")
                continue
            if _sha256(path) != str(file_info["sha256"]):
                errors.append(f"sha256_mismatch:{path.relative_to(output_dir)}")
            counted_bytes += actual_size
        if any(path.is_symlink() for path in artifact_dir.rglob("*")):
            errors.append(f"symlink_not_portable:{artifact_dir.relative_to(output_dir)}")
    if int(manifest.get("selected_count", -1)) != len(manifest.get("items", [])):
        errors.append("selected_count_mismatch")
    if counted_bytes != int(manifest.get("total_bytes", -1)):
        errors.append("total_bytes_mismatch")
    return {
        "ok": not errors,
        "status": "verified" if not errors else "invalid",
        "account_name": manifest.get("account_name", output_dir.parent.name),
        "output_dir": _relative(output_dir, root),
        "selected_count": manifest.get("selected_count", 0),
        "direction_count": manifest.get("direction_count", 0),
        "verified_bytes": counted_bytes,
        "errors": errors,
    }


def build_offline_sources(
    root: Path,
    *,
    nas_root: Path | None = None,
    accounts: list[str] | None = None,
    min_total: int = 10,
    max_total: int = 20,
    per_direction_max: int = 5,
    apply: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    if min_total < 1 or max_total < min_total:
        raise ValueError("expected 1 <= min_total <= max_total")
    if per_direction_max < 1:
        raise ValueError("per_direction_max must be at least 1")
    selected_accounts = _load_accounts(root, accounts)
    nas_root = _resolve_nas_root(root, selected_accounts, nas_root)
    account_results: list[dict[str, Any]] = []
    total_bytes = 0
    has_errors = False

    for account in selected_accounts:
        account_name = str(account["account_name"])
        platform = str(account.get("platform") or "")
        account_center = (root / str(account["skill_path"])).parent.parent
        existing_manifest = _existing_manifest(account_center)
        if nas_root is None or not nas_root.is_dir():
            if existing_manifest is not None:
                account_results.append(
                    {
                        "ok": True,
                        "account_name": account_name,
                        "platform": platform,
                        "account_center": _relative(account_center, root),
                        "offline_source_status": "nas_unavailable_existing_bundle_preserved",
                        "selected_count": int(existing_manifest.get("selected_count", 0)),
                        "direction_count": int(existing_manifest.get("direction_count", 0)),
                        "direction_counts": existing_manifest.get("direction_counts", {}),
                        "total_bytes": int(existing_manifest.get("total_bytes", 0)),
                        "manifest": _relative(account_center / OUTPUT_DIR_NAME / "manifest.json", root),
                        "selection_diff": {
                            "status": "unavailable_without_nas",
                            "added": [],
                            "removed": [],
                            "changed": [],
                            "unchanged_count": int(existing_manifest.get("selected_count", 0)),
                        },
                        "gaps": ["nas_unavailable"],
                        "errors": [],
                    }
                )
                continue
            pending_result: dict[str, Any] = {
                "ok": True,
                "account_name": account_name,
                "platform": platform,
                "account_center": _relative(account_center, root),
                "offline_source_status": "pending_nas_sync",
                "selected_count": 0,
                "direction_count": 0,
                "direction_counts": {},
                "total_bytes": 0,
                "manifest": _relative(account_center / OUTPUT_DIR_NAME / "manifest.json", root),
                "selection_diff": {
                    "status": "unavailable_without_nas",
                    "added": [],
                    "removed": [],
                    "changed": [],
                    "unchanged_count": 0,
                },
                "gaps": ["nas_unavailable"],
                "errors": [],
            }
            if apply:
                pending_result["write"] = _write_pending_bundle(
                    root=root,
                    account_center=account_center,
                    account_name=account_name,
                    platform=platform,
                )
            account_results.append(pending_result)
            continue
        account_center, candidates, discovery = _build_candidates(
            root=root,
            account=account,
            nas_root=nas_root,
            candidate_limit=max(per_direction_max * 2, 10),
        )
        selected, errors = _select_candidates(
            candidates,
            min_total=min_total,
            max_total=max_total,
            per_direction_max=per_direction_max,
        )
        inspected: list[SourceCandidate] = []
        for item in selected:
            inspection = _inspect_source(item.source_dir)
            inspected.append(
                replace(
                    item,
                    content_type=str(inspection["content_type"]),
                    file_count=int(inspection["file_count"]),
                    byte_count=int(inspection["byte_count"]),
                    quality_score=int(inspection["quality_score"]),
                    portable_ready=bool(inspection["portable_ready"]),
                    missing_core=tuple(inspection["missing_core"]),
                )
            )
        selected = inspected
        for item in selected:
            if not item.portable_ready:
                errors.append(
                    f"selected_source_incomplete:{item.direction}:{item.source_id}:{','.join(item.missing_core)}"
                )
        formal_directions = int(discovery["formal_direction_count"])
        matched_directions = int(discovery["matched_direction_count"])
        if matched_directions != formal_directions:
            missing_directions = sorted(set(_card_inventory(account_center)) - set(candidates))
            errors.extend(f"source_root_unmatched:{direction}" for direction in missing_directions)
        direction_counts: dict[str, int] = defaultdict(int)
        for item in selected:
            direction_counts[item.direction] += 1
        planned_bytes = sum(item.byte_count for item in selected)
        total_bytes += planned_bytes
        selection_diff = _selection_diff(existing_manifest, selected)
        result: dict[str, Any] = {
            "ok": not errors,
            "account_name": account_name,
            "platform": platform,
            "account_center": _relative(account_center, root),
            "source_root": discovery["source_root"],
            "formal_direction_count": formal_directions,
            "matched_direction_count": matched_directions,
            "selected_count": len(selected),
            "direction_counts": dict(sorted(direction_counts.items())),
            "manifest": _relative(account_center / OUTPUT_DIR_NAME / "manifest.json", root),
            "planned_bytes": planned_bytes,
            "planned_size": _human_size(planned_bytes),
            "offline_source_status": (
                "refresh_review_required"
                if existing_manifest is not None and selection_diff["status"] == "changes_detected"
                else "ready_offline_unchanged"
                if existing_manifest is not None
                else "ready_to_build"
            ),
            "existing_bundle": existing_manifest is not None,
            "selection_diff": selection_diff,
            "gaps": [],
            "errors": errors,
            "items": [
                {
                    "direction": item.direction,
                    "source_id": item.source_id,
                    "title": item.title,
                    "content_type": item.content_type,
                    "bytes": item.byte_count,
                    "file_count": item.file_count,
                    "quality_score": item.quality_score,
                    "source_dir": str(item.source_dir),
                    "formal_card": _relative(item.card_path, root),
                }
                for item in selected
            ],
        }
        if errors:
            has_errors = True
        elif apply and existing_manifest is not None and not force:
            result["write_skipped"] = "existing_bundle_requires_explicit_force_after_diff_review"
        elif apply:
            free_bytes = shutil.disk_usage(account_center).free
            if free_bytes < int(planned_bytes * 1.1):
                result["ok"] = False
                result["errors"].append("insufficient_local_disk_space")
                has_errors = True
            else:
                written = _write_account_bundle(
                    root=root,
                    account_center=account_center,
                    account_name=account_name,
                    platform=platform,
                    selected=selected,
                    discovery=discovery,
                    force=force,
                )
                result["write"] = written
                result["manifest"] = written["manifest"]
                result["offline_source_status"] = "ready_offline"
        account_results.append(result)

    offline_statuses = {str(item.get("offline_source_status") or "") for item in account_results}
    if has_errors:
        overall_status = "partial_failure"
    elif offline_statuses & {"pending_nas_sync", "nas_unavailable_existing_bundle_preserved"}:
        overall_status = "nas_unavailable"
    elif any("write" in item and item.get("offline_source_status") == "ready_offline" for item in account_results):
        overall_status = "applied"
    elif "refresh_review_required" in offline_statuses:
        overall_status = "refresh_review_required"
    else:
        overall_status = "dry_run"
    return {
        "ok": not has_errors,
        "status": overall_status,
        "nas_root": str(nas_root) if nas_root is not None else "",
        "policy": {
            "min_total_per_account": min_total,
            "max_total_per_account": max_total,
            "max_per_direction": per_direction_max,
            "selection": "先覆盖每个方向 1 条，再均匀补到每账号最少总数；优先完整度高且体积小的条目",
        },
        "account_count": len(account_results),
        "selected_count": sum(int(item.get("selected_count", 0)) for item in account_results),
        "planned_bytes": total_bytes,
        "planned_size": _human_size(total_bytes),
        "accounts": account_results,
    }


def verify_offline_sources(root: Path, accounts: list[str] | None = None) -> dict[str, Any]:
    root = root.resolve()
    selected_accounts = _load_accounts(root, accounts)
    results = []
    for account in selected_accounts:
        account_center = (root / str(account["skill_path"])).parent.parent
        results.append(verify_account_bundle(root, account_center / OUTPUT_DIR_NAME))
    all_ok = all(result["ok"] for result in results)
    all_verified = all(result.get("status") == "verified" for result in results)
    return {
        "ok": all_ok,
        "status": "verified" if all_ok and all_verified else "pending" if all_ok else "invalid",
        "account_count": len(results),
        "selected_count": sum(int(result.get("selected_count", 0)) for result in results),
        "verified_bytes": sum(int(result.get("verified_bytes", 0)) for result in results),
        "accounts": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build self-contained lightweight offline evidence packages inside formal account centers."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default="")
    parser.add_argument("--account", action="append", dest="accounts")
    parser.add_argument("--min-total", type=int, default=10)
    parser.add_argument("--max-total", type=int, default=20)
    parser.add_argument("--per-direction-max", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify and args.apply:
        parser.error("--verify and --apply are mutually exclusive")
    try:
        if args.verify:
            result = verify_offline_sources(Path(args.root), args.accounts)
        else:
            result = build_offline_sources(
                Path(args.root),
                nas_root=Path(args.nas_root) if args.nas_root else None,
                accounts=args.accounts,
                min_total=args.min_total,
                max_total=args.max_total,
                per_direction_max=args.per_direction_max,
                apply=args.apply,
                force=args.force,
            )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
