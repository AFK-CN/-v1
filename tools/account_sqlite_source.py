from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


OUTPUT_ROOT = Path("10_Knowledge/candidates/account_assets/sqlite_account_sources")

PLATFORMS = {
    "xhs": {
        "content_table": "xhs_note",
        "creator_table": "xhs_creator",
        "source_id": "note_id",
        "content_type": "type",
        "publish_time": "time",
        "updated_time": "last_update_time",
        "video": "video_url",
        "images": "image_list",
        "metrics": {
            "likes": "liked_count",
            "collects": "collected_count",
            "comments": "comment_count",
            "shares": "share_count",
        },
    },
    "douyin": {
        "content_table": "douyin_aweme",
        "creator_table": "dy_creator",
        "source_id": "aweme_id",
        "content_type": "aweme_type",
        "publish_time": "create_time",
        "updated_time": "last_modify_ts",
        "video": "video_download_url",
        "images": "images",
        "metrics": {
            "likes": "liked_count",
            "collects": "collected_count",
            "comments": "comment_count",
            "shares": "share_count",
        },
    },
}


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in value.strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        raise ValueError("profile_id must contain a letter or number")
    return cleaned


def _integer(value: Any) -> int:
    try:
        return int(str(value or "0").replace(",", ""))
    except ValueError:
        return 0


def _has_media(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and text not in {"[]", "{}", "null", "None"})


def _read_only_connection(database: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(database.resolve()))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_account_source_snapshot(
    root: Path,
    *,
    database: Path,
    account_name: str,
    platform: str,
    profile_id: str,
    workflow_id: str,
    apply: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    database = database.expanduser().resolve()
    if platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {platform}")
    if not database.is_file():
        raise FileNotFoundError(f"database not found: {database}")
    profile_id = _safe_id(profile_id)
    config = PLATFORMS[platform]
    content_table = config["content_table"]
    creator_table = config["creator_table"]

    with _read_only_connection(database) as connection:
        content_columns = _columns(connection, content_table)
        creator_columns = _columns(connection, creator_table)
        if "nickname" not in content_columns or "nickname" not in creator_columns:
            raise ValueError("expected nickname columns are missing")
        creator = connection.execute(
            f'SELECT * FROM "{creator_table}" WHERE nickname = ? ORDER BY id LIMIT 1',
            (account_name,),
        ).fetchone()
        if creator is None:
            raise ValueError(f"account not found: {account_name}")
        rows = connection.execute(
            f'SELECT * FROM "{content_table}" WHERE nickname = ? ORDER BY id',
            (account_name,),
        ).fetchall()

    records: list[dict[str, Any]] = []
    content_types: Counter[str] = Counter()
    video_count = 0
    image_count = 0
    latest_publish_time = 0
    for row in rows:
        payload = dict(row)
        source_id = str(payload.get(config["source_id"]) or payload.get("id") or "")
        content_type = str(payload.get(config["content_type"]) or "unknown")
        has_video = _has_media(payload.get(config["video"]))
        has_images = _has_media(payload.get(config["images"]))
        publish_time = _integer(payload.get(config["publish_time"]))
        latest_publish_time = max(latest_publish_time, publish_time)
        content_types[content_type] += 1
        video_count += int(has_video)
        image_count += int(has_images)
        records.append(
            {
                "stable_id": f"{platform}:{config['source_id']}:{source_id}",
                "platform": platform,
                "account_name": account_name,
                "source_id": source_id,
                "source_ref": f"sqlite:{content_table}:{payload.get('id', '')}",
                "title": str(payload.get("title") or "").strip(),
                "content_type": content_type,
                "publish_time": publish_time,
                "updated_time": _integer(payload.get(config["updated_time"])),
                "metrics": {
                    name: _integer(payload.get(column))
                    for name, column in config["metrics"].items()
                },
                "evidence_presence": {"video_url": has_video, "image_list": has_images},
            }
        )

    output_dir = root / OUTPUT_ROOT / profile_id
    inventory_path = output_dir / "nas_sqlite_inventory.jsonl"
    manifest_path = output_dir / "source_manifest.json"
    summary = {
        "ok": True,
        "status": "linked_read_only" if apply else "dry_run",
        "profile_id": profile_id,
        "workflow_id": workflow_id,
        "account": {
            "name": account_name,
            "platform": platform,
            "user_id": str(dict(creator).get("user_id") or ""),
            "fans": _integer(dict(creator).get("fans")),
        },
        "database": str(database),
        "database_mode": "read_only",
        "record_count": len(records),
        "content_types": dict(sorted(content_types.items())),
        "media_counts": {"video_url": video_count, "image_list": image_count},
        "latest_publish_time": latest_publish_time,
        "candidate_only": True,
        "formal_write_allowed": False,
    }
    if not apply:
        return summary

    output_dir.mkdir(parents=True, exist_ok=True)
    with inventory_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "schema_version": 1,
        **summary,
        "linked_at": datetime.now().isoformat(timespec="seconds"),
        "database_size": database.stat().st_size,
        "inventory": inventory_path.relative_to(root).as_posix(),
        "inventory_sha256": _sha256(inventory_path),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                f"# {account_name} NAS SQLite 候选证据入口",
                "",
                f"- 状态：`{manifest['status']}`",
                f"- 记录数：{manifest['record_count']}",
                "- 数据库访问：只读，不修改 NAS 原始数据。",
                "- 知识层级：候选证据，不可作为正式知识直接调用。",
                f"- 工作流：`{workflow_id}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {**summary, "manifest": manifest_path.relative_to(root).as_posix(), "inventory_sha256": manifest["inventory_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a read-only, account-scoped SQLite source snapshot.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--database", required=True)
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = build_account_source_snapshot(
            Path(args.root),
            database=Path(args.database),
            account_name=args.account_name,
            platform=args.platform,
            profile_id=args.profile_id,
            workflow_id=args.workflow_id,
            apply=args.apply,
        )
    except (FileNotFoundError, ValueError, sqlite3.Error) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
