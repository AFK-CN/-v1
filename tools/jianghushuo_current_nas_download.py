from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.jianghushuo_current_nas_repair import FFMPEG, extract_audio, extract_frames, probe_duration, probe_stream_types, transcribe
from tools.jianghushuo_nas import CURRENT_ACCOUNT_DIR, evidence_ready, evidence_status, resolve_evidence_dir, transcript_quality, video_path
from tools.jianghushuo_v2_learning import WORKFLOW_ROOT, full_relearning_sequence, write_json
from tools.video_learning import download_binary_url, load_unique_records_detailed, write_transcript_artifacts


def download_candidates(root: Path, nas_root: Path) -> list[dict[str, Any]]:
    records, _, _, _ = load_unique_records_detailed(root.resolve())
    by_id = {record.source_id: record for record in records if record.source_id}
    values: list[dict[str, Any]] = []
    for item in full_relearning_sequence(root.resolve()):
        source_id = str(item["source_id"])
        status = evidence_status(source_id, nas_root)
        if evidence_ready(source_id, nas_root):
            continue
        record = by_id.get(source_id)
        download_url = str(record.video_download_url or "") if record is not None else ""
        values.append(
            {
                **item,
                "download_url": download_url,
                "needs_download": not bool(status["has_video"]),
                "eligible": bool(status["has_video"] or download_url),
                "evidence": status,
            }
        )
    return values


def download_video(download_url: str, source_id: str, nas_root: Path) -> tuple[Path, list[str]]:
    artifact_dir = resolve_evidence_dir(source_id, nas_root)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    target = artifact_dir / "source.codex.mp4"
    if target.is_file() and target.stat().st_size > 0 and "video" in probe_stream_types(target):
        return target, ["using_existing_codex_video"]
    partial = artifact_dir / "source.codex.mp4.download"
    warnings: list[str] = []
    try:
        download_binary_url(download_url, partial)
        stream_types = probe_stream_types(partial)
        if "video" not in stream_types:
            raise RuntimeError(f"downloaded_media_has_no_video_stream:{sorted(stream_types)}")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return target, warnings


