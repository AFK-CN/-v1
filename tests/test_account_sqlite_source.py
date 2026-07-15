from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.account_sqlite_source import build_account_source_snapshot


class AccountSqliteSourceTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "source.db"
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE xhs_creator (id INTEGER PRIMARY KEY, user_id TEXT, nickname TEXT, fans TEXT)"
            )
            connection.execute(
                "CREATE TABLE xhs_note (id INTEGER PRIMARY KEY, nickname TEXT, note_id TEXT, type TEXT, "
                "title TEXT, time INTEGER, last_update_time INTEGER, liked_count TEXT, collected_count TEXT, "
                "comment_count TEXT, share_count TEXT, video_url TEXT, image_list TEXT)"
            )
            connection.execute(
                "INSERT INTO xhs_creator VALUES (1, 'u1', '小森林的小世界', '123')"
            )
            connection.executemany(
                "INSERT INTO xhs_note VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, "小森林的小世界", "n1", "video", "视频", 10, 11, "2", "3", "4", "5", "https://video", "[]"),
                    (2, "小森林的小世界", "n2", "normal", "图文", 20, 21, "6", "7", "8", "9", "", "[\"image\"]"),
                    (3, "其他账号", "n3", "normal", "不应出现", 30, 31, "1", "1", "1", "1", "", "[]"),
                ],
            )
        return path

    def test_apply_writes_only_selected_account_as_candidate_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_account_source_snapshot(
                root,
                database=self._database(root),
                account_name="小森林的小世界",
                platform="xhs",
                profile_id="xiaosenlin_xiaoshijie",
                workflow_id="xiaosenlin-xiaoshijie-v2-full",
                apply=True,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["record_count"], 2)
            self.assertEqual(result["media_counts"], {"video_url": 1, "image_list": 1})
            manifest = json.loads((root / result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["database_mode"], "read_only")
            self.assertTrue(manifest["candidate_only"])
            inventory = (root / manifest["inventory"]).read_text(encoding="utf-8")
            self.assertIn('"source_id": "n1"', inventory)
            self.assertIn('"source_id": "n2"', inventory)
            self.assertNotIn("n3", inventory)

    def test_dry_run_does_not_write_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_account_source_snapshot(
                root,
                database=self._database(root),
                account_name="小森林的小世界",
                platform="xhs",
                profile_id="xiaosenlin_xiaoshijie",
                workflow_id="xiaosenlin-xiaoshijie-v2-full",
                apply=False,
            )
            self.assertEqual(result["status"], "dry_run")
            self.assertFalse((root / "10_Knowledge").exists())


if __name__ == "__main__":
    unittest.main()
