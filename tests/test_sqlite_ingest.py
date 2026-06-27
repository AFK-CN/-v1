import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.sqlite_ingest import ingest_sqlite_database, sqlite_ingest_status


class SqliteIngestTests(unittest.TestCase):
    def test_apply_writes_incremental_candidates_state_and_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说").mkdir(parents=True)
            self._write_fixture(root / "数据" / "sqlite_tables.db")

            result = ingest_sqlite_database(root, apply=True, batch_id="20260627_120000")

            self.assertTrue(result["ok"])
            self.assertEqual(result["content"]["new"], 2)
            self.assertEqual(result["content"]["changed"], 0)
            self.assertEqual(result["content"]["missing"], 0)
            self.assertEqual(result["comments"], {"status": "ignored"})
            self.assertEqual({row["account_name"] for row in result["accounts"]}, {"姜胡说", "测试小红书"})

            batch_dir = root / "00_Inbox" / "sqlite_imports" / "20260627_120000"
            records_path = batch_dir / "records.jsonl"
            manifest_path = batch_dir / "manifest.json"
            state_path = root / "00_System" / "runtime" / "state" / "sqlite_ingest" / "state.json"
            source_index = root / "10_Knowledge" / "evidence" / "index" / "sqlite_source_index.md"
            status_index = root / "10_Knowledge" / "evidence" / "index" / "sqlite_import_status.md"
            source_json = root / "10_Knowledge" / "evidence" / "index" / "sqlite_source_index.json"
            account_candidates_md = root / "10_Knowledge" / "candidates" / "account_assets" / "sqlite_imports" / "latest_account_candidates.md"
            account_candidates_json = root / "10_Knowledge" / "candidates" / "account_assets" / "sqlite_imports" / "latest_account_candidates.json"

            self.assertTrue(records_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(state_path.exists())
            self.assertTrue(source_index.exists())
            self.assertTrue(status_index.exists())
            self.assertTrue(source_json.exists())
            self.assertTrue(account_candidates_md.exists())
            self.assertTrue(account_candidates_json.exists())

            records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["stable_id"] for row in records], ["douyin:aweme:a1", "xhs:note:n1"])
            self.assertEqual(records[0]["raw_locator"], {"table": "douyin_aweme", "pk": 1, "source_id": "a1"})
            self.assertEqual(records[0]["change_type"], "new")
            self.assertNotIn("评论内容", records_path.read_text(encoding="utf-8"))
            self.assertIn("姜胡说", source_index.read_text(encoding="utf-8"))
            self.assertIn("测试小红书", source_index.read_text(encoding="utf-8"))
            self.assertIn("评论处理：已忽略", status_index.read_text(encoding="utf-8"))

            account_candidates = json.loads(account_candidates_json.read_text(encoding="utf-8"))
            by_name = {row["account_name"]: row for row in account_candidates["accounts"]}
            self.assertEqual(by_name["姜胡说"]["knowledge_status"], "formal_account_exists")
            self.assertEqual(by_name["测试小红书"]["knowledge_status"], "candidate_account")
            self.assertIn("赚钱", by_name["姜胡说"]["direction_counts"])
            self.assertIn("00_Inbox/sqlite_imports/20260627_120000", account_candidates_md.read_text(encoding="utf-8"))

            status = sqlite_ingest_status(root)
            self.assertTrue(status["ok"])
            self.assertEqual(status["latest_batch_id"], "20260627_120000")

    def test_second_apply_does_not_recreate_unchanged_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "数据" / "sqlite_tables.db"
            self._write_fixture(db_path)

            first = ingest_sqlite_database(root, apply=True, batch_id="20260627_120000")
            second = ingest_sqlite_database(root, apply=True, batch_id="20260627_120100")

            self.assertEqual(first["content"]["new"], 2)
            self.assertEqual(second["content"]["new"], 0)
            self.assertEqual(second["content"]["changed"], 0)
            self.assertFalse((root / "00_Inbox" / "sqlite_imports" / "20260627_120100" / "records.jsonl").exists())

            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE douyin_aweme SET title = ?, last_modify_ts = ? WHERE aweme_id = ?", ("新标题", 3000, "a1"))

            changed = ingest_sqlite_database(root, apply=True, batch_id="20260627_120200")

            self.assertEqual(changed["content"]["new"], 0)
            self.assertEqual(changed["content"]["changed"], 1)
            records_path = root / "00_Inbox" / "sqlite_imports" / "20260627_120200" / "records.jsonl"
            records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["stable_id"], "douyin:aweme:a1")
            self.assertEqual(records[0]["change_type"], "changed")

    def test_dry_run_does_not_write_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fixture(root / "数据" / "sqlite_tables.db")

            result = ingest_sqlite_database(root, apply=False, batch_id="20260627_120000")

            self.assertTrue(result["ok"])
            self.assertEqual(result["content"]["new"], 2)
            self.assertFalse((root / "00_Inbox").exists())
            self.assertFalse((root / "00_System" / "runtime" / "state" / "sqlite_ingest" / "state.json").exists())
            self.assertFalse((root / "10_Knowledge" / "evidence" / "index" / "sqlite_source_index.md").exists())

    def test_cli_applies_sqlite_ingest_and_reports_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fixture(root / "数据" / "sqlite_tables.db")

            apply_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(root),
                    "sqlite-ingest",
                    "--apply",
                    "--batch-id",
                    "20260627_120000",
                ],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            payload = json.loads(apply_result.stdout)
            self.assertEqual(payload["content"]["new"], 2)

            status_result = subprocess.run(
                [sys.executable, "-m", "tools.kb.cli", "--root", str(root), "sqlite-status"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            status_payload = json.loads(status_result.stdout)
            self.assertEqual(status_payload["latest_batch_id"], "20260627_120000")

    def _write_fixture(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True)
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE dy_creator (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    fans TEXT,
                    videos_count TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER
                );
                CREATE TABLE douyin_aweme (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    aweme_id TEXT,
                    title TEXT,
                    desc TEXT,
                    create_time INTEGER,
                    liked_count TEXT,
                    comment_count TEXT,
                    share_count TEXT,
                    collected_count TEXT,
                    aweme_url TEXT,
                    video_download_url TEXT,
                    source_keyword TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER
                );
                CREATE TABLE douyin_aweme_comment (
                    id INTEGER PRIMARY KEY,
                    comment_id TEXT,
                    aweme_id TEXT,
                    content TEXT,
                    like_count TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER
                );
                CREATE TABLE xhs_creator (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    fans TEXT,
                    interaction TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER
                );
                CREATE TABLE xhs_note (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    note_id TEXT,
                    title TEXT,
                    desc TEXT,
                    tag_list TEXT,
                    liked_count TEXT,
                    collected_count TEXT,
                    comment_count TEXT,
                    share_count TEXT,
                    note_url TEXT,
                    video_url TEXT,
                    image_list TEXT,
                    source_keyword TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER
                );
                CREATE TABLE xhs_note_comment (
                    id INTEGER PRIMARY KEY,
                    comment_id TEXT,
                    note_id TEXT,
                    content TEXT,
                    like_count TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER
                );
                """
            )
            conn.execute("INSERT INTO dy_creator VALUES (1, 'u1', '姜胡说', '100', '1', 1000, 1000)")
            conn.execute("INSERT INTO xhs_creator VALUES (1, 'x1', '测试小红书', '20', '30', 1000, 1000)")
            conn.execute(
                """
                INSERT INTO douyin_aweme VALUES (
                    1, 'u1', '姜胡说', 'a1', '#赚钱 普通人做自媒体', '创业 方法 短视频',
                    1700000000, '100', '20', '30', '40', 'https://example.com/a1', '', '姜胡说', 1000, 1000
                )
                """
            )
            conn.execute(
                """
                INSERT INTO xhs_note VALUES (
                    1, 'x1', '测试小红书', 'n1', '一人食减脂餐', '一周备餐 低卡',
                    '减脂,备餐', '50', '60', '5', '3', 'https://example.com/n1', '', '', '', 1000, 1000
                )
                """
            )
            conn.execute("INSERT INTO douyin_aweme_comment VALUES (1, 'c1', 'a1', '评论内容1', '9', 1000, 1000)")
            conn.execute("INSERT INTO xhs_note_comment VALUES (1, 'xc1', 'n1', '评论内容2', '8', 1000, 1000)")


if __name__ == "__main__":
    unittest.main()
