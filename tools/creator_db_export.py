from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def default_lark_cli() -> str:
    configured = str(os.environ.get("LARK_CLI") or "").strip()
    if configured:
        return configured
    found = shutil.which("lark-cli")
    if found:
        return found
    return str(Path.home() / ".local/bin/lark-cli")


LARK_CLI = default_lark_cli()
DEFAULT_DB_PATH = Path("数据") / "sqlite_tables.db"
DEFAULT_OUTPUT_DIR = Path("90_Temp") / "exports" / "creator_db"
MAX_FEISHU_BATCH_ROWS = 400


@dataclass(frozen=True)
class ContentSpec:
    platform: str
    content_table: str
    content_id_col: str
    comment_table: str | None = None
    comment_fk_col: str | None = None
    author_name_cols: tuple[str, ...] = ("nickname",)
    author_id_cols: tuple[str, ...] = ("user_id",)
    loose_match_cols: tuple[str, ...] = ("source_keyword",)


@dataclass(frozen=True)
class CreatorSpec:
    platform: str
    creator_table: str
    name_cols: tuple[str, ...]
    id_cols: tuple[str, ...]


CREATOR_SPECS: tuple[CreatorSpec, ...] = (
    CreatorSpec("douyin", "dy_creator", ("nickname",), ("user_id",)),
    CreatorSpec("xhs", "xhs_creator", ("nickname",), ("user_id",)),
    CreatorSpec("weibo", "weibo_creator", ("nickname",), ("user_id",)),
    CreatorSpec("bilibili", "bilibili_up_info", ("nickname",), ("user_id",)),
    CreatorSpec("kuaishou", "kuaishou_video", ("nickname",), ("user_id",)),
    CreatorSpec("tieba", "tieba_creator", ("nickname", "user_name"), ("user_id",)),
    CreatorSpec("zhihu", "zhihu_creator", ("user_nickname",), ("user_id", "url_token")),
)


CONTENT_SPECS: tuple[ContentSpec, ...] = (
    ContentSpec("douyin", "douyin_aweme", "aweme_id", "douyin_aweme_comment", "aweme_id"),
    ContentSpec("xhs", "xhs_note", "note_id", "xhs_note_comment", "note_id"),
    ContentSpec("weibo", "weibo_note", "note_id", "weibo_note_comment", "note_id"),
    ContentSpec("bilibili", "bilibili_video", "video_id", "bilibili_video_comment", "video_id"),
    ContentSpec(
        "bilibili",
        "bilibili_up_dynamic",
        "dynamic_id",
        None,
        None,
        author_name_cols=("user_name",),
        author_id_cols=("user_id",),
    ),
    ContentSpec("kuaishou", "kuaishou_video", "video_id", "kuaishou_video_comment", "video_id"),
    ContentSpec(
        "tieba",
        "tieba_note",
        "note_id",
        "tieba_comment",
        "note_id",
        author_name_cols=("user_nickname",),
        author_id_cols=("user_link",),
    ),
    ContentSpec(
        "zhihu",
        "zhihu_content",
        "content_id",
        "zhihu_comment",
        "content_id",
        author_name_cols=("user_nickname",),
        author_id_cols=("user_id", "user_url_token"),
    ),
)


CONTENT_OUTPUT_PRIORITY = (
    "export_platform",
    "export_table",
    "id",
    "user_id",
    "nickname",
    "user_nickname",
    "title",
    "desc",
    "content",
    "content_text",
    "aweme_id",
    "note_id",
    "video_id",
    "dynamic_id",
    "content_id",
    "aweme_url",
    "note_url",
    "video_url",
    "content_url",
    "liked_count",
    "collected_count",
    "comment_count",
    "comments_count",
    "share_count",
    "shared_count",
    "create_time",
    "created_time",
    "publish_time",
    "time",
    "source_keyword",
)

COMMENT_OUTPUT_PRIORITY = (
    "export_platform",
    "export_table",
    "id",
    "comment_id",
    "parent_comment_id",
    "aweme_id",
    "note_id",
    "video_id",
    "content_id",
    "user_id",
    "nickname",
    "user_nickname",
    "content",
    "like_count",
    "comment_like_count",
    "sub_comment_count",
    "create_time",
    "create_date_time",
    "publish_time",
    "ip_location",
)


