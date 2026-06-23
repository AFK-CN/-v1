import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.jianghushuo_download_plan import build_download_plan
from tools.video_learning import NormalizedRecord


def record(source_id: str, title: str, body: str = "") -> NormalizedRecord:
    return NormalizedRecord(
        platform="douyin",
        source_id=source_id,
        source_file="test.json",
        title=title,
        body=body,
        author_name="姜胡说",
        published_at="",
        metrics={"likes": int(source_id), "collects": 0, "comments": 0, "shares": 0},
        tags=[],
        url=f"https://example.com/{source_id}",
        video_download_url=f"https://example.com/{source_id}.mp4",
        text_fingerprint=source_id,
        account_name="姜胡说",
    )


class JianghushuoDownloadPlanTests(unittest.TestCase):
    def test_queue_runner_isolates_child_stdin_from_source_id_worklist(self):
        script = (Path(__file__).parents[1] / "tools" / "run_jianghushuo_all_directions_download.sh").read_text(encoding="utf-8")
        self.assertIn('WORKLIST="$(mktemp)"', script)
        self.assertIn('< /dev/null', script)

    def test_assigns_each_video_once_and_excludes_complete_materials(self):
        records = [record("1", "赚钱方法"), record("2", "创业项目"), record("3", "技能积累与产品化")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            complete_dir = root / "01_Case_Cleaning/video_learning/video_artifacts/douyin_1"
            complete_dir.mkdir(parents=True)
            (complete_dir / "source.mp4").write_bytes(b"video")
            (complete_dir / "transcript.srt").write_text("text", encoding="utf-8")
            (complete_dir / "transcript.json").write_text('{"segments": [{"end": 100}]}', encoding="utf-8")

            with patch("tools.jianghushuo_download_plan.media_file_is_usable", return_value=True), patch(
                "tools.jianghushuo_download_plan.transcript_covers_video", return_value=True
            ):
                result = build_download_plan(root, records, top_n=1)

        targets = result["targets"]
        self.assertEqual(len({item["source_id"] for item in targets}), len(targets))
        self.assertIn("技能沉淀", {item["primary_direction"] for item in targets})
        self.assertFalse(next(item for item in targets if item["source_id"] == "1")["needs_download"])
        self.assertNotIn("1", {item["source_id"] for item in result["download_items"]})

    def test_filters_other_accounts(self):
        other = record("9", "赚钱")
        object.__setattr__(other, "account_name", "李宗恒")
        result = build_download_plan(Path("/tmp/not-used"), [record("1", "赚钱"), other], top_n=1)
        self.assertEqual({item["source_id"] for item in result["targets"]}, {"1"})

    def test_incomplete_transcript_is_not_counted_as_complete_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "01_Case_Cleaning/video_learning/video_artifacts/douyin_1"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "source.mp4").write_bytes(b"video")
            (artifact_dir / "transcript.srt").write_text("partial", encoding="utf-8")
            (artifact_dir / "transcript.json").write_text(
                '{"segments": [{"start": 0, "end": 10, "text": "partial"}]}',
                encoding="utf-8",
            )

            with patch("tools.jianghushuo_download_plan.media_file_is_usable", return_value=True):
                result = build_download_plan(root, [record("1", "赚钱方法")], top_n=1)

        self.assertTrue(result["targets"][0]["needs_download"])


if __name__ == "__main__":
    unittest.main()
