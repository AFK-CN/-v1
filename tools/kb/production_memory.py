from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from .schemas import now_iso


SCHEMA_VERSION = 2
DEFAULT_DB_PATH = Path("20_User/data/content_production.sqlite")
TOPIC_FIELDS = (
    "title",
    "audience",
    "problem",
    "direction",
    "angle",
    "mechanism",
    "content_type",
)
FIELD_WEIGHTS = {
    "title": 0.10,
    "audience": 0.10,
    "problem": 0.25,
    "direction": 0.05,
    "angle": 0.20,
    "mechanism": 0.25,
    "content_type": 0.05,
}
DEFAULT_WARNING_THRESHOLD = 0.62
DEFAULT_BLOCK_THRESHOLD = 0.84
DEFAULT_MAX_CONFLICTS = 5
PRODUCTION_VISUAL_COLUMNS = {
    "visual_manifest_path": "TEXT NOT NULL DEFAULT ''",
    "visual_manifest_sha256": "TEXT NOT NULL DEFAULT ''",
    "visual_golden_version": "TEXT NOT NULL DEFAULT ''",
    "visual_status": "TEXT NOT NULL DEFAULT ''",
    "generator_name": "TEXT NOT NULL DEFAULT ''",
    "model_version": "TEXT NOT NULL DEFAULT ''",
    "prompt_set_sha256": "TEXT NOT NULL DEFAULT ''",
    "reference_assets_json": "TEXT NOT NULL DEFAULT '[]'",
    "visual_qa_json": "TEXT NOT NULL DEFAULT '{}'",
    "accepted_at": "TEXT NOT NULL DEFAULT ''",
}


def database_path(root: Path) -> Path:
    return root.resolve() / DEFAULT_DB_PATH


def connect(root: Path) -> sqlite3.Connection:
    path = database_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _account_manifest(root: Path, account_skill_id: str) -> dict[str, Any]:
    registry_path = root.resolve() / "20_User/config/account_skill_registry.json"
    if not registry_path.is_file():
        return {}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    for account in registry.get("accounts", []):
        if not isinstance(account, dict) or str(account.get("account_skill_id")) != account_skill_id:
            continue
        skill_path = Path(str(account.get("skill_path") or ""))
        if skill_path.is_absolute():
            account_dir = skill_path.parent.parent
        else:
            account_dir = (root.resolve() / skill_path).parent.parent
        manifest_path = account_dir / "ACCOUNT_SKILL_MANIFEST.json"
        if not manifest_path.is_file():
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _production_gates(root: Path, account_skill_id: str) -> set[str]:
    manifest = _account_manifest(root, account_skill_id)
    gates = manifest.get("required_production_gates") or []
    return {str(gate) for gate in gates if str(gate).strip()}


