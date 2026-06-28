from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SQLITE_DB = Path("数据") / "sqlite_tables.db"


@dataclass(frozen=True)
class PublishContent:
    platform: str
    source_id: str
    title: str = ""
    body: str = ""
    tags: tuple[str, ...] = ()
    db_source: str = ""


def decode_maybe_json_string(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        decoded = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return text
    if isinstance(decoded, list):
        return ",".join(str(item) for item in decoded)
    return str(decoded)


def split_tag_text(value: object) -> list[str]:
    text = decode_maybe_json_string(value)
    if not text:
        return []
    candidates = re.split(r"[,，、\n\r]+", text)
    return list(dict.fromkeys(tag.strip().strip("#[]【】\"' ") for tag in candidates if tag.strip().strip("#[]【】\"' ")))


def extract_hashtags(*values: str) -> list[str]:
    text = " ".join(value for value in values if value)
    tags: list[str] = []
    for match in re.finditer(r"#\s*([^#\s，,。；;：:【】\[\]]+)", text):
        tag = match.group(1).replace("[话题]", "").strip("#[]【】\"' ")
        if tag:
            tags.append(tag)
    return list(dict.fromkeys(tags))


def load_publish_content_from_sqlite(root: Path, platform: str, source_id: str) -> PublishContent | None:
    db_path = root / DEFAULT_SQLITE_DB
    if not db_path.exists() or platform not in {"douyin", "xhs"} or not source_id:
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            if platform == "xhs":
                row = conn.execute(
                    "SELECT title, desc, tag_list FROM xhs_note WHERE note_id = ? LIMIT 1",
                    (source_id,),
                ).fetchone()
                if not row:
                    return None
                return PublishContent(
                    platform=platform,
                    source_id=source_id,
                    title=str(row["title"] or "").strip(),
                    body=str(row["desc"] or "").strip(),
                    tags=tuple(split_tag_text(row["tag_list"])),
                    db_source="sqlite:xhs_note",
                )
            row = conn.execute(
                "SELECT title, desc FROM douyin_aweme WHERE CAST(aweme_id AS TEXT) = ? LIMIT 1",
                (source_id,),
            ).fetchone()
            if not row:
                return None
            title = str(row["title"] or "").strip()
            body = str(row["desc"] or "").strip()
            return PublishContent(
                platform=platform,
                source_id=source_id,
                title=title,
                body=body,
                tags=tuple(extract_hashtags(title, body)),
                db_source="sqlite:douyin_aweme",
            )
    except sqlite3.Error:
        return None
