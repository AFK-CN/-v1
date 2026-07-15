import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.jianghushuo_evidence_acquire import acquisition_inventory
from tools.video_learning import NormalizedRecord


def record(source_id: str, video_url: str = "") -> NormalizedRecord:
    return NormalizedRecord(
        platform="douyin",
        source_id=source_id,
        source_file="test",
        title=source_id,
        body=source_id,
        author_name="姜胡说",
        published_at="",
        metrics={"likes": 0, "collects": 0, "comments": 0, "shares": 0},
        tags=[],
        url="",
        video_download_url=video_url,
        text_fingerprint=source_id,
        account_name="姜胡说",
    )


class JianghushuoEvidenceAcquireTests(unittest.TestCase):
    def test_inventory_separates_ready_eligible_and_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            account_dir = Path(tmp)
            plan = [{"source_id": "1"}, {"source_id": "2"}, {"source_id": "3"}, {"source_id": "4"}]
            by_id = {"1": record("1"), "2": record("2", "https://example.com/2.mp4"), "3": record("3")}
            with patch("tools.jianghushuo_evidence_acquire.bundle_ready", side_effect=lambda _, sid: sid == "1"), patch(
                "tools.jianghushuo_evidence_acquire.media_file_is_usable", return_value=False
            ):
                result = acquisition_inventory(plan, by_id, account_dir)

        self.assertEqual(result["ready_ids"], ["1"])
        self.assertEqual(result["eligible_ids"], ["2"])
        self.assertEqual(result["unavailable_video_url_ids"], ["3"])
        self.assertEqual(result["missing_record_ids"], ["4"])


if __name__ == "__main__":
    unittest.main()
