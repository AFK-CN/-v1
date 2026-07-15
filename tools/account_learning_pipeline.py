from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tools.kb.schemas import now_iso


CONFIG_PATH = Path("00_System/shareable/config/account_learning_pipeline.json")
DEFAULT_CANDIDATE_ROOT = Path("10_Knowledge/candidates/account_learning_workflows")
LENS_FILES = (
    "positioning.jsonl",
    "topics.jsonl",
    "structures.jsonl",
    "expression.jsonl",
    "counterexamples.jsonl",
)
METHOD_SECTIONS = (
    "## R - 原始证据",
    "## I - 方法论解释",
    "## A1 - 已发生案例",
    "## A2 - 未来触发场景",
    "## E - 可执行步骤",
    "## B - 边界与反例",
)
RELATION_TYPES = {"depends_on", "contrasts_with", "composes_with"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"missing:{path.name}"]
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid_jsonl:{path.name}:{line_number}:{exc.msg}")
            continue
        if not isinstance(item, dict):
            errors.append(f"invalid_record:{path.name}:{line_number}")
            continue
        records.append(item)
    return records, errors


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._").lower()
    if not cleaned:
        raise ValueError("workflow_id or profile_id must contain an ASCII letter or number")
    return cleaned


def load_config(root: Path) -> dict[str, Any]:
    path = root.resolve() / CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Missing account learning pipeline config: {path}")
    return _read_json(path)


def workflow_root(root: Path, workflow_id: str) -> Path:
    config = load_config(root)
    candidate_root = Path(str(config.get("candidate_root") or DEFAULT_CANDIDATE_ROOT))
    return root.resolve() / candidate_root / _safe_id(workflow_id)


def state_path(root: Path, workflow_id: str) -> Path:
    return workflow_root(root, workflow_id) / "PIPELINE_STATE.json"


def _stage_ids(config: dict[str, Any]) -> list[str]:
    return [str(stage["id"]) for stage in config.get("stages", [])]