def export_creator_database(
    root: Path,
    creator: str,
    *,
    platform: str | None = None,
    db_path: Path | None = None,
    output_dir: Path | None = None,
    include_comments: bool = True,
    limit: int | None = None,
    dry_run: bool = False,
    to_feishu: bool = False,
    public_share: bool = False,
    lark_cli: str = LARK_CLI,
) -> dict[str, Any]:
    if not creator.strip():
        raise ValueError("creator is required")

    database = _resolve_path(root, db_path or DEFAULT_DB_PATH)
    if not database.exists():
        raise FileNotFoundError(f"database not found: {database}")

    export_dir = _build_export_dir(root, output_dir or DEFAULT_OUTPUT_DIR, creator)
    export_dir.mkdir(parents=True, exist_ok=True)

    selected_platform = platform.lower() if platform else None
    specs = [spec for spec in CONTENT_SPECS if selected_platform in (None, spec.platform)]
    if not specs:
        raise ValueError(f"unsupported platform: {platform}")

    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        creators = _find_creators(conn, creator, selected_platform)
        contents, content_ids = _find_contents(conn, creator, specs, creators, limit=limit)
        comments = _find_comments(conn, specs, content_ids) if include_comments else []

    content_rows = _shape_rows(contents, CONTENT_OUTPUT_PRIORITY)
    comment_rows = _shape_rows(comments, COMMENT_OUTPUT_PRIORITY)
    content_csv = export_dir / "contents.csv"
    comment_csv = export_dir / "comments.csv"
    content_jsonl = export_dir / "contents.jsonl"
    comment_jsonl = export_dir / "comments.jsonl"
    manifest_path = export_dir / "manifest.json"

    _write_csv(content_csv, content_rows)
    _write_jsonl(content_jsonl, content_rows)
    _write_csv(comment_csv, comment_rows)
    _write_jsonl(comment_jsonl, comment_rows)

    feishu_result: dict[str, Any] | None = None
    if to_feishu:
        feishu_result = _write_feishu_sheet(
            creator=creator,
            content_rows=content_rows,
            comment_rows=comment_rows,
            dry_run=dry_run,
            public_share=public_share,
            lark_cli=lark_cli,
        )

    manifest = {
        "ok": True,
        "creator": creator,
        "platform": selected_platform or "all",
        "database": str(database),
        "export_dir": str(export_dir),
        "content_count": len(content_rows),
        "comment_count": len(comment_rows),
        "include_comments": include_comments,
        "matched_creators": creators,
        "files": {
            "contents_csv": str(content_csv),
            "contents_jsonl": str(content_jsonl),
            "comments_csv": str(comment_csv),
            "comments_jsonl": str(comment_jsonl),
            "manifest": str(manifest_path),
        },
        "feishu": feishu_result,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _resolve_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return root / path


def _build_export_dir(root: Path, base_dir: Path, creator: str) -> Path:
    safe_creator = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", creator).strip("_") or "creator"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _resolve_path(root, base_dir) / f"{stamp}_{safe_creator}"


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    return [row["name"] for row in rows]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _find_creators(conn: sqlite3.Connection, creator: str, platform: str | None) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for spec in CREATOR_SPECS:
        if platform and spec.platform != platform:
            continue
        if not _table_exists(conn, spec.creator_table):
            continue
        columns = _table_columns(conn, spec.creator_table)
        match_cols = [col for col in spec.name_cols if col in columns]
        if not match_cols:
            continue
        where, params = _like_where(match_cols, creator)
        query = f"SELECT * FROM {_quote_identifier(spec.creator_table)} WHERE {where}"
        for row in conn.execute(query, params).fetchall():
            payload = dict(row)
            matches.append(
                {
                    "platform": spec.platform,
                    "table": spec.creator_table,
                    "ids": {col: payload.get(col) for col in spec.id_cols if col in payload and payload.get(col) not in (None, "")},
                    "names": {col: payload.get(col) for col in spec.name_cols if col in payload and payload.get(col) not in (None, "")},
                }
            )
    return matches


def _find_contents(
    conn: sqlite3.Connection,
    creator: str,
    specs: list[ContentSpec],
    creators: list[dict[str, Any]],
    *,
    limit: int | None,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], set[Any]]]:
    content_rows: list[dict[str, Any]] = []
    content_ids: dict[tuple[str, str], set[Any]] = {}
    seen: set[tuple[str, str, Any]] = set()

    creator_ids_by_platform = _creator_ids_by_platform(creators)
    per_table_limit = limit if limit and limit > 0 else None

    for spec in specs:
        if not _table_exists(conn, spec.content_table):
            continue
        columns = _table_columns(conn, spec.content_table)
        clauses: list[str] = []
        params: list[Any] = []

        match_cols = [col for col in spec.author_name_cols + spec.loose_match_cols if col in columns]
        if match_cols:
            where, where_params = _like_where(match_cols, creator)
            clauses.append(f"({where})")
            params.extend(where_params)

        ids = creator_ids_by_platform.get(spec.platform, set())
        id_cols = [col for col in spec.author_id_cols if col in columns]
        if ids and id_cols:
            id_placeholders = ",".join("?" for _ in ids)
            id_clauses = [f"CAST({_quote_identifier(col)} AS TEXT) IN ({id_placeholders})" for col in id_cols]
            clauses.append("(" + " OR ".join(id_clauses) + ")")
            for _ in id_cols:
                params.extend(str(value) for value in ids)

        if not clauses:
            continue

        query = f"SELECT * FROM {_quote_identifier(spec.content_table)} WHERE {' OR '.join(clauses)}"
        if per_table_limit is not None:
            query += " LIMIT ?"
            params.append(per_table_limit)

        for row in conn.execute(query, params).fetchall():
            payload = dict(row)
            row_id = payload.get(spec.content_id_col) or payload.get("id")
            dedupe_key = (spec.platform, spec.content_table, row_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            enriched = {"export_platform": spec.platform, "export_table": spec.content_table, **payload}
            content_rows.append(enriched)
            if row_id not in (None, ""):
                content_ids.setdefault((spec.comment_table or "", spec.comment_fk_col or ""), set()).add(row_id)

    return content_rows, content_ids


def _find_comments(
    conn: sqlite3.Connection,
    specs: list[ContentSpec],
    content_ids: dict[tuple[str, str], set[Any]],
) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()
    for spec in specs:
        if not spec.comment_table or not spec.comment_fk_col:
            continue
        ids = content_ids.get((spec.comment_table, spec.comment_fk_col), set())
        if not ids or not _table_exists(conn, spec.comment_table):
            continue
        columns = _table_columns(conn, spec.comment_table)
        if spec.comment_fk_col not in columns:
            continue
        placeholders = ",".join("?" for _ in ids)
        query = (
            f"SELECT * FROM {_quote_identifier(spec.comment_table)} "
            f"WHERE CAST({_quote_identifier(spec.comment_fk_col)} AS TEXT) IN ({placeholders})"
        )
        for row in conn.execute(query, [str(value) for value in ids]).fetchall():
            payload = dict(row)
            dedupe_key = (spec.comment_table, payload.get("comment_id") or payload.get("id"))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            comments.append({"export_platform": spec.platform, "export_table": spec.comment_table, **payload})
    return comments


def _creator_ids_by_platform(creators: list[dict[str, Any]]) -> dict[str, set[Any]]:
    result: dict[str, set[Any]] = {}
    for creator in creators:
        platform = creator["platform"]
        values = result.setdefault(platform, set())
        for value in creator.get("ids", {}).values():
            if value not in (None, ""):
                values.add(value)
    return result


def _like_where(columns: list[str], value: str) -> tuple[str, list[Any]]:
    clauses = [f"LOWER(CAST({_quote_identifier(col)} AS TEXT)) LIKE LOWER(?)" for col in columns]
    return " OR ".join(clauses), [f"%{value}%" for _ in columns]


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _shape_rows(rows: list[dict[str, Any]], priority: tuple[str, ...]) -> list[dict[str, Any]]:
    all_columns: list[str] = []
    seen: set[str] = set()
    for col in priority:
        if any(col in row for row in rows):
            all_columns.append(col)
            seen.add(col)
    for row in rows:
        for col in row:
            if col not in seen:
                seen.add(col)
                all_columns.append(col)
    return [{col: _cell_value(row.get(col, "")) for col in all_columns} for row in rows]


def _cell_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    headers = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        if headers:
            writer.writeheader()
            writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_feishu_sheet(
    *,
    creator: str,
    content_rows: list[dict[str, Any]],
    comment_rows: list[dict[str, Any]],
    dry_run: bool,
    public_share: bool,
    lark_cli: str,
) -> dict[str, Any]:
    title = f"{creator} 内容评论导出 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    create_payload = _run_lark_json(
        [
            lark_cli,
            "sheets",
            "+create",
            "--as",
            "user",
            "--title",
            title,
            "--headers",
            json.dumps(list(content_rows[0].keys()) if content_rows else ["empty"], ensure_ascii=False),
        ]
        + (["--dry-run"] if dry_run else []),
    )
    token = _extract_spreadsheet_token(create_payload)
    url = _extract_spreadsheet_url(create_payload, token)
    result: dict[str, Any] = {"title": title, "url": url, "spreadsheet_token": token, "dry_run": dry_run}

    if dry_run:
        result["planned"] = {"content_rows": len(content_rows), "comment_rows": len(comment_rows), "public_share": public_share}
        return result
    if not token:
        raise RuntimeError(f"could not extract spreadsheet token from lark-cli response: {create_payload}")

    info = _run_lark_json([lark_cli, "sheets", "+info", "--as", "user", "--spreadsheet-token", token])
    content_sheet_id = _extract_first_sheet_id(info)
    if content_rows:
        _append_rows(lark_cli, token, content_sheet_id, content_rows)

    if comment_rows:
        comment_sheet = _run_lark_json(
            [lark_cli, "sheets", "+create-sheet", "--as", "user", "--spreadsheet-token", token, "--title", "comments"]
        )
        comment_sheet_id = _extract_sheet_id(comment_sheet)
        if not comment_sheet_id:
            info = _run_lark_json([lark_cli, "sheets", "+info", "--as", "user", "--spreadsheet-token", token])
            comment_sheet_id = _extract_sheet_id_by_title(info, "comments")
        if not comment_sheet_id:
            raise RuntimeError(f"could not extract comments sheet id from lark-cli response: {comment_sheet}")
        headers = {key: key for key in comment_rows[0].keys()}
        _append_rows(lark_cli, token, comment_sheet_id, [headers] + comment_rows)

    if public_share:
        before = _get_public_permission(lark_cli, token)
        patch = _run_lark_json(
            [
                lark_cli,
                "drive",
                "permission.public",
                "patch",
                "--as",
                "user",
                "--params",
                json.dumps({"token": token, "type": "sheet"}, ensure_ascii=False),
                "--data",
                json.dumps(
                    {
                        "link_share_entity": "anyone_readable",
                        "external_access": True,
                        "security_entity": "anyone_can_view",
                        "comment_entity": "anyone_can_view",
                        "share_entity": "anyone",
                    },
                    ensure_ascii=False,
                ),
                "--yes",
            ]
        )
        after = _get_public_permission(lark_cli, token)
        result["public_permission"] = {"before": before, "patch": patch, "after": after}

    verify_command = [lark_cli, "sheets", "+read", "--as", "user", "--spreadsheet-token", token, "--range", "A1:A1"]
    if content_sheet_id:
        verify_command.extend(["--sheet-id", content_sheet_id])
    result["readback"] = _run_lark_json(verify_command)
    return result


