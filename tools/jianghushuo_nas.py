from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


CURRENT_ACCOUNT_DIR = Path("/Volumes/AFK/zhishikushuju/dy/accounts/dy_77700555383")
PREVIOUS_MOUNT_ACCOUNT_DIR = Path("/Volumes/dy/accounts/dy_77700555383")
LEGACY_ACCOUNT_DIR = Path("/Volumes/AFK/zhishikushuju/姜胡说")
TRANSCRIPT_JUNK_MARKERS = (
    "字幕by索兰娅",
    "字幕由",
    "感谢观看",
    "谢谢观看",
    "来聊那我们是不是应该放在音乐挺啊算了不不放音乐了晚上放音乐不好是不是",
    "那我们是不是应该放在音乐",
    "算了不不放音乐了",
    "晚上放音乐不好是不是",
)


def read_transcript_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            segments = payload.get("segments")
            if isinstance(segments, list):
                raw_values = [str(item.get("text") or "") for item in segments if isinstance(item, dict)]
            else:
                raw_values = [str(payload.get("text") or "")]
        elif isinstance(payload, list):
            raw_values = [str(item.get("text") or "") for item in payload if isinstance(item, dict)]
        else:
            raw_values = []
    else:
        raw_values = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    values: list[str] = []
    for raw in raw_values:
        value = raw.strip()
        if not value or value.isdigit() or "-->" in value:
            continue
        compact = re.sub(r"\s+", "", value).lower()
        normalized_compact = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", compact)
        if normalized_compact == "来聊" or any(
            re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", marker.lower()) in normalized_compact
            for marker in TRANSCRIPT_JUNK_MARKERS
        ):
            continue
        if compact and not re.search(r"[^嗯啊哎呀哦呃诶嘿哈完了]", compact):
            continue
        values.append(value)
    return values


def transcript_quality(path: Path) -> dict[str, Any]:
    file_present = path.is_file() and path.stat().st_size > 0
    lines = read_transcript_lines(path) if file_present else []
    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", "".join(lines))
    char_count = len(normalized)
    usable = char_count >= 20
    if not file_present:
        reason = "missing"
    elif not lines:
        reason = "junk_only"
    elif not usable:
        reason = "too_short"
    else:
        reason = "usable"
    return {
        "file_present": file_present,
        "usable": usable,
        "reason": reason,
        "line_count": len(lines),
        "normalized_char_count": char_count,
    }


def account_dir_candidates(nas_root: Path | None = None) -> list[Path]:
    """Return compatible Jianghushuo account directories, newest layout first."""

    candidates: list[Path] = []
    if nas_root is not None:
        root = nas_root.expanduser()
        candidates.extend(
            [
                root,
                root / "accounts" / CURRENT_ACCOUNT_DIR.name,
                root / CURRENT_ACCOUNT_DIR.name,
                root / "姜胡说",
            ]
        )
    candidates.extend([CURRENT_ACCOUNT_DIR, PREVIOUS_MOUNT_ACCOUNT_DIR, LEGACY_ACCOUNT_DIR])
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def evidence_dir_candidates(source_id: str, nas_root: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    for account_dir in account_dir_candidates(nas_root):
        candidates.extend(
            [
                account_dir / f"dy_{source_id}" / "video",
                account_dir / f"douyin_{source_id}",
            ]
        )
    return candidates


def resolve_evidence_dir(source_id: str, nas_root: Path | None = None) -> Path:
    """Resolve an existing evidence directory, retaining a deterministic fallback."""

    candidates = evidence_dir_candidates(source_id, nas_root)
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def transcript_path(source_id: str, nas_root: Path | None = None) -> Path:
    artifact_dir = resolve_evidence_dir(source_id, nas_root)
    for name in (
        "transcript.codex.srt",
        "transcript.codex.txt",
        "transcript.codex.json",
        "transcript.srt",
        "transcript.txt",
        "transcript.json",
    ):
        path = artifact_dir / name
        if path.is_file() and path.stat().st_size > 0:
            return path
    return artifact_dir / "transcript.srt"


def video_path(source_id: str, nas_root: Path | None = None) -> Path:
    artifact_dir = resolve_evidence_dir(source_id, nas_root)
    for name in ("source.mp4", "source.codex.mp4"):
        path = artifact_dir / name
        if path.is_file() and path.stat().st_size > 0:
            return path
    return artifact_dir / "source.mp4"


def evidence_status(source_id: str, nas_root: Path | None = None) -> dict[str, Any]:
    artifact_dir = resolve_evidence_dir(source_id, nas_root)
    transcript = transcript_path(source_id, nas_root)
    video = video_path(source_id, nas_root)
    quality = transcript_quality(transcript)
    frame_files = list((artifact_dir / "frames").glob("*.jpg")) + list((artifact_dir / "frames").glob("*.png"))
    frame_files.extend((artifact_dir / "frames_codex").glob("*.jpg"))
    frame_files.extend((artifact_dir / "frames_codex").glob("*.png"))
    frame_files.extend((artifact_dir / "keyframes").glob("*.jpg"))
    frame_files.extend((artifact_dir / "keyframes").glob("*.png"))
    frame_files.extend(artifact_dir.glob("*.jpg"))
    frame_files.extend(artifact_dir.glob("*.png"))
    has_frames = any(path.is_file() and path.stat().st_size > 0 for path in frame_files)
    frame_indexes = (artifact_dir / "frames.codex.json", artifact_dir / "frames.json")
    has_frame_index = any(path.is_file() and path.stat().st_size > 0 for path in frame_indexes)
    legacy_scenes = list(artifact_dir.glob("*Scenes.csv")) + list(artifact_dir.glob("scenes.csv"))
    has_legacy_scenes = any(path.is_file() and path.stat().st_size > 0 for path in legacy_scenes)
    is_current_layout = artifact_dir.name == "video" and artifact_dir.parent.name == f"dy_{source_id}"
    return {
        "artifact_dir": str(artifact_dir),
        "layout": "dy_account_video" if is_current_layout else "legacy_douyin_bundle",
        "has_video": video.is_file() and video.stat().st_size > 0,
        "video_path": str(video),
        "has_audio": any(
            path.is_file() and path.stat().st_size > 0
            for path in (artifact_dir / "audio.codex.wav", artifact_dir / "audio.wav")
        ),
        "has_metadata": any(
            path.is_file() and path.stat().st_size > 0
            for path in (
                artifact_dir / "ffprobe.json",
                artifact_dir / "source.json",
                artifact_dir.parent / "source.json",
                artifact_dir.parent / "manifest_item.json",
                artifact_dir.parent / "status.json",
            )
        ),
        "has_transcript": quality["usable"],
        "transcript_file_present": quality["file_present"],
        "transcript_quality": quality,
        "has_keyframes": has_frames,
        "has_scenes": has_legacy_scenes or (has_frame_index and has_frames),
        "scene_evidence_kind": "time_sampled_frames" if is_current_layout and has_frame_index and has_frames else ("scene_csv" if has_legacy_scenes else "missing"),
        "transcript_path": str(transcript),
    }


def evidence_ready(source_id: str, nas_root: Path | None = None) -> bool:
    video = video_path(source_id, nas_root)
    transcript = transcript_path(source_id, nas_root)
    return bool(video.is_file() and video.stat().st_size > 0 and transcript_quality(transcript)["usable"])
