from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.video_learning import detect_directions
from tools.video_learning import normalize_record


DEFAULT_DB_PATH = Path("数据") / "sqlite_tables.db"
STATE_PATH = Path("00_System/runtime/state/sqlite_ingest/state.json")
INBOX_ROOT = Path("00_Inbox/sqlite_imports")
INDEX_DIR = Path("10_Knowledge/evidence/index")
ACCOUNT_ASSET_ROOT = Path("10_Knowledge/candidates/account_assets/sqlite_imports")
FORMAL_ACCOUNTS_ROOT = Path("10_Knowledge/formal/accounts")


@dataclass(frozen=True)
class SqliteContentSpec:
    platform: str
    table: str
    source_id_col: str
    stable_kind: str
    comment_table: str
    comment_fk_col: str


CONTENT_SPECS: tuple[SqliteContentSpec, ...] = (
    SqliteContentSpec("douyin", "douyin_aweme", "aweme_id", "aweme", "douyin_aweme_comment", "aweme_id"),
    SqliteContentSpec("xhs", "xhs_note", "note_id", "note", "xhs_note_comment", "note_id"),
)

CREATOR_TABLES: tuple[tuple[str, str], ...] = (
    ("douyin", "dy_creator"),
    ("xhs", "xhs_creator"),
    ("weibo", "weibo_creator"),
    ("bilibili", "bilibili_up_info"),
    ("kuaishou", "kuaishou_video"),
    ("tieba", "tieba_creator"),
    ("zhihu", "zhihu_creator"),
)