def _append_rows(lark_cli: str, token: str, sheet_id: str | None, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    headers = list(rows[0].keys())
    values = [[row.get(header, "") for header in headers] for row in rows]
    for start in range(0, len(values), MAX_FEISHU_BATCH_ROWS):
        batch = values[start : start + MAX_FEISHU_BATCH_ROWS]
        range_ref = f"A1:{_column_name(len(headers))}{len(batch)}"
        command = [
            lark_cli,
            "sheets",
            "+append",
            "--as",
            "user",
            "--spreadsheet-token",
            token,
            "--values",
            json.dumps(batch, ensure_ascii=False),
        ]
        if sheet_id:
            command.extend(["--sheet-id", sheet_id, "--range", range_ref])
        else:
            command.extend(["--range", range_ref])
        _run_lark_json(command)


def _column_name(column_count: int) -> str:
    if column_count < 1:
        return "A"
    name = ""
    number = column_count
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _get_public_permission(lark_cli: str, token: str) -> dict[str, Any]:
    return _run_lark_json(
        [
            lark_cli,
            "drive",
            "permission.public",
            "get",
            "--as",
            "user",
            "--params",
            json.dumps({"token": token, "type": "sheet"}, ensure_ascii=False),
        ]
    )


def _run_lark_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"lark-cli failed: {command}")
    output = completed.stdout.strip()
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"raw": output}


