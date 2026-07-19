from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from tools.kb.expression_assets import valid_coordinate, validate_expression_asset_file
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


def _account_scope_id(profile_id: str, workflow_id: str) -> str:
    if profile_id.strip():
        try:
            return _safe_id(profile_id)
        except ValueError:
            pass
    return _safe_id(workflow_id)


def _candidate_resource_allowed(path: Path) -> bool:
    return (
        path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
        and path.name != ".DS_Store"
    )


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
    (target / "expression_assets").mkdir(parents=True, exist_ok=True)
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
        "schema_version": str(config.get("version") or "2.6"),
        "workflow_id": workflow_id,
        "account_name": account_name.strip(),
        "account_id": _account_scope_id(profile_id, workflow_id),
        "profile_id": profile_id.strip(),
        "source_scope": source_scope.strip(),
        "media_branches": branches,
        "method": config["method"],
        "stage1_observation_schema": str(config.get("stage1_deep_observation", {}).get("schema_id") or ""),
        "publish_copy_observation_schema": str(
            config.get("stage1_deep_observation", {}).get("publish_copy_schema_id") or ""
        ),
        "publish_copy_study_schema": str(
            config.get("stage1_deep_observation", {}).get("publish_copy_study_schema_id") or ""
        ),
        "stage1_visual_reference_candidate_schema": str(
            config.get("stage1_deep_observation", {}).get(
                "production_reference_candidate_schema_id"
            )
            or ""
        ),
        "stage2_production_mechanism_schema": str(
            config.get("stage2_production_mechanism", {}).get("schema_id") or ""
        ),
        "stage6_production_handoff_schema": str(
            config.get("stage6_production_handoff", {}).get("schema_id") or ""
        ),
        "stage6_account_skill_schema": str(
            config.get("stage6_account_skill_package", {}).get("schema_id") or ""
        ),
        "stage6_upgrade_compatibility_schema": str(
            config.get("stage6_upgrade_compatibility", {}).get("schema_id") or ""
        ),
        "stage6_visual_reference_schema": str(
            config.get("stage6_visual_reference_package", {}).get("schema_id") or ""
        ),
        "expression_asset_schema": str(
            config.get("expression_asset_learning", {}).get("schema_id") or ""
        ),
        "expression_asset_contract_version": str(
            config.get("expression_asset_learning", {}).get("contract_version") or ""
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


def _validate_expression_asset_stage(
    root: Path,
    base: Path,
    workflow_state: dict[str, Any],
    config: dict[str, Any],
    stage_id: str,
    errors: list[str],
    metrics: dict[str, Any],
) -> None:
    if not _state_schema_enabled(
        workflow_state,
        config,
        state_field="expression_asset_schema",
        config_section="expression_asset_learning",
    ):
        return
    lane = config.get("expression_asset_learning", {})
    asset_root = base / str(lane.get("root") or "expression_assets")
    stage_contract = lane.get("stages", {}).get(stage_id, {})
    for relative in stage_contract.get("required_files", []):
        if not (asset_root / str(relative)).is_file():
            errors.append(f"expression_assets:missing:{relative}")
    expected_account_id = str(workflow_state.get("account_id") or workflow_state.get("profile_id") or workflow_state.get("workflow_id") or "")
    expected_workflow_id = str(workflow_state.get("workflow_id") or "")

    if stage_id == "stage1_parallel_extraction":
        audit_path = asset_root / "audit_report.json"
        if audit_path.is_file():
            audit = _read_json(audit_path)
            _required_fields(
                audit,
                ("schema_version", "status", "account_id", "source_count", "surface_coverage", "extraction_started"),
                "expression_asset_audit",
                errors,
            )
            if audit.get("schema_version") != "expression_asset_audit_v1" or audit.get("status") != "completed":
                errors.append("expression_assets:audit_status_invalid")
            if audit.get("account_id") != expected_account_id:
                errors.append("expression_assets:audit_account_mismatch")
            if audit.get("extraction_started") is not False:
                errors.append("expression_assets:audit_must_precede_extraction")
            if not isinstance(audit.get("source_count"), int) or int(audit.get("source_count", 0)) < 1:
                errors.append("expression_assets:audit_source_count_invalid")
            coverage = audit.get("surface_coverage")
            if not isinstance(coverage, dict) or not coverage:
                errors.append("expression_assets:audit_surface_coverage_missing")
        sample_path = asset_root / "expression_assets.sample.jsonl"
        if sample_path.is_file():
            validation = validate_expression_asset_file(
                root,
                sample_path,
                expected_account_id=expected_account_id,
                expected_workflow_id=expected_workflow_id,
            )
            if not validation.get("ok"):
                errors.extend(f"expression_assets:sample:{item}" for item in validation.get("errors", []))
            metrics["expression_asset_sample_count"] = int(validation.get("record_count", 0) or 0)

    elif stage_id == "stage2_triple_verification":
        sample_path = asset_root / "expression_assets.sample.jsonl"
        retrieval_path = asset_root / "retrieval_validation.json"
        acceptance_path = asset_root / "sample_acceptance.json"
        if retrieval_path.is_file():
            retrieval = _read_json(retrieval_path)
            _required_fields(
                retrieval,
                ("schema_version", "status", "account_id", "queries", "checks", "sample_file_sha256"),
                "expression_asset_retrieval",
                errors,
            )
            if retrieval.get("schema_version") != "expression_asset_retrieval_validation_v1" or retrieval.get("status") != "passed":
                errors.append("expression_assets:retrieval_validation_not_passed")
            if retrieval.get("account_id") != expected_account_id:
                errors.append("expression_assets:retrieval_account_mismatch")
            queries = retrieval.get("queries")
            if not isinstance(queries, list) or not queries or any(not isinstance(item, dict) or item.get("passed") is not True for item in queries):
                errors.append("expression_assets:retrieval_queries_incomplete")
            checks = retrieval.get("checks")
            required_checks = {
                "top_k_relevance",
                "source_traceability",
                "abstraction_quality",
                "adaptation_quality",
                "risk_detection",
                "account_isolation",
            }
            if not isinstance(checks, dict) or any(checks.get(item) is not True for item in required_checks):
                errors.append("expression_assets:retrieval_checks_incomplete")
            if sample_path.is_file() and retrieval.get("sample_file_sha256") != _sha256_file(sample_path):
                errors.append("expression_assets:retrieval_sample_hash_mismatch")
        if acceptance_path.is_file():
            acceptance = _read_json(acceptance_path)
            if acceptance.get("status") != "accepted" or acceptance.get("account_id") != expected_account_id:
                errors.append("expression_assets:sample_acceptance_invalid")
            if sample_path.is_file() and acceptance.get("sample_file_sha256") != _sha256_file(sample_path):
                errors.append("expression_assets:sample_acceptance_hash_mismatch")
            if retrieval_path.is_file() and acceptance.get("retrieval_validation_sha256") != _sha256_file(retrieval_path):
                errors.append("expression_assets:sample_acceptance_retrieval_hash_mismatch")

    elif stage_id == "stage4_method_linking":
        links, link_errors = _read_jsonl(asset_root / "asset_method_links.jsonl")
        errors.extend(f"expression_assets:links:{item}" for item in link_errors)
        for link in links:
            _required_fields(link, ("asset_id", "method_id", "relation", "evidence_coordinate"), "expression_asset_link", errors)
            if not valid_coordinate(link.get("evidence_coordinate")):
                errors.append("expression_assets:link_coordinate_invalid")
        if not links:
            errors.append("expression_assets:asset_method_links_empty")
        for name in ("钩子与留存机制图谱.md", "金句与句式图谱.md", "内容结构完整图谱.md"):
            path = asset_root / name
            if path.is_file() and len(path.read_text(encoding="utf-8").strip()) < 40:
                errors.append(f"expression_assets:view_too_short:{name}")

    elif stage_id == "stage5_pressure_test":
        pressure_path = asset_root / "pressure_test_report.json"
        if pressure_path.is_file():
            report = _read_json(pressure_path)
            required_tests = {
                "retrieval",
                "adaptation",
                "source_copying",
                "unsupported_performance_claim",
                "cross_account_contamination",
                "cross_surface_mismatch",
            }
            results = report.get("test_results")
            if (
                report.get("schema_version") != "expression_asset_pressure_test_v1"
                or report.get("status") != "passed"
                or report.get("account_id") != expected_account_id
                or not isinstance(results, dict)
                or any(results.get(item) is not True for item in required_tests)
                or report.get("failures") not in ([], None)
            ):
                errors.append("expression_assets:pressure_test_not_passed")

    elif stage_id == "stage6_learning_delivery":
        full_path = asset_root / "expression_assets.jsonl"
        if full_path.is_file():
            validation = validate_expression_asset_file(
                root,
                full_path,
                expected_account_id=expected_account_id,
                expected_workflow_id=expected_workflow_id,
            )
            if not validation.get("ok"):
                errors.extend(f"expression_assets:full:{item}" for item in validation.get("errors", []))
            metrics["expression_asset_count"] = int(validation.get("record_count", 0) or 0)
        manifest_path = asset_root / "manifest.json"
        if manifest_path.is_file():
            manifest = _read_json(manifest_path)
            _required_fields(
                manifest,
                ("schema_version", "status", "account_id", "record_count", "full_file_sha256", "files", "boundaries"),
                "expression_asset_manifest",
                errors,
            )
            if manifest.get("schema_version") != "expression_asset_package_v1" or manifest.get("status") != "ready_for_review":
                errors.append("expression_assets:manifest_status_invalid")
            if manifest.get("account_id") != expected_account_id:
                errors.append("expression_assets:manifest_account_mismatch")
            if full_path.is_file() and manifest.get("full_file_sha256") != _sha256_file(full_path):
                errors.append("expression_assets:manifest_full_hash_mismatch")
            boundaries = manifest.get("boundaries")
            expected_boundaries = {
                "candidate_only": True,
                "formal_write": False,
                "callable": False,
                "source_generation_eligible": False,
                "cross_account_merge": False,
            }
            if not isinstance(boundaries, dict) or any(boundaries.get(key) is not value for key, value in expected_boundaries.items()):
                errors.append("expression_assets:manifest_boundaries_invalid")
            files = manifest.get("files")
            if not isinstance(files, list) or not files:
                errors.append("expression_assets:manifest_files_missing")
            else:
                for item in files:
                    if not isinstance(item, dict) or not _portable_relative_path(item.get("path")):
                        errors.append("expression_assets:manifest_file_invalid")
                        continue
                    target = asset_root / str(item.get("path"))
                    if not target.is_file():
                        errors.append(f"expression_assets:manifest_file_missing:{item.get('path')}")
                    elif item.get("sha256") != _sha256_file(target):
                        errors.append(f"expression_assets:manifest_file_hash_mismatch:{item.get('path')}")
        for name in ("表达资产总览.md", "发布层与视频层协同图谱.md", "表达资产使用说明.md", "反例与慎用表达.md", "单条内容拆解索引.md"):
            path = asset_root / name
            if path.is_file() and len(path.read_text(encoding="utf-8").strip()) < 40:
                errors.append(f"expression_assets:view_too_short:{name}")


def _portable_relative_path(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or Path(text).is_absolute() or text.startswith("/Volumes/"):
        return False
    return ".." not in Path(text).parts


def _version_at_least(value: Any, minimum: tuple[int, int]) -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", str(value or "").strip())
    if not match:
        return False
    return (int(match.group(1)), int(match.group(2))) >= minimum


def _validate_accepted_ai_output_manifest(
    base: Path,
    manifest_value: str,
    expected_account: str,
    contract: dict[str, Any],
    positive_ids: set[str],
    positive_hashes: set[str],
    errors: list[str],
) -> None:
    if not _portable_relative_path(manifest_value):
        errors.append("visual_reference:accepted_ai_manifest_path_not_portable")
        return
    manifest_path = (base / manifest_value).resolve()
    try:
        manifest_path.relative_to(base.resolve())
    except ValueError:
        errors.append("visual_reference:accepted_ai_manifest_outside_workflow")
        return
    if not manifest_path.is_file():
        errors.append("visual_reference:accepted_ai_manifest_missing")
        return

    manifest = _read_json(manifest_path)
    expected_source_kind = str(contract.get("source_kind") or "")
    expected_origin_kind = str(contract.get("origin_kind") or "")
    expected_policy = str(contract.get("reference_policy") or "")
    if manifest.get("source_kind") != expected_source_kind:
        errors.append("visual_reference:accepted_ai_source_kind_invalid")
    if manifest.get("origin_kind") != expected_origin_kind:
        errors.append("visual_reference:accepted_ai_origin_kind_invalid")
    if manifest.get("reference_policy") != expected_policy:
        errors.append("visual_reference:accepted_ai_reference_policy_invalid")
    if manifest.get("account_name") != expected_account:
        errors.append("visual_reference:accepted_ai_account_mismatch")

    allowed_uses = set(map(str, contract.get("allowed_uses", [])))
    forbidden_uses = set(map(str, contract.get("forbidden_uses", [])))
    required_false_fields = tuple(map(str, contract.get("required_false_fields", [])))
    items = manifest.get("items")
    if not isinstance(items, list):
        errors.append("visual_reference:accepted_ai_items_must_be_list")
        return

    for index, item in enumerate(items):
        label = f"accepted_ai_item_{index}"
        if not isinstance(item, dict):
            errors.append(f"visual_reference:{label}:not_object")
            continue
        item_id = str(item.get("id") or "").strip()
        label = item_id or label
        if not item_id:
            errors.append(f"visual_reference:{label}:id_missing")
        if item.get("source_kind") != expected_source_kind:
            errors.append(f"visual_reference:{label}:source_kind_invalid")
        if item.get("origin_kind") != expected_origin_kind:
            errors.append(f"visual_reference:{label}:origin_kind_invalid")
        if item.get("source_account_name") != expected_account:
            errors.append(f"visual_reference:{label}:account_mismatch")
        uses = set(map(str, item.get("allowed_use", [])))
        if not uses or not uses.issubset(allowed_uses) or bool(uses & forbidden_uses):
            errors.append(f"visual_reference:{label}:allowed_use_invalid")
        for field in required_false_fields:
            if item.get(field) is not False:
                errors.append(f"visual_reference:{label}:{field}_must_be_false")
        expected_hash = str(item.get("sha256") or "").strip().lower()
        if item_id in positive_ids:
            errors.append(f"visual_reference:{label}:positive_id_overlap")
        if expected_hash and expected_hash in positive_hashes:
            errors.append(f"visual_reference:{label}:positive_hash_overlap")
        for forbidden_field in (
            "food_realism",
            "camera_realism",
            "authenticity_reference",
            "master_reference",
            "golden_positive",
        ):
            if item.get(forbidden_field) not in (None, False, "", []):
                errors.append(f"visual_reference:{label}:{forbidden_field}_forbidden")


def _validate_visual_reference_package(
    base: Path,
    workflow_state: dict[str, Any],
    config: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    starting_error_count = len(errors)
    contract = config.get("stage6_visual_reference_package", {})
    profile_path = base / str(contract.get("profile") or "VISUAL_REFERENCE_PROFILE.json")
    manifest_path = base / str(contract.get("manifest") or "visual_reference_candidate/manifest.json")
    visual_reference_path = base / str(
        contract.get("required_candidate_reference")
        or "account_skill_candidate/references/visual-evidence.md"
    )
    metrics: dict[str, Any] = {
        "visual_reference_status": "missing",
        "visual_reference_item_count": 0,
        "visual_reference_role_coverage": 0,
        "visual_reference_risk_coverage": 0,
    }
    if not profile_path.is_file():
        errors.append("visual_reference:missing_profile")
        return metrics
    if not manifest_path.is_file():
        errors.append("visual_reference:missing_manifest")
        return metrics

    profile = _read_json(profile_path)
    manifest = _read_json(manifest_path)
    visual_branches = set(map(str, contract.get("visual_media_branches", [])))
    workflow_branches = set(map(str, workflow_state.get("media_branches", [])))
    applicable = bool(visual_branches & workflow_branches)
    expected_account = str(workflow_state.get("account_name") or "")
    expected_profile_schema = str(contract.get("schema_id") or "")
    expected_manifest_schema = str(contract.get("manifest_schema_id") or "")

    for payload, prefix, schema in (
        (profile, "visual_reference_profile", expected_profile_schema),
        (manifest, "visual_reference_manifest", expected_manifest_schema),
    ):
        if payload.get("schema_version") != schema:
            errors.append(f"{prefix}:schema_invalid")
        if payload.get("account_name") != expected_account:
            errors.append(f"{prefix}:account_mismatch")
        if (
            payload.get("formal_write") is not False
            or payload.get("callable") is not False
            or payload.get("user_review_required") is not True
        ):
            errors.append(f"{prefix}:candidate_boundary_invalid")

    if not applicable:
        if profile.get("visual_applicability") != "not_applicable":
            errors.append("visual_reference_profile:non_visual_workflow_must_be_not_applicable")
        if manifest.get("status") != "not_applicable" or manifest.get("items") not in ([], None):
            errors.append("visual_reference_manifest:non_visual_workflow_must_be_empty")
        metrics["visual_reference_status"] = "not_applicable"
        return metrics

    if profile.get("visual_applicability") != "applicable":
        errors.append("visual_reference_profile:visual_workflow_must_be_applicable")
    if profile.get("status") != "ready_for_review" or manifest.get("status") != "ready_for_review":
        errors.append("visual_reference:status_must_be_ready_for_review")
    sampling = profile.get("sampling_profiles")
    if not isinstance(sampling, dict):
        errors.append("visual_reference_profile:sampling_profiles_missing")
        sampling = {}
    if sampling.get("audit_offline_source") != "direction_balanced":
        errors.append("visual_reference_profile:audit_sampling_invalid")
    if sampling.get("production_visual_source") != "role_and_risk":
        errors.append("visual_reference_profile:production_sampling_invalid")
    if manifest.get("sampling") != "role_and_risk":
        errors.append("visual_reference_manifest:sampling_invalid")
    if profile.get("positive_manifest") != str(contract.get("manifest")):
        errors.append("visual_reference_profile:positive_manifest_invalid")

    separation = profile.get("source_separation")
    current_policy = _version_at_least(workflow_state.get("schema_version"), (2, 8))
    expected_separation = (
        contract.get("source_kinds", {})
        if current_policy
        else contract.get("legacy_source_kinds", contract.get("source_kinds", {}))
    )
    if not isinstance(separation, dict) or any(
        separation.get(key) != value for key, value in expected_separation.items()
    ):
        errors.append("visual_reference_profile:source_separation_invalid")

    allowed_roles = set(map(str, contract.get("production_roles", [])))
    allowed_risks = set(map(str, contract.get("risk_dimensions", [])))
    declared_roles = set(map(str, profile.get("production_role_inventory", [])))
    declared_risks = set(map(str, profile.get("risk_dimension_inventory", [])))
    if not declared_roles or not declared_roles.issubset(allowed_roles):
        errors.append("visual_reference_profile:production_role_inventory_invalid")
    if not declared_risks or not declared_risks.issubset(allowed_risks):
        errors.append("visual_reference_profile:risk_dimension_inventory_invalid")
    if set(map(str, manifest.get("required_roles", []))) != declared_roles:
        errors.append("visual_reference_manifest:required_roles_mismatch")
    if set(map(str, manifest.get("required_risk_dimensions", []))) != declared_risks:
        errors.append("visual_reference_manifest:required_risks_mismatch")
    if manifest.get("source_kind") != contract.get("positive_source_kind"):
        errors.append("visual_reference_manifest:positive_source_kind_invalid")

    items = manifest.get("items")
    if not isinstance(items, list):
        errors.append("visual_reference_manifest:items_must_be_list")
        items = []
    minimum = int(contract.get("minimum_positive_assets", 3))
    if len(items) < minimum:
        errors.append(f"visual_reference_manifest:positive_item_count_below_{minimum}")
    ids: set[str] = set()
    hashes: set[str] = set()
    covered_roles: set[str] = set()
    covered_risks: set[str] = set()
    allowed_uses = set(map(str, contract.get("allowed_positive_uses", [])))
    manifest_root = manifest_path.parent.resolve()

    for index, item in enumerate(items):
        label = f"item_{index}"
        if not isinstance(item, dict):
            errors.append(f"visual_reference:{label}:not_object")
            continue
        item_id = str(item.get("id") or "").strip()
        label = item_id or label
        if not item_id:
            errors.append(f"visual_reference:{label}:id_missing")
        elif item_id in ids:
            errors.append(f"visual_reference:{label}:id_duplicate")
        ids.add(item_id)
        if item.get("source_kind") != contract.get("positive_source_kind"):
            errors.append(f"visual_reference:{label}:source_kind_invalid")
        if item.get("source_account_name") != expected_account:
            errors.append(f"visual_reference:{label}:cross_account_asset_forbidden")
        if not str(item.get("source_id") or "").strip():
            errors.append(f"visual_reference:{label}:source_id_missing")
        if not str(item.get("evidence_coordinate") or "").strip():
            errors.append(f"visual_reference:{label}:evidence_coordinate_missing")
        if item.get("method_evidence_eligible") is not False:
            errors.append(f"visual_reference:{label}:method_evidence_must_be_false")
        positive_origin = contract.get("positive_origin_contract", {})
        if item.get("origin_kind") not in (None, "", positive_origin.get("origin_kind")):
            errors.append(f"visual_reference:{label}:origin_kind_must_be_account_original")
        if item.get("ai_generated") is True:
            errors.append(f"visual_reference:{label}:ai_generated_positive_forbidden")
        if current_policy:
            if item.get("origin_kind") != positive_origin.get("origin_kind"):
                errors.append(f"visual_reference:{label}:origin_kind_missing")
            for field in map(str, positive_origin.get("required_true_fields", [])):
                if item.get(field) is not True:
                    errors.append(f"visual_reference:{label}:{field}_must_be_true")
            for field in map(str, positive_origin.get("required_false_fields", [])):
                if item.get(field) is not False:
                    errors.append(f"visual_reference:{label}:{field}_must_be_false")
        uses = set(map(str, item.get("allowed_use", [])))
        if not uses or not uses.issubset(allowed_uses):
            errors.append(f"visual_reference:{label}:allowed_use_invalid")
        roles = set(map(str, item.get("production_roles", [])))
        risks = set(map(str, item.get("risk_dimensions", [])))
        if not roles or not roles.issubset(declared_roles):
            errors.append(f"visual_reference:{label}:production_roles_invalid")
        if not risks or not risks.issubset(declared_risks):
            errors.append(f"visual_reference:{label}:risk_dimensions_invalid")
        covered_roles.update(roles)
        covered_risks.update(risks)

        relative = str(item.get("path") or "").strip()
        if not _portable_relative_path(relative):
            errors.append(f"visual_reference:{label}:path_not_portable")
            continue
        target = (manifest_root / relative).resolve()
        try:
            target.relative_to(manifest_root)
        except ValueError:
            errors.append(f"visual_reference:{label}:path_outside_package")
            continue
        if not target.is_file():
            errors.append(f"visual_reference:{label}:asset_missing")
            continue
        expected_hash = str(item.get("sha256") or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            errors.append(f"visual_reference:{label}:sha256_invalid")
        elif _sha256_file(target) != expected_hash:
            errors.append(f"visual_reference:{label}:sha256_mismatch")
        if expected_hash in hashes:
            errors.append(f"visual_reference:{label}:duplicate_asset_hash")
        hashes.add(expected_hash)
        for forbidden_field in ("nas_path", "original_source_dir", "absolute_source_path"):
            if str(item.get(forbidden_field) or "").strip():
                errors.append(f"visual_reference:{label}:{forbidden_field}_forbidden")

    missing_roles = declared_roles - covered_roles
    missing_risks = declared_risks - covered_risks
    errors.extend(f"visual_reference:role_not_covered:{role}" for role in sorted(missing_roles))
    errors.extend(f"visual_reference:risk_not_covered:{risk}" for risk in sorted(missing_risks))

    accepted_contract = contract.get("accepted_ai_output_contract", {})
    accepted_manifest_field = str(
        accepted_contract.get("profile_manifest_field") or "accepted_ai_output_manifest"
    )
    accepted_manifest_value = str(profile.get(accepted_manifest_field) or "").strip()
    if accepted_manifest_value:
        _validate_accepted_ai_output_manifest(
            base,
            accepted_manifest_value,
            expected_account,
            accepted_contract,
            ids,
            hashes,
            errors,
        )

    if not visual_reference_path.is_file():
        errors.append("visual_reference:missing_candidate_reference")
    else:
        reference_text = visual_reference_path.read_text(encoding="utf-8")
        for source_kind in expected_separation:
            if str(source_kind) not in reference_text:
                errors.append(f"visual_reference:candidate_reference_missing_source_kind:{source_kind}")

    negative_value = str(profile.get("negative_manifest") or "").strip()
    if negative_value:
        if not _portable_relative_path(negative_value):
            errors.append("visual_reference:negative_manifest_path_not_portable")
        else:
            negative_path = (base / negative_value).resolve()
            try:
                negative_path.relative_to(base.resolve())
            except ValueError:
                errors.append("visual_reference:negative_manifest_outside_workflow")
            else:
                if not negative_path.is_file():
                    errors.append("visual_reference:negative_manifest_missing")
                else:
                    negative = _read_json(negative_path)
                    if negative.get("source_kind") != "user_rejected_output":
                        errors.append("visual_reference:negative_source_kind_invalid")
                    if negative.get("reference_policy") != "validation_only":
                        errors.append("visual_reference:negative_reference_policy_invalid")
                    if negative.get("never_use_as_positive_reference") is not True:
                        errors.append("visual_reference:negative_positive_guard_missing")
                    for item in negative.get("items", []):
                        if not isinstance(item, dict):
                            continue
                        if str(item.get("id") or "") in ids:
                            errors.append("visual_reference:negative_positive_id_overlap")
                        if str(item.get("sha256") or "") in hashes:
                            errors.append("visual_reference:negative_positive_hash_overlap")

    metrics.update(
        {
            "visual_reference_status": (
                "ready_for_review" if len(errors) == starting_error_count else "invalid"
            ),
            "visual_reference_item_count": len(items),
            "visual_reference_role_coverage": len(covered_roles),
            "visual_reference_risk_coverage": len(covered_risks),
        }
    )
    return metrics


def _validate_deep_observation_candidate(
    item: dict[str, Any],
    workflow_state: dict[str, Any],
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

    if lens == "expression":
        _validate_signal_observation(
            item,
            key="publish_copy_observation",
            schema_id=str(contract.get("publish_copy_schema_id") or ""),
            dimensions=[str(value) for value in contract.get("publish_copy_dimensions", [])],
            fields=[str(value) for value in contract.get("publish_copy_observation_fields", [])],
            fingerprint_key="publish_copy_fingerprint",
            errors=errors,
        )
        return
    content_form = str(item.get("content_form") or "").lower()
    if "图文" not in content_form and "image_text" not in content_form and "image-text" not in content_form:
        return
    visual_dimensions = [str(value) for value in contract.get("image_text_visual_dimensions", [])]
    visual_fields = [str(value) for value in contract.get("image_text_visual_observation_fields", [])]
    enforce_production_reference_candidate = (
        workflow_state.get("stage1_visual_reference_candidate_schema")
        == contract.get("production_reference_candidate_schema_id")
    )
    if not enforce_production_reference_candidate:
        visual_dimensions = [
            value for value in visual_dimensions if value != "production_reference_candidate"
        ]
        visual_fields = [
            value for value in visual_fields if value != "production_reference_candidates"
        ]
    _validate_signal_observation(
        item,
        key="image_text_visual_observation",
        schema_id=str(contract.get("image_text_visual_schema_id") or ""),
        dimensions=visual_dimensions,
        fields=visual_fields,
        fingerprint_key="visual_sequence_fingerprint",
        errors=errors,
    )


def _validate_signal_observation(
    item: dict[str, Any],
    *,
    key: str,
    schema_id: str,
    dimensions: list[str],
    fields: list[str],
    fingerprint_key: str,
    errors: list[str],
) -> None:
    candidate_id = str(item.get("id") or "unknown")
    observation = item.get(key)
    if not isinstance(observation, dict):
        errors.append(f"candidate:{candidate_id}:missing_{key}")
        return
    if observation.get("schema") != schema_id:
        errors.append(f"candidate:{candidate_id}:invalid_{key}_schema")
    _required_keys(observation, tuple(fields), f"{key}:{candidate_id}", errors)
    observed = observation.get("observed_signals")
    missing = observation.get("missing_or_uncertain_signals")
    considered = observation.get("dimensions_considered")
    coordinates = observation.get("evidence_coordinates")
    if not isinstance(observed, list):
        errors.append(f"candidate:{candidate_id}:{key}_observed_signals_must_be_list")
        observed = []
    if not isinstance(missing, list):
        errors.append(f"candidate:{candidate_id}:{key}_missing_signals_must_be_list")
        missing = []
    if not isinstance(considered, list) or set(map(str, considered)) != set(dimensions):
        errors.append(f"candidate:{candidate_id}:{key}_dimensions_incomplete")
        considered = []
    if not isinstance(coordinates, list) or not coordinates:
        errors.append(f"candidate:{candidate_id}:{key}_evidence_coordinates_missing")
    labels = {
        str(record.get("signal"))
        for record in observed
        if isinstance(record, dict) and record.get("signal")
    }
    for index, record in enumerate(observed):
        if not isinstance(record, dict):
            errors.append(f"candidate:{candidate_id}:{key}_signal_{index}_must_be_object")
            continue
        _required_fields(
            record,
            ("signal", "evidence", "source_coordinate"),
            f"{key}_signal:{candidate_id}",
            errors,
        )
    unresolved = set(map(str, considered)) - labels - set(map(str, missing))
    if unresolved:
        errors.append(f"candidate:{candidate_id}:{key}_unresolved_dimensions:{','.join(sorted(unresolved))}")
    if not str(observation.get(fingerprint_key) or "").strip():
        errors.append(f"candidate:{candidate_id}:missing_{fingerprint_key}")
    if key == "publish_copy_observation":
        _validate_publish_source_facets(observation, candidate_id, errors)


def _validate_publish_source_facets(
    observation: dict[str, Any],
    record_id: str,
    errors: list[str],
) -> None:
    if observation.get("publish_layer_status") != "observed":
        errors.append(f"publish_copy_observation:{record_id}:publish_layer_not_observed")
    facets = observation.get("source_facets")
    required_facets = {"title", "body", "topics", "coordination"}
    if not isinstance(facets, dict) or set(facets) != required_facets:
        errors.append(f"publish_copy_observation:{record_id}:source_facets_incomplete")
        return
    allowed_statuses = {"observed_raw", "observed_analysis", "explicitly_missing"}
    statuses: list[str] = []
    for name in sorted(required_facets):
        facet = facets.get(name)
        if not isinstance(facet, dict):
            errors.append(f"publish_copy_observation:{record_id}:facet_{name}_must_be_object")
            continue
        _required_fields(
            facet,
            ("status", "evidence", "source_coordinate"),
            f"publish_copy_facet:{record_id}:{name}",
            errors,
        )
        status = str(facet.get("status") or "")
        statuses.append(status)
        if status not in allowed_statuses:
            errors.append(f"publish_copy_observation:{record_id}:facet_{name}_invalid_status:{status}")
    if statuses and not any(status.startswith("observed") for status in statuses):
        errors.append(f"publish_copy_observation:{record_id}:no_observed_publish_facet")


def _validate_publish_copy_study(
    base: Path,
    state: dict[str, Any],
    config: dict[str, Any],
    candidates: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    contract = config.get("stage1_deep_observation", {})
    observation_schema = str(contract.get("publish_copy_schema_id") or "")
    study_schema = str(contract.get("publish_copy_study_schema_id") or "")
    if state.get("publish_copy_observation_schema") != observation_schema:
        return {}
    if state.get("publish_copy_study_schema") != study_schema:
        errors.append("publish_copy_study:invalid_state_schema")
        return {}

    expression_candidates = {
        str(item.get("id")): item
        for item in candidates
        if str(item.get("type") or item.get("lens") or "") == "expression" and item.get("id")
    }
    expected_source_ids = {
        str(source_id)
        for item in expression_candidates.values()
        for source_id in item.get("source_refs", [])
        if str(source_id)
    }
    observation_path = base / "candidates/publish_copy_observations.jsonl"
    records, record_errors = _read_jsonl(observation_path)
    errors.extend(record_errors)
    record_ids: list[str] = []
    observed_source_ids: list[str] = []
    record_by_source: dict[str, dict[str, Any]] = {}
    for record in records:
        _required_fields(
            record,
            (
                "id",
                "type",
                "source_refs",
                "expression_candidate_ids",
                "card_path",
                "card_schema",
                "compatibility_mode",
                "status",
                "callable",
                "publish_copy_observation",
            ),
            "publish_copy_record",
            errors,
        )
        record_id = str(record.get("id") or "")
        record_ids.append(record_id)
        source_refs = [str(value) for value in record.get("source_refs", []) if str(value)]
        if len(source_refs) != 1:
            errors.append(f"publish_copy_record:{record_id}:requires_one_source_ref")
            continue
        source_id = source_refs[0]
        observed_source_ids.append(source_id)
        record_by_source[source_id] = record
        if record.get("type") != "publish_copy_observation":
            errors.append(f"publish_copy_record:{record_id}:invalid_type")
        if record.get("status") != "candidate_observation":
            errors.append(f"publish_copy_record:{record_id}:not_completed")
        if record.get("callable") is not False:
            errors.append(f"publish_copy_record:{record_id}:candidate_boundary_violation")
        linked_ids = [str(value) for value in record.get("expression_candidate_ids", []) if str(value)]
        if not linked_ids:
            errors.append(f"publish_copy_record:{record_id}:missing_expression_link")
        for candidate_id in linked_ids:
            candidate = expression_candidates.get(candidate_id)
            if candidate is None:
                errors.append(f"publish_copy_record:{record_id}:unknown_expression_candidate:{candidate_id}")
            elif source_id not in set(map(str, candidate.get("source_refs", []))):
                errors.append(f"publish_copy_record:{record_id}:expression_link_source_mismatch:{candidate_id}")
        _validate_signal_observation(
            record,
            key="publish_copy_observation",
            schema_id=observation_schema,
            dimensions=[str(value) for value in contract.get("publish_copy_dimensions", [])],
            fields=[str(value) for value in contract.get("publish_copy_observation_fields", [])],
            fingerprint_key="publish_copy_fingerprint",
            errors=errors,
        )

    if len(record_ids) != len(set(record_ids)):
        errors.append("publish_copy_study:duplicate_record_ids")
    if len(observed_source_ids) != len(set(observed_source_ids)):
        errors.append("publish_copy_study:duplicate_source_ids")
    observed_source_set = set(observed_source_ids)
    if observed_source_set != expected_source_ids:
        missing = sorted(expected_source_ids - observed_source_set)
        unknown = sorted(observed_source_set - expected_source_ids)
        if missing:
            errors.append(f"publish_copy_study:missing_sources:{','.join(missing)}")
        if unknown:
            errors.append(f"publish_copy_study:unknown_sources:{','.join(unknown)}")

    for candidate_id, candidate in expression_candidates.items():
        expected_refs = {
            str(record_by_source[source_id].get("id") or "")
            for source_id in map(str, candidate.get("source_refs", []))
            if source_id in record_by_source
        }
        actual_refs = {str(value) for value in candidate.get("publish_copy_observation_refs", []) if str(value)}
        if expected_refs != actual_refs:
            errors.append(f"candidate:{candidate_id}:publish_copy_observation_refs_mismatch")

    report_path = base / "PUBLISH_COPY_SPECIAL_STUDY.json"
    report_md = base / "PUBLISH_COPY_SPECIAL_STUDY.md"
    if not report_path.exists():
        errors.append("publish_copy_study:missing_json_report")
        return {}
    if not report_md.exists():
        errors.append("publish_copy_study:missing_markdown_report")
    report = _read_json(report_path)
    _required_fields(
        report,
        (
            "schema_version",
            "workflow_id",
            "status",
            "observation_schema",
            "observation_file",
            "observation_sha256",
            "expected_source_count",
            "completed_source_count",
            "deferred_source_count",
            "dimension_coverage",
            "facet_coverage",
            "cross_card_pattern_candidates",
            "formal_write",
            "callable",
            "user_review_required",
        ),
        "publish_copy_study",
        errors,
    )
    if report.get("schema_version") != study_schema or report.get("observation_schema") != observation_schema:
        errors.append("publish_copy_study:invalid_report_schema")
    if report.get("status") != "completed":
        errors.append("publish_copy_study:status_not_completed")
    expected_count = len(expected_source_ids)
    if report.get("expected_source_count") != expected_count:
        errors.append("publish_copy_study:expected_count_mismatch")
    if report.get("completed_source_count") != len(observed_source_set):
        errors.append("publish_copy_study:completed_count_mismatch")
    if report.get("deferred_source_count") != 0:
        errors.append("publish_copy_study:deferred_sources_remain")
    if report.get("formal_write") is not False or report.get("callable") is not False:
        errors.append("publish_copy_study:candidate_boundary_violation")
    if report.get("user_review_required") is not True:
        errors.append("publish_copy_study:user_review_gate_missing")
    if observation_path.exists() and report.get("observation_sha256") != _sha256_file(observation_path):
        errors.append("publish_copy_study:observation_hash_mismatch")
    configured_dimensions = {
        str(value) for value in contract.get("publish_copy_dimensions", []) if str(value)
    }
    observed_dimension_counts: dict[str, int] = {dimension: 0 for dimension in configured_dimensions}
    missing_dimension_counts: dict[str, int] = {dimension: 0 for dimension in configured_dimensions}
    facet_status_counts: dict[str, dict[str, int]] = {
        facet: {} for facet in ("title", "body", "topics", "coordination")
    }
    for record in records:
        observation = record.get("publish_copy_observation", {})
        if not isinstance(observation, dict):
            continue
        for signal in observation.get("observed_signals", []):
            if isinstance(signal, dict):
                label = str(signal.get("signal") or "")
                if label in observed_dimension_counts:
                    observed_dimension_counts[label] += 1
        for label in map(str, observation.get("missing_or_uncertain_signals", [])):
            if label in missing_dimension_counts:
                missing_dimension_counts[label] += 1
        facets = observation.get("source_facets", {})
        if isinstance(facets, dict):
            for facet, counts in facet_status_counts.items():
                value = facets.get(facet, {})
                status = str(value.get("status") or "missing") if isinstance(value, dict) else "missing"
                counts[status] = counts.get(status, 0) + 1
    dimension_coverage = report.get("dimension_coverage")
    if not isinstance(dimension_coverage, dict) or set(dimension_coverage) != configured_dimensions:
        errors.append("publish_copy_study:dimension_coverage_incomplete")
    else:
        for dimension in sorted(configured_dimensions):
            value = dimension_coverage.get(dimension, {})
            if not isinstance(value, dict) or value.get("observed_source_count") != observed_dimension_counts[dimension] or value.get("missing_source_count") != missing_dimension_counts[dimension]:
                errors.append(f"publish_copy_study:dimension_coverage_mismatch:{dimension}")
    if report.get("facet_coverage") != facet_status_counts:
        errors.append("publish_copy_study:facet_coverage_mismatch")

    pattern_candidates = report.get("cross_card_pattern_candidates")
    pattern_source_ids: list[str] = []
    if not isinstance(pattern_candidates, list) or not pattern_candidates:
        errors.append("publish_copy_study:missing_cross_card_patterns")
        pattern_candidates = []
    for pattern in pattern_candidates:
        if not isinstance(pattern, dict):
            errors.append("publish_copy_study:pattern_must_be_object")
            continue
        _required_fields(
            pattern,
            (
                "id",
                "signals",
                "source_count",
                "source_refs",
                "status",
                "callable",
                "triple_verification_required",
            ),
            "publish_copy_pattern",
            errors,
        )
        signals = {str(value) for value in pattern.get("signals", []) if str(value)}
        if not signals.issubset(configured_dimensions):
            errors.append(f"publish_copy_study:pattern_unknown_signals:{pattern.get('id', 'unknown')}")
        source_refs = [str(value) for value in pattern.get("source_refs", []) if str(value)]
        pattern_source_ids.extend(source_refs)
        if pattern.get("source_count") != len(set(source_refs)):
            errors.append(f"publish_copy_study:pattern_source_count_mismatch:{pattern.get('id', 'unknown')}")
        if pattern.get("status") != "candidate_only" or pattern.get("callable") is not False:
            errors.append(f"publish_copy_study:pattern_boundary_violation:{pattern.get('id', 'unknown')}")
        if pattern.get("triple_verification_required") is not True:
            errors.append(f"publish_copy_study:pattern_missing_review_gate:{pattern.get('id', 'unknown')}")
    if len(pattern_source_ids) != len(set(pattern_source_ids)):
        errors.append("publish_copy_study:pattern_source_assigned_multiple_times")
    if set(pattern_source_ids) != expected_source_ids:
        errors.append("publish_copy_study:pattern_source_coverage_mismatch")
    state_counts = (
        state.get("publish_copy_expected_count"),
        state.get("publish_copy_completed_count"),
        state.get("publish_copy_deferred_count"),
    )
    if state_counts != (expected_count, len(observed_source_set), 0):
        errors.append("publish_copy_study:state_count_mismatch")
    return {
        "publish_copy_expected_count": expected_count,
        "publish_copy_completed_count": len(observed_source_set),
        "publish_copy_deferred_count": 0,
    }


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
                _validate_deep_observation_candidate(item, workflow_state, config, errors)
            ids.append(str(item.get("id", "")))
        if len(ids) != len(set(ids)):
            errors.append("candidate_ids_not_unique")
        metrics.update(_validate_publish_copy_study(base, workflow_state, config, candidates, errors))
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
            if str(manifest.get("schema_version") or "") in {"2.2", "2.3", "2.4", "2.5", "2.6"}:
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
        if _state_schema_enabled(
            workflow_state,
            config,
            state_field="stage6_visual_reference_schema",
            config_section="stage6_visual_reference_package",
        ):
            metrics.update(
                _validate_visual_reference_package(base, workflow_state, config, errors)
            )
        skill_contract = config.get("stage6_account_skill_package", {})
        if skill_contract.get("required") is True:
            skill_root = base / str(skill_contract.get("root") or "account_skill_candidate")
            skill_path = base / str(skill_contract.get("skill") or "account_skill_candidate/SKILL.md")
            skill_manifest_path = base / str(
                skill_contract.get("manifest") or "account_skill_candidate/ACCOUNT_SKILL_MANIFEST.json"
            )
            if not skill_path.exists():
                errors.append("missing:account_skill_candidate/SKILL.md")
            else:
                skill_text = skill_path.read_text(encoding="utf-8")
                if not skill_text.startswith("---\n") or "name:" not in skill_text or "description:" not in skill_text:
                    errors.append("account_skill_candidate_frontmatter_invalid")
                for marker in skill_contract.get("required_skill_markers", []):
                    if str(marker) not in skill_text:
                        errors.append(f"account_skill_candidate_rule_missing:{marker}")
            for relative in skill_contract.get("required_references", []):
                if not (skill_root / str(relative)).exists():
                    errors.append(f"missing:account_skill_candidate/{relative}")
            for relative in skill_contract.get("required_account_views", []):
                if not (skill_root / str(relative)).exists():
                    errors.append(f"missing:account_skill_candidate/{relative}")
            if not skill_manifest_path.exists():
                errors.append("missing:account_skill_candidate/ACCOUNT_SKILL_MANIFEST.json")
            else:
                skill_manifest = _read_json(skill_manifest_path)
                _required_fields(
                    skill_manifest,
                    (
                        "schema_version",
                        "status",
                        "source_method_ids",
                        "formal_write",
                        "callable",
                        "user_review_required",
                    ),
                    "account_skill_candidate",
                    errors,
                )
                if skill_manifest.get("schema_version") != skill_contract.get("schema_id"):
                    errors.append("account_skill_candidate_invalid_schema")
                if skill_manifest.get("status") != "ready_for_review":
                    errors.append("account_skill_candidate_status_must_be_ready_for_review")
                if (
                    skill_manifest.get("formal_write") is not False
                    or skill_manifest.get("callable") is not False
                    or skill_manifest.get("user_review_required") is not True
                ):
                    errors.append("account_skill_candidate_must_remain_candidate_only")
                if {str(item) for item in skill_manifest.get("source_method_ids", [])} != verified_ids:
                    errors.append("account_skill_candidate_method_ids_must_match_verified_ids")
        compatibility_contract = config.get("stage6_upgrade_compatibility", {})
        if _state_schema_enabled(
            workflow_state,
            config,
            state_field="stage6_upgrade_compatibility_schema",
            config_section="stage6_upgrade_compatibility",
        ):
            compatibility_path = base / str(
                compatibility_contract.get("manifest")
                or "account_skill_candidate/UPGRADE_COMPATIBILITY.json"
            )
            if not compatibility_path.is_file():
                errors.append("missing:account_skill_candidate/UPGRADE_COMPATIBILITY.json")
            else:
                compatibility = _read_json(compatibility_path)
                if compatibility.get("schema_version") != compatibility_contract.get("schema_id"):
                    errors.append("account_skill_upgrade_compatibility_schema_invalid")
                for field, expected in {
                    "candidate_only": True,
                    "formal_write": False,
                    "callable": False,
                    "user_review_required": True,
                }.items():
                    if compatibility.get(field) is not expected:
                        errors.append(f"account_skill_upgrade_compatibility_boundary_invalid:{field}")
                previous = [str(item) for item in compatibility.get("previous_capability_ids", [])]
                new_ids = [str(item) for item in compatibility.get("new_capability_ids", [])]
                capability_items = compatibility.get("capabilities")
                if not isinstance(capability_items, list) or not capability_items:
                    errors.append("account_skill_upgrade_compatibility_capabilities_missing")
                    capability_items = []
                capability_ids = [
                    str(item.get("id") or "") for item in capability_items if isinstance(item, dict)
                ]
                current_set = set(capability_ids)
                previous_set = set(previous)
                if not previous_set.issubset(current_set):
                    for cap_id in sorted(previous_set - current_set):
                        errors.append(f"account_skill_upgrade_silent_capability_loss:{cap_id}")
                if set(new_ids) != current_set - previous_set:
                    errors.append("account_skill_upgrade_new_capability_delta_mismatch")
                if (
                    len(capability_ids) != len(current_set)
                    or any(not item for item in capability_ids)
                    or len(previous) != len(previous_set)
                    or len(new_ids) != len(set(new_ids))
                ):
                    errors.append("account_skill_upgrade_capability_ids_invalid")
                for item in capability_items:
                    if not isinstance(item, dict):
                        errors.append("account_skill_upgrade_capability_invalid")
                        continue
                    cap_id = str(item.get("id") or "")
                    sources = item.get("source_paths")
                    if not isinstance(sources, list) or not sources:
                        errors.append(f"account_skill_upgrade_capability_sources_missing:{cap_id}")
                        continue
                    for source in sources:
                        source_value = str(source or "")
                        if not _portable_relative_path(source_value):
                            errors.append(f"account_skill_upgrade_source_not_portable:{cap_id}")
                            continue
                        source_path = (base / source_value).resolve()
                        try:
                            source_path.relative_to(skill_root.resolve())
                        except ValueError:
                            errors.append(f"account_skill_upgrade_cross_account_source:{cap_id}")
                        else:
                            if not source_path.is_file():
                                errors.append(f"account_skill_upgrade_source_missing:{cap_id}:{source_value}")
                for change in compatibility.get("changed_capabilities", []):
                    if not isinstance(change, dict):
                        errors.append("account_skill_upgrade_change_record_invalid")
                        continue
                    confirmation = change.get("user_confirmation")
                    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
                        errors.append("account_skill_upgrade_change_confirmation_missing")
                        continue
                    proposal_value = str(confirmation.get("proposal_path") or "")
                    if not _portable_relative_path(proposal_value):
                        errors.append("account_skill_upgrade_change_proposal_not_portable")
                        continue
                    proposal_path = (base / proposal_value).resolve()
                    try:
                        proposal_path.relative_to(skill_root.resolve())
                    except ValueError:
                        errors.append("account_skill_upgrade_change_proposal_cross_account")
                    else:
                        if not proposal_path.is_file():
                            errors.append(
                                f"account_skill_upgrade_change_proposal_missing:{proposal_value}"
                            )
                isolation = compatibility.get("isolation")
                expected_isolation = {
                    "same_account_only": True,
                    "cross_account_merge": False,
                    "system_rule_contamination": False,
                    "absolute_or_nas_paths": False,
                }
                if not isinstance(isolation, dict) or any(
                    isolation.get(key) is not value for key, value in expected_isolation.items()
                ):
                    errors.append("account_skill_upgrade_isolation_invalid")
                snapshots = compatibility.get("source_snapshot")
                if not isinstance(snapshots, list) or not snapshots:
                    errors.append("account_skill_upgrade_source_snapshot_missing")
                    snapshots = []
                for snapshot in snapshots:
                    if not isinstance(snapshot, dict):
                        errors.append("account_skill_upgrade_source_snapshot_invalid")
                        continue
                    source_value = str(snapshot.get("path") or "")
                    expected_hash = str(snapshot.get("sha256") or "").lower()
                    if not _portable_relative_path(source_value):
                        errors.append("account_skill_upgrade_snapshot_path_not_portable")
                        continue
                    source_path = (base / source_value).resolve()
                    try:
                        source_path.relative_to(skill_root.resolve())
                    except ValueError:
                        errors.append("account_skill_upgrade_snapshot_cross_account")
                    else:
                        if not source_path.is_file():
                            errors.append(f"account_skill_upgrade_snapshot_missing:{source_value}")
                        elif not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                            errors.append(f"account_skill_upgrade_snapshot_hash_invalid:{source_value}")
                        elif _sha256_file(source_path) != expected_hash:
                            errors.append(f"account_skill_upgrade_snapshot_hash_mismatch:{source_value}")
    _validate_expression_asset_stage(
        root,
        base,
        workflow_state,
        config,
        stage_id,
        errors,
        metrics,
    )
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
    completed_invalid = [
        stage["id"]
        for stage in state["stages"]
        if stage.get("status") == "completed" and not validations[stage["id"]]["ok"]
    ]
    return {
        "ok": not completed_invalid,
        "workflow_id": state["workflow_id"],
        "account_name": state["account_name"],
        "status": state["status"] if not completed_invalid else f"{state['status']}_with_validation_errors",
        "current_stage": state["current_stage"],
        "completed_stage_failures": completed_invalid,
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


def _candidate_compatibility_from_formal(
    root: Path,
    *,
    workflow_id: str,
    source_root: Path,
    source_account_root: Path,
    target_root: Path,
) -> dict[str, Any]:
    root = root.resolve()
    source_root = source_root.resolve()
    source_account_root = source_account_root.resolve()
    target_root = target_root.resolve()
    formal_path = source_root / "UPGRADE_COMPATIBILITY.json"
    if not formal_path.is_file():
        raise FileNotFoundError("formal_account_skill_upgrade_compatibility_missing")
    formal = _read_json(formal_path)
    workflow_base = workflow_root(root, workflow_id)
    fallback = target_root / "references" / "upgrade-compatibility.md"
    if not fallback.is_file():
        raise FileNotFoundError("candidate_upgrade_compatibility_reference_missing")

    def candidate_source(value: str) -> str:
        source = (root / value).resolve()
        if source == (source_root / "UPGRADE_COMPATIBILITY.json").resolve():
            return fallback.relative_to(workflow_base).as_posix()
        try:
            relative = source.relative_to(source_root.resolve())
        except ValueError:
            relative = None
        if relative is not None and (target_root / relative).is_file():
            return (target_root / relative).relative_to(workflow_base).as_posix()
        try:
            account_relative = source.relative_to(source_account_root.resolve())
        except ValueError:
            account_relative = None
        if account_relative is not None and len(account_relative.parts) == 1:
            view = target_root / "account_views" / account_relative.name
            if view.is_file():
                return view.relative_to(workflow_base).as_posix()
        if source == (source_account_root / "METHOD_INDEX.json").resolve():
            method_snapshot = target_root / "references" / "formal-method-index.json"
            if method_snapshot.is_file():
                return method_snapshot.relative_to(workflow_base).as_posix()
        return fallback.relative_to(workflow_base).as_posix()

    capabilities: list[dict[str, Any]] = []
    for item in formal.get("capabilities", []):
        if not isinstance(item, dict):
            continue
        converted = dict(item)
        converted["source_paths"] = sorted(
            {
                candidate_source(str(source))
                for source in item.get("source_paths", [])
                if str(source).strip()
            }
        )
        capabilities.append(converted)
    changed_capabilities: list[dict[str, Any]] = []
    for item in formal.get("changed_capabilities", []):
        if not isinstance(item, dict):
            continue
        converted = dict(item)
        confirmation = item.get("user_confirmation")
        if isinstance(confirmation, dict):
            converted_confirmation = dict(confirmation)
            proposal_path = str(confirmation.get("proposal_path") or "")
            if proposal_path:
                converted_confirmation["proposal_path"] = candidate_source(proposal_path)
            converted["user_confirmation"] = converted_confirmation
        changed_capabilities.append(converted)
    source_paths = sorted(
        {
            source
            for item in capabilities
            for source in item.get("source_paths", [])
            if str(source).strip()
            and not str(source).endswith("/UPGRADE_COMPATIBILITY.json")
        }
    )
    return {
        "schema_version": formal.get("schema_version"),
        "account_skill_id": formal.get("account_skill_id"),
        "base_version": formal.get("base_version"),
        "target_version": formal.get("target_version"),
        "upgrade_scope": formal.get("upgrade_scope", "system_account_batch_member"),
        "candidate_only": True,
        "formal_write": False,
        "callable": False,
        "user_review_required": True,
        "previous_capability_ids": formal.get("previous_capability_ids", []),
        "new_capability_ids": formal.get("new_capability_ids", []),
        "capabilities": capabilities,
        "changed_capabilities": changed_capabilities,
        "source_snapshot": [
            {"path": source, "sha256": _sha256_file(workflow_base / source)} for source in source_paths
        ],
        "regression_package_manifests": [],
        "isolation": {
            "same_account_only": True,
            "cross_account_merge": False,
            "system_rule_contamination": False,
            "absolute_or_nas_paths": False,
        },
        "rollback": {
            "mode": "restore_pre_v29_candidate_snapshot",
            "formal_account_skill_unchanged_by_candidate_migration": True,
            "delete_formal_evidence": False,
        },
        "migration": {
            "type": "backfill_v29_from_same_account_formal_skill",
            "source_manifest": formal_path.relative_to(root).as_posix(),
            "migrated_at": now_iso(),
        },
    }


def migrate_account_skill_candidate(root: Path, workflow_id: str, *, force: bool = False) -> dict[str, Any]:
    """Backfill the stage-6 candidate package from an already approved formal account Skill."""

    from tools.kb.account_skills import resolve_account_skill

    root = root.resolve()
    config = load_config(root)
    state = load_state(root, workflow_id)
    resolved = resolve_account_skill(root, str(state.get("account_name") or ""))
    if not resolved.get("ok"):
        return {
            "ok": False,
            "workflow_id": _safe_id(workflow_id),
            "error": "formal_account_skill_not_found",
            "account_name": state.get("account_name", ""),
        }
    source_skill = root / str(resolved["skill_path"])
    source_root = source_skill.parent
    target_root = workflow_root(root, workflow_id) / "account_skill_candidate"
    contract = config.get("stage6_account_skill_package", {})
    required_files = {"SKILL.md", *[str(item) for item in contract.get("required_references", [])]}
    for directory in ("references", "scripts", "agents", "proposals"):
        source_directory = source_root / directory
        if source_directory.is_dir():
            required_files.update(
                path.relative_to(source_root).as_posix()
                for path in source_directory.rglob("*")
                if _candidate_resource_allowed(path)
            )
    copied: list[str] = []
    preserved: list[str] = []
    for relative in sorted(required_files):
        source = source_root / relative
        target = target_root / relative
        if not source.exists():
            return {
                "ok": False,
                "workflow_id": _safe_id(workflow_id),
                "error": f"formal_account_skill_missing:{relative}",
                "source_skill": str(source_skill.relative_to(root)),
            }
        if target.exists() and not force:
            preserved.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative)

    source_account_root = source_root.parent
    formal_compatibility = source_root / "UPGRADE_COMPATIBILITY.json"
    if not formal_compatibility.is_file():
        return {
            "ok": False,
            "workflow_id": _safe_id(workflow_id),
            "error": "formal_account_skill_upgrade_compatibility_missing",
            "source_skill": str(source_skill.relative_to(root)),
        }
    method_index = source_account_root / "METHOD_INDEX.json"
    method_snapshot = target_root / "references" / "formal-method-index.json"
    if method_index.is_file():
        if force or not method_snapshot.exists():
            method_snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(method_index, method_snapshot)
            copied.append("references/formal-method-index.json")
        else:
            preserved.append("references/formal-method-index.json")
    for relative in [str(item) for item in contract.get("required_account_views", [])]:
        filename = Path(relative).name
        source = source_account_root / filename
        target = target_root / relative
        if not source.exists():
            return {
                "ok": False,
                "workflow_id": _safe_id(workflow_id),
                "error": f"formal_account_view_missing:{filename}",
                "source_skill": str(source_skill.relative_to(root)),
            }
        if target.exists() and not force:
            preserved.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative)

    verified, errors = _read_jsonl(workflow_root(root, workflow_id) / "verified.jsonl")
    if errors:
        return {"ok": False, "workflow_id": _safe_id(workflow_id), "errors": errors}
    manifest_path = target_root / "ACCOUNT_SKILL_MANIFEST.json"
    if force or not manifest_path.exists():
        _write_json(
            manifest_path,
            {
                "schema_version": str(contract.get("schema_id") or "account_skill_candidate_v1"),
                "status": "ready_for_review",
                "workflow_id": state["workflow_id"],
                "account_name": state["account_name"],
                "account_skill_id": resolved.get("account_skill_id", ""),
                "account_skill_version": resolved.get("version", ""),
                "pipeline_version": str(config.get("version") or ""),
                "source_method_ids": sorted(str(item.get("id")) for item in verified if item.get("id")),
                "formal_write": False,
                "callable": False,
                "user_review_required": True,
                "migration": {
                    "type": "backfill_from_approved_formal_account_skill",
                    "source_skill": str(source_skill.relative_to(root)),
                    "migrated_at": now_iso(),
                },
            },
        )
        copied.append("ACCOUNT_SKILL_MANIFEST.json")
    else:
        preserved.append("ACCOUNT_SKILL_MANIFEST.json")

    compatibility_path = target_root / "UPGRADE_COMPATIBILITY.json"
    if force or not compatibility_path.exists():
        try:
            candidate_compatibility = _candidate_compatibility_from_formal(
                root,
                workflow_id=workflow_id,
                source_root=source_root,
                source_account_root=source_account_root,
                target_root=target_root,
            )
        except FileNotFoundError as exc:
            return {
                "ok": False,
                "workflow_id": _safe_id(workflow_id),
                "error": str(exc),
                "source_skill": str(source_skill.relative_to(root)),
            }
        _write_json(compatibility_path, candidate_compatibility)
        copied.append("UPGRADE_COMPATIBILITY.json")
    else:
        preserved.append("UPGRADE_COMPATIBILITY.json")

    state["schema_version"] = str(config.get("version") or state.get("schema_version") or "")
    state["stage6_account_skill_schema"] = str(contract.get("schema_id") or "")
    state["stage6_upgrade_compatibility_schema"] = str(
        config.get("stage6_upgrade_compatibility", {}).get("schema_id") or ""
    )
    validation = validate_stage(root, workflow_id, "stage6_learning_delivery")
    for stage in state["stages"]:
        if stage.get("id") == "stage6_learning_delivery":
            stage["validation"] = validation
            break
    migrations = state.setdefault("migrations", [])
    migration_id = "backfill_account_skill_candidate_v1"
    if not any(isinstance(item, dict) and item.get("id") == migration_id for item in migrations):
        migrations.append({"id": migration_id, "completed_at": now_iso(), "source": resolved["skill_path"]})
    v29_migration_id = "backfill_account_skill_upgrade_compatibility_v29"
    if not any(isinstance(item, dict) and item.get("id") == v29_migration_id for item in migrations):
        migrations.append(
            {
                "id": v29_migration_id,
                "completed_at": now_iso(),
                "source": resolved["skill_path"],
                "mode": "same_account_formal_snapshot_only",
            }
        )
    state["updated_at"] = now_iso()
    _write_json(state_path(root, workflow_id), state)
    return {
        "ok": bool(validation.get("ok")),
        "workflow_id": state["workflow_id"],
        "account_name": state["account_name"],
        "source_skill": resolved["skill_path"],
        "copied": copied,
        "preserved": preserved,
        "validation": validation,
    }


def migrate_all_account_skill_candidates(root: Path, *, force: bool = False) -> dict[str, Any]:
    config = load_config(root)
    candidate_root = root.resolve() / Path(str(config.get("candidate_root") or DEFAULT_CANDIDATE_ROOT))
    results = []
    if candidate_root.exists():
        for state_file in sorted(candidate_root.glob("*/PIPELINE_STATE.json")):
            results.append(migrate_account_skill_candidate(root, state_file.parent.name, force=force))
    return {
        "ok": all(item.get("ok") for item in results),
        "workflow_count": len(results),
        "failed": [item.get("workflow_id", "") for item in results if not item.get("ok")],
        "results": results,
    }


def audit_all_account_learning_v29(root: Path) -> dict[str, Any]:
    """Prove every registered account has one isolated, current v2.9 learning delivery."""

    from tools.kb.account_skills import (
        audit_account_skill_v29_compatibility,
        resolve_account_skill,
    )

    root = root.resolve()
    config = load_config(root)
    candidate_root = root / Path(str(config.get("candidate_root") or DEFAULT_CANDIDATE_ROOT))
    expected_pipeline = str(
        config.get("historical_workflow_v29_migration", {}).get("pipeline_state_version_required")
        or "2.9"
    )
    expected_compatibility = str(
        config.get("stage6_upgrade_compatibility", {}).get("schema_id") or ""
    )
    formal_audit = audit_account_skill_v29_compatibility(root)
    registered_accounts = [
        item
        for item in formal_audit.get("results", [])
        if isinstance(item, dict) and item.get("account_skill_id")
    ]
    registered_tokens = {
        str(item.get("account_skill_id") or ""): str(item.get("account_name") or "")
        for item in registered_accounts
    }
    results: list[dict[str, Any]] = []
    seen_account_ids: set[str] = set()
    duplicate_account_ids: set[str] = set()
    cross_account_token_leaks: list[dict[str, str]] = []
    semantic_hash_owners: dict[str, list[dict[str, str]]] = {}
    semantic_relative_paths = (
        "skill/SKILL.md",
        "skill/references/production.md",
        "skill/references/style.md",
        "skill/references/boundaries.md",
        "skill/references/acceptance.md",
        "skill/references/publishing-copy.md",
        "账号整体方法论.md",
        "内容生产使用说明.md",
        "减少AI味输出规则.md",
        "内容输出标准模板.md",
    )
    for state_file in sorted(candidate_root.glob("*/PIPELINE_STATE.json")) if candidate_root.is_dir() else []:
        state = _read_json(state_file)
        workflow_id = str(state.get("workflow_id") or state_file.parent.name)
        account_name = str(state.get("account_name") or "")
        errors: list[str] = []
        if str(state.get("schema_version") or "") != expected_pipeline:
            errors.append(f"pipeline_version_mismatch:{state.get('schema_version', '')}:{expected_pipeline}")
        if str(state.get("stage6_upgrade_compatibility_schema") or "") != expected_compatibility:
            errors.append("stage6_upgrade_compatibility_schema_missing")
        deferred_evidence_count = 0
        deferred_evidence_isolated = True
        if "deferred_evidence" in str(state.get("status") or ""):
            acceptance_summary_path = state_file.parent / "REAL_ACCEPTANCE_SUMMARY.json"
            if not acceptance_summary_path.is_file():
                errors.append("deferred_evidence_acceptance_summary_missing")
                deferred_evidence_isolated = False
            else:
                acceptance_summary = _read_json(acceptance_summary_path)
                overview_scope = acceptance_summary.get("overview_scope", {})
                expanded_audit = acceptance_summary.get("expanded_audit", {})
                semantic = acceptance_summary.get("semantic_consistency", {})
                deferred_evidence_count = int(overview_scope.get("deferred_evidence", 0) or 0)
                total = int(overview_scope.get("source_total", 0) or 0)
                learned = int(overview_scope.get("deep_learned", 0) or 0)
                deferred_evidence_isolated = (
                    acceptance_summary.get("status") == "passed"
                    and deferred_evidence_count > 0
                    and learned + deferred_evidence_count == total
                    and expanded_audit.get("completed") is True
                    and int(expanded_audit.get("records_scanned", 0) or 0) == learned
                    and semantic.get("passed") is True
                    and int(semantic.get("conflict_count", 0) or 0) == 0
                )
                if not deferred_evidence_isolated:
                    errors.append("deferred_evidence_not_isolated_or_fully_audited")
        workflow_validation = validate_workflow(root, workflow_id)
        if not workflow_validation.get("ok"):
            errors.extend(
                f"workflow_stage_invalid:{stage_id}"
                for stage_id in workflow_validation.get("completed_stage_failures", [])
            )

        resolved = resolve_account_skill(root, account_name)
        if not resolved.get("ok"):
            errors.append("formal_account_skill_not_resolved")
            results.append(
                {
                    "ok": False,
                    "workflow_id": workflow_id,
                    "account_name": account_name,
                    "errors": errors,
                }
            )
            continue
        account_skill_id = str(resolved.get("account_skill_id") or "")
        if account_skill_id in seen_account_ids:
            duplicate_account_ids.add(account_skill_id)
        seen_account_ids.add(account_skill_id)
        source_skill = root / str(resolved["skill_path"])
        source_root = source_skill.parent
        source_account_root = source_root.parent
        target_root = state_file.parent / "account_skill_candidate"
        for relative in semantic_relative_paths:
            semantic_path = source_account_root / relative
            if not semantic_path.is_file():
                continue
            semantic_text = semantic_path.read_text(encoding="utf-8", errors="ignore")
            for other_id, other_name in registered_tokens.items():
                if other_id == account_skill_id:
                    continue
                for token in (other_id, other_name):
                    if token and len(token) >= 3 and token in semantic_text:
                        cross_account_token_leaks.append(
                            {
                                "account_skill_id": account_skill_id,
                                "path": semantic_path.relative_to(root).as_posix(),
                                "foreign_account_skill_id": other_id,
                                "token": token,
                            }
                        )
            semantic_hash_owners.setdefault(_sha256_file(semantic_path), []).append(
                {
                    "account_skill_id": account_skill_id,
                    "path": semantic_path.relative_to(root).as_posix(),
                }
            )
        proposal_root = source_root / "proposals"
        for proposal_path in (
            sorted(proposal_root.rglob("*.md")) if proposal_root.is_dir() else []
        ):
            proposal_text = proposal_path.read_text(encoding="utf-8", errors="ignore")
            for other_id, other_name in registered_tokens.items():
                if other_id == account_skill_id:
                    continue
                for token in (other_id, other_name):
                    if token and len(token) >= 3 and token in proposal_text:
                        cross_account_token_leaks.append(
                            {
                                "account_skill_id": account_skill_id,
                                "path": proposal_path.relative_to(root).as_posix(),
                                "foreign_account_skill_id": other_id,
                                "token": token,
                            }
                        )
        candidate_manifest = _read_json(target_root / "ACCOUNT_SKILL_MANIFEST.json")
        if candidate_manifest.get("account_skill_id") != account_skill_id:
            errors.append("candidate_account_skill_id_mismatch")
        if str(candidate_manifest.get("account_skill_version") or "") != str(resolved.get("version") or ""):
            errors.append("candidate_account_skill_version_mismatch")
        if str(candidate_manifest.get("pipeline_version") or "") != expected_pipeline:
            errors.append("candidate_pipeline_version_mismatch")

        synchronized_files: list[str] = []
        for source in [source_skill]:
            target = target_root / source.relative_to(source_root)
            synchronized_files.append(source.relative_to(root).as_posix())
            if not target.is_file() or _sha256_file(source) != _sha256_file(target):
                errors.append(f"candidate_learning_snapshot_mismatch:{source.relative_to(source_root).as_posix()}")
        for directory in ("references", "scripts", "agents", "proposals"):
            source_directory = source_root / directory
            if not source_directory.is_dir():
                continue
            for source in sorted(path for path in source_directory.rglob("*") if _candidate_resource_allowed(path)):
                relative = source.relative_to(source_root)
                target = target_root / relative
                synchronized_files.append(source.relative_to(root).as_posix())
                if not target.is_file() or _sha256_file(source) != _sha256_file(target):
                    errors.append(f"candidate_learning_snapshot_mismatch:{relative.as_posix()}")
        for filename in (
            "账号整体方法论.md",
            "内容生产使用说明.md",
            "减少AI味输出规则.md",
            "内容输出标准模板.md",
        ):
            source = source_account_root / filename
            target = target_root / "account_views" / filename
            if not source.is_file() or not target.is_file() or _sha256_file(source) != _sha256_file(target):
                errors.append(f"candidate_account_view_mismatch:{filename}")
        method_index = source_account_root / "METHOD_INDEX.json"
        method_snapshot = target_root / "references" / "formal-method-index.json"
        if not method_index.is_file() or not method_snapshot.is_file() or _sha256_file(method_index) != _sha256_file(method_snapshot):
            errors.append("candidate_formal_method_index_mismatch")

        compatibility = _read_json(target_root / "UPGRADE_COMPATIBILITY.json")
        if compatibility.get("account_skill_id") != account_skill_id:
            errors.append("candidate_upgrade_compatibility_account_mismatch")
        if str(compatibility.get("target_version") or "") != str(resolved.get("version") or ""):
            errors.append("candidate_upgrade_compatibility_version_mismatch")
        garbage = sorted(
            path.relative_to(root).as_posix()
            for base in (source_root, target_root)
            for path in base.rglob("*")
            if path.is_file()
            and ("__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"} or path.name == ".DS_Store")
        )
        errors.extend(f"generated_garbage:{path}" for path in garbage)
        results.append(
            {
                "ok": not errors,
                "workflow_id": workflow_id,
                "account_name": account_name,
                "account_skill_id": account_skill_id,
                "account_skill_version": resolved.get("version", ""),
                "pipeline_version": state.get("schema_version", ""),
                "learning_snapshot_file_count": len(synchronized_files),
                "deferred_evidence_count": deferred_evidence_count,
                "deferred_evidence_isolated": deferred_evidence_isolated,
                "errors": errors,
            }
        )

    registered_ids = {
        str(item.get("account_skill_id") or "")
        for item in formal_audit.get("results", [])
        if isinstance(item, dict) and item.get("account_skill_id")
    }
    missing_workflows = sorted(registered_ids - seen_account_ids)
    extra_workflows = sorted(seen_account_ids - registered_ids)
    formal_compatibility_ok = bool(formal_audit.get("ok")) if registered_ids else not results
    cross_account_template_collisions = [
        {"sha256": digest, "owners": owners}
        for digest, owners in sorted(semantic_hash_owners.items())
        if len({item["account_skill_id"] for item in owners}) > 1
    ]
    return {
        "ok": (bool(results) or not registered_ids)
        and all(item.get("ok") for item in results)
        and formal_compatibility_ok
        and not missing_workflows
        and not extra_workflows
        and not duplicate_account_ids
        and not cross_account_token_leaks
        and not cross_account_template_collisions,
        "pipeline_version": expected_pipeline,
        "registered_account_count": len(registered_ids),
        "workflow_count": len(results),
        "passed_count": sum(1 for item in results if item.get("ok")),
        "formal_compatibility_passed_count": formal_audit.get("passed_count", 0),
        "missing_workflows": missing_workflows,
        "extra_workflows": extra_workflows,
        "duplicate_account_skill_ids": sorted(duplicate_account_ids),
        "cross_account_token_leaks": cross_account_token_leaks,
        "cross_account_template_collisions": cross_account_template_collisions,
        "failed": [item["workflow_id"] for item in results if not item.get("ok")],
        "results": results,
    }


def refresh_workflow(root: Path, workflow_id: str, *, source_scope: str = "") -> dict[str, Any]:
    """Refresh stored validation evidence after a candidate-only workflow is rebuilt."""

    root = root.resolve()
    config = load_config(root)
    state = load_state(root, workflow_id)
    state["schema_version"] = str(config.get("version") or "2.6")
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


def upgrade_expression_asset_lane(
    root: Path,
    workflow_id: str,
    *,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Enable the new lane inside an existing workflow without creating a second workflow."""

    root = root.resolve()
    config = load_config(root)
    state = load_state(root, workflow_id)
    lane = config.get("expression_asset_learning", {})
    schema_id = str(lane.get("schema_id") or "")
    contract_version = str(lane.get("contract_version") or "")
    if not schema_id or not contract_version:
        return {"ok": False, "error": "expression_asset_learning_contract_missing"}
    if state.get("expression_asset_schema") == schema_id:
        return {
            "ok": True,
            "already_enabled": True,
            "workflow_id": state.get("workflow_id"),
            "same_workflow": True,
            "stage_count": len(state.get("stages", [])),
        }
    if not user_confirmed:
        return {
            "ok": False,
            "error": "user_confirmation_required",
            "workflow_id": state.get("workflow_id"),
            "same_workflow": True,
            "planned_schema": schema_id,
        }
    before_payload = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    before_stages = [
        {"id": item.get("id"), "status": item.get("status"), "completed_at": item.get("completed_at", "")}
        for item in state.get("stages", [])
        if isinstance(item, dict)
    ]
    base = workflow_root(root, workflow_id)
    (base / str(lane.get("root") or "expression_assets")).mkdir(parents=True, exist_ok=True)
    state["schema_version"] = str(config.get("version") or state.get("schema_version") or "")
    state["account_id"] = str(
        state.get("account_id")
        or _account_scope_id(
            str(state.get("profile_id") or ""),
            str(state.get("workflow_id") or workflow_id),
        )
    )
    state["expression_asset_schema"] = schema_id
    state["expression_asset_contract_version"] = contract_version
    state["expression_asset_upgrade"] = {
        "status": "pending_backfill",
        "same_workflow": True,
        "previous_state_sha256": hashlib.sha256(before_payload).hexdigest(),
        "previous_stages": before_stages,
        "enabled_at": now_iso(),
        "formal_write": False,
        "account_assets_generated": False,
    }
    state["updated_at"] = now_iso()
    _write_json(state_path(root, workflow_id), state)
    (base / "WORKFLOW_PLAN.md").write_text(_render_plan(config, state), encoding="utf-8")
    return {
        "ok": True,
        "workflow_id": state["workflow_id"],
        "same_workflow": True,
        "stage_count": len(state.get("stages", [])),
        "expression_asset_schema": schema_id,
        "status": "pending_backfill",
        "formal_write_allowed": False,
        "account_assets_generated": False,
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
    expression_upgrade = subparsers.add_parser("upgrade-expression-assets")
    expression_upgrade.add_argument("--workflow-id", required=True)
    expression_upgrade.add_argument("--user-confirmed", action="store_true")
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
        elif args.command == "upgrade-expression-assets":
            result = upgrade_expression_asset_lane(
                root,
                args.workflow_id,
                user_confirmed=args.user_confirmed,
            )
        else:
            result = complete_stage(root, args.workflow_id, args.stage, user_confirmed=args.user_confirmed)
    except (FileNotFoundError, FileExistsError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
