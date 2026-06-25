from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import video_learning
from tools.kb import web_console


class KBWebConsoleTests(unittest.TestCase):
    def _seed_video_record(self, root: Path) -> str:
        data_dir = root / "数据" / "douyin" / "json" / "姜胡说"
        data_dir.mkdir(parents=True)
        source_id = "a1"
        rows = [
            {
                "aweme_id": source_id,
                "title": "#创业 普通人先行动",
                "desc": "不要想太多，先做一个小实验",
                "nickname": "姜胡说",
                "liked_count": "100",
                "collected_count": "80",
                "comment_count": "20",
                "share_count": "40",
                "aweme_url": "https://www.douyin.com/video/a1",
                "video_download_url": "https://download.example/a1.mp4",
            }
        ]
        (data_dir / "creator_contents.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return source_id

    def test_candidate_batches_group_by_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_video_record(root)
            result = web_console.run_scan_task(root, {"top_n": 10})
            batches = web_console.candidate_batches(root)

            self.assertGreaterEqual(result["result"]["candidate_topics_count"], 1)
            self.assertTrue(batches)
            self.assertEqual(batches[0]["count"], 1)
            self.assertIn(source_id, batches[0]["source_ids"])

    def test_worker_download_task_selects_queue_and_writes_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_video_record(root)
            web_console.run_scan_task(root, {"top_n": 10})
            batches = web_console.candidate_batches(root)
            direction = batches[0]["direction"]
            task = web_console.queue_download_task(root, direction, [source_id])

            def fake_download(url: str, path: Path, timeout: int = 300) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"video")

            with patch("tools.video_learning.ensure_video_file", side_effect=fake_download):
                processed = web_console.run_pending_web_tasks_once(root)

            self.assertTrue(processed)
            task_dir = root / "14_KB_System" / "runtime" / "tasks" / "done" / task["task_id"]
            self.assertTrue(task_dir.exists())
            status = json.loads((task_dir / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["task_status"], "done")
            self.assertTrue((root / "01_Case_Cleaning" / "video_learning" / "video_artifacts" / f"douyin_{source_id}" / "source.mp4").exists())
            queue = video_learning.load_queue(root)
            self.assertTrue(any(item.get("source_id") == source_id for item in queue.get("items", [])))

    def test_dashboard_state_includes_worker_and_task_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_video_record(root)
            web_console.run_scan_task(root, {"top_n": 10})
            state = web_console.dashboard_state(root)

            self.assertIn("queue_status", state)
            self.assertIn("batches", state)
            self.assertIn("tasks", state)
            self.assertIn("web_state", state)

    def test_dashboard_state_attaches_latest_download_result_to_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_id = self._seed_video_record(root)
            web_console.run_scan_task(root, {"top_n": 10})
            direction = web_console.candidate_batches(root)[0]["direction"]
            task = web_console.queue_download_task(root, direction, [source_id])

            def fake_download(url: str, path: Path, timeout: int = 300) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"video")

            with patch("tools.video_learning.ensure_video_file", side_effect=fake_download):
                web_console.run_pending_web_tasks_once(root)

            state = web_console.dashboard_state(root)
            batch = next(item for item in state["batches"] if item["direction"] == direction)
            self.assertEqual(batch["latest_download"]["task_status"], "done")
            self.assertIn("下载完成 1 条", batch["latest_download"]["summary"])
            self.assertEqual(task["task_status"], "pending")