def _visual_gate_payload(
    root: Path,
    payload: dict[str, Any],
    *,
    content_id: str,
    account_skill_id: str,
    skill_version: str,
) -> dict[str, Any]:
    visual_status = str(payload.get("visual_status") or "").strip()
    manifest_value = str(payload.get("visual_manifest_path") or "").strip()
    if visual_status != "approved":
        raise ValueError("visual_package gate requires visual_status=approved")
    if not manifest_value:
        raise ValueError("visual_package gate requires visual_manifest_path")
    manifest_path = Path(manifest_value)
    if not manifest_path.is_absolute():
        manifest_path = root.resolve() / manifest_path
    if not manifest_path.is_file():
        raise ValueError("visual_manifest_path does not exist")
    try:
        visual = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"visual manifest is invalid JSON: {exc}") from exc
    validation = visual.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "passed":
        raise ValueError("visual_package gate requires validation.status=passed")
    if str(validation.get("validator") or "") != "visual-package-v1.0":
        raise ValueError("visual_package gate requires validator=visual-package-v1.0")
    if not str(validation.get("validated_at") or "").strip():
        raise ValueError("visual_package gate requires validation.validated_at")
    prompt_set_sha256 = str(validation.get("prompt_set_sha256") or "").strip().lower()
    if len(prompt_set_sha256) != 64 or any(char not in "0123456789abcdef" for char in prompt_set_sha256):
        raise ValueError("visual_package gate requires valid prompt_set_sha256")
    if not isinstance(visual.get("pages"), list) or not visual.get("pages"):
        raise ValueError("visual_package gate requires pages")
    if any(str(page.get("status") or "") != "approved" for page in visual["pages"] if isinstance(page, dict)):
        raise ValueError("visual_package gate requires all pages approved")
    calibration = visual.get("calibration_gate")
    if not isinstance(calibration, dict) or calibration.get("status") != "passed":
        raise ValueError("visual_package gate requires calibration_gate passed")
    if str(visual.get("content_id") or "") != content_id:
        raise ValueError("visual manifest content_id mismatch")
    if str(visual.get("account_skill_id") or "") != account_skill_id:
        raise ValueError("visual manifest account_skill_id mismatch")
    if skill_version and str(visual.get("skill_version") or "") != skill_version:
        raise ValueError("visual manifest skill_version mismatch")
    actual_hash = _sha256_file(manifest_path)
    expected_hash = str(payload.get("visual_manifest_sha256") or "").strip().lower()
    if expected_hash and expected_hash != actual_hash:
        raise ValueError("visual_manifest_sha256 mismatch")
    generator = visual.get("generator") if isinstance(visual.get("generator"), dict) else {}
    reference_ids = [
        str(item.get("id"))
        for item in visual.get("references", [])
        if isinstance(item, dict) and item.get("id")
    ]
    visual_qa = {
        str(page.get("id")): page.get("visual_review")
        for page in visual.get("pages", [])
        if isinstance(page, dict) and page.get("id") and isinstance(page.get("visual_review"), dict)
    }
    return {
        "visual_manifest_path": manifest_value,
        "visual_manifest_sha256": actual_hash,
        "visual_golden_version": str(visual.get("golden_package_version") or ""),
        "visual_status": visual_status,
        "generator_name": str(generator.get("name") or payload.get("generator_name") or ""),
        "model_version": str(generator.get("model_version") or payload.get("model_version") or ""),
        "prompt_set_sha256": prompt_set_sha256,
        "reference_assets_json": json.dumps(reference_ids, ensure_ascii=False, sort_keys=True),
        "visual_qa_json": json.dumps(visual_qa, ensure_ascii=False, sort_keys=True),
        "accepted_at": str(payload.get("accepted_at") or validation.get("validated_at") or now_iso()),
    }