def _extract_spreadsheet_token(payload: dict[str, Any]) -> str | None:
    candidates = _walk_values(payload)
    for value in candidates:
        if isinstance(value, str):
            if re.fullmatch(r"shtcn[\w-]+", value) or re.fullmatch(r"[A-Za-z0-9]{10,}", value):
                return value
    return None


def _extract_spreadsheet_url(payload: dict[str, Any], token: str | None) -> str | None:
    for value in _walk_values(payload):
        if isinstance(value, str) and "feishu.cn" in value and "sheets" in value:
            return value
    if token:
        return f"https://u.feishu.cn/sheets/{token}"
    return None


def _extract_first_sheet_id(payload: dict[str, Any]) -> str | None:
    for value in _walk_values(payload):
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9]{6}", value):
            return value
    return None


def _extract_sheet_id(payload: dict[str, Any]) -> str | None:
    return _extract_first_sheet_id(payload)


def _extract_sheet_id_by_title(payload: dict[str, Any], title: str) -> str | None:
    def visit(value: Any) -> str | None:
        if isinstance(value, dict):
            values = {str(k).lower(): v for k, v in value.items()}
            if values.get("title") == title:
                for key in ("sheet_id", "sheetid", "id"):
                    if isinstance(values.get(key), str):
                        return values[key]
            for child in value.values():
                found = visit(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = visit(child)
                if found:
                    return found
        return None

    return visit(payload)


def _walk_values(value: Any) -> list[Any]:
    values: list[Any] = []
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_walk_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk_values(child))
    else:
        values.append(value)
    return values
