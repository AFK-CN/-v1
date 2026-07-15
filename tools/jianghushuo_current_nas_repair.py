from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.jianghushuo_nas import CURRENT_ACCOUNT_DIR, evidence_status, transcript_quality, video_path
from tools.jianghushuo_v2_learning import WORKFLOW_ROOT, full_relearning_sequence, write_json
from tools.video_learning import write_transcript_artifacts


FFMPEG = Path("/opt/homebrew/bin/ffmpeg")
FFPROBE = Path("/opt/homebrew/bin/ffprobe")


def frame_interval(duration: float, target_frames: int = 12) -> float:
    return max(duration / max(target_frames, 1), 1.0)


def probe_duration(video_path: Path) -> float:
    completed = subprocess.run(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(completed.stdout.strip())


def probe_stream_types(video_path: Path) -> set[str]:
    completed = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def repair_candidates(root: Path, nas_root: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in full_relearning_sequence(root.resolve()):
        status = evidence_status(str(item["source_id"]), nas_root)
        if status["has_video"] and not status["has_transcript"]:
            values.append({**item, "evidence": status})
    return values


def extract_audio(video_path: Path, artifact_dir: Path) -> Path:
    existing = artifact_dir / "audio.wav"
    if existing.is_file() and existing.stat().st_size > 0:
        return existing
    target = artifact_dir / "audio.codex.wav"
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return target


def transcribe(model: Any, audio_path: Path, artifact_dir: Path) -> dict[str, Any]:
    transcript_json = artifact_dir / "transcript.codex.json"
    transcript_srt = artifact_dir / "transcript.codex.srt"
    transcript_txt = artifact_dir / "transcript.codex.txt"
    attempts = (
        {"vad_filter": True, "condition_on_previous_text": True},
        {"vad_filter": False, "condition_on_previous_text": False},
    )
    final_segments: list[dict[str, Any]] = []
    language = "zh"
    duration: float | None = None
    for settings in attempts:
        raw_segments, info = model.transcribe(str(audio_path), language="zh", **settings)
        final_segments = []
        for segment in raw_segments:
            text = str(segment.text or "").strip()
            if not text:
                continue
            final_segments.append(
                {
                    "index": len(final_segments) + 1,
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                }
            )
        language = str(getattr(info, "language", "zh") or "zh")
        duration = getattr(info, "duration", None)
        write_transcript_artifacts(transcript_json, transcript_srt, language, duration, final_segments)
        transcript_txt.write_text("\n".join(item["text"] for item in final_segments) + ("\n" if final_segments else ""), encoding="utf-8")
        quality = transcript_quality(transcript_srt)
        if quality["usable"]:
            return {"ok": True, "segment_count": len(final_segments), "quality": quality}
    return {
        "ok": False,
        "segment_count": len(final_segments),
        "quality": transcript_quality(transcript_srt),
        "error": "transcript_remains_unusable_after_two_attempts",
    }


def extract_frames(video_path: Path, artifact_dir: Path, target_frames: int = 12) -> dict[str, Any]:
    if "video" not in probe_stream_types(video_path):
        return {"ok": False, "skipped": "no_video_stream", "frame_count": 0}
    frames_dir = artifact_dir / "frames_codex"
    frames_dir.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(video_path)
    interval = frame_interval(duration, target_frames)
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{interval:.6f}",
            "-frames:v",
            str(target_frames),
            str(frames_dir / "%06d.jpg"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    frames = sorted(frames_dir.glob("*.jpg"))
    payload = {
        "generator": "codex_time_sampled_frames_v1",
        "source_video": str(video_path),
        "duration_seconds": duration,
        "interval_seconds": interval,
        "frames": [
            {"path": str(path.relative_to(artifact_dir)), "approx_second": round(index * interval, 3)}
            for index, path in enumerate(frames)
        ],
    }
    (artifact_dir / "frames.codex.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": bool(frames), "frame_count": len(frames), "duration_seconds": duration}


def select_candidates(
    candidates: list[dict[str, Any]],
    *,
    source_ids: list[str] | None = None,
    offset: int = 0,
    limit: int = 0,
) -> list[dict[str, Any]]:
    if source_ids:
        wanted = {str(value) for value in source_ids}
        selected = [item for item in candidates if str(item["source_id"]) in wanted]
    else:
        selected = candidates[max(offset, 0) :]
    return selected[: max(limit, 0)] if limit else selected


def attempted_source_ids(history_path: Path) -> set[str]:
    values: set[str] = set()
    if not history_path.is_file():
        return values
    for raw_line in history_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        source_id = str(payload.get("source_id") or "").strip() if isinstance(payload, dict) else ""
        if source_id:
            values.add(source_id)
    return values


def run(
    root: Path,
    nas_root: Path,
    limit: int,
    with_frames: bool,
    dry_run: bool,
    *,
    source_ids: list[str] | None = None,
    offset: int = 0,
    skip_attempted: bool = False,
    worker_id: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    if not FFMPEG.is_file() or not FFPROBE.is_file():
        raise FileNotFoundError("system ffmpeg/ffprobe not available under /opt/homebrew/bin")
    candidates = repair_candidates(root, nas_root)
    history_path = root / WORKFLOW_ROOT / "EVIDENCE_REPAIR_HISTORY.jsonl"
    skipped_ids = attempted_source_ids(history_path) if skip_attempted else set()
    if skipped_ids:
        candidates = [item for item in candidates if str(item["source_id"]) not in skipped_ids]
    selected = select_candidates(candidates, source_ids=source_ids, offset=offset, limit=limit)
    summary: dict[str, Any] = {
        "ok": True,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "nas_root": str(nas_root),
        "candidate_count": len(candidates),
        "skipped_attempted_count": len(skipped_ids),
        "selected_count": len(selected),
        "selected_ids": [str(item["source_id"]) for item in selected],
        "dry_run": dry_run,
        "worker_id": worker_id,
        "results": [],
        "formal_write_allowed": False,
    }
    if dry_run:
        return summary

    from faster_whisper import WhisperModel  # type: ignore

    model = WhisperModel("tiny", device="cpu", compute_type="int8", local_files_only=True)
    status_name = f"EVIDENCE_REPAIR_STATUS.{worker_id}.json" if worker_id else "EVIDENCE_REPAIR_STATUS.json"
    status_path = root / WORKFLOW_ROOT / status_name
    for item in selected:
        source_id = str(item["source_id"])
        artifact_dir = Path(str(item["evidence"]["artifact_dir"]))
        source_video = video_path(source_id, nas_root)
        result: dict[str, Any] = {"source_id": source_id, "artifact_dir": str(artifact_dir), "ok": False}
        try:
            audio_path = extract_audio(source_video, artifact_dir)
            result["media_stream_types"] = sorted(probe_stream_types(source_video))
            result["transcript"] = transcribe(model, audio_path, artifact_dir)
            if with_frames and not evidence_status(source_id, nas_root)["has_keyframes"]:
                result["frames"] = extract_frames(source_video, artifact_dir)
            result["after"] = evidence_status(source_id, nas_root)
            result["ok"] = bool(result["after"]["has_transcript"])
            if not result["ok"]:
                result["error"] = str(result["transcript"].get("error") or "transcript_unusable")
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        summary["results"].append(result)
        summary["completed_count"] = sum(bool(value.get("ok")) for value in summary["results"])
        summary["failed_count"] = len(summary["results"]) - summary["completed_count"]
        write_json(status_path, summary)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(json.dumps({"source_id": source_id, "ok": result["ok"], "error": result.get("error", "")}, ensure_ascii=False), flush=True)
    summary["ok"] = not any(not value.get("ok") for value in summary["results"])
    write_json(status_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair missing Jianghushuo transcripts in the current dy NAS layout without overwriting original derivatives.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default=str(CURRENT_ACCOUNT_DIR))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--skip-attempted", action="store_true")
    parser.add_argument("--worker-id", default="")
    parser.add_argument("--with-frames", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(
        Path(args.root),
        Path(args.nas_root),
        max(args.limit, 0),
        args.with_frames,
        args.dry_run,
        source_ids=args.source_id,
        offset=max(args.offset, 0),
        skip_attempted=args.skip_attempted,
        worker_id=str(args.worker_id).strip(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