def init_workflow(
    root: Path,
    *,
    account_name: str,
    source_scope: str,
    media_branches: list[str],
    profile_id: str = "",
    workflow_id: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    if not account_name.strip() or not source_scope.strip():
        raise ValueError("account_name and source_scope are required")
    branches = sorted({branch.strip() for branch in media_branches if branch.strip()})
    if not branches:
        raise ValueError("at least one media branch is required")
    identity = workflow_id or profile_id
    if not identity:
        raise ValueError("workflow_id or profile_id is required")
    workflow_id = _safe_id(identity)
    config = load_config(root)
    target = workflow_root(root, workflow_id)
    if (target / "PIPELINE_STATE.json").exists():
        raise FileExistsError(f"workflow already exists: {workflow_id}")
    (target / "candidates").mkdir(parents=True, exist_ok=True)
    (target / "rejected").mkdir(parents=True, exist_ok=True)
    (target / "methods").mkdir(parents=True, exist_ok=True)
    stages = []
    for index, stage in enumerate(config["stages"]):
        stages.append(
            {
                "id": stage["id"],
                "name": stage["name"],
                "status": "in_progress" if index == 0 else "pending",
                "completed_at": "",
                "user_confirmed": False,
                "validation": {"ok": False, "errors": ["not_validated"]},
            }
        )
    state = {
        "schema_version": str(config.get("version") or "2.2"),
        "workflow_id": workflow_id,
        "account_name": account_name.strip(),
        "profile_id": profile_id.strip(),
        "source_scope": source_scope.strip(),
        "media_branches": branches,
        "method": config["method"],
        "stage1_observation_schema": str(config.get("stage1_deep_observation", {}).get("schema_id") or ""),
        "stage2_production_mechanism_schema": str(
            config.get("stage2_production_mechanism", {}).get("schema_id") or ""
        ),
        "stage6_production_handoff_schema": str(
            config.get("stage6_production_handoff", {}).get("schema_id") or ""
        ),
        "status": "in_progress",
        "current_stage": stages[0]["id"],
        "formal_write_allowed": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "stages": stages,
    }
    _write_json(target / "PIPELINE_STATE.json", state)
    (target / "WORKFLOW_PLAN.md").write_text(_render_plan(config, state), encoding="utf-8")
    return {"ok": True, "workflow_id": workflow_id, "workflow_dir": str(target.relative_to(root)), "state": state}


def _render_plan(config: dict[str, Any], state: dict[str, Any]) -> str:
    lines = [
        f"# {state['account_name']}账号专业学习计划",
        "",
        f"- workflow_id: `{state['workflow_id']}`",
        f"- 资料范围: {state['source_scope']}",
        f"- 媒介分支: {', '.join(state['media_branches'])}",
        f"- 方法: {config['method']}",
        "- 写入边界: 只写候选学习区，不直接写正式账号中心。",
        "",
        "## 七阶段",
        "",
    ]
    for index, stage in enumerate(config["stages"], 1):
        artifacts = "、".join(f"`{item}`" for item in stage["required_artifacts"])
        lines.extend([f"{index}. **{stage['name']}**：{stage['principle']}。", f"   产物：{artifacts}。"])
    lines.extend(
        [
            "",
            "## 确认门",
            "",
            "- 阶段 0 完成后确认整体账号理解，再进入五视角提取。",
            "- 阶段 2 完成后确认通过与淘汰名单，再构造方法单元。",
            "- 阶段 6 只交付候选和审核清单；正式入库继续走原有审核流程。",
            "",
        ]
    )
    return "\n".join(lines)


def load_state(root: Path, workflow_id: str) -> dict[str, Any]:
    path = state_path(root, workflow_id)
    if not path.exists():
        raise FileNotFoundError(f"Unknown workflow: {workflow_id}")
    return _read_json(path)


def _candidate_records(base: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for filename in LENS_FILES:
        items, item_errors = _read_jsonl(base / "candidates" / filename)
        errors.extend(item_errors)
        if not items:
            errors.append(f"empty_lens:{filename}")
        for item in items:
            item.setdefault("lens", filename.removesuffix(".jsonl"))
        records.extend(items)
    return records, errors


def _required_fields(record: dict[str, Any], fields: tuple[str, ...], prefix: str, errors: list[str]) -> None:
    record_id = str(record.get("id") or "unknown")
    for field in fields:
        value = record.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"{prefix}:{record_id}:missing_{field}")


def _required_keys(record: dict[str, Any], fields: tuple[str, ...], prefix: str, errors: list[str]) -> None:
    record_id = str(record.get("id") or "unknown")
    for field in fields:
        if field not in record or record.get(field) is None:
            errors.append(f"{prefix}:{record_id}:missing_{field}")


def _state_schema_enabled(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    state_field: str,
    config_section: str,
) -> bool:
    schema_id = str(config.get(config_section, {}).get("schema_id") or "")
    return bool(schema_id and state.get(state_field) == schema_id)


def _validate_deep_observation_candidate(
    item: dict[str, Any],
    config: dict[str, Any],
    errors: list[str],
) -> None:
    lens = str(item.get("type") or item.get("lens") or "")
    if lens not in {"structures", "expression"}:
        return
    contract = config.get("stage1_deep_observation", {})
    schema_id = str(contract.get("schema_id") or "")
    candidate_id = str(item.get("id") or "unknown")
    if item.get("observation_schema") != schema_id:
        errors.append(f"candidate:{candidate_id}:invalid_observation_schema")
    observation = item.get("observation")
    if not isinstance(observation, dict):
        errors.append(f"candidate:{candidate_id}:missing_observation")
        return
    fields_key = "structure_observation_fields" if lens == "structures" else "expression_observation_fields"
    required = tuple(str(field) for field in contract.get(fields_key, []))
    _required_keys(observation, required, f"candidate_observation:{candidate_id}", errors)
    if observation.get("status") != contract.get("candidate_status"):
        errors.append(f"candidate:{candidate_id}:invalid_observation_status")

    dimensions = observation.get("dimensions_considered")
    evidence_coordinates = observation.get("evidence_coordinates")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append(f"candidate:{candidate_id}:dimensions_considered_must_be_nonempty_list")
        dimensions = []
    if not isinstance(evidence_coordinates, list) or not evidence_coordinates:
        errors.append(f"candidate:{candidate_id}:evidence_coordinates_must_be_nonempty_list")

    observed_field = "observed_units" if lens == "structures" else "observed_signals"
    missing_field = "missing_or_uncertain_units" if lens == "structures" else "missing_or_uncertain_signals"
    label_field = "unit" if lens == "structures" else "signal"
    observed = observation.get(observed_field)
    missing = observation.get(missing_field)
    if not isinstance(observed, list):
        errors.append(f"candidate:{candidate_id}:{observed_field}_must_be_list")
        observed = []
    if not isinstance(missing, list):
        errors.append(f"candidate:{candidate_id}:{missing_field}_must_be_list")
        missing = []

    labels: list[str] = []
    for index, evidence in enumerate(observed):
        if not isinstance(evidence, dict):
            errors.append(f"candidate:{candidate_id}:{observed_field}_{index}_must_be_object")
            continue
        _required_fields(
            evidence,
            (label_field, "evidence", "source_coordinate"),
            f"candidate_observation_evidence:{candidate_id}",
            errors,
        )
        labels.append(str(evidence.get(label_field) or ""))
    unresolved = set(map(str, dimensions)) - set(labels) - set(map(str, missing))
    if unresolved:
        errors.append(f"candidate:{candidate_id}:unresolved_observation_dimensions:{','.join(sorted(unresolved))}")
    if lens == "structures":
        unit_order = observation.get("unit_order")
        if not isinstance(unit_order, list):
            errors.append(f"candidate:{candidate_id}:unit_order_must_be_list")
        elif set(map(str, unit_order)) != set(labels):
            errors.append(f"candidate:{candidate_id}:unit_order_must_cover_observed_units")
    fingerprint_field = "structure_fingerprint" if lens == "structures" else "expression_fingerprint"
    if not str(observation.get(fingerprint_field) or "").strip():
        errors.append(f"candidate:{candidate_id}:missing_{fingerprint_field}")


def _validate_real_acceptance(base: Path, config: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    acceptance = config.get("real_acceptance", {})
    summary_name = str(acceptance.get("summary_artifact") or "REAL_ACCEPTANCE_SUMMARY.json")
    summary_path = base / summary_name
    if not list(base.glob("REAL_ACCEPTANCE_REPORT_*.md")):
        errors.append("real_acceptance:missing_report")
    if not summary_path.exists():
        errors.append(f"real_acceptance:missing_summary:{summary_name}")
        return {}

    summary = _read_json(summary_path)
    _required_fields(
        summary,
        (
            "schema_version",
            "status",
            "report_file",
            "sample_method",
            "sampled_source_ids",
            "strata",
            "expanded_audit",
            "semantic_consistency",
            "overview_scope",
            "commercial_learning",
            "formal_write",
            "callable",
        ),
        "real_acceptance",
        errors,
    )
    if summary.get("status") != "passed":
        errors.append("real_acceptance:status_not_passed")
    if "severe_issues" not in summary:
        errors.append("real_acceptance:missing_severe_issues")
    if summary.get("formal_write") is not False or summary.get("callable") is not False:
        errors.append("real_acceptance:candidate_boundary_violation")
    report_file = str(summary.get("report_file") or "")
    if not report_file or not (base / report_file).is_file():
        errors.append("real_acceptance:report_file_not_found")
    if not summary.get("sample_method") or not summary.get("sampled_source_ids"):
        errors.append("real_acceptance:sample_not_reproducible")

    strata = summary.get("strata", {})
    if not isinstance(strata, dict):
        errors.append("real_acceptance:invalid_strata")
        strata = {}
    allowed_statuses = set(acceptance.get("allowed_stratum_statuses", []))
    for stratum in acceptance.get("required_strata", []):
        record = strata.get(stratum, {})
        status = record.get("status") if isinstance(record, dict) else None
        if status not in allowed_statuses:
            errors.append(f"real_acceptance:stratum_not_passed:{stratum}")
        if status == "not_applicable" and not record.get("reason"):
            errors.append(f"real_acceptance:stratum_missing_na_reason:{stratum}")

    severe_issues = summary.get("severe_issues", [])
    if not isinstance(severe_issues, list):
        errors.append("real_acceptance:invalid_severe_issues")
        severe_issues = []
    expanded = summary.get("expanded_audit", {})
    if severe_issues and (not isinstance(expanded, dict) or expanded.get("completed") is not True):
        errors.append("real_acceptance:severe_issue_without_expanded_audit")
    semantic = summary.get("semantic_consistency", {})
    if not isinstance(semantic, dict) or semantic.get("passed") is not True:
        errors.append("real_acceptance:semantic_consistency_failed")
    overview_scope = summary.get("overview_scope", {})
    if not isinstance(overview_scope, dict) or overview_scope.get("consistent") is not True:
        errors.append("real_acceptance:overview_scope_inconsistent")

    commercial = summary.get("commercial_learning", {})
    if not isinstance(commercial, dict):
        errors.append("real_acceptance:invalid_commercial_learning")
        commercial = {}
    for axis in ("product_ads", "platform_projects"):
        record = commercial.get(axis, {})
        if not isinstance(record, dict):
            errors.append(f"real_acceptance:{axis}:invalid")
            continue
        total = record.get("total")
        audited = record.get("audited")
        if not isinstance(total, int) or total < 0 or not isinstance(audited, int) or audited < 0:
            errors.append(f"real_acceptance:{axis}:invalid_counts")
            continue
        if audited != total:
            errors.append(f"real_acceptance:{axis}:audit_incomplete:{audited}/{total}")
        artifact = str(record.get("artifact") or "")
        if total and (not artifact or not (base / artifact).is_file()):
            errors.append(f"real_acceptance:{axis}:artifact_not_found")
    return summary


def validate_stage(root: Path, workflow_id: str, stage_id: str) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    if stage_id not in _stage_ids(config):
        raise ValueError(f"Unknown stage: {stage_id}")
    base = workflow_root(root, workflow_id)
    workflow_state = _read_json(base / "PIPELINE_STATE.json") if (base / "PIPELINE_STATE.json").exists() else {}
    errors: list[str] = []
    metrics: dict[str, Any] = {}
    if stage_id == "stage0_account_overview":
        overview_md = base / "ACCOUNT_OVERVIEW.md"
        overview_json = base / "ACCOUNT_OVERVIEW.json"
        if not overview_md.exists():
            errors.append("missing:ACCOUNT_OVERVIEW.md")
        else:
            text = overview_md.read_text(encoding="utf-8")
            required = ("## 1. 账号结构", "## 2. 关键术语与定位", "## 3. 批判与偏差", "## 4. 学习应用潜力")
            errors.extend(f"overview_missing_section:{section}" for section in required if section not in text)
        if not overview_json.exists():
            errors.append("missing:ACCOUNT_OVERVIEW.json")
        else:
            overview = _read_json(overview_json)
            _required_fields(overview, ("one_line_theme", "content_pillars", "terminology", "limitations", "evidence_refs"), "overview", errors)
            if len(overview.get("content_pillars", [])) not in range(3, 8):
                errors.append("overview_content_pillars_must_be_3_to_7")
            if len(overview.get("limitations", [])) < 3:
                errors.append("overview_requires_3_limitations")
            if len(overview.get("evidence_refs", [])) < 2:
                errors.append("overview_requires_2_evidence_refs")
    elif stage_id == "stage1_parallel_extraction":
        candidates, candidate_errors = _candidate_records(base)
        errors.extend(candidate_errors)
        ids: list[str] = []
        for item in candidates:
            _required_fields(item, ("id", "title", "type", "source_refs", "summary", "tags"), "candidate", errors)
            if _state_schema_enabled(
                workflow_state,
                config,
                state_field="stage1_observation_schema",
                config_section="stage1_deep_observation",
            ):
                _validate_deep_observation_candidate(item, config, errors)
            ids.append(str(item.get("id", "")))
        if len(ids) != len(set(ids)):
            errors.append("candidate_ids_not_unique")
        acceptance_summary = _validate_real_acceptance(base, config, errors)
        metrics["candidate_count"] = len(candidates)
        metrics["real_acceptance_status"] = acceptance_summary.get("status", "missing")
    elif stage_id == "stage2_triple_verification":
        candidates, candidate_errors = _candidate_records(base)
        errors.extend(candidate_errors)
        candidate_ids = {str(item.get("id")) for item in candidates if item.get("id")}
        candidate_lens_by_id = {
            str(item.get("id")): str(item.get("type") or item.get("lens") or "")
            for item in candidates
            if item.get("id")
        }
        clusters, cluster_errors = _read_jsonl(base / "candidate_clusters.jsonl")
        errors.extend(cluster_errors)
        cluster_ids: list[str] = []
        assigned_candidate_ids: list[str] = []
        cluster_by_id: dict[str, dict[str, Any]] = {}
        allowed_cluster_types = set(config.get("candidate_consolidation", {}).get("cluster_types", []))
        allowed_roles = set(config.get("candidate_consolidation", {}).get("candidate_roles", []))
        for cluster in clusters:
            _required_fields(
                cluster,
                ("id", "title", "cluster_type", "core_mechanism", "candidate_ids", "source_refs", "lens_roles"),
                "cluster",
                errors,
            )
            cluster_id = str(cluster.get("id") or "")
            cluster_ids.append(cluster_id)
            cluster_by_id[cluster_id] = cluster
            cluster_type = str(cluster.get("cluster_type") or "")
            if cluster_type not in allowed_cluster_types:
                errors.append(f"cluster:{cluster_id}:invalid_cluster_type:{cluster_type}")
            members = [str(item) for item in cluster.get("candidate_ids", [])]
            assigned_candidate_ids.extend(members)
            roles = cluster.get("lens_roles", {})
            if not isinstance(roles, dict):
                errors.append(f"cluster:{cluster_id}:invalid_lens_roles")
                roles = {}
            unknown_roles = set(roles) - allowed_roles
            if unknown_roles:
                errors.append(f"cluster:{cluster_id}:invalid_roles:{','.join(sorted(unknown_roles))}")
            role_members = [str(item) for values in roles.values() if isinstance(values, list) for item in values]
            if set(role_members) != set(members) or len(role_members) != len(set(role_members)):
                errors.append(f"cluster:{cluster_id}:role_assignment_mismatch")
            if cluster_type == "method_candidate" and not roles.get("method_core"):
                errors.append(f"cluster:{cluster_id}:method_candidate_requires_core")
            if cluster_type == "method_candidate" and _state_schema_enabled(
                workflow_state,
                config,
                state_field="stage2_production_mechanism_schema",
                config_section="stage2_production_mechanism",
            ):
                mechanism_contract = config.get("stage2_production_mechanism", {})
                mechanism_kind = str(cluster.get("mechanism_kind") or "")
                allowed_mechanism_kinds = set(map(str, mechanism_contract.get("mechanism_kinds", [])))
                if mechanism_kind not in allowed_mechanism_kinds:
                    errors.append(f"cluster:{cluster_id}:invalid_mechanism_kind:{mechanism_kind}")
                member_lenses = {candidate_lens_by_id.get(member, "") for member in members}
                production_lenses = set(map(str, mechanism_contract.get("required_when_method_candidate_contains", [])))
                if member_lenses & production_lenses:
                    production_analysis = cluster.get("production_analysis")
                    if not isinstance(production_analysis, dict):
                        errors.append(f"cluster:{cluster_id}:missing_production_analysis")
                    else:
                        _required_fields(
                            production_analysis,
                            tuple(map(str, mechanism_contract.get("required_analysis_fields", []))),
                            f"cluster_production_analysis:{cluster_id}",
                            errors,
                        )
        if len(cluster_ids) != len(set(cluster_ids)):
            errors.append("cluster_ids_not_unique")
        if len(assigned_candidate_ids) != len(set(assigned_candidate_ids)):
            errors.append("candidate_assigned_to_multiple_clusters")
        if set(assigned_candidate_ids) != candidate_ids:
            missing = sorted(candidate_ids - set(assigned_candidate_ids))
            unknown = sorted(set(assigned_candidate_ids) - candidate_ids)
            if missing:
                errors.append(f"cluster_missing_candidates:{','.join(missing)}")
            if unknown:
                errors.append(f"cluster_unknown_candidates:{','.join(unknown)}")
        verified, verified_errors = _read_jsonl(base / "verified.jsonl")
        rejected, rejected_errors = _read_jsonl(base / "rejected.jsonl")
        errors.extend(verified_errors + rejected_errors)
        decision_ids: list[str] = []
        for item in verified:
            _required_fields(item, ("id", "title", "triple_verification"), "verified", errors)
            verified_id = str(item.get("id", ""))
            decision_ids.append(verified_id)
            if cluster_by_id.get(verified_id, {}).get("cluster_type") != "method_candidate":
                errors.append(f"verified:{verified_id}:cluster_not_method_candidate")
            checks = item.get("triple_verification", {})
            for check in ("v1_cross_context", "v2_predictive_usefulness", "v3_account_exclusivity"):
                result = checks.get(check, {}) if isinstance(checks, dict) else {}
                if result.get("passed") is not True or not result.get("reason"):
                    errors.append(f"verified:{item.get('id', 'unknown')}:{check}_not_proven")
            v1_refs = checks.get("v1_cross_context", {}).get("evidence_refs", []) if isinstance(checks, dict) else []
            if len(set(map(str, v1_refs))) < int(config["verification"]["v1_min_independent_sources"]):
                errors.append(f"verified:{item.get('id', 'unknown')}:v1_requires_independent_sources")
            v1_contexts = checks.get("v1_cross_context", {}).get("relation_or_scene_types", []) if isinstance(checks, dict) else []
            if len(set(map(str, v1_contexts))) < int(config["verification"]["v1_min_relation_or_scene_types"]):
                errors.append(f"verified:{item.get('id', 'unknown')}:v1_requires_relation_or_scene_types")
        for item in rejected:
            _required_fields(item, ("id", "title", "failed_checks", "reason", "disposition"), "rejected", errors)
            decision_ids.append(str(item.get("id", "")))
        if len(decision_ids) != len(set(decision_ids)):
            errors.append("verification_decision_ids_not_unique")
        cluster_id_set = set(cluster_ids)
        if set(decision_ids) != cluster_id_set:
            missing = sorted(cluster_id_set - set(decision_ids))
            unknown = sorted(set(decision_ids) - cluster_id_set)
            if missing:
                errors.append(f"verification_missing_decisions:{','.join(missing)}")
            if unknown:
                errors.append(f"verification_unknown_decisions:{','.join(unknown)}")
        if len(verified) < int(config["verification"]["minimum_verified_methods"]):
            errors.append("verification_requires_at_least_one_method")
        metrics.update(
            {
                "candidate_count": len(candidates),
                "cluster_count": len(clusters),
                "verified_count": len(verified),
                "rejected_count": len(rejected),
            }
        )
    elif stage_id == "stage3_ria_construction":
        verified, read_errors = _read_jsonl(base / "verified.jsonl")
        errors.extend(read_errors)
        verified_ids = {str(item.get("id")) for item in verified if item.get("id")}
        method_ids: set[str] = set()
        for method_dir in sorted((base / "methods").iterdir()) if (base / "methods").exists() else []:
            if not method_dir.is_dir():
                continue
            method_md = method_dir / "METHOD.md"
            method_json = method_dir / "method.json"
            if not method_md.exists() or not method_json.exists():
                errors.append(f"method:{method_dir.name}:missing_method_artifact")
                continue
            payload = _read_json(method_json)
            method_id = str(payload.get("id") or method_dir.name)
            method_ids.add(method_id)
            _required_fields(
                payload,
                (
                    "id",
                    "schema_version",
                    "version",
                    "status",
                    "callable",
                    "account_scope",
                    "title",
                    "trigger_signals",
                    "trigger_model",
                    "do_not_use",
                    "execution_steps",
                    "source_refs",
                ),
                "method",
                errors,
            )
            if payload.get("status") != "verified_candidate" or payload.get("callable") is not False:
                errors.append(f"method:{method_id}:candidate_must_not_be_callable")
            trigger_model = payload.get("trigger_model", {})
            if isinstance(trigger_model, dict):
                _required_fields(
                    trigger_model,
                    ("mechanism", "applicable_relations", "transferable_scenes", "do_not_trigger_on"),
                    f"method_trigger:{method_id}",
                    errors,
                )
            else:
                errors.append(f"method_trigger:{method_id}:invalid_trigger_model")
            text = method_md.read_text(encoding="utf-8")
            errors.extend(f"method:{method_id}:missing_section:{section}" for section in METHOD_SECTIONS if section not in text)
            if len(set(map(str, payload.get("source_refs", [])))) < 2:
                errors.append(f"method:{method_id}:requires_2_source_refs")
        if method_ids != verified_ids:
            errors.append("method_ids_must_match_verified_ids")
        metrics["method_count"] = len(method_ids)
    elif stage_id == "stage4_method_linking":
        verified, read_errors = _read_jsonl(base / "verified.jsonl")
        errors.extend(read_errors)
        verified_ids = {str(item.get("id")) for item in verified if item.get("id")}
        index_path = base / "METHOD_INDEX.json"
        if not index_path.exists():
            errors.append("missing:METHOD_INDEX.json")
        else:
            index = _read_json(index_path)
            methods = index.get("methods", [])
            indexed_ids = {str(item.get("id")) for item in methods if isinstance(item, dict) and item.get("id")}
            if indexed_ids != verified_ids:
                errors.append("method_index_ids_must_match_verified_ids")
            for relation in index.get("relations", []):
                source = str(relation.get("source", ""))
                target = str(relation.get("target", ""))
                relation_type = str(relation.get("type", ""))
                if source not in verified_ids or target not in verified_ids or source == target:
                    errors.append("method_index_invalid_relation_endpoint")
                if relation_type not in RELATION_TYPES:
                    errors.append(f"method_index_invalid_relation_type:{relation_type}")
        if not (base / "GLOSSARY.md").exists():
            errors.append("missing:GLOSSARY.md")
    elif stage_id == "stage5_pressure_test":
        verified, read_errors = _read_jsonl(base / "verified.jsonl")
        errors.extend(read_errors)
        method_ids = {str(item.get("id")) for item in verified if item.get("id")}
        required_types = set(config["verification"]["required_test_types"])
        for method_id in sorted(method_ids):
            method_dir = base / "methods" / method_id
            prompts_path = method_dir / "test-prompts.json"
            results_path = method_dir / "test-results.json"
            if not prompts_path.exists() or not results_path.exists():
                errors.append(f"pressure_test:{method_id}:missing_artifact")
                continue
            prompts = _read_json(prompts_path)
            cases = prompts.get("test_cases", [])
            case_ids = [str(case.get("id") or "") for case in cases if isinstance(case, dict)]
            if not case_ids or len(case_ids) != len(set(case_ids)):
                errors.append(f"pressure_test:{method_id}:case_ids_missing_or_duplicate")
            case_types = {str(case.get("type")) for case in cases if isinstance(case, dict)}
            if not required_types.issubset(case_types):
                errors.append(f"pressure_test:{method_id}:missing_test_types")
            required_decoys = set(config["verification"].get("required_negative_decoy_kinds", []))
            present_decoys = {
                str(case.get("decoy_kind"))
                for case in cases
                if isinstance(case, dict) and case.get("type") == "should_not_trigger"
            }
            if not required_decoys.issubset(present_decoys):
                errors.append(f"pressure_test:{method_id}:missing_lexical_decoy")
            for case in cases:
                if not isinstance(case, dict) or case.get("type") != "cross_scene_transfer":
                    continue
                if (
                    not case.get("source_scene")
                    or not case.get("target_scene")
                    or case.get("source_scene") == case.get("target_scene")
                    or case.get("mechanism_preserved") is not True
                ):
                    errors.append(f"pressure_test:{method_id}:invalid_cross_scene_transfer")
            if len(method_ids) > 1 and not any(
                case.get("type") == "should_not_trigger" and case.get("sibling_method_id") in method_ids - {method_id}
                for case in cases
                if isinstance(case, dict)
            ):
                errors.append(f"pressure_test:{method_id}:missing_sibling_decoy")
            results = _read_json(results_path)
            _required_fields(
                results,
                ("executor", "executed_at", "prompt_set_sha256", "case_results"),
                f"pressure_test:{method_id}",
                errors,
            )
            if results.get("prompt_set_sha256") != _sha256_file(prompts_path):
                errors.append(f"pressure_test:{method_id}:prompt_hash_mismatch")
            case_results = results.get("case_results", [])
            result_ids = [str(item.get("id") or "") for item in case_results if isinstance(item, dict)]
            if set(result_ids) != set(case_ids) or len(result_ids) != len(set(result_ids)):
                errors.append(f"pressure_test:{method_id}:case_results_mismatch")
            for item in case_results:
                if not isinstance(item, dict):
                    errors.append(f"pressure_test:{method_id}:invalid_case_result")
                    continue
                _required_fields(item, ("id", "passed", "actual_decision", "evidence"), "case_result", errors)
                if not isinstance(item.get("passed"), bool):
                    errors.append(f"pressure_test:{method_id}:case_passed_not_boolean")
            computed_passed = sum(item.get("passed") is True for item in case_results if isinstance(item, dict))
            computed_failed = len(case_results) - computed_passed
            computed_rate = computed_passed / len(case_results) if case_results else 0.0
            if int(results.get("total", -1)) != len(cases) or int(results.get("total", -1)) != len(case_results):
                errors.append(f"pressure_test:{method_id}:result_count_mismatch")
            if int(results.get("passed", -1)) != computed_passed or int(results.get("failed", -1)) != computed_failed:
                errors.append(f"pressure_test:{method_id}:aggregate_result_mismatch")
            if abs(float(results.get("pass_rate", -1)) - computed_rate) > 1e-9:
                errors.append(f"pressure_test:{method_id}:pass_rate_mismatch")
            if computed_rate < float(config["verification"]["pressure_test_min_pass_rate"]):
                errors.append(f"pressure_test:{method_id}:pass_rate_below_gate")
            if computed_failed != 0:
                errors.append(f"pressure_test:{method_id}:has_failed_cases")
        metrics["method_count"] = len(method_ids)
    else:
        digest = base / "LEARNING_DIGEST.md"
        manifest_path = base / "promotion_manifest.json"
        verified, read_errors = _read_jsonl(base / "verified.jsonl")
        errors.extend(read_errors)
        verified_ids = {str(item.get("id")) for item in verified if item.get("id")}
        if not digest.exists() or len(digest.read_text(encoding="utf-8").strip()) < 80:
            errors.append("learning_digest_missing_or_too_short")
        if not manifest_path.exists():
            errors.append("missing:promotion_manifest.json")
        else:
            manifest = _read_json(manifest_path)
            promoted_ids = {str(item) for item in manifest.get("method_ids", [])}
            if promoted_ids != verified_ids:
                errors.append("promotion_manifest_ids_must_match_verified_ids")
            if manifest.get("status") != "ready_for_review":
                errors.append("promotion_manifest_status_must_be_ready_for_review")
            if (
                manifest.get("formal_write") is not False
                or manifest.get("callable") is not False
                or manifest.get("user_review_required") is not True
            ):
                errors.append("promotion_manifest_must_remain_candidate_only")
            if str(manifest.get("schema_version") or "") == "2.2":
                state = _read_json(base / "PIPELINE_STATE.json")
                consistency_fields = (
                    "deep_card_count",
                    "deferred_evidence_count",
                    "verified_candidate_method_count",
                )
                for field in consistency_fields:
                    if field not in manifest:
                        errors.append(f"promotion_manifest_missing_accounting:{field}")
                    elif field in state and manifest.get(field) != state.get(field):
                        errors.append(f"promotion_manifest_accounting_mismatch:{field}")
                if "source_total" not in manifest:
                    errors.append("promotion_manifest_missing_accounting:source_total")
                elif (
                    isinstance(manifest.get("deep_card_count"), int)
                    and isinstance(manifest.get("deferred_evidence_count"), int)
                    and manifest["source_total"]
                    != manifest["deep_card_count"] + manifest["deferred_evidence_count"]
                ):
                    errors.append("promotion_manifest_accounting_mismatch:source_total")
        if _state_schema_enabled(
            workflow_state,
            config,
            state_field="stage6_production_handoff_schema",
            config_section="stage6_production_handoff",
        ):
            handoff_path = base / "ACCOUNT_PRODUCTION_HANDOFF.json"
            if not handoff_path.exists():
                errors.append("missing:ACCOUNT_PRODUCTION_HANDOFF.json")
            else:
                handoff = _read_json(handoff_path)
                handoff_contract = config.get("stage6_production_handoff", {})
                _required_fields(
                    handoff,
                    (
                        "schema_version",
                        "status",
                        "source_method_ids",
                        "coverage",
                        "formal_write",
                        "callable",
                        "user_review_required",
                    ),
                    "production_handoff",
                    errors,
                )
                if handoff.get("schema_version") != handoff_contract.get("schema_id"):
                    errors.append("production_handoff_invalid_schema")
                if handoff.get("status") != "ready_for_review":
                    errors.append("production_handoff_status_must_be_ready_for_review")
                if (
                    handoff.get("formal_write") is not False
                    or handoff.get("callable") is not False
                    or handoff.get("user_review_required") is not True
                ):
                    errors.append("production_handoff_must_remain_candidate_only")
                if {str(item) for item in handoff.get("source_method_ids", [])} != verified_ids:
                    errors.append("production_handoff_method_ids_must_match_verified_ids")

                coverage = handoff.get("coverage")
                if not isinstance(coverage, dict):
                    errors.append("production_handoff_invalid_coverage")
                    coverage = {}
                allowed_coverage = set(map(str, handoff_contract.get("coverage_statuses", [])))
                coverage_fields = tuple(map(str, handoff_contract.get("coverage_fields", [])))
                for field in coverage_fields:
                    status = str(coverage.get(field) or "")
                    if status not in allowed_coverage:
                        errors.append(f"production_handoff_invalid_coverage:{field}:{status}")

                candidate_fields = tuple(map(str, handoff_contract.get("candidate_fields", [])))
                _required_keys(handoff, candidate_fields, "production_handoff", errors)
                coverage_to_candidates = {
                    "structures": "structure_library_candidates",
                    "expression": "expression_fingerprint_candidates",
                    "anti_ai": "anti_ai_rule_candidates",
                    "production_templates": "production_template_mappings",
                    "acceptance": "acceptance_checks",
                }
                for coverage_field, candidate_field in coverage_to_candidates.items():
                    values = handoff.get(candidate_field)
                    if not isinstance(values, list):
                        errors.append(f"production_handoff:{candidate_field}_must_be_list")
                    elif coverage.get(coverage_field) == "verified" and not values:
                        errors.append(f"production_handoff:{coverage_field}_verified_but_empty")
    return {"ok": not errors, "workflow_id": _safe_id(workflow_id), "stage_id": stage_id, "errors": errors, "metrics": metrics}


def complete_stage(root: Path, workflow_id: str, stage_id: str, *, user_confirmed: bool = False) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    stage_ids = _stage_ids(config)
    if stage_id not in stage_ids:
        raise ValueError(f"Unknown stage: {stage_id}")
    state = load_state(root, workflow_id)
    index = stage_ids.index(stage_id)
    if index and state["stages"][index - 1]["status"] != "completed":
        raise ValueError(f"previous stage is not complete: {stage_ids[index - 1]}")
    if state["stages"][index]["status"] == "completed":
        return {"ok": True, "already_completed": True, "state": state}
    validation = validate_stage(root, workflow_id, stage_id)
    if not validation["ok"]:
        return {"ok": False, "error": "stage_validation_failed", "validation": validation, "state": state}
    if stage_id in set(config.get("confirmation_gates", [])) and not user_confirmed:
        return {"ok": False, "error": "user_confirmation_required", "validation": validation, "state": state}
    now = now_iso()
    state["stages"][index].update(
        {"status": "completed", "completed_at": now, "user_confirmed": bool(user_confirmed), "validation": validation}
    )
    if index + 1 < len(stage_ids):
        state["stages"][index + 1]["status"] = "in_progress"
        state["current_stage"] = stage_ids[index + 1]
    else:
        state["current_stage"] = "completed"
        state["status"] = "completed"
    state["updated_at"] = now
    _write_json(state_path(root, workflow_id), state)
    return {"ok": True, "completed_stage": stage_id, "next_stage": state["current_stage"], "state": state}


def workflow_status(root: Path, workflow_id: str) -> dict[str, Any]:
    state = load_state(root, workflow_id)
    validations = {stage["id"]: validate_stage(root, workflow_id, stage["id"]) for stage in state["stages"]}
    return {
        "ok": True,
        "workflow_id": state["workflow_id"],
        "account_name": state["account_name"],
        "status": state["status"],
        "current_stage": state["current_stage"],
        "formal_write_allowed": False,
        "stages": state["stages"],
        "validations": validations,
    }


def validate_workflow(root: Path, workflow_id: str) -> dict[str, Any]:
    state = load_state(root, workflow_id)
    validations = [validate_stage(root, workflow_id, stage["id"]) for stage in state["stages"]]
    completed_invalid = [item["stage_id"] for item in validations if not item["ok"] and next(s for s in state["stages"] if s["id"] == item["stage_id"])["status"] == "completed"]
    return {
        "ok": not completed_invalid,
        "workflow_id": state["workflow_id"],
        "completed_stage_failures": completed_invalid,
        "validations": validations,
        "formal_write_allowed": False,
    }


def refresh_workflow(root: Path, workflow_id: str, *, source_scope: str = "") -> dict[str, Any]:
    """Refresh stored validation evidence after a candidate-only workflow is rebuilt."""

    root = root.resolve()
    config = load_config(root)
    state = load_state(root, workflow_id)
    state["schema_version"] = str(config.get("version") or "2.2")
    state["method"] = config["method"]
    if source_scope.strip():
        state["source_scope"] = source_scope.strip()
    validations: list[dict[str, Any]] = []
    invalid_stages: list[str] = []
    for stage in state["stages"]:
        validation = validate_stage(root, workflow_id, stage["id"])
        stage["validation"] = validation
        validations.append(validation)
        if stage.get("status") == "completed" and not validation["ok"]:
            invalid_stages.append(stage["id"])
    state["updated_at"] = now_iso()
    _write_json(state_path(root, workflow_id), state)
    (workflow_root(root, workflow_id) / "WORKFLOW_PLAN.md").write_text(
        _render_plan(config, state), encoding="utf-8"
    )
    return {
        "ok": not invalid_stages,
        "workflow_id": state["workflow_id"],
        "source_scope": state["source_scope"],
        "completed_stage_failures": invalid_stages,
        "validations": validations,
        "formal_write_allowed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Professional seven-stage account learning pipeline")
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--account-name", required=True)
    init_parser.add_argument("--source-scope", required=True)
    init_parser.add_argument("--media-branch", action="append", required=True)
    init_parser.add_argument("--profile-id", default="")
    init_parser.add_argument("--workflow-id", default="")
    for command in ("status", "validate"):
        item = subparsers.add_parser(command)
        item.add_argument("--workflow-id", required=True)
    refresh = subparsers.add_parser("refresh")
    refresh.add_argument("--workflow-id", required=True)
    refresh.add_argument("--source-scope", default="")
    complete = subparsers.add_parser("complete-stage")
    complete.add_argument("--workflow-id", required=True)
    complete.add_argument("--stage", required=True)
    complete.add_argument("--user-confirmed", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = Path(args.root)
    try:
        if args.command == "init":
            result = init_workflow(
                root,
                account_name=args.account_name,
                source_scope=args.source_scope,
                media_branches=args.media_branch,
                profile_id=args.profile_id,
                workflow_id=args.workflow_id,
            )
        elif args.command == "status":
            result = workflow_status(root, args.workflow_id)
        elif args.command == "validate":
            result = validate_workflow(root, args.workflow_id)
        elif args.command == "refresh":
            result = refresh_workflow(root, args.workflow_id, source_scope=args.source_scope)
        else:
            result = complete_stage(root, args.workflow_id, args.stage, user_confirmed=args.user_confirmed)
    except (FileNotFoundError, FileExistsError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
