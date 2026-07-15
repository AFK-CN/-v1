from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.account_learning_card import validate_card_text
from tools.jianghushuo_v2_learning import (
    candidate_records,
    batch_items,
    content_classification,
    full_relearning_sequence,
    render_upgraded_card,
    relearning_sequence,
)
from tools.video_learning import NormalizedRecord


REPO_ROOT = Path(__file__).resolve().parents[1]


class JianghushuoV2LearningTests(unittest.TestCase):
    def test_commercial_classification_does_not_treat_discussion_as_an_ad(self) -> None:
        record = SimpleNamespace(
            title="为什么接广告不能只看报价",
            body="这期讨论创作者如何判断广告，不包含赞助或合作推广声明。",
            tags=["自媒体"],
        )

        self.assertEqual(content_classification(record)["id"], "natural_content")

    def test_commercial_and_collaboration_markers_are_isolated_from_natural_v1(self) -> None:
        ad = SimpleNamespace(title="本视频由甲品牌赞助", body="", tags=[])
        interview = SimpleNamespace(title="采访一位嘉宾", body="", tags=[])

        self.assertEqual(content_classification(ad)["id"], "product_ad")
        self.assertTrue(content_classification(ad)["excluded_from_natural_v1"])
        self.assertEqual(content_classification(interview)["id"], "collaboration_ownership")
        self.assertTrue(content_classification(interview)["excluded_from_natural_v1"])

    def test_relearning_sequence_covers_all_downgraded_cards_once(self) -> None:
        sequence = relearning_sequence(REPO_ROOT)

        self.assertEqual(len(sequence), 127)
        self.assertEqual(len({item["source_id"] for item in sequence}), 127)
        self.assertEqual(len(batch_items(REPO_ROOT, 1, 10)), 10)
        self.assertGreaterEqual(len({item["direction"] for item in batch_items(REPO_ROOT, 1, 10)}), 10)

    def test_full_relearning_sequence_comes_from_current_database(self) -> None:
        sequence = full_relearning_sequence(REPO_ROOT)

        self.assertEqual(len(sequence), 598)
        self.assertEqual(len({item["source_id"] for item in sequence}), 598)

    def test_upgraded_card_uses_single_primary_direction_and_passes_contract(self) -> None:
        item = batch_items(REPO_ROOT, 1, 10)[0]
        legacy_text = (REPO_ROOT / item["legacy_candidate_path"]).read_text(encoding="utf-8")
        record = NormalizedRecord(
            platform="douyin",
            source_id=item["source_id"],
            source_file="candidate.json",
            title="项目驱动学习才能变现",
            body="通过真实项目发现问题、解决问题，并把过程公开记录。",
            author_name="姜胡说",
            published_at="2026-01-01",
            metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
            tags=["学习", "成长"],
            url=f"https://www.douyin.com/video/{item['source_id']}",
            video_download_url="",
            text_fingerprint="sample",
            account_name="姜胡说",
            image_urls=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            srt = Path(tmp) / "transcript.srt"
            srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n学习就可以赚钱\n", encoding="utf-8")
            text = render_upgraded_card(
                record,
                item,
                "batch_01",
                {"has_video": True, "has_transcript": True, "has_keyframes": True, "has_scenes": True},
                legacy_text,
                srt,
            )

        validation = validate_card_text(text)
        self.assertTrue(validation.valid, validation.errors)
        self.assertIn(f"主方向：{item['direction']}", text)
        self.assertIn("旧卡不重复计为独立来源", text)
        self.assertIn("状态：candidate_learned", text)

    def test_legacy_candidate_records_returns_all_five_lenses(self) -> None:
        item = batch_items(REPO_ROOT, 1, 10)[0]
        legacy_text = (REPO_ROOT / item["legacy_candidate_path"]).read_text(encoding="utf-8")
        record = NormalizedRecord(
            platform="douyin",
            source_id=item["source_id"],
            source_file="candidate.json",
            title="项目驱动学习",
            body="通过真实项目发现问题并公开记录。",
            author_name="姜胡说",
            published_at="",
            metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
            tags=[],
            url="",
            video_download_url="",
            text_fingerprint="sample",
            account_name="姜胡说",
        )

        result = candidate_records(
            record,
            item,
            "batch_01",
            {"has_transcript": True, "has_keyframes": True},
            legacy_text,
        )

        self.assertEqual(set(result), {"positioning", "topics", "structures", "expression", "counterexamples"})


if __name__ == "__main__":
    unittest.main()
