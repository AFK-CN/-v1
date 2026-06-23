import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import content_rough_scan
from tools.video_learning import NormalizedRecord


def make_record(
    source_id: str,
    platform: str,
    account_name: str,
    title: str,
    body: str = "",
    tags: list[str] | None = None,
    likes: int = 10,
) -> NormalizedRecord:
    return NormalizedRecord(
        platform=platform,
        source_id=source_id,
        source_file="fixture.json",
        title=title,
        body=body,
        author_name=account_name,
        published_at="",
        metrics={"likes": likes, "collects": 2, "comments": 1, "shares": 1},
        tags=tags or [],
        url=f"https://example.com/{source_id}",
        video_download_url="",
        text_fingerprint=source_id,
        account_name=account_name,
    )


def test_profile(expected_count: int = 2) -> dict:
    return {
        "profile_id": "fixture",
        "account_name": "目标账号",
        "platforms": ["douyin", "xhs"],
        "expected_count": expected_count,
        "confidence_margin": 0.2,
        "directions": {
            "赚钱": ["赚钱", "变现"],
            "阅读输入": ["读书", "阅读"],
        },
        "excluded_deep_ids": [],
    }


class ContentRoughScanTests(unittest.TestCase):
    def test_jsonl_reader_does_not_split_unicode_line_separator_inside_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            rows = [{"source_id": "1", "title": "前半段\u2028后半段"}]
            content_rough_scan.write_jsonl(path, rows)
            self.assertEqual(content_rough_scan.read_jsonl(path), rows)

    def test_confirmed_deep_items_replace_lowest_unconfirmed_within_direction_limit(self):
        plan_items = [
            {"source_id": "1", "primary_direction": "赚钱", "direction_rank": 1},
            {"source_id": "2", "primary_direction": "赚钱", "direction_rank": 2},
        ]
        resolved = content_rough_scan.resolve_deep_items(
            plan_items,
            confirmed={"3": "赚钱"},
            direction_limits={"赚钱": 2},
            excluded_ids=set(),
        )
        self.assertEqual(set(resolved), {"1", "3"})
        self.assertTrue(resolved["3"]["confirmed_learned"])

    def test_core_direction_keywords_outweigh_support_keywords(self):
        profile = test_profile(expected_count=1)
        profile["directions"] = {
            "赚钱": {"core": ["赚钱"], "support": []},
            "阅读输入": {"core": ["阅读"], "support": ["赚钱"]},
        }
        rows = content_rough_scan.build_inventory(
            Path("/tmp"),
            [make_record("d1", "douyin", "目标账号", "赚钱方法")],
            profile,
        )
        self.assertEqual(rows[0]["primary_direction"], "赚钱")
        self.assertFalse(rows[0]["needs_review"])

    def test_build_inventory_supports_douyin_transcript_and_xhs_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_dir = root / "01_Case_Cleaning/video_learning/video_artifacts/douyin_d1"
            transcript_dir.mkdir(parents=True)
            (transcript_dir / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n赚钱方法\n", encoding="utf-8")
            manifest_dir = root / "01_Case_Cleaning/video_learning/state"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "learning_manifest.json").write_text(
                json.dumps({"items": {"xhs:x1": {"image": {"images": [{"ocr_text": "阅读一本好书"}]}}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            records = [
                make_record("d1", "douyin", "目标账号", "普通人的方法"),
                make_record("x1", "xhs", "目标账号", "图文笔记"),
                make_record("d2", "douyin", "其他账号", "赚钱"),
            ]

            rows = content_rough_scan.build_inventory(root, records, test_profile())

        self.assertEqual({row["source_id"] for row in rows}, {"d1", "x1"})
        by_id = {row["source_id"]: row for row in rows}
        self.assertEqual(by_id["d1"]["primary_direction"], "赚钱")
        self.assertIn("transcript", by_id["d1"]["text_sources"])
        self.assertEqual(by_id["x1"]["primary_direction"], "阅读输入")
        self.assertEqual(by_id["x1"]["content_type"], "image_text")
        self.assertIn("ocr", by_id["x1"]["text_sources"])

    def test_partial_transcript_is_flagged_for_video_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "01_Case_Cleaning/video_learning/video_artifacts/douyin_d1"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "source.mp4").write_bytes(b"video")
            (artifact_dir / "transcript.srt").write_text(
                "1\n00:00:00,000 --> 00:00:10,000\n赚钱方法\n",
                encoding="utf-8",
            )
            (artifact_dir / "transcript.json").write_text(
                '{"segments": [{"start": 0, "end": 10, "text": "赚钱方法"}]}',
                encoding="utf-8",
            )

            with patch("tools.content_rough_scan.transcript_covers_video", return_value=False, create=True):
                rows = content_rough_scan.build_inventory(
                    root,
                    [make_record("d1", "douyin", "目标账号", "普通人的方法")],
                    test_profile(expected_count=1),
                )

        self.assertIn("partial_transcript", rows[0]["text_sources"])
        self.assertEqual(rows[0]["material_status"], "video_and_partial_transcript")
        self.assertEqual(content_rough_scan.evidence_level(rows[0]), "needs_video_review")

    def test_deep_plan_direction_is_authoritative_and_excluded_media_is_preserved(self):
        profile = test_profile(expected_count=2)
        profile["excluded_deep_ids"] = ["d2"]
        records = [
            make_record("d1", "douyin", "目标账号", "读书也能赚钱"),
            make_record("d2", "douyin", "目标账号", "读书方法"),
        ]
        deep_items = {
            "d1": {"primary_direction": "阅读输入"},
            "d2": {"primary_direction": "阅读输入"},
        }

        rows = content_rough_scan.build_inventory(Path("/tmp"), records, profile, deep_items=deep_items)
        by_id = {row["source_id"]: row for row in rows}

        self.assertEqual(by_id["d1"]["primary_direction"], "阅读输入")
        self.assertEqual(by_id["d1"]["deep_learning_status"], "selected")
        self.assertEqual(by_id["d2"]["deep_learning_status"], "excluded_missing_media")
        self.assertFalse(by_id["d2"]["is_deep_learning_target"])

    def test_low_confidence_and_ties_require_review_until_overridden(self):
        records = [
            make_record("d1", "douyin", "目标账号", "读书赚钱"),
            make_record("d2", "douyin", "目标账号", "没有关键词"),
        ]
        rows = content_rough_scan.build_inventory(Path("/tmp"), records, test_profile())
        by_id = {row["source_id"]: row for row in rows}

        self.assertTrue(by_id["d1"]["needs_review"])
        self.assertEqual(by_id["d1"]["review_reason"], "top_score_tied")
        self.assertTrue(by_id["d2"]["needs_review"])
        self.assertEqual(by_id["d2"]["review_reason"], "no_direction_signal")

        reviewed = content_rough_scan.apply_overrides(
            rows,
            {
                "d1": {"primary_direction": "阅读输入", "note": "主题以学习方法为主"},
                "d2": {"primary_direction": "赚钱", "note": "人工审核"},
            },
            test_profile(),
        )
        self.assertFalse(any(row["needs_review"] for row in reviewed))

    def test_validation_rejects_duplicates_missing_rows_and_unreviewed_items(self):
        profile = test_profile(expected_count=2)
        good = [
            {"source_id": "1", "account_name": "目标账号", "primary_direction": "赚钱", "needs_review": False, "is_deep_learning_target": True},
            {"source_id": "2", "account_name": "目标账号", "primary_direction": "阅读输入", "needs_review": False, "is_deep_learning_target": False},
        ]
        self.assertEqual(content_rough_scan.validate_inventory(good, profile, expected_deep_count=1), [])
        broken = [dict(good[0]), dict(good[0], needs_review=True)]
        errors = content_rough_scan.validate_inventory(broken, profile, expected_deep_count=1)
        self.assertTrue(any("duplicate" in error for error in errors))
        self.assertTrue(any("needs_review" in error for error in errors))

    def test_write_outputs_creates_inventory_review_and_direction_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = content_rough_scan.build_inventory(
                root,
                [
                    make_record("1", "douyin", "目标账号", "赚钱"),
                    make_record("2", "xhs", "目标账号", "读书"),
                ],
                test_profile(),
            )
            result = content_rough_scan.write_outputs(root, test_profile(), rows, validation_errors=[])

            output_dir = root / result["output_dir"]
            inventory = (output_dir / "all_content_inventory.jsonl").read_text(encoding="utf-8").splitlines()
            direction_files = list((output_dir / "directions").glob("*/粗扫内容和选题.md"))
            review_exists = (output_dir / "review_queue.jsonl").exists()
            validation_exists = (output_dir / "validation_report.json").exists()

        self.assertEqual(len(inventory), 2)
        self.assertEqual(len(direction_files), 2)
        self.assertTrue(review_exists)
        self.assertTrue(validation_exists)

    def test_direction_markdown_extracts_candidate_radar_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_dir = root / "01_Case_Cleaning/video_learning/video_artifacts/douyin_1"
            transcript_dir.mkdir(parents=True)
            (transcript_dir / "transcript.srt").write_text(
                "1\n00:00:00,000 --> 00:00:02,000\n很多人以为赚钱靠项目，其实赚钱靠解决问题。\n",
                encoding="utf-8",
            )
            rows = content_rough_scan.build_inventory(
                root,
                [
                    make_record("1", "douyin", "目标账号", "普通人如何赚钱", "很多人以为赚钱靠项目，其实赚钱靠解决问题。", likes=100),
                    make_record("2", "douyin", "目标账号", "读书方法", likes=10),
                ],
                test_profile(),
            )

            markdown = content_rough_scan.direction_markdown("赚钱", [row for row in rows if row["primary_direction"] == "赚钱"], test_profile())

        self.assertIn("## 3. 主题簇", markdown)
        self.assertIn("## 4. 候选短句", markdown)
        self.assertIn("## 5. 候选问题句", markdown)
        self.assertIn("## 6. 候选反常识表达", markdown)
        self.assertIn("[transcript_available]", markdown)
        self.assertIn("普通人如何赚钱", markdown)

    def test_write_outputs_writes_rough_scan_insights_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = content_rough_scan.build_inventory(
                root,
                [make_record("1", "douyin", "目标账号", "真正的赚钱不是卖时间，而是解决问题。", likes=100)],
                test_profile(expected_count=1),
            )
            result = content_rough_scan.write_outputs(root, test_profile(expected_count=1), rows, validation_errors=[])
            insights_path = root / result["output_dir"] / "directions" / "赚钱" / "rough_scan_insights.json"
            insights = json.loads(insights_path.read_text(encoding="utf-8"))

        self.assertEqual(insights["direction"], "赚钱")
        self.assertTrue(insights["topic_clusters"])
        self.assertTrue(insights["expressions"])


if __name__ == "__main__":
    unittest.main()
