from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tools.account_learning_card import CONTRACT_ID, detect_schema
from tools.account_learning_pipeline import load_config, refresh_workflow, workflow_root
from tools.account_learning_stage1_extract import (
    IMAGE_TEXT_VISUAL_KEYWORDS,
    _derive_observation,
    _derive_signal_observation,
    card_content_form,
    derive_publish_copy_observation,
    make_publish_copy_record,
    render_publish_copy_study,
    summarize_publish_copy_records,
)
from tools.kb.schemas import now_iso


LENSES = ("positioning", "topics", "structures", "expression", "counterexamples")
STAGE1_LENSES = ("structures", "expression")
V26_MIGRATION_ID = "upgrade_account_learning_v2_6"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        item = json.loads(raw)
        if not isinstance(item, dict):
            raise ValueError(f"expected JSON object: {path}:{line_number}")
        rows.append(item)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _field(text: str, name: str) -> str:
    match = re.search(rf"^(?:[-*]\s*)?{re.escape(name)}\s*[：:]\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip("`")


def _card_score(path: Path, text: str) -> tuple[int, int, int, int, str]:
    schema = detect_schema(text)
    return (
        2 if schema == CONTRACT_ID else (1 if schema == "evidence_card_v1" else 0),
        1 if "发布内容层学习" in text else 0,
        1 if "## 12. 证据缺口与候选判断" in text else 0,
        1 if "deep_relearn" in path.as_posix() else 0,
        path.as_posix(),
    )


def _card_index(roots: list[Path]) -> tuple[dict[str, Path], dict[str, str]]:
    selected: dict[str, tuple[tuple[int, int, int, int, str], Path, str]] = {}
    seen_paths: set[Path] = set()
    for base in roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("cards/*.md")):
            path = path.resolve()
            if path in seen_paths:
                continue
            seen_paths.add(path)
            text = path.read_text(encoding="utf-8", errors="ignore")
            source_id = _field(text, "source_id")
            if not source_id:
                stem = path.stem
                source_id = stem.split("_", 1)[-1] if "_" in stem else stem
            score = _card_score(path, text)
            existing = selected.get(source_id)
            if existing is None or score > existing[0]:
                selected[source_id] = (score, path, text)
    return (
        {source_id: record[1] for source_id, record in selected.items()},
        {source_id: record[2] for source_id, record in selected.items()},
    )


def _candidate_card_roots(root: Path, base: Path, state: dict[str, Any]) -> list[Path]:
    roots = [base]
    profile_id = str(state.get("profile_id") or "").strip()
    if not profile_id:
        return roots
    asset_root = root / "10_Knowledge/candidates/account_assets"
    for branch in ("nas_video_learning", "local_account_learning", "image_text_learning"):
        candidate = asset_root / branch / profile_id
        if candidate.exists():
            roots.append(candidate)
    return roots


def _is_image_text(text: str) -> tuple[bool, str]:
    content_form = card_content_form(text)
    content_probe = content_form.lower()
    if "图文" in content_probe or "image_text" in content_probe or "image-text" in content_probe:
        return True, content_form
    media_match = re.search(r"^(?:[-*]\s*)?(?:媒体类型|媒介分支)\s*[：:]\s*([^\n]+)", text, re.MULTILINE)
    media_type = media_match.group(1).strip() if media_match else ""
    media_probe = media_type.lower()
    is_image_text = "图文" in media_probe or "image_text" in media_probe or "image-text" in media_probe
    return is_image_text, content_form


def _candidate_card(
    root: Path,
    base: Path,
    item: dict[str, Any],
    card_paths: dict[str, Path],
    card_texts: dict[str, str],
) -> tuple[Path | None, str]:
    explicit = str(item.get("card_path") or "").strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            return path, path.read_text(encoding="utf-8", errors="ignore")
    refs = [str(value) for value in item.get("source_refs", []) if str(value)]
    if len(refs) != 1:
        return None, ""
    path = card_paths.get(refs[0])
    if path is None:
        return None, ""
    return path, card_texts.get(refs[0], "")


def _upgrade_stage1_candidates(
    root: Path,
    base: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    *,
    apply: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    contract = config.get("stage1_deep_observation", {})
    observation_schema = str(contract.get("schema_id") or "")
    publish_schema = str(contract.get("publish_copy_schema_id") or "")
    visual_schema = str(contract.get("image_text_visual_schema_id") or "")
    card_paths, card_texts = _card_index(_candidate_card_roots(root, base, state))
    candidate_by_id: dict[str, dict[str, Any]] = {}
    source_ids: set[str] = set()
    unified_source_ids: set[str] = set()
    stats = {
        "structure_expression_count": 0,
        "deep_observation_backfilled": 0,
        "deep_observation_preserved": 0,
        "deep_observation_deferred": 0,
        "publish_copy_expected": 0,
        "publish_copy_backfilled": 0,
        "publish_copy_preserved": 0,
        "image_text_visual_expected": 0,
        "image_text_visual_backfilled": 0,
        "image_text_visual_preserved": 0,
    }
    for lens in LENSES:
        path = base / "candidates" / f"{lens}.jsonl"
        rows = _read_jsonl(path)
        changed = False
        for item in rows:
            candidate_id = str(item.get("id") or "")
            if candidate_id:
                candidate_by_id[candidate_id] = item
            source_ids.update(str(value) for value in item.get("source_refs", []) if str(value))
            if lens not in STAGE1_LENSES:
                continue
            stats["structure_expression_count"] += 1
            card_path, card_text = _candidate_card(root, base, item, card_paths, card_texts)
            unified = bool(card_text and detect_schema(card_text) == CONTRACT_ID)
            if unified:
                unified_source_ids.update(str(value) for value in item.get("source_refs", []) if str(value))
            if not unified or card_path is None:
                if item.get("observation_schema") == observation_schema and isinstance(item.get("observation"), dict):
                    stats["deep_observation_preserved"] += 1
                else:
                    stats["deep_observation_deferred"] += 1
                continue

            is_image_text, content_form = _is_image_text(card_text)
            item["compatibility_mode"] = "unified_card"
            item["card_schema"] = CONTRACT_ID
            item["content_form"] = content_form or ("图文" if is_image_text else "")
            if item.get("observation_schema") == observation_schema and isinstance(item.get("observation"), dict):
                stats["deep_observation_preserved"] += 1
            else:
                item["observation_schema"] = observation_schema
                item["observation"] = _derive_observation(
                    lens=lens,
                    text=card_text,
                    path=card_path,
                    root=root,
                    contract=contract,
                )
                stats["deep_observation_backfilled"] += 1
                changed = True

            if lens == "expression":
                stats["publish_copy_expected"] += 1
                if isinstance(item.get("publish_copy_observation"), dict):
                    stats["publish_copy_preserved"] += 1
                else:
                    item["publish_copy_observation"] = derive_publish_copy_observation(
                        schema_id=publish_schema,
                        dimensions=[str(value) for value in contract.get("publish_copy_dimensions", [])],
                        text=card_text,
                        path=card_path,
                        root=root,
                        status=str(contract.get("candidate_status") or "single_card_observation"),
                    )
                    stats["publish_copy_backfilled"] += 1
                    changed = True
            if is_image_text and lens == "structures":
                stats["image_text_visual_expected"] += 1
                if isinstance(item.get("image_text_visual_observation"), dict):
                    stats["image_text_visual_preserved"] += 1
                else:
                    item["image_text_visual_observation"] = _derive_signal_observation(
                        schema_id=visual_schema,
                        dimensions=[str(value) for value in contract.get("image_text_visual_dimensions", [])],
                        keyword_map=IMAGE_TEXT_VISUAL_KEYWORDS,
                        headings=("内容结构", "视频/图文表现层学习"),
                        fingerprint_key="visual_sequence_fingerprint",
                        text=card_text,
                        path=card_path,
                        root=root,
                        status=str(contract.get("candidate_status") or "single_card_observation"),
                    )
                    stats["image_text_visual_backfilled"] += 1
                    changed = True
        if apply and changed:
            _write_jsonl(path, rows)
    stats["source_total"] = len(source_ids)
    stats["unified_source_count"] = len(unified_source_ids)
    stats["deferred_source_count"] = max(len(source_ids) - len(unified_source_ids), 0)
    stats["stage1_schema_enabled"] = stats["deep_observation_deferred"] == 0
    return stats, candidate_by_id


def _upgrade_publish_copy_study(
    root: Path,
    base: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    contract = config.get("stage1_deep_observation", {})
    observation_schema = str(contract.get("publish_copy_schema_id") or "")
    study_schema = str(contract.get("publish_copy_study_schema_id") or "")
    dimensions = [str(value) for value in contract.get("publish_copy_dimensions", [])]
    candidate_status = str(contract.get("candidate_status") or "single_card_observation")
    expression_path = base / "candidates/expression.jsonl"
    expression_rows = _read_jsonl(expression_path)
    source_to_candidate_ids: dict[str, list[str]] = {}
    for item in expression_rows:
        candidate_id = str(item.get("id") or "")
        for source_id in item.get("source_refs", []):
            source_id = str(source_id)
            if source_id and candidate_id:
                source_to_candidate_ids.setdefault(source_id, []).append(candidate_id)
    expected_source_ids = set(source_to_candidate_ids)
    card_paths, card_texts = _card_index(_candidate_card_roots(root, base, state))
    records: list[dict[str, Any]] = []
    observation_by_source: dict[str, dict[str, Any]] = {}
    missing_card_source_ids: list[str] = []
    for source_id in sorted(expected_source_ids):
        card_path = card_paths.get(source_id)
        card_text = card_texts.get(source_id, "")
        if card_path is None or not card_text:
            missing_card_source_ids.append(source_id)
            continue
        record = make_publish_copy_record(
            source_id=source_id,
            expression_candidate_ids=source_to_candidate_ids[source_id],
            card_path=card_path,
            card_text=card_text,
            root=root,
            schema_id=observation_schema,
            dimensions=dimensions,
            status=candidate_status,
        )
        records.append(record)
        observation_by_source[source_id] = record["publish_copy_observation"]

    changed_expression = False
    for item in expression_rows:
        source_refs = [str(value) for value in item.get("source_refs", []) if str(value)]
        refs = [f"publish-copy-{source_id}" for source_id in source_refs if source_id in observation_by_source]
        if item.get("publish_copy_observation_refs") != refs:
            item["publish_copy_observation_refs"] = refs
            changed_expression = True
        if len(source_refs) == 1 and source_refs[0] in observation_by_source:
            observation = observation_by_source[source_refs[0]]
            if item.get("publish_copy_observation") != observation:
                item["publish_copy_observation"] = observation
                changed_expression = True

    report = summarize_publish_copy_records(
        workflow_id=str(state.get("workflow_id") or base.name),
        account_name=str(state.get("account_name") or base.name),
        records=records,
        expected_source_ids=expected_source_ids,
        study_schema=study_schema,
        observation_schema=observation_schema,
    )
    report["missing_card_source_ids"] = missing_card_source_ids
    if apply:
        if changed_expression:
            _write_jsonl(expression_path, expression_rows)
        observation_path = base / "candidates/publish_copy_observations.jsonl"
        _write_jsonl(observation_path, records)
        report["observation_sha256"] = hashlib.sha256(observation_path.read_bytes()).hexdigest()
        _write_json(base / "PUBLISH_COPY_SPECIAL_STUDY.json", report)
        (base / "PUBLISH_COPY_SPECIAL_STUDY.md").write_text(
            render_publish_copy_study(report),
            encoding="utf-8",
        )
    return report


def _compact(value: str, limit: int = 280) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _first_summary(
    members: list[str],
    candidate_by_id: dict[str, dict[str, Any]],
    lenses: set[str],
    fallback: str,
) -> str:
    for member in members:
        candidate = candidate_by_id.get(member, {})
        lens = str(candidate.get("type") or candidate.get("lens") or "")
        summary = _compact(str(candidate.get("summary") or ""))
        if lens in lenses and summary:
            return summary
    return _compact(fallback)


def _upgrade_clusters(
    base: Path,
    candidate_by_id: dict[str, dict[str, Any]],
    *,
    apply: bool,
) -> dict[str, Any]:
    path = base / "candidate_clusters.jsonl"
    clusters = _read_jsonl(path)
    method_candidates = 0
    backfilled = 0
    preserved = 0
    for cluster in clusters:
        if cluster.get("cluster_type") != "method_candidate":
            continue
        method_candidates += 1
        members = [str(value) for value in cluster.get("candidate_ids", []) if str(value)]
        member_lenses = {
            str(candidate_by_id.get(member, {}).get("type") or candidate_by_id.get(member, {}).get("lens") or "")
            for member in members
        }
        if not cluster.get("mechanism_kind"):
            if "structures" in member_lenses and "expression" in member_lenses:
                cluster["mechanism_kind"] = "composite"
            elif "structures" in member_lenses:
                cluster["mechanism_kind"] = "content_structure"
            elif "expression" in member_lenses:
                cluster["mechanism_kind"] = "expression_fingerprint"
            elif "topics" in member_lenses:
                cluster["mechanism_kind"] = "topic_system"
            else:
                cluster["mechanism_kind"] = "positioning"
        analysis = cluster.get("production_analysis")
        required = {
            "fixed_elements",
            "variable_elements",
            "tension_engine",
            "trust_engine",
            "understanding_engine",
            "beneficiary_engine",
            "length_basis",
            "boundaries",
        }
        if isinstance(analysis, dict) and required.issubset(analysis) and all(analysis.get(key) for key in required):
            preserved += 1
            continue
        core = _compact(str(cluster.get("core_mechanism") or cluster.get("title") or "已验证核心机制"))
        roles = cluster.get("lens_roles", {}) if isinstance(cluster.get("lens_roles"), dict) else {}
        boundary_members = [
            str(value)
            for role in ("boundary", "evidence_gate")
            for value in roles.get(role, [])
            if str(value)
        ]
        boundary_summary = _first_summary(
            boundary_members or members,
            candidate_by_id,
            {"counterexamples"},
            "只命中题材、人物、场景、道具或平台词而缺少核心机制时不得触发。",
        )
        cluster["production_analysis"] = {
            "fixed_elements": [core],
            "variable_elements": ["题材、人物、场景、道具与表达实现可变化，但不得改变核心因果和证据边界。"],
            "tension_engine": _first_summary(members, candidate_by_id, {"structures"}, core),
            "trust_engine": _first_summary(members, candidate_by_id, {"positioning", "expression"}, core),
            "understanding_engine": _first_summary(members, candidate_by_id, {"structures", "topics"}, core),
            "beneficiary_engine": _first_summary(members, candidate_by_id, {"positioning", "topics"}, core),
            "length_basis": "以核心机制、证据推进、结果或反馈和受益落点形成信息闭环为完成条件，不使用固定时长或篇幅。",
            "boundaries": [boundary_summary],
        }
        cluster["v26_migration_basis"] = "existing_cluster_core_and_member_candidate_evidence"
        backfilled += 1
    if apply and backfilled:
        _write_jsonl(path, clusters)
    return {
        "method_candidate_count": method_candidates,
        "production_analysis_backfilled": backfilled,
        "production_analysis_preserved": preserved,
        "stage2_schema_enabled": method_candidates == backfilled + preserved,
    }


def _handoff_entry(source: str, method_ids: list[str]) -> dict[str, Any]:
    return {
        "source": source,
        "basis": "approved_formal_account_skill_backfill",
        "source_method_ids": method_ids,
    }


def _upgrade_handoff(base: Path, *, apply: bool) -> dict[str, Any]:
    path = base / "ACCOUNT_PRODUCTION_HANDOFF.json"
    if path.exists():
        payload = _read_json(path)
        return {"status": "preserved", "path": path.name, "schema_version": payload.get("schema_version", "")}
    verified = _read_jsonl(base / "verified.jsonl")
    method_ids = sorted(str(item.get("id")) for item in verified if item.get("id"))
    payload = {
        "schema_version": "account_production_handoff_v1",
        "status": "ready_for_review",
        "formal_write": False,
        "callable": False,
        "user_review_required": True,
        "source_method_ids": method_ids,
        "coverage": {
            "structures": "verified",
            "expression": "verified",
            "anti_ai": "verified",
            "production_templates": "verified",
            "acceptance": "verified",
        },
        "structure_library_candidates": [
            _handoff_entry("account_skill_candidate/references/production.md", method_ids)
        ],
        "expression_fingerprint_candidates": [
            _handoff_entry("account_skill_candidate/references/style.md", method_ids)
        ],
        "anti_ai_rule_candidates": [
            _handoff_entry("account_skill_candidate/account_views/减少AI味输出规则.md", method_ids)
        ],
        "production_template_mappings": [
            _handoff_entry("account_skill_candidate/account_views/内容输出标准模板.md", method_ids)
        ],
        "acceptance_checks": [
            _handoff_entry("account_skill_candidate/references/acceptance.md", method_ids)
        ],
        "migration": {
            "type": "backfill_from_approved_formal_account_skill_candidate",
            "migrated_at": now_iso(),
        },
    }
    if apply:
        _write_json(path, payload)
    return {"status": "backfilled", "path": path.name, "schema_version": payload["schema_version"]}


def _upgrade_state_and_manifest(
    root: Path,
    base: Path,
    config: dict[str, Any],
    stage1: dict[str, Any],
    publish_copy: dict[str, Any],
    stage2: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    state_path = base / "PIPELINE_STATE.json"
    state = _read_json(state_path)
    manifest_path = base / "promotion_manifest.json"
    manifest = _read_json(manifest_path)
    verified_count = len(_read_jsonl(base / "verified.jsonl"))
    accounting = _authoritative_accounting(base, state, manifest, stage1, verified_count)
    state.update(accounting)
    state["v26_unified_source_count"] = int(stage1["unified_source_count"])
    state["v26_legacy_compatible_source_count"] = max(
        int(accounting["deep_card_count"]) - int(stage1["unified_source_count"]),
        0,
    )
    state["schema_version"] = str(config.get("version") or "2.6")
    state["method"] = str(config.get("method") or state.get("method") or "")
    state["publish_copy_observation_schema"] = str(
        config.get("stage1_deep_observation", {}).get("publish_copy_schema_id") or ""
    )
    state["publish_copy_study_schema"] = str(
        config.get("stage1_deep_observation", {}).get("publish_copy_study_schema_id") or ""
    )
    state["publish_copy_expected_count"] = int(publish_copy.get("expected_source_count") or 0)
    state["publish_copy_completed_count"] = int(publish_copy.get("completed_source_count") or 0)
    state["publish_copy_deferred_count"] = int(publish_copy.get("deferred_source_count") or 0)
    if stage1.get("stage1_schema_enabled"):
        state["stage1_observation_schema"] = str(config.get("stage1_deep_observation", {}).get("schema_id") or "")
    else:
        state["stage1_observation_schema"] = ""
    if stage2.get("stage2_schema_enabled"):
        state["stage2_production_mechanism_schema"] = str(
            config.get("stage2_production_mechanism", {}).get("schema_id") or ""
        )
    state["stage6_production_handoff_schema"] = str(
        config.get("stage6_production_handoff", {}).get("schema_id") or ""
    )
    state["stage6_account_skill_schema"] = str(
        config.get("stage6_account_skill_package", {}).get("schema_id") or ""
    )
    migrations = state.setdefault("migrations", [])
    if not any(isinstance(item, dict) and item.get("id") == V26_MIGRATION_ID for item in migrations):
        migrations.append(
            {
                "id": V26_MIGRATION_ID,
                "completed_at": now_iso(),
                "mode": "evidence_backfill_with_legacy_compatibility",
            }
        )
    publish_migration_id = "backfill_publish_copy_special_learning_v1"
    if not any(isinstance(item, dict) and item.get("id") == publish_migration_id for item in migrations):
        migrations.append(
            {
                "id": publish_migration_id,
                "completed_at": now_iso(),
                "mode": "per_source_publish_layer_observation_and_cross_card_candidate_summary",
            }
        )
    state["updated_at"] = now_iso()
    manifest.update(accounting)
    manifest["schema_version"] = str(config.get("version") or "2.6")
    manifest["v26_unified_source_count"] = state["v26_unified_source_count"]
    manifest["v26_legacy_compatible_source_count"] = state["v26_legacy_compatible_source_count"]
    manifest["publish_copy_observation_schema"] = state["publish_copy_observation_schema"]
    manifest["publish_copy_study_schema"] = state["publish_copy_study_schema"]
    manifest["publish_copy_expected_count"] = state["publish_copy_expected_count"]
    manifest["publish_copy_completed_count"] = state["publish_copy_completed_count"]
    manifest["publish_copy_deferred_count"] = state["publish_copy_deferred_count"]
    if apply:
        _write_json(state_path, state)
        _write_json(manifest_path, manifest)
    return {
        "schema_version": state["schema_version"],
        "stage1_observation_schema": state.get("stage1_observation_schema", ""),
        "stage2_production_mechanism_schema": state.get("stage2_production_mechanism_schema", ""),
        "stage6_production_handoff_schema": state.get("stage6_production_handoff_schema", ""),
        "stage6_account_skill_schema": state.get("stage6_account_skill_schema", ""),
        **accounting,
        "v26_unified_source_count": state["v26_unified_source_count"],
        "v26_legacy_compatible_source_count": state["v26_legacy_compatible_source_count"],
        "publish_copy_observation_schema": state["publish_copy_observation_schema"],
        "publish_copy_study_schema": state["publish_copy_study_schema"],
        "publish_copy_expected_count": state["publish_copy_expected_count"],
        "publish_copy_completed_count": state["publish_copy_completed_count"],
        "publish_copy_deferred_count": state["publish_copy_deferred_count"],
    }


def _valid_accounting(payload: dict[str, Any]) -> dict[str, int] | None:
    values = {
        key: payload.get(key)
        for key in ("source_total", "deep_card_count", "deferred_evidence_count")
    }
    if not all(isinstance(value, int) and value >= 0 for value in values.values()):
        return None
    if values["source_total"] != values["deep_card_count"] + values["deferred_evidence_count"]:
        return None
    return {key: int(value) for key, value in values.items()}


def _authoritative_accounting(
    base: Path,
    state: dict[str, Any],
    manifest: dict[str, Any],
    stage1: dict[str, Any],
    verified_count: int,
) -> dict[str, int]:
    completion_path = base / "FINAL_COMPLETION_AUDIT.json"
    if completion_path.exists():
        completion = _read_json(completion_path).get("source_scope", {})
        if isinstance(completion, dict):
            planned = completion.get("planned")
            ready = completion.get("evidence_ready")
            blocked = completion.get("blocked")
            if all(isinstance(value, int) and value >= 0 for value in (planned, ready, blocked)) and planned == ready + blocked:
                return {
                    "source_total": planned,
                    "deep_card_count": ready,
                    "deferred_evidence_count": blocked,
                    "verified_candidate_method_count": verified_count,
                }

    gap_path = base / "EVIDENCE_GAP_STATUS.json"
    if gap_path.exists():
        gap = _read_json(gap_path)
        planned = gap.get("nas_plan_count")
        ready = gap.get("evidence_ready_count")
        blocked = gap.get("blocked_count")
        if all(isinstance(value, int) and value >= 0 for value in (planned, ready, blocked)) and planned == ready + blocked:
            return {
                "source_total": planned,
                "deep_card_count": ready,
                "deferred_evidence_count": blocked,
                "verified_candidate_method_count": verified_count,
            }

    promotion_path = base / "PROMOTION_STATUS.json"
    if promotion_path.exists():
        promotion = _read_json(promotion_path)
        ready = promotion.get("formal_card_count")
        blocked = promotion.get("evidence_blocked_count")
        if not isinstance(blocked, int):
            blocked = promotion.get("candidate_only_system_pending_count")
        if isinstance(ready, int) and ready >= 0 and isinstance(blocked, int) and blocked >= 0:
            return {
                "source_total": ready + blocked,
                "deep_card_count": ready,
                "deferred_evidence_count": blocked,
                "verified_candidate_method_count": verified_count,
            }

    for payload in (manifest, state):
        existing = _valid_accounting(payload)
        if existing and not (
            existing["deep_card_count"] == 0
            and existing["deferred_evidence_count"] == existing["source_total"]
            and "deferred" not in str(state.get("status") or "")
        ):
            return {**existing, "verified_candidate_method_count": verified_count}

    source_total = int(stage1["source_total"])
    explicitly_deferred = "deferred" in str(state.get("status") or "")
    deep_count = int(stage1["unified_source_count"])
    deferred_count = max(source_total - deep_count, 0)
    if not explicitly_deferred:
        deep_count = source_total
        deferred_count = 0
    return {
        "source_total": source_total,
        "deep_card_count": deep_count,
        "deferred_evidence_count": deferred_count,
        "verified_candidate_method_count": verified_count,
    }


def _render_report(result: dict[str, Any]) -> str:
    stage1 = result["stage1"]
    publish_copy = result["publish_copy"]
    stage2 = result["stage2"]
    state = result["state"]
    return "\n".join(
        [
            f"# {result['account_name']}账号学习 v2.6 迁移报告",
            "",
            f"- workflow_id: `{result['workflow_id']}`",
            f"- 状态: `{result['status']}`",
            f"- 目标版本: `{state['schema_version']}`",
            f"- 权威学习计数: {state['deep_card_count']} / {state['source_total']}；证据延期 {state['deferred_evidence_count']}",
            f"- v2.6 统一卡证据: {state['v26_unified_source_count']}；旧卡兼容: {state['v26_legacy_compatible_source_count']}",
            "- 写入边界: 只更新候选学习工作流，不修改正式账号 Skill。",
            "",
            "## 阶段 1",
            "",
            f"- 统一证据源: {stage1['unified_source_count']} / {stage1['source_total']}",
            f"- 深层结构/表达观察新增: {stage1['deep_observation_backfilled']}",
            f"- 深层结构/表达观察保留: {stage1['deep_observation_preserved']}",
            f"- 旧证据兼容降级: {stage1['deep_observation_deferred']}",
            f"- 发布文案观察新增/应有: {stage1['publish_copy_backfilled']} / {stage1['publish_copy_expected']}",
            f"- 图文视觉观察新增/应有: {stage1['image_text_visual_backfilled']} / {stage1['image_text_visual_expected']}",
            "",
            "## 发布文案专项学习",
            "",
            f"- 逐条专项观察: {publish_copy['completed_source_count']} / {publish_copy['expected_source_count']}",
            f"- 证据延期: {publish_copy['deferred_source_count']}",
            f"- 统一卡: {publish_copy['unified_card_count']}；旧卡发布层兼容证据: {publish_copy['legacy_publish_evidence_count']}",
            "- 标题、正文或文案、话题及协同均保留证据坐标；缺失项显式记录，不补造。",
            "",
            "## 阶段 2 与阶段 6",
            "",
            f"- 生产机制分析新增: {stage2['production_analysis_backfilled']}",
            f"- 生产机制分析保留: {stage2['production_analysis_preserved']}",
            f"- 生产交接: `{result['handoff']['status']}`",
            f"- 工作流验证: `{result['validation'].get('ok')}`",
            "",
            "## 边界",
            "",
            "- 旧卡缺少统一十二段证据时保留兼容降级，不用空字段伪造深层观察。",
            "- 回填只使用现有候选卡、机制簇与已批准正式账号 Skill 候选副本。",
            "- 所有候选继续保持 formal_write=false、callable=false、user_review_required=true。",
            "",
        ]
    )


def upgrade_workflow(root: Path, workflow_id: str, *, apply: bool = False) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    base = workflow_root(root, workflow_id)
    state_before = _read_json(base / "PIPELINE_STATE.json")
    stage1, candidate_by_id = _upgrade_stage1_candidates(root, base, config, state_before, apply=apply)
    publish_copy = _upgrade_publish_copy_study(root, base, config, state_before, apply=apply)
    stage2 = _upgrade_clusters(base, candidate_by_id, apply=apply)
    handoff = _upgrade_handoff(base, apply=apply)
    state = _upgrade_state_and_manifest(root, base, config, stage1, publish_copy, stage2, apply=apply)
    if apply:
        validation = refresh_workflow(root, workflow_id)
    else:
        validation = {"ok": True, "status": "dry_run_not_validated"}
    result = {
        "ok": bool(validation.get("ok")),
        "status": "applied" if apply else "dry_run",
        "workflow_id": workflow_id,
        "account_name": state_before.get("account_name", ""),
        "stage1": stage1,
        "publish_copy": publish_copy,
        "stage2": stage2,
        "handoff": handoff,
        "state": state,
        "validation": validation,
        "formal_write_allowed": False,
    }
    if apply:
        json_path = base / "V26_MIGRATION_REPORT.json"
        md_path = base / "V26_MIGRATION_REPORT.md"
        _write_json(json_path, result)
        md_path.write_text(_render_report(result), encoding="utf-8")
        result["report"] = md_path.relative_to(root).as_posix()
    return result


def upgrade_workflows(
    root: Path,
    workflow_ids: list[str],
    *,
    apply: bool = False,
) -> dict[str, Any]:
    results = [upgrade_workflow(root, workflow_id, apply=apply) for workflow_id in workflow_ids]
    return {
        "ok": all(item.get("ok") for item in results),
        "status": "applied" if apply else "dry_run",
        "workflow_count": len(results),
        "failed": [item["workflow_id"] for item in results if not item.get("ok")],
        "results": results,
        "formal_write_allowed": False,
    }


def _workflow_ids(root: Path) -> list[str]:
    config = load_config(root)
    candidate_root = root.resolve() / Path(str(config.get("candidate_root") or "10_Knowledge/candidates/account_learning_workflows"))
    return sorted(path.parent.name for path in candidate_root.glob("*/PIPELINE_STATE.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade existing candidate account-learning workflows to v2.6.")
    parser.add_argument("--root", default=".")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--workflow-id", action="append")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--exclude-workflow-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    workflow_ids = _workflow_ids(root) if args.all else list(args.workflow_id or [])
    excluded = set(args.exclude_workflow_id)
    workflow_ids = [workflow_id for workflow_id in workflow_ids if workflow_id not in excluded]
    try:
        result = upgrade_workflows(root, workflow_ids, apply=args.apply)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
