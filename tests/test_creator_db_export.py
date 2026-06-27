import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.creator_db_export import export_creator_database


class CreatorDbExportTests(unittest.TestCase):
    def test_exports_creator_contents_and_comments_from_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "数据" / "sqlite_tables.db"
            db_path.parent.mkdir(parents=True)
            self._write_xhs_fixture(db_path)

            result = export_creator_database(root, "测试博主", platform="xhs")

            self.assertTrue(result["ok"])
            self.assertEqual(result["content_count"], 2)
            self.assertEqual(result["comment_count"], 2)
            contents_csv = Path(result["files"]["contents_csv"])
            comments_csv = Path(result["files"]["comments_csv"])
            self.assertTrue(contents_csv.exists())
            self.assertTrue(comments_csv.exists())

            with contents_csv.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["note_id"] for row in rows], ["n1", "n2"])
            self.assertEqual(rows[0]["export_platform"], "xhs")
            self.assertEqual(rows[0]["export_table"], "xhs_note")

            with comments_csv.open(encoding="utf-8-sig") as handle:
                comment_rows = list(csv.DictReader(handle))
            self.assertEqual({row["content"] for row in comment_rows}, {"评论1", "评论2"})

    def test_cli_exports_creator_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "数据" / "sqlite_tables.db"
            db_path.parent.mkdir(parents=True)
            self._write_xhs_fixture(db_path)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(root),
                    "export-creator-db",
                    "--creator",
                    "测试博主",
                    "--platform",
                    "xhs",
                ],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["content_count"], 2)
            self.assertEqual(result["comment_count"], 2)

    def _write_xhs_fixture(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE xhs_creator (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    avatar TEXT,
                    ip_location TEXT,
                    add_ts INTEGER,
                    last_modify_ts INTEGER,
                    desc TEXT,
                    gender TEXT,
                    follows TEXT,
                    fans TEXT,
                    interaction TEXT,
                    tag_list TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE xhs_note (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    note_id TEXT,
                    type TEXT,
                    title TEXT,
                    desc TEXT,
                    liked_count TEXT,
                    collected_count TEXT,
                    comment_count TEXT,
                    share_count TEXT,
                    note_url TEXT,
                    source_keyword TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE xhs_note_comment (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    nickname TEXT,
                    comment_id TEXT,
                    create_time INTEGER,
                    note_id TEXT,
                    content TEXT,
                    sub_comment_count INTEGER,
                    parent_comment_id TEXT,
                    like_count TEXT
                )
                """
            )
            conn.execute("INSERT INTO xhs_creator (user_id, nickname) VALUES (?, ?)", ("u1", "测试博主"))
            conn.executemany(
                """
                INSERT INTO xhs_note (
                    user_id, nickname, note_id, type, title, desc, liked_count,
                    collected_count, comment_count, share_count, note_url, source_keyword
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("u1", "测试博主", "n1", "normal", "标题1", "正文1", "10", "5", "1", "2", "https://xhs.example/n1", ""),
                    ("u1", "测试博主", "n2", "video", "标题2", "正文2", "20", "6", "1", "3", "https://xhs.example/n2", ""),
                ],
            )
            conn.executemany(
                """
                INSERT INTO xhs_note_comment (
                    user_id, nickname, comment_id, create_time, note_id, content,
                    sub_comment_count, parent_comment_id, like_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("c1", "用户1", "cm1", 1, "n1", "评论1", 0, "", "8"),
                    ("c2", "用户2", "cm2", 2, "n2", "评论2", 0, "", "9"),
                    ("c3", "用户3", "cm3", 3, "other", "不应导出", 0, "", "10"),
                ],
            )