def transcribe_chunked(
    model: Any,
    audio_path: Path,
    artifact_dir: Path,
    *,
    source_id: str,
    chunk_seconds: int = 600,
) -> dict[str, Any]:
    duration = probe_duration(audio_path)
    if duration <= chunk_seconds * 1.5:
        return transcribe(model, audio_path, artifact_dir)

    chunks_dir = artifact_dir / "transcript_codex_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_count = max(math.ceil(duration / chunk_seconds), 1)
    merged: list[dict[str, Any]] = []
    for index in range(chunk_count):
        offset = index * chunk_seconds
        chunk_json = chunks_dir / f"chunk_{index:04d}.json"
        if chunk_json.is_file():
            payload = json.loads(chunk_json.read_text(encoding="utf-8"))
            segments = payload.get("segments") if isinstance(payload, dict) else []
            if isinstance(segments, list):
                merged.extend(item for item in segments if isinstance(item, dict))
                print(json.dumps({"source_id": source_id, "chunk": index + 1, "chunk_count": chunk_count, "status": "reused"}, ensure_ascii=False), flush=True)
                continue

        chunk_audio = chunks_dir / f"chunk_{index:04d}.wav"
        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-ss",
                str(offset),
                "-t",
                str(chunk_seconds),
                "-i",
                str(audio_path),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(chunk_audio),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        chunk_segments: list[dict[str, Any]] = []
        attempts = (
            {"vad_filter": True, "condition_on_previous_text": True},
            {"vad_filter": False, "condition_on_previous_text": False},
        )
        for settings in attempts:
            raw_segments, _ = model.transcribe(str(chunk_audio), language="zh", **settings)
            chunk_segments = []
            for segment in raw_segments:
                text_value = str(segment.text or "").strip()
                if not text_value:
                    continue
                chunk_segments.append(
                    {
                        "index": 0,
                        "start": float(segment.start) + offset,
                        "end": float(segment.end) + offset,
                        "text": text_value,
                    }
                )
            if chunk_segments:
                break
        chunk_json.write_text(
            json.dumps({"source_id": source_id, "offset": offset, "segments": chunk_segments}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        chunk_audio.unlink(missing_ok=True)
        merged.extend(chunk_segments)
        print(
            json.dumps(
                {"source_id": source_id, "chunk": index + 1, "chunk_count": chunk_count, "status": "completed", "segment_count": len(chunk_segments)},
                ensure_ascii=False,
            ),
            flush=True,
        )

    merged.sort(key=lambda item: (float(item.get("start") or 0.0), float(item.get("end") or 0.0)))
    for index, item in enumerate(merged, start=1):
        item["index"] = index
    transcript_json = artifact_dir / "transcript.codex.json"
    transcript_srt = artifact_dir / "transcript.codex.srt"
    transcript_txt = artifact_dir / "transcript.codex.txt"
    write_transcript_artifacts(transcript_json, transcript_srt, "zh", duration, merged)
    transcript_txt.write_text("\n".join(str(item["text"]) for item in merged) + ("\n" if merged else ""), encoding="utf-8")
    quality = transcript_quality(transcript_srt)
    return {
        "ok": bool(quality["usable"]),
        "segment_count": len(merged),
        "chunk_count": chunk_count,
        "quality": quality,
        **({} if quality["usable"] else {"error": "chunked_transcript_remains_unusable"}),
    }


def run(
    root: Path,
    nas_root: Path,
    *,
    source_ids: list[str] | None = None,
    limit: int = 0,
    with_frames: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    candidates = download_candidates(root, nas_root)
    eligible = [item for item in candidates if item["eligible"]]
    if source_ids:
        wanted = {str(value) for value in source_ids}
        eligible = [item for item in eligible if str(item["source_id"]) in wanted]
    else:
        eligible = [item for item in eligible if item["needs_download"]]
    selected = eligible[: max(limit, 0)] if limit else eligible
    summary: dict[str, Any] = {
        "ok": True,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "nas_root": str(nas_root),
        "recovery_candidate_count": len(candidates),
        "missing_video_count": sum(bool(item["needs_download"]) for item in candidates),
        "eligible_count": sum(bool(item["eligible"]) for item in candidates),
        "unavailable_url_count": sum(not bool(item["eligible"]) for item in candidates),
        "selected_ids": [str(item["source_id"]) for item in selected],
        "dry_run": dry_run,
        "results": [],
        "formal_write_allowed": False,
    }
    if dry_run or not selected:
        return summary

    from faster_whisper import WhisperModel  # type: ignore

    model = WhisperModel("tiny", device="cpu", compute_type="int8", local_files_only=True)
    status_path = root / WORKFLOW_ROOT / "EVIDENCE_DOWNLOAD_STATUS.json"
    history_path = root / WORKFLOW_ROOT / "EVIDENCE_DOWNLOAD_HISTORY.jsonl"
    for item in selected:
        source_id = str(item["source_id"])
        result: dict[str, Any] = {"source_id": source_id, "ok": False, "download_ok": False}
        try:
            if item["evidence"]["has_video"]:
                source_video = video_path(source_id, nas_root)
                warnings = ["using_existing_candidate_video"]
            else:
                source_video, warnings = download_video(str(item["download_url"]), source_id, nas_root)
            artifact_dir = source_video.parent
            result["download_ok"] = True
            result["download_warnings"] = warnings
            result["media_stream_types"] = sorted(probe_stream_types(source_video))
            audio_path = extract_audio(source_video, artifact_dir)
            result["transcript"] = transcribe_chunked(model, audio_path, artifact_dir, source_id=source_id)
            if with_frames and not evidence_status(source_id, nas_root)["has_keyframes"]:
                result["frames"] = extract_frames(source_video, artifact_dir)
            result["after"] = evidence_status(source_id, nas_root)
            result["ok"] = evidence_ready(source_id, nas_root)
            if not result["ok"]:
                result["error"] = str(result["transcript"].get("error") or "downloaded_but_transcript_unusable")
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        summary["results"].append(result)
        summary["downloaded_count"] = sum(bool(value.get("download_ok")) for value in summary["results"])
        summary["evidence_ready_count"] = sum(bool(value.get("ok")) for value in summary["results"])
        summary["failed_count"] = len(summary["results"]) - summary["evidence_ready_count"]
        write_json(status_path, summary)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(json.dumps({"source_id": source_id, "ok": result["ok"], "error": result.get("error", "")}, ensure_ascii=False), flush=True)
    summary["ok"] = not any(not value.get("ok") for value in summary["results"])
    write_json(status_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover missing Jianghushuo videos from SQLite official play URLs without overwriting NAS originals.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default=str(CURRENT_ACCOUNT_DIR))
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-frames", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(
        Path(args.root),
        Path(args.nas_root),
        source_ids=args.source_id,
        limit=max(args.limit, 0),
        with_frames=not args.no_frames,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
