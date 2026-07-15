from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.jianghushuo_nas import evidence_status, resolve_evidence_dir, transcript_path, video_path


class JianghushuoNasTests(unittest.TestCase):
    def test_current_dy_layout_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "accounts" / "dy_77700555383" / "dy_1234567890123456789" / "video"
            frames = video / "frames"
            frames.mkdir(parents=True)
            (video / "source.mp4").write_bytes(b"video")
            (video / "audio.wav").write_bytes(b"audio")
            (video / "transcript.srt").write_text("这是一段足够完整、可以支撑内容学习和原文回查的逐字稿。", encoding="utf-8")
            (video / "frames.json").write_text("{}", encoding="utf-8")
            (frames / "000001.jpg").write_bytes(b"jpg")

            status = evidence_status("1234567890123456789", root)

            self.assertEqual(resolve_evidence_dir("1234567890123456789", root), video)
            self.assertEqual(transcript_path("1234567890123456789", root), video / "transcript.srt")
            self.assertTrue(status["has_video"])
            self.assertTrue(status["has_transcript"])
            self.assertTrue(status["has_keyframes"])
            self.assertTrue(status["has_scenes"])
            self.assertEqual(status["scene_evidence_kind"], "time_sampled_frames")

    def test_legacy_layout_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            account = Path(tmp) / "姜胡说"
            bundle = account / "douyin_1234567890123456789"
            keyframes = bundle / "keyframes"
            keyframes.mkdir(parents=True)
            (bundle / "source.mp4").write_bytes(b"video")
            (bundle / "transcript.srt").write_text("这是一段足够完整、可以支撑内容学习和原文回查的逐字稿。", encoding="utf-8")
            (bundle / "source-Scenes.csv").write_text("scene", encoding="utf-8")
            (keyframes / "frame.jpg").write_bytes(b"jpg")

            status = evidence_status("1234567890123456789", Path(tmp))

            self.assertEqual(status["layout"], "legacy_douyin_bundle")
            self.assertTrue(status["has_keyframes"])
            self.assertTrue(status["has_scenes"])
            self.assertEqual(status["scene_evidence_kind"], "scene_csv")

    def test_watermark_only_transcript_is_not_evidence_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "accounts" / "dy_77700555383" / "dy_1234567890123456789" / "video"
            video.mkdir(parents=True)
            (video / "source.mp4").write_bytes(b"video")
            (video / "transcript.srt").write_text(
                "1\n00:00:00,000 --> 00:00:03,000\n字幕by索兰娅\n", encoding="utf-8"
            )

            status = evidence_status("1234567890123456789", root)

            self.assertFalse(status["has_transcript"])
            self.assertTrue(status["transcript_file_present"])
            self.assertEqual(status["transcript_quality"]["reason"], "junk_only")

    def test_codex_video_is_used_only_when_original_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "dy_1234567890123456789" / "video"
            video.mkdir(parents=True)
            recovered = video / "source.codex.mp4"
            recovered.write_bytes(b"recovered")

            self.assertEqual(video_path("1234567890123456789", root), recovered)
            self.assertTrue(evidence_status("1234567890123456789", root)["has_video"])

            original = video / "source.mp4"
            original.write_bytes(b"original")
            self.assertEqual(video_path("1234567890123456789", root), original)


if __name__ == "__main__":
    unittest.main()
