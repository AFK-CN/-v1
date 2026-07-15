from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.jianghushuo_current_nas_repair import attempted_source_ids, frame_interval, select_candidates


class JianghushuoCurrentNasRepairTests(unittest.TestCase):
    def test_frame_interval_targets_twelve_frames_without_subsecond_sampling(self) -> None:
        self.assertEqual(frame_interval(6.0), 1.0)
        self.assertEqual(frame_interval(120.0), 10.0)

    def test_select_candidates_supports_source_ids_and_paging(self) -> None:
        candidates = [{"source_id": str(value)} for value in range(5)]
        self.assertEqual(
            [item["source_id"] for item in select_candidates(candidates, source_ids=["3", "1"])],
            ["1", "3"],
        )
        self.assertEqual(
            [item["source_id"] for item in select_candidates(candidates, offset=2, limit=2)],
            ["2", "3"],
        )

    def test_attempted_source_ids_ignores_malformed_history_lines(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.jsonl"
            path.write_text('{"source_id":"123"}\nnot-json\n{"source_id":"456"}\n', encoding="utf-8")
            self.assertEqual(attempted_source_ids(path), {"123", "456"})


if __name__ == "__main__":
    unittest.main()