def ingest_sqlite_database(
    root: Path,
    *,
    apply: bool = False,
    db_path: Path | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    database = _resolve(root, db_path or DEFAULT_DB_PATH)
    if not database.exists():
        return {"ok": False, "status": "missing_database", "database": str(database)}

    batch_id = batch_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    previous_state = _read_json(root / STATE_PATH, default={})
    previous_fingerprints = previous_state.get("content_fingerprints", {})
    previous_known = set(previous_fingerprints)

    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        table_infos = _table_infos(conn)
        accounts = _read_accounts(conn)
        candidates, current_fingerprints = _read_content_candidates(conn, root)

    current_known = set(current_fingerprints)
    rows_to_write: list[dict[str, Any]] = []
    counts = {"new": 0, "changed": 0, "missing": 0, "unchanged": 0, "total": len(candidates)}
    for candidate in candidates:
        stable_id = candidate["stable_id"]
        previous = previous_fingerprints.get(stable_id)
        current = current_fingerprints[stable_id]
        if previous is None:
            change_type = "new"
        elif previous != current:
            change_type = "changed"
        else:
            change_type = "unchanged"
        counts[change_type] += 1
        if change_type in {"new", "changed"}:
            rows_to_write.append({**candidate, "change_type": change_type})

    missing = sorted(previous_known - current_known)
    counts["missing"] = len(missing)

    result = {
        "ok": True,
        "status": "applied" if apply else "dry_run",
        "database": str(database),
        "batch_id": batch_id,
        "content": counts,
        "comments": {"status": "ignored"},
        "accounts": accounts,
        "tables": table_infos,
        "candidate_count": len(rows_to_write),
        "missing_stable_ids": missing,
    }

    if not apply:
        return result

    batch_dir: Path | None = None
    if rows_to_write:
        batch_dir = root / INBOX_ROOT / batch_id
        _write_batch(batch_dir, result, rows_to_write)
        _write_account_candidates(root, batch_id, batch_dir, accounts, rows_to_write)

    state = {
        "version": 1,
        "database": str(database.relative_to(root) if _is_relative_to(database, root) else database),
        "last_run_at": datetime.now().isoformat(timespec="seconds"),
        "latest_batch_id": batch_id if batch_dir else previous_state.get("latest_batch_id", ""),
        "latest_batch_dir": str(batch_dir.relative_to(root)) if batch_dir else previous_state.get("latest_batch_dir", ""),
        "content_fingerprints": current_fingerprints,
        "tables": table_infos,
        "accounts": accounts,
        "last_result": result,
    }
    _write_json(root / STATE_PATH, state)
    _write_indexes(root, state, result)
    return result


def sqlite_ingest_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    state_path = root / STATE_PATH
    if not state_path.exists():
        return {"ok": False, "status": "requires_ingest", "state_path": str(state_path)}
    state = _read_json(state_path, default={})
    return {
        "ok": True,
        "status": "ready",
        "database": state.get("database", str(DEFAULT_DB_PATH)),
        "latest_batch_id": state.get("latest_batch_id", ""),
        "latest_batch_dir": state.get("latest_batch_dir", ""),
        "accounts": state.get("accounts", []),
        "tables": state.get("tables", []),
        "last_result": state.get("last_result", {}),
    }


def _read_content_candidates(conn: sqlite3.Connection, root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    candidates: list[dict[str, Any]] = []
    fingerprints: dict[str, str] = {}
    for spec in CONTENT_SPECS:
        if not _table_exists(conn, spec.table):
            continue
        columns = _table_columns(conn, spec.table)
        order_col = "id" if "id" in columns else spec.source_id_col
        query = f"SELECT * FROM {_quote(spec.table)} ORDER BY {_quote(order_col)}"
        for row in conn.execute(query).fetchall():
            payload = dict(row)
            record = normalize_record(spec.platform, payload, Path(f"数据/sqlite_tables.db#{spec.table}:{payload.get('id', '')}"))
            source_id = str(payload.get(spec.source_id_col) or payload.get("id") or "")
            stable_id = f"{spec.platform}:{spec.stable_kind}:{source_id}" if source_id else f"{spec.platform}:{spec.table}:row:{payload.get('id')}"
            fingerprint = _content_fingerprint(payload, record.text_fingerprint)
            fingerprints[stable_id] = fingerprint
            candidates.append(
                {
                    "stable_id": stable_id,
                    "platform": spec.platform,
                    "account_name": record.account_name or record.author_name or str(payload.get("source_keyword") or ""),
                    "source_table": spec.table,
                    "source_pk": payload.get("id", ""),
                    "source_id": source_id,
                    "title": _summary(record.title, limit=80),
                    "summary": _summary(record.body or record.title, limit=160),
                    "url": record.url,
                    "content_type": str(payload.get("type") or ""),
                    "video_url": str(payload.get("video_url") or payload.get("video_download_url") or ""),
                    "metrics": record.metrics,
                    "tags": record.tags,
                    "source_keyword": str(payload.get("source_keyword") or ""),
                    "suggested_directions": detect_directions(record),
                    "raw_locator": {"table": spec.table, "pk": payload.get("id", ""), "source_id": source_id},
                }
            )
    return candidates, fingerprints


def _read_accounts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    accounts: dict[tuple[str, str], dict[str, Any]] = {}
    for platform, table in CREATOR_TABLES:
        if not _table_exists(conn, table):
            continue
        columns = _table_columns(conn, table)
        if "nickname" not in columns:
            continue
        for row in conn.execute(f"SELECT * FROM {_quote(table)}").fetchall():
            payload = dict(row)
            name = str(payload.get("nickname") or payload.get("user_nickname") or "").strip()
            if not name:
                continue
            key = (platform, name)
            accounts[key] = {
                "platform": platform,
                "account_name": name,
                "creator_table": table,
                "user_id": payload.get("user_id", ""),
                "fans": payload.get("fans", payload.get("total_fans", "")),
                "last_modify_ts": payload.get("last_modify_ts", ""),
            }
    for spec in CONTENT_SPECS:
        if not _table_exists(conn, spec.table):
            continue
        columns = _table_columns(conn, spec.table)
        if "nickname" not in columns:
            continue
        for row in conn.execute(f"SELECT nickname, COUNT(*) AS content_count FROM {_quote(spec.table)} GROUP BY nickname").fetchall():
            name = str(row["nickname"] or "").strip()
            if not name:
                continue
            key = (spec.platform, name)
            account = accounts.setdefault(
                key,
                {
                    "platform": spec.platform,
                    "account_name": name,
                    "creator_table": "",
                    "user_id": "",
                    "fans": "",
                    "last_modify_ts": "",
                },
            )
            account["content_count"] = row["content_count"]
    return sorted(accounts.values(), key=lambda item: (item["platform"], item["account_name"]))


def _comment_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    stats = {"total": 0, "tables": []}
    for spec in CONTENT_SPECS:
        if not _table_exists(conn, spec.comment_table):
            continue
        count = conn.execute(f"SELECT COUNT(*) FROM {_quote(spec.comment_table)}").fetchone()[0]
        stats["total"] += count
        stats["tables"].append({"platform": spec.platform, "table": spec.comment_table, "count": count})
    return stats


def _table_infos(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
    infos = []
    for row in rows:
        table = row["name"]
        count = conn.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0]
        infos.append({"table": table, "count": count, "schema_hash": _hash_text(row["sql"] or "")})
    return infos


def _write_batch(batch_dir: Path, result: dict[str, Any], records: list[dict[str, Any]]) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    records = [_jsonl_safe(record) for record in records]
    _write_json(batch_dir / "manifest.json", result)
    with (batch_dir / "records.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (batch_dir / "import_summary.md").write_text(_batch_summary_markdown(result, records), encoding="utf-8")
    (batch_dir / "accounts.md").write_text(_accounts_markdown(result["accounts"]), encoding="utf-8")
    (batch_dir / "next_actions.md").write_text(_next_actions_markdown(result["accounts"], records), encoding="utf-8")


def _write_indexes(root: Path, state: dict[str, Any], result: dict[str, Any]) -> None:
    index_dir = root / INDEX_DIR
    index_dir.mkdir(parents=True, exist_ok=True)
    source_payload = {
        "version": 1,
        "database": state.get("database", str(DEFAULT_DB_PATH)),
        "latest_batch_id": state.get("latest_batch_id", ""),
        "latest_batch_dir": state.get("latest_batch_dir", ""),
        "accounts": state.get("accounts", []),
        "tables": state.get("tables", []),
        "last_result": result,
    }
    _write_json(index_dir / "sqlite_source_index.json", source_payload)
    (index_dir / "sqlite_source_index.md").write_text(_source_index_markdown(source_payload), encoding="utf-8")
    (index_dir / "sqlite_import_status.md").write_text(_status_markdown(source_payload), encoding="utf-8")


def _write_account_candidates(
    root: Path,
    batch_id: str,
    batch_dir: Path,
    accounts: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    output_dir = root / ACCOUNT_ASSET_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)
    account_payload = _account_candidate_payload(root, batch_id, batch_dir, accounts, records)
    _write_json(output_dir / "latest_account_candidates.json", account_payload)
    (output_dir / "latest_account_candidates.md").write_text(_account_candidates_markdown(account_payload), encoding="utf-8")


def _account_candidate_payload(
    root: Path,
    batch_id: str,
    batch_dir: Path,
    accounts: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault((record["platform"], record["account_name"] or "未知账号"), []).append(record)

    account_lookup = {(account["platform"], account["account_name"]): account for account in accounts}
    rows: list[dict[str, Any]] = []
    for (platform, account_name), account_records in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        direction_counts: dict[str, int] = {}
        for record in account_records:
            for direction in record.get("suggested_directions", []):
                direction_counts[direction] = direction_counts.get(direction, 0) + 1
        top_records = sorted(
            account_records,
            key=lambda record: (
                int(record.get("metrics", {}).get("likes", 0))
                + int(record.get("metrics", {}).get("collects", 0))
                + int(record.get("metrics", {}).get("comments", 0))
                + int(record.get("metrics", {}).get("shares", 0))
            ),
            reverse=True,
        )[:5]
        rows.append(
            {
                "platform": platform,
                "account_name": account_name,
                "knowledge_status": "formal_account_exists" if (root / FORMAL_ACCOUNTS_ROOT / account_name).exists() else "candidate_account",
                "content_count": len(account_records),
                "new_count": sum(1 for record in account_records if record.get("change_type") == "new"),
                "changed_count": sum(1 for record in account_records if record.get("change_type") == "changed"),
                "fans": account_lookup.get((platform, account_name), {}).get("fans", ""),
                "direction_counts": dict(sorted(direction_counts.items(), key=lambda item: (-item[1], item[0]))),
                "top_records": [
                    {
                        "stable_id": record["stable_id"],
                        "title": record["title"],
                        "url": record["url"],
                        "raw_locator": record["raw_locator"],
                    }
                    for record in top_records
                ],
            }
        )
    return {
        "version": 1,
        "batch_id": batch_id,
        "source_batch_dir": str(batch_dir.relative_to(root)) if _is_relative_to(batch_dir, root) else str(batch_dir),
        "comment_policy": "ignored",
        "accounts": rows,
    }


def _account_candidates_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SQLite 账号学习候选入口",
        "",
        f"- 批次：{payload['batch_id']}",
        f"- 来源候选批次：{payload['source_batch_dir']}",
        "- 评论处理：已忽略",
        "",
        "| 平台 | 账号 | 状态 | 新增 | 变更 | 主要方向 |",
        "|---|---|---|---:|---:|---|",
    ]
    for account in payload["accounts"]:
        top_directions = "、".join(list(account["direction_counts"])[:5]) or "未归类"
        lines.append(
            f"| {account['platform']} | {account['account_name']} | {account['knowledge_status']} | {account['new_count']} | {account['changed_count']} | {top_directions} |"
        )
    return "\n".join(lines) + "\n"


def _batch_summary_markdown(result: dict[str, Any], records: list[dict[str, Any]]) -> str:
    lines = [
        "# SQLite 导入批次摘要",
        "",
        f"- 批次：{result['batch_id']}",
        f"- 数据库：{result['database']}",
        f"- 新增内容：{result['content']['new']}",
        f"- 变更内容：{result['content']['changed']}",
        "- 评论处理：已忽略",
        "",
        "| 平台 | 账号 | 类型 | 标题 | 建议方向 | 原始定位 |",
        "|---|---|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            "| {platform} | {account_name} | {change_type} | {title} | {directions} | {table}:{pk} |".format(
                platform=_markdown_cell(record["platform"]),
                account_name=_markdown_cell(record["account_name"]),
                change_type=record["change_type"],
                title=_markdown_cell(record["title"] or "无标题"),
                directions=_markdown_cell("、".join(record["suggested_directions"])),
                table=record["raw_locator"]["table"],
                pk=record["raw_locator"]["pk"],
            )
        )
    return "\n".join(lines) + "\n"


def _accounts_markdown(accounts: list[dict[str, Any]]) -> str:
    lines = ["# SQLite 账号清单", "", "| 平台 | 账号 | 内容数 | 粉丝 | 来源表 |", "|---|---|---:|---:|---|"]
    for account in accounts:
        lines.append(
            f"| {account['platform']} | {account['account_name']} | {account.get('content_count', 0)} | {account.get('fans', '')} | {account.get('creator_table', '')} |"
        )
    return "\n".join(lines) + "\n"


def _next_actions_markdown(accounts: list[dict[str, Any]], records: list[dict[str, Any]]) -> str:
    account_names = sorted({record["account_name"] for record in records if record.get("account_name")})
    lines = ["# 下一步建议", ""]
    if not records:
        lines.append("- 本次没有新增或变更内容。")
    for name in account_names:
        lines.append(f"- {name}：进入账号学习候选审核；已正式入库账号可继续粗扫，新增账号先生成候选账号报告。")
    return "\n".join(lines) + "\n"


def _source_index_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SQLite 原始数据源索引",
        "",
        f"- 数据库：{payload['database']}",
        f"- 最新批次：{payload.get('latest_batch_id') or '无'}",
        f"- 最新批次目录：{payload.get('latest_batch_dir') or '无'}",
        "- 评论处理：已忽略",
        "",
        "## 账号",
        "",
        "| 平台 | 账号 | 内容数 | 粉丝 |",
        "|---|---|---:|---:|",
    ]
    for account in payload.get("accounts", []):
        lines.append(f"| {account['platform']} | {account['account_name']} | {account.get('content_count', 0)} | {account.get('fans', '')} |")
    lines.extend(["", "## 表规模", "", "| 表 | 行数 |", "|---|---:|"])
    for table in payload.get("tables", []):
        lines.append(f"| {table['table']} | {table['count']} |")
    return "\n".join(lines) + "\n"


def _status_markdown(payload: dict[str, Any]) -> str:
    result = payload.get("last_result", {})
    content = result.get("content", {})
    return (
        "# SQLite 导入状态\n\n"
        f"- 最新批次：{payload.get('latest_batch_id') or '无'}\n"
        f"- 最新批次目录：{payload.get('latest_batch_dir') or '无'}\n"
        f"- 内容总数：{content.get('total', 0)}\n"
        f"- 本次新增：{content.get('new', 0)}\n"
        f"- 本次变更：{content.get('changed', 0)}\n"
        f"- 本次 missing：{content.get('missing', 0)}\n"
        "- 评论处理：已忽略\n"
    )


def _content_fingerprint(payload: dict[str, Any], text_fingerprint: str) -> str:
    selected = {
        "text": text_fingerprint,
        "title": payload.get("title", ""),
        "desc": payload.get("desc", ""),
        "content": payload.get("content", ""),
        "liked_count": payload.get("liked_count", ""),
        "collected_count": payload.get("collected_count", ""),
        "comment_count": payload.get("comment_count", ""),
        "share_count": payload.get("share_count", ""),
        "last_modify_ts": payload.get("last_modify_ts", ""),
    }
    return _hash_text(json.dumps(selected, ensure_ascii=False, sort_keys=True))


def _summary(text: str, limit: int = 120) -> str:
    compact = " ".join(str(text or "").split())
    return compact if len(compact) <= limit else compact[:limit] + "..."


def _markdown_cell(value: Any) -> str:
    return " ".join(str(value or "").split()).replace("|", "/")


def _jsonl_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonl_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_jsonl_safe(child) for child in value]
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({_quote(table)})").fetchall()]


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