def initialize_database(root: Path) -> dict[str, Any]:
    with connect(root) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                account_skill_id TEXT NOT NULL,
                title TEXT NOT NULL,
                audience TEXT NOT NULL DEFAULT '',
                problem TEXT NOT NULL DEFAULT '',
                direction TEXT NOT NULL DEFAULT '',
                angle TEXT NOT NULL DEFAULT '',
                mechanism TEXT NOT NULL DEFAULT '',
                content_type TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'candidate',
                skill_version TEXT NOT NULL DEFAULT '',
                topic_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS productions (
                content_id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                account_skill_id TEXT NOT NULL,
                skill_version TEXT NOT NULL DEFAULT '',
                output_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'generated',
                created_at TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT '',
                visual_manifest_path TEXT NOT NULL DEFAULT '',
                visual_manifest_sha256 TEXT NOT NULL DEFAULT '',
                visual_golden_version TEXT NOT NULL DEFAULT '',
                visual_status TEXT NOT NULL DEFAULT '',
                generator_name TEXT NOT NULL DEFAULT '',
                model_version TEXT NOT NULL DEFAULT '',
                prompt_set_sha256 TEXT NOT NULL DEFAULT '',
                reference_assets_json TEXT NOT NULL DEFAULT '[]',
                visual_qa_json TEXT NOT NULL DEFAULT '{}',
                accepted_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(topic_id) REFERENCES topics(topic_id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                account_skill_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT '',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                assessment TEXT NOT NULL DEFAULT '',
                decision TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(content_id) REFERENCES productions(content_id),
                FOREIGN KEY(topic_id) REFERENCES topics(topic_id)
            );

            CREATE TABLE IF NOT EXISTS topic_relations (
                source_topic_id TEXT NOT NULL,
                target_topic_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                similarity REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                PRIMARY KEY(source_topic_id, target_topic_id, relation_type),
                FOREIGN KEY(source_topic_id) REFERENCES topics(topic_id),
                FOREIGN KEY(target_topic_id) REFERENCES topics(topic_id)
            );

            CREATE INDEX IF NOT EXISTS idx_topics_account
                ON topics(account_skill_id, status, created_at);
            CREATE INDEX IF NOT EXISTS idx_topics_direction
                ON topics(account_skill_id, direction, content_type);
            CREATE INDEX IF NOT EXISTS idx_topics_fingerprint
                ON topics(account_skill_id, topic_fingerprint);
            CREATE INDEX IF NOT EXISTS idx_productions_topic
                ON productions(account_skill_id, topic_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_feedback_content
                ON feedback(account_skill_id, content_id, created_at);
            """
        )
        existing_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(productions)")
        }
        for column, definition in PRODUCTION_VISUAL_COLUMNS.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE productions ADD COLUMN {column} {definition}")
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        connection.commit()
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "database": str(DEFAULT_DB_PATH),
    }


def validate_database(root: Path) -> dict[str, Any]:
    path = database_path(root)
    if not path.exists():
        return {"ok": False, "errors": ["production_memory_database_missing"]}
    required_tables = {"metadata", "topics", "productions", "feedback", "topic_relations"}
    errors: list[str] = []
    try:
        with connect(root) as connection:
            tables = {
                str(row["name"])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            missing = required_tables - tables
            errors.extend(f"production_memory_table_missing:{name}" for name in sorted(missing))
            version = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            if not version or str(version["value"]) != str(SCHEMA_VERSION):
                errors.append("production_memory_schema_version_invalid")
            production_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(productions)")
            }
            for column in sorted(set(PRODUCTION_VISUAL_COLUMNS) - production_columns):
                errors.append(f"production_memory_column_missing:productions:{column}")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                errors.append("production_memory_integrity_check_failed")
    except sqlite3.DatabaseError as exc:
        errors.append(f"production_memory_database_error:{exc}")
    return {"ok": not errors, "errors": errors, "database": str(DEFAULT_DB_PATH)}


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def text_units(value: Any) -> set[str]:
    text = normalize_text(value)
    if not text:
        return set()
    if len(text) <= 2:
        return {text}
    return {text[index : index + 2] for index in range(len(text) - 1)}


def text_similarity(left: Any, right: Any) -> float:
    left_text = normalize_text(left)
    right_text = normalize_text(right)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    left_units = text_units(left_text)
    right_units = text_units(right_text)
    union = left_units | right_units
    return len(left_units & right_units) / len(union) if union else 0.0


def topic_fingerprint(topic: dict[str, Any]) -> str:
    payload = "|".join(normalize_text(topic.get(field, "")) for field in TOPIC_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def topic_similarity(candidate: dict[str, Any], existing: dict[str, Any]) -> tuple[float, list[str]]:
    weighted = 0.0
    available_weight = 0.0
    overlap: list[str] = []
    for field, weight in FIELD_WEIGHTS.items():
        if not normalize_text(candidate.get(field)) or not normalize_text(existing.get(field)):
            continue
        score = text_similarity(candidate.get(field), existing.get(field))
        weighted += score * weight
        available_weight += weight
        if score >= 0.78:
            overlap.append(field)
    return (weighted / available_weight if available_weight else 0.0, overlap)


def _topic_rows(connection: sqlite3.Connection, account_skill_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT topic_id, account_skill_id, title, audience, problem, direction,
               angle, mechanism, content_type, platform, status, skill_version,
               topic_fingerprint, created_at
        FROM topics
        WHERE account_skill_id = ? AND status NOT IN ('discarded', 'deleted')
        ORDER BY created_at DESC
        """,
        (account_skill_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def check_topics(
    root: Path,
    account_skill_id: str,
    candidates: Iterable[dict[str, Any]],
    *,
    warning_threshold: float = DEFAULT_WARNING_THRESHOLD,
    block_threshold: float = DEFAULT_BLOCK_THRESHOLD,
    max_conflicts: int = DEFAULT_MAX_CONFLICTS,
) -> dict[str, Any]:
    initialize_database(root)
    account_skill_id = str(account_skill_id).strip()
    if not account_skill_id:
        raise ValueError("account_skill_id is required")
    candidate_list = [dict(item) for item in candidates]
    with connect(root) as connection:
        existing = _topic_rows(connection, account_skill_id)
    results = []
    status_counts = {"pass": 0, "warning": 0, "blocked": 0}
    for index, candidate in enumerate(candidate_list, 1):
        candidate_id = str(candidate.get("candidate_id") or f"candidate_{index}")
        matches = []
        for prior in existing:
            score, overlap = topic_similarity(candidate, prior)
            if score < warning_threshold:
                continue
            matches.append(
                {
                    "topic_id": prior["topic_id"],
                    "title": prior["title"],
                    "similarity": round(score, 4),
                    "overlap_fields": overlap,
                    "status": prior["status"],
                }
            )
        matches.sort(key=lambda item: item["similarity"], reverse=True)
        matches = matches[: max(max_conflicts, 1)]
        highest = matches[0]["similarity"] if matches else 0.0
        if highest >= block_threshold:
            status = "blocked"
        elif matches:
            status = "warning"
        else:
            status = "pass"
        status_counts[status] += 1
        results.append(
            {
                "candidate_id": candidate_id,
                "title": str(candidate.get("title") or ""),
                "status": status,
                "highest_similarity": highest,
                "conflicts": matches,
            }
        )
    return {
        "ok": status_counts["blocked"] == 0,
        "account_skill_id": account_skill_id,
        "checked_history_count": len(existing),
        "candidate_count": len(candidate_list),
        "status_counts": status_counts,
        "results": results,
        "token_boundary": "compact_conflicts_only",
    }


def record_topics(root: Path, account_skill_id: str, topics: Iterable[dict[str, Any]]) -> dict[str, Any]:
    initialize_database(root)
    account_skill_id = str(account_skill_id).strip()
    if not account_skill_id:
        raise ValueError("account_skill_id is required")
    recorded = []
    with connect(root) as connection:
        for item in topics:
            row = dict(item)
            title = str(row.get("title") or "").strip()
            if not title:
                raise ValueError("topic title is required")
            topic_id = str(row.get("topic_id") or f"topic_{uuid.uuid4().hex}")
            created_at = str(row.get("created_at") or now_iso())
            values = {
                field: str(row.get(field) or "").strip()
                for field in TOPIC_FIELDS
            }
            connection.execute(
                """
                INSERT INTO topics(
                    topic_id, account_skill_id, title, audience, problem, direction,
                    angle, mechanism, content_type, platform, status, skill_version,
                    topic_fingerprint, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic_id) DO UPDATE SET
                    title=excluded.title,
                    audience=excluded.audience,
                    problem=excluded.problem,
                    direction=excluded.direction,
                    angle=excluded.angle,
                    mechanism=excluded.mechanism,
                    content_type=excluded.content_type,
                    platform=excluded.platform,
                    status=excluded.status,
                    skill_version=excluded.skill_version,
                    topic_fingerprint=excluded.topic_fingerprint,
                    updated_at=excluded.updated_at
                """,
                (
                    topic_id,
                    account_skill_id,
                    values["title"],
                    values["audience"],
                    values["problem"],
                    values["direction"],
                    values["angle"],
                    values["mechanism"],
                    values["content_type"],
                    str(row.get("platform") or ""),
                    str(row.get("status") or "candidate"),
                    str(row.get("skill_version") or ""),
                    topic_fingerprint(row),
                    created_at,
                    now_iso(),
                ),
            )
            recorded.append(topic_id)
        connection.commit()
    return {"ok": True, "account_skill_id": account_skill_id, "recorded": recorded}


def record_production(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    initialize_database(root)
    topic_id = str(payload.get("topic_id") or "").strip()
    account_skill_id = str(payload.get("account_skill_id") or "").strip()
    if not topic_id or not account_skill_id:
        raise ValueError("topic_id and account_skill_id are required")
    content_id = str(payload.get("content_id") or f"content_{uuid.uuid4().hex}")
    skill_version = str(payload.get("skill_version") or "")
    gates = _production_gates(root, account_skill_id)
    visual_fields = {
        "visual_manifest_path": str(payload.get("visual_manifest_path") or ""),
        "visual_manifest_sha256": str(payload.get("visual_manifest_sha256") or ""),
        "visual_golden_version": str(payload.get("visual_golden_version") or ""),
        "visual_status": str(payload.get("visual_status") or ""),
        "generator_name": str(payload.get("generator_name") or ""),
        "model_version": str(payload.get("model_version") or ""),
        "prompt_set_sha256": str(payload.get("prompt_set_sha256") or ""),
        "reference_assets_json": json.dumps(payload.get("reference_assets") or [], ensure_ascii=False, sort_keys=True),
        "visual_qa_json": json.dumps(payload.get("visual_qa") or {}, ensure_ascii=False, sort_keys=True),
        "accepted_at": str(payload.get("accepted_at") or ""),
    }
    if "visual_package" in gates:
        visual_fields = _visual_gate_payload(
            root,
            payload,
            content_id=content_id,
            account_skill_id=account_skill_id,
            skill_version=skill_version,
        )
    with connect(root) as connection:
        topic = connection.execute(
            "SELECT account_skill_id FROM topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise ValueError(f"unknown topic_id: {topic_id}")
        if str(topic["account_skill_id"]) != account_skill_id:
            raise ValueError("topic account_skill_id mismatch")
        connection.execute(
            """
            INSERT INTO productions(
                content_id, topic_id, account_skill_id, skill_version,
                output_path, status, created_at, published_at,
                visual_manifest_path, visual_manifest_sha256, visual_golden_version,
                visual_status, generator_name, model_version, prompt_set_sha256,
                reference_assets_json, visual_qa_json, accepted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(content_id) DO UPDATE SET
                output_path=excluded.output_path,
                status=excluded.status,
                skill_version=excluded.skill_version,
                published_at=excluded.published_at,
                visual_manifest_path=excluded.visual_manifest_path,
                visual_manifest_sha256=excluded.visual_manifest_sha256,
                visual_golden_version=excluded.visual_golden_version,
                visual_status=excluded.visual_status,
                generator_name=excluded.generator_name,
                model_version=excluded.model_version,
                prompt_set_sha256=excluded.prompt_set_sha256,
                reference_assets_json=excluded.reference_assets_json,
                visual_qa_json=excluded.visual_qa_json,
                accepted_at=excluded.accepted_at
            """,
            (
                content_id,
                topic_id,
                account_skill_id,
                skill_version,
                str(payload.get("output_path") or ""),
                str(payload.get("status") or "generated"),
                str(payload.get("created_at") or now_iso()),
                str(payload.get("published_at") or ""),
                visual_fields["visual_manifest_path"],
                visual_fields["visual_manifest_sha256"],
                visual_fields["visual_golden_version"],
                visual_fields["visual_status"],
                visual_fields["generator_name"],
                visual_fields["model_version"],
                visual_fields["prompt_set_sha256"],
                visual_fields["reference_assets_json"],
                visual_fields["visual_qa_json"],
                visual_fields["accepted_at"],
            ),
        )
        connection.commit()
    return {
        "ok": True,
        "content_id": content_id,
        "topic_id": topic_id,
        "required_production_gates": sorted(gates),
        "visual_status": visual_fields["visual_status"],
    }


def record_feedback(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    initialize_database(root)
    content_id = str(payload.get("content_id") or "").strip()
    if not content_id:
        raise ValueError("content_id is required")
    feedback_id = str(payload.get("feedback_id") or f"feedback_{uuid.uuid4().hex}")
    with connect(root) as connection:
        production = connection.execute(
            "SELECT topic_id, account_skill_id FROM productions WHERE content_id = ?",
            (content_id,),
        ).fetchone()
        if not production:
            raise ValueError(f"unknown content_id: {content_id}")
        connection.execute(
            """
            INSERT INTO feedback(
                feedback_id, content_id, topic_id, account_skill_id, source_type,
                platform, metrics_json, assessment, decision, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(feedback_id) DO UPDATE SET
                metrics_json=excluded.metrics_json,
                assessment=excluded.assessment,
                decision=excluded.decision
            """,
            (
                feedback_id,
                content_id,
                str(production["topic_id"]),
                str(production["account_skill_id"]),
                str(payload.get("source_type") or "manual"),
                str(payload.get("platform") or ""),
                json.dumps(payload.get("metrics") or {}, ensure_ascii=False, sort_keys=True),
                str(payload.get("assessment") or ""),
                str(payload.get("decision") or ""),
                str(payload.get("created_at") or now_iso()),
            ),
        )
        connection.commit()
    return {"ok": True, "feedback_id": feedback_id, "content_id": content_id}


def review_context(root: Path, content_id: str) -> dict[str, Any]:
    initialize_database(root)
    with connect(root) as connection:
        production = connection.execute(
            """
            SELECT p.content_id, p.topic_id, p.account_skill_id, p.skill_version,
                   p.output_path, p.status, p.created_at, p.published_at,
                   p.visual_manifest_path, p.visual_manifest_sha256,
                   p.visual_golden_version, p.visual_status, p.generator_name,
                   p.model_version, p.prompt_set_sha256, p.reference_assets_json,
                   p.visual_qa_json, p.accepted_at,
                   t.title, t.audience, t.problem, t.direction, t.angle,
                   t.mechanism, t.content_type, t.platform
            FROM productions p
            JOIN topics t ON t.topic_id = p.topic_id
            WHERE p.content_id = ?
            """,
            (content_id,),
        ).fetchone()
        if not production:
            return {"ok": False, "error": "content_not_found", "content_id": content_id}
        feedback_rows = connection.execute(
            """
            SELECT feedback_id, source_type, platform, metrics_json,
                   assessment, decision, created_at
            FROM feedback WHERE content_id = ? ORDER BY created_at
            """,
            (content_id,),
        ).fetchall()
    feedback_items = []
    for row in feedback_rows:
        item = dict(row)
        item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
        feedback_items.append(item)
    content = dict(production)
    content["reference_assets"] = json.loads(content.pop("reference_assets_json") or "[]")
    content["visual_qa"] = json.loads(content.pop("visual_qa_json") or "{}")
    return {
        "ok": True,
        "content": content,
        "feedback": feedback_items,
        "token_boundary": "one_content_only",
    }
