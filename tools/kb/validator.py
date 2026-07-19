from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import (
    EVIDENCE_INDEX_DIR,
    SYSTEM_CONFIG_DIR,
    SYSTEM_INDEX_DIR,
    SYSTEM_RULES_DIR,
    SYSTEM_SKILL_PACKAGES_DIR,
    now_iso,
    skill_proposals_dir,
)
from .account_skills import validate_registry
from .distribution import audit_distribution
from .skill_package import installed_skill_package_status, skill_package_drift
from .system_cleaner import audit_system_boundaries, load_account_tokens
from .user_layer import validate_user_layer


REQUIRED_FILES = (
    "知识库入口.md",
    "README.md",
    "00_System/shareable/docs/project_use/项目调用规则.md",
    "00_System/shareable/docs/project_use/用户操作台.md",
    "00_System/shareable/docs/project_use/本机使用速查.md",
    "00_System/shareable/docs/project_use/系统升级3.0记录.md",
    "00_System/shareable/docs/project_use/系统升级3.1记录.md",
    "00_System/shareable/docs/releases/3.1.0.md",
    f"{SYSTEM_RULES_DIR}/初始化生命周期.md",
    f"{SYSTEM_RULES_DIR}/输出契约.md",
    f"{SYSTEM_CONFIG_DIR}/output_contracts.json",
    f"{SYSTEM_CONFIG_DIR}/account_learning_pipeline.json",
    f"{SYSTEM_CONFIG_DIR}/account_learning_card_contract.json",
    f"{SYSTEM_CONFIG_DIR}/content_classification_defaults.json",
    f"{SYSTEM_CONFIG_DIR}/formal_retrieval.json",
    f"{SYSTEM_CONFIG_DIR}/expression_asset_contract.json",
    f"{SYSTEM_CONFIG_DIR}/system_version.json",
    f"{SYSTEM_CONFIG_DIR}/search_terms.json",
    f"{SYSTEM_CONFIG_DIR}/skill_contract.json",
    f"{SYSTEM_CONFIG_DIR}/layer_map.json",
    f"{SYSTEM_CONFIG_DIR}/user_layer_schema.json",
    f"{SYSTEM_CONFIG_DIR}/account_skill_contract.json",
    f"{SYSTEM_CONFIG_DIR}/production_memory_schema.json",
    f"{SYSTEM_RULES_DIR}/规则权威源.md",
    f"{SYSTEM_INDEX_DIR}/controller_routes.json",
    f"{EVIDENCE_INDEX_DIR}/knowledge_index.json",
    f"{EVIDENCE_INDEX_DIR}/knowledge_index_summary.md",
    f"{EVIDENCE_INDEX_DIR}/formal_knowledge_index.json",
    f"{EVIDENCE_INDEX_DIR}/candidate_asset_index.json",
    f"{EVIDENCE_INDEX_DIR}/raw_blocked_index.json",
    f"{EVIDENCE_INDEX_DIR}/account_knowledge_index.json",
    f"{EVIDENCE_INDEX_DIR}/account_knowledge_index.md",
    f"{SYSTEM_INDEX_DIR}/task_entry_index.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/SKILL.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/agents/openai.yaml",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/references/calling-rules.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base-zh/SKILL.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base-zh/agents/openai.yaml",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base-zh/references/calling-rules.md",
    "00_System/shareable/skills/active/content-processing/SKILL.md",
    "00_System/shareable/skills/active/content-processing/agents/openai.yaml",
    "00_System/shareable/skills/active/content-processing/references/json-cleaning.md",
    "00_System/shareable/skills/active/content-processing/references/deduplication.md",
    "00_System/shareable/skills/active/account-learning/SKILL.md",
    "00_System/shareable/skills/active/account-learning/agents/openai.yaml",
    "00_System/shareable/skills/active/account-learning/references/unified-learning-card-standard.md",
    "00_System/shareable/skills/active/account-learning/references/professional-extraction-validation.md",
    "00_System/shareable/skills/active/account-learning/references/capability-preserving-upgrades.md",
    "00_System/shareable/skills/active/account-learning/references/expression-asset-learning.md",
    "00_System/shareable/skills/active/content-review/SKILL.md",
    "00_System/shareable/skills/active/content-review/agents/openai.yaml",
    "00_System/shareable/skills/rollback.md",
    "20_User/config/account_skill_registry.json",
    "20_User/config/production_defaults.json",
    "20_User/config/review_defaults.json",
)


def validate_system(root: Path, write_report: bool = False) -> dict[str, Any]:
    root = root.resolve()
    failed = []
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            failed.append(f"missing:{relative}")
    entry_text = read_text(root / "知识库入口.md")
    project_use_text = read_text(root / "00_System" / "shareable" / "docs" / "project_use" / "项目调用规则.md")
    skill_text = read_text(root / SYSTEM_SKILL_PACKAGES_DIR / "knowledge-base" / "SKILL.md")
    skill_ui_text = read_text(root / SYSTEM_SKILL_PACKAGES_DIR / "knowledge-base" / "agents" / "openai.yaml")
    zh_skill_text = read_text(root / SYSTEM_SKILL_PACKAGES_DIR / "knowledge-base-zh" / "SKILL.md")
    zh_skill_ui_text = read_text(root / SYSTEM_SKILL_PACKAGES_DIR / "knowledge-base-zh" / "agents" / "openai.yaml")
    task_index_text = read_text(root / SYSTEM_INDEX_DIR / "task_entry_index.md")
    user_console_text = read_text(root / "00_System" / "shareable" / "docs" / "project_use" / "用户操作台.md")
    knowledge_summary_text = read_text(root / EVIDENCE_INDEX_DIR / "knowledge_index_summary.md")
    output_contract_text = read_text(root / SYSTEM_RULES_DIR / "输出契约.md")
    controller = load_json(root / SYSTEM_INDEX_DIR / "controller_routes.json", failed, "controller_routes_invalid_json")
    output_contracts = load_json(root / SYSTEM_CONFIG_DIR / "output_contracts.json", failed, "output_contracts_invalid_json")
    account_learning_pipeline = load_json(
        root / SYSTEM_CONFIG_DIR / "account_learning_pipeline.json",
        failed,
        "account_learning_pipeline_invalid_json",
    )
    account_learning_card_contract = load_json(
        root / SYSTEM_CONFIG_DIR / "account_learning_card_contract.json",
        failed,
        "account_learning_card_contract_invalid_json",
    )
    account_skill_contract = load_json(
        root / SYSTEM_CONFIG_DIR / "account_skill_contract.json",
        failed,
        "account_skill_contract_invalid_json",
    )
    formal_retrieval = load_json(
        root / SYSTEM_CONFIG_DIR / "formal_retrieval.json",
        failed,
        "formal_retrieval_invalid_json",
    )
    expression_asset_contract = load_json(
        root / SYSTEM_CONFIG_DIR / "expression_asset_contract.json",
        failed,
        "expression_asset_contract_invalid_json",
    )
    system_version = load_json(
        root / SYSTEM_CONFIG_DIR / "system_version.json",
        failed,
        "system_version_invalid_json",
    )
    search_terms = load_json(root / SYSTEM_CONFIG_DIR / "search_terms.json", failed, "search_terms_invalid_json")
    skill_contract = load_json(root / SYSTEM_CONFIG_DIR / "skill_contract.json", failed, "skill_contract_invalid_json")
    layer_map = load_json(root / SYSTEM_CONFIG_DIR / "layer_map.json", failed, "layer_map_invalid_json")
    account_index = load_json(root / EVIDENCE_INDEX_DIR / "account_knowledge_index.json", failed, "account_index_invalid_json")
    raw_blocked_index = load_json(root / EVIDENCE_INDEX_DIR / "raw_blocked_index.json", failed, "raw_blocked_index_invalid_json")
    if "索引" not in entry_text:
        failed.append("entry_missing_index_first_rule")
    if "controller_routes.json" not in entry_text:
        failed.append("entry_missing_controller_route")
    if "@知识库 + 你的需求" not in user_console_text:
        failed.append("user_console_missing_simple_entry")
    if "controller_routes.json" not in task_index_text:
        failed.append("task_index_missing_controller_route")
    if f"{SYSTEM_INDEX_DIR}/task_entry_index.md" not in knowledge_summary_text:
        failed.append("knowledge_summary_missing_task_entry_index")
    if f"{SYSTEM_RULES_DIR}/用户操作台.md" in knowledge_summary_text:
        failed.append("knowledge_summary_contains_retired_user_console_path")
    if "输出契约" not in output_contract_text:
        failed.append("output_contract_doc_missing_title")
    validate_system_skill_docs(root, failed)
    validate_account_learning_pipeline(account_learning_pipeline, failed)
    validate_account_learning_card_contract(account_learning_card_contract, failed)
    validate_account_skill_contract(account_skill_contract, failed)
    validate_formal_retrieval(formal_retrieval, failed)
    validate_expression_asset_contract(expression_asset_contract, failed)
    validate_system_version(root, system_version, failed)
    validate_raw_blocked_index(raw_blocked_index, failed)
    if "禁止全盘扫库" not in project_use_text and "禁止全量扫库" not in project_use_text:
        failed.append("project_use_missing_no_full_scan_rule")
    if "数据" not in project_use_text:
        failed.append("project_use_missing_data_protection")
    if "full-library scans" not in skill_text and "scan the whole knowledge base" not in skill_text and "全盘扫库" not in skill_text:
        failed.append("skill_missing_no_full_scan_rule")
    if "数据/" not in skill_text:
        failed.append("skill_missing_data_protection")
    if "controller_routes.json" not in skill_text:
        failed.append("skill_missing_controller_route")
    if "display_name: \"知识库\"" not in skill_ui_text:
        failed.append("skill_ui_missing_knowledge_base_display_name")
    if "总控" not in skill_ui_text:
        failed.append("skill_ui_missing_controller_wording")
    if "@知识库" not in zh_skill_text:
        failed.append("zh_skill_missing_at_knowledge_base_trigger")
    if "controller_routes.json" not in zh_skill_text:
        failed.append("zh_skill_missing_controller_route")
    if "display_name: \"知识库\"" not in zh_skill_ui_text:
        failed.append("zh_skill_ui_missing_knowledge_base_display_name")
    if "总控" not in zh_skill_ui_text:
        failed.append("zh_skill_ui_missing_controller_wording")
    route_summary = validate_controller_routes(controller, failed) if controller else {"route_count": 0, "agent_count": 0}
    contract_summary = validate_output_contracts(output_contracts, failed) if output_contracts else {"contract_count": 0}
    if search_terms:
        validate_search_terms(search_terms, failed)
    if layer_map:
        validate_layer_map(layer_map, failed)
    user_layer_result = validate_user_layer(root)
    failed.extend(user_layer_result.get("errors", []))
    account_skill_registry_result = validate_registry(root)
    for error in account_skill_registry_result.get("errors", []):
        if error not in failed:
            failed.append(error)
    boundary_result = audit_system_boundaries(root)
    for item in boundary_result.get("violations", []):
        failed.append(f"system_boundary:{item['type']}:{item['path']}:{item['token']}")
    for item in boundary_result.get("legacy_path_references", []):
        failed.append(f"legacy_path_reference:{item['path']}")
    if (root / SYSTEM_CONFIG_DIR / "skill_contract.json").exists():
        for relative in skill_package_drift(root):
            failed.append(f"skill_package_drift:{relative}")
    portability = validate_shareable_portability(root)
    for item in portability["legacy_references"]:
        failed.append(f"shareable_legacy_reference:{item['path']}:{item['token']}")
    for item in portability["absolute_paths"]:
        failed.append(f"shareable_absolute_path:{item['path']}:{item['token']}")
    workflow_result = validate_account_learning_workflows(root)
    for item in workflow_result["invalid"]:
        failed.append(f"account_learning_workflow_invalid:{item['workflow_id']}:{','.join(item['failures'])}")
    v29_audit = workflow_result["v29_audit"]
    if not v29_audit.get("ok"):
        v29_failures_before = len(failed)
        for workflow_id in v29_audit.get("failed", []):
            failed.append(f"account_learning_v29_workflow_invalid:{workflow_id}")
        for account_skill_id in v29_audit.get("missing_workflows", []):
            failed.append(f"account_learning_v29_workflow_missing:{account_skill_id}")
        for account_skill_id in v29_audit.get("extra_workflows", []):
            failed.append(f"account_learning_v29_workflow_extra:{account_skill_id}")
        for account_skill_id in v29_audit.get("duplicate_account_skill_ids", []):
            failed.append(f"account_learning_v29_workflow_duplicate:{account_skill_id}")
        for item in v29_audit.get("cross_account_token_leaks", []):
            failed.append(
                "account_learning_cross_account_token_leak:"
                f"{item.get('account_skill_id', '')}:{item.get('path', '')}:"
                f"{item.get('foreign_account_skill_id', '')}"
            )
        for item in v29_audit.get("cross_account_template_collisions", []):
            failed.append(f"account_learning_cross_account_template_collision:{item.get('sha256', '')}")
        if len(failed) == v29_failures_before:
            failed.append("account_learning_v29_audit_invalid")
    installed_skills = installed_skill_package_status(root)
    enforce_global_install = bool(skill_contract.get("global_install_required")) and (root / ".git").exists()
    if enforce_global_install and not installed_skills.get("bound_to_root"):
        failed.append("installed_skill_not_bound_to_current_root")
    if enforce_global_install and not installed_skills.get("ok"):
        for relative in installed_skills.get("drift", []):
            failed.append(f"installed_skill_drift:{relative}")
        for relative in installed_skills.get("locator_drift", []):
            failed.append(f"installed_skill_locator_drift:{relative}")
    tooling_result = validate_active_tooling(root)
    failed.extend(tooling_result["errors"])
    formal_scope = validate_formal_layer_scope(root)
    failed.extend(f"formal_layer_out_of_scope:{item}" for item in formal_scope["out_of_scope"])
    account_structure = validate_account_structure_and_index(root, account_index)
    failed.extend(account_structure["errors"])
    process_residue = validate_retired_process_residue(root)
    failed.extend(process_residue["errors"])
    candidate_hygiene = validate_candidate_layer_hygiene(root)
    failed.extend(candidate_hygiene["errors"])
    distribution = audit_distribution(root)
    failed.extend(distribution["errors"])
    health = build_health_summary(root, account_index, route_summary)
    health["account_skill_count"] = account_skill_registry_result.get("registered", 0)
    health["production_memory_ok"] = user_layer_result.get("production_memory", {}).get("ok", False)
    health["system_boundary_violation_count"] = len(boundary_result.get("violations", []))
    health["legacy_path_reference_count"] = len(boundary_result.get("legacy_path_references", []))
    health["shareable_legacy_reference_count"] = len(portability["legacy_references"])
    health["shareable_absolute_path_count"] = len(portability["absolute_paths"])
    health["account_learning_workflow_count"] = workflow_result["workflow_count"]
    health["invalid_account_learning_workflow_count"] = len(workflow_result["invalid"])
    health["account_learning_v29_passed_count"] = v29_audit.get("passed_count", 0)
    health["account_learning_v29_registered_count"] = v29_audit.get("registered_account_count", 0)
    health["account_learning_v29_deferred_evidence_count"] = sum(
        int(item.get("deferred_evidence_count", 0) or 0)
        for item in v29_audit.get("results", [])
        if isinstance(item, dict)
    )
    health["account_learning_v29_deferred_isolated"] = all(
        item.get("deferred_evidence_isolated") is True
        for item in v29_audit.get("results", [])
        if isinstance(item, dict) and int(item.get("deferred_evidence_count", 0) or 0) > 0
    )
    health["account_learning_cross_account_token_leak_count"] = len(
        v29_audit.get("cross_account_token_leaks", [])
    )
    health["account_learning_template_collision_count"] = len(
        v29_audit.get("cross_account_template_collisions", [])
    )
    health["global_skill_status"] = installed_skills.get("status", "unknown")
    health["global_skill_bound_to_root"] = bool(installed_skills.get("bound_to_root"))
    health["active_account_specific_tool_count"] = tooling_result["account_specific_file_count"]
    health["formal_layer_out_of_scope_count"] = len(formal_scope["out_of_scope"])
    health["account_index_missing_path_count"] = account_structure["missing_path_count"]
    health["account_structure_error_count"] = len(account_structure["errors"])
    health["retired_process_residue_count"] = len(process_residue["paths"])
    health["candidate_test_artifact_count"] = len(candidate_hygiene["paths"])
    health["distribution_portable"] = distribution["portable"]
    health["open_source_ready"] = distribution["open_source_ready"]
    health["legal_release_blocker"] = distribution["legal_release_blocker"]
    health.update(contract_summary)
    result = {"ok": not failed, "failed": failed, "health": health}
    if write_report:
        report_dir = runtime_path(root, "reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "latest_system_validation_report.md"
        report_path.write_text(render_validation_report(failed, health), encoding="utf-8")
        result["report"] = str(report_path.relative_to(root))
    return result


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_json(path: Path, failed: list[str], failure_code: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        failed.append(failure_code)
        return {}
    if not isinstance(payload, dict):
        failed.append(failure_code)
        return {}
    return payload


def validate_system_skill_docs(root: Path, failed: list[str]) -> None:
    """Validate the split Skill references instead of a retired monolithic workflow file."""

    documents = {
        "account_skill": read_text(root / "00_System/shareable/skills/active/account-learning/SKILL.md"),
        "gates": read_text(root / "00_System/shareable/skills/active/account-learning/references/seven-stage-gates.md"),
        "professional": read_text(
            root / "00_System/shareable/skills/active/account-learning/references/professional-extraction-validation.md"
        ),
        "card": read_text(
            root / "00_System/shareable/skills/active/account-learning/references/unified-learning-card-standard.md"
        ),
        "packaging": read_text(
            root / "00_System/shareable/skills/active/account-learning/references/account-skill-packaging.md"
        ),
        "upgrades": read_text(
            root / "00_System/shareable/skills/active/account-learning/references/capability-preserving-upgrades.md"
        ),
        "expression_assets": read_text(
            root / "00_System/shareable/skills/active/account-learning/references/expression-asset-learning.md"
        ),
        "processing": read_text(root / "00_System/shareable/skills/active/content-processing/references/pipeline.md"),
    }
    required_phrases = {
        "account_skill_missing_seven_stage_reference": ("account_skill", "seven-stage-gates.md"),
        "account_skill_missing_candidate_only_boundary": ("account_skill", "候选"),
        "account_gates_missing_account_overview": ("gates", "整体理解"),
        "account_gates_missing_triple_verification": ("gates", "三重验证"),
        "account_gates_missing_pressure_test": ("gates", "压力测试"),
        "account_professional_missing_rejected_audit": ("professional", "rejected.jsonl"),
        "account_professional_missing_candidate_clusters": ("professional", "candidate_clusters.jsonl"),
        "account_professional_missing_test_hash": ("professional", "提示集哈希"),
        "account_card_missing_contract": ("card", "unified_three_layer_v2"),
        "account_card_missing_three_layers": ("card", "## 一、三层结构"),
        "account_packaging_missing_manifest": ("packaging", "ACCOUNT_SKILL_MANIFEST.json"),
        "account_packaging_missing_upgrade_manifest": ("packaging", "UPGRADE_COMPATIBILITY.json"),
        "account_packaging_missing_callable_boundary": ("packaging", "callable=false"),
        "account_upgrade_missing_no_loss_rule": ("upgrades", "previous_capability_ids"),
        "account_upgrade_missing_cross_account_boundary": ("upgrades", "跨账号能力合并"),
        "account_upgrade_missing_multi_image_mother": ("upgrades", "continuity_mother_asset_id"),
        "account_upgrade_missing_formal_v29_audit": ("upgrades", "account-skills-v29-audit"),
        "account_upgrade_missing_all_account_v29_audit": ("upgrades", "account-learning-v29-audit"),
        "account_expression_missing_single_workflow_boundary": ("expression_assets", "不是第二套工作流"),
        "account_expression_missing_mid_content_hooks": ("expression_assets", "内容过程"),
        "account_expression_missing_source_generation_boundary": ("expression_assets", "原文永远不可作为生成输入"),
        "content_processing_missing_rough_pool": ("processing", "完整粗学与选题池"),
        "content_processing_missing_deep_plan": ("processing", "deep_learning_plan.json"),
    }
    for failure, (document, phrase) in required_phrases.items():
        if phrase not in documents[document]:
            failed.append(failure)


def validate_shareable_portability(root: Path) -> dict[str, list[dict[str, str]]]:
    base = root / "00_System" / "shareable"
    legacy_tokens = (
        "14_KB_System",
        "13_Evolving_Skills",
        "02_Viral_Methods",
        "08_Content_Factory",
        "20_User/syncable",
        "00_System/shareable/memory",
    )
    absolute_pattern = re.compile(
        r"(?:/" + r"Users/|/" + r"Volumes/|[A-Za-z]:\\\\" + r"Users\\\\)[^\s`\"']+"
    )
    legacy_references: list[dict[str, str]] = []
    absolute_paths: list[dict[str, str]] = []
    if not base.exists():
        return {"legacy_references": legacy_references, "absolute_paths": absolute_paths}
    for path in sorted(item for item in base.rglob("*") if item.is_file() and item.suffix in {".md", ".json", ".jsonl", ".yaml", ".yml", ".txt"}):
        relative = path.relative_to(root).as_posix()
        if "/skills/history/" in f"/{relative}" or "/docs/superpowers/" in f"/{relative}":
            continue
        if relative == "00_System/shareable/config/layer_map.json":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in legacy_tokens:
            if token in text:
                legacy_references.append({"path": relative, "token": token})
        for match in absolute_pattern.finditer(text):
            absolute_paths.append({"path": relative, "token": match.group(0)})
    return {"legacy_references": legacy_references, "absolute_paths": absolute_paths}


def validate_account_learning_workflows(root: Path) -> dict[str, Any]:
    from tools import account_learning_pipeline

    candidate_root = root / account_learning_pipeline.DEFAULT_CANDIDATE_ROOT
    config_path = root / account_learning_pipeline.CONFIG_PATH
    state_files = sorted(candidate_root.glob("*/PIPELINE_STATE.json")) if candidate_root.exists() else []
    invalid: list[dict[str, Any]] = []
    for state_file in state_files:
        workflow_id = state_file.parent.name
        try:
            result = account_learning_pipeline.validate_workflow(root, workflow_id)
            failures = [str(item) for item in result.get("completed_stage_failures", [])]
            if not result.get("ok"):
                invalid.append({"workflow_id": workflow_id, "failures": failures or ["validation_failed"]})
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            invalid.append({"workflow_id": workflow_id, "failures": [f"exception_{type(exc).__name__}"]})
    if not config_path.is_file():
        v29_audit = {
            "ok": True,
            "skipped": True,
            "reason": "account_learning_pipeline_config_missing",
            "registered_account_count": 0,
            "workflow_count": len(state_files),
            "passed_count": 0,
            "missing_workflows": [],
            "extra_workflows": [],
            "duplicate_account_skill_ids": [],
            "cross_account_token_leaks": [],
            "cross_account_template_collisions": [],
            "failed": [],
            "results": [],
        }
    else:
        try:
            v29_audit = account_learning_pipeline.audit_all_account_learning_v29(root)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            v29_audit = {
                "ok": False,
                "audit_error": type(exc).__name__,
                "registered_account_count": 0,
                "workflow_count": len(state_files),
                "passed_count": 0,
                "missing_workflows": [],
                "extra_workflows": [],
                "duplicate_account_skill_ids": [],
                "cross_account_token_leaks": [],
                "cross_account_template_collisions": [],
                "failed": [],
                "results": [],
            }
    return {
        "workflow_count": len(state_files),
        "invalid": invalid,
        "v29_audit": v29_audit,
    }


def validate_active_tooling(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    account_specific_files: list[str] = []
    account_tokens = load_account_tokens(root)
    source_suffixes = {".py", ".sh", ".cjs", ".js", ".ts"}
    for base_name in ("tools", "tests"):
        base = root / base_name
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file() and item.suffix in source_suffixes):
            lowered = path.name.lower()
            if any(token.lower() in lowered for token in account_tokens):
                account_specific_files.append(path.relative_to(root).as_posix())
    for relative in account_specific_files:
        errors.append(f"active_account_specific_tool:{relative}")
    forbidden_code_markers = {
        "tools/video_learning.py": ("def write_formal_entries", "formal/content_factory"),
        "tools/kb/cli.py": ("account-ingest-direction", "account-validate-cards"),
    }
    for relative, markers in forbidden_code_markers.items():
        text = read_text(root / relative)
        for marker in markers:
            if marker in text:
                errors.append(f"retired_active_code_marker:{relative}:{marker}")
    account_content_files: list[str] = []
    tools_root = root / "tools"
    if tools_root.exists():
        for path in sorted(item for item in tools_root.rglob("*") if item.is_file() and item.suffix in source_suffixes):
            text = path.read_text(encoding="utf-8", errors="ignore")
            matched = [token for token in account_tokens if token and token in text]
            if matched:
                relative = path.relative_to(root).as_posix()
                account_content_files.append(relative)
                errors.append(f"active_account_content_in_tool:{relative}:{matched[0]}")
    return {
        "errors": errors,
        "account_specific_file_count": len(account_specific_files),
        "account_specific_files": account_specific_files,
        "account_content_file_count": len(account_content_files),
        "account_content_files": account_content_files,
    }


def validate_formal_layer_scope(root: Path) -> dict[str, list[str]]:
    formal_root = root / "10_Knowledge" / "formal"
    out_of_scope: list[str] = []
    if formal_root.exists():
        for path in sorted(formal_root.iterdir()):
            if path.name not in {"accounts", "README.md"}:
                out_of_scope.append(path.relative_to(root).as_posix())
    return {"out_of_scope": out_of_scope}


def validate_account_structure_and_index(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    missing_path_count = 0
    accounts_root = root / "10_Knowledge" / "formal" / "accounts"
    actual_names: set[str] = set()
    if accounts_root.exists():
        for path in sorted(accounts_root.iterdir()):
            if path.name == "README.md":
                continue
            if not path.is_dir():
                errors.append(f"formal_accounts_unexpected_file:{path.relative_to(root).as_posix()}")
                continue
            actual_names.add(path.name)
            for required in ("ACCOUNT_SKILL_MANIFEST.json", "skill/SKILL.md"):
                if not (path / required).exists():
                    errors.append(f"formal_account_required_file_missing:{path.name}:{required}")
            if (path / "账号中心").exists():
                errors.append(f"formal_account_redundant_account_center_wrapper:{path.name}")

    discovery_errors = payload.get("discovery_errors", [])
    if isinstance(discovery_errors, list):
        errors.extend(str(item) for item in discovery_errors)
    accounts = payload.get("accounts", [])
    if not isinstance(accounts, list):
        return {
            "errors": [*errors, "account_index_accounts_invalid"],
            "missing_path_count": missing_path_count,
            "account_count": 0,
        }
    indexed_names: set[str] = set()
    indexed_ids: set[str] = set()
    for account in accounts:
        if not isinstance(account, dict):
            errors.append("account_index_item_invalid")
            continue
        account_id = str(account.get("account_id") or "")
        account_name = str(account.get("account_name") or "")
        formal_dir = str(account.get("formal_account_dir") or "")
        expected_dir = f"10_Knowledge/formal/accounts/{account_name}"
        if not account_id or account_id in indexed_ids:
            errors.append(f"account_index_id_missing_or_duplicate:{account_id}")
        indexed_ids.add(account_id)
        indexed_names.add(account_name)
        if formal_dir != expected_dir:
            errors.append(f"account_index_noncanonical_formal_dir:{account_id}:{formal_dir}")
        manifest_path = root / expected_dir / "ACCOUNT_SKILL_MANIFEST.json"
        manifest = load_json(manifest_path, errors, f"formal_account_manifest_invalid:{account_id}")
        if manifest:
            if manifest.get("account_skill_id") != account_id:
                errors.append(f"formal_account_manifest_id_mismatch:{account_id}")
            if manifest.get("account_name") != account_name:
                errors.append(f"formal_account_manifest_name_mismatch:{account_id}")
            expected_skill = f"{expected_dir}/skill/SKILL.md"
            if manifest.get("canonical_skill_path") != expected_skill:
                errors.append(f"formal_account_manifest_skill_path_mismatch:{account_id}")
        checked_paths = [formal_dir]
        for direction in account.get("directions", []) if isinstance(account.get("directions"), list) else []:
            if isinstance(direction, dict):
                checked_paths.append(str(direction.get("formal_direction_dir") or ""))
        for layer in account.get("knowledge_layers", []) if isinstance(account.get("knowledge_layers"), list) else []:
            if isinstance(layer, dict):
                checked_paths.append(str(layer.get("path") or ""))
        for relative in checked_paths:
            if not relative or not (root / relative).exists():
                missing_path_count += 1
                errors.append(f"account_index_path_missing:{account_id}:{relative}")
    for name in sorted(actual_names - indexed_names):
        errors.append(f"formal_account_missing_from_index:{name}")
    for name in sorted(indexed_names - actual_names):
        errors.append(f"account_index_orphan_account:{name}")
    return {
        "errors": errors,
        "missing_path_count": missing_path_count,
        "account_count": len(indexed_names),
    }


def validate_retired_process_residue(root: Path) -> dict[str, Any]:
    retired_paths = (
        ".playwright-cli",
        "00_System/shareable/skills/history",
        "00_System/shareable/docs/system_cleaning/2026-07-15_system_cleaning_report.md",
        "00_System/shareable/rules/子知识库创建规则.md",
        "tools/kb/web_console.py",
        "tools/kb/graph.py",
        "tools/kb/memory.py",
        "tools/kb/evolution.py",
        "tools/kb/agent_registry.py",
        "tests/test_kb_web_console.py",
        "tests/test_kb_graph.py",
    )
    paths = [relative for relative in retired_paths if (root / relative).exists()]
    retired_cache_modules = {
        "web_console",
        "graph",
        "memory",
        "evolution",
        "agent_registry",
        "test_kb_web_console",
        "test_kb_graph",
    }
    cache_paths = [
        path.relative_to(root).as_posix()
        for base in (root / "tools", root / "tests")
        if base.exists()
        for path in base.rglob("*.pyc")
        if path.name.split(".cpython", 1)[0] in retired_cache_modules
    ]
    paths.extend(cache_paths)
    errors = [f"retired_process_residue:{relative}" for relative in sorted(set(paths))]
    return {"errors": errors, "paths": sorted(set(paths))}


def validate_candidate_layer_hygiene(root: Path) -> dict[str, Any]:
    candidates_root = root / "10_Knowledge" / "candidates"
    test_markers = ("image_text_e2e_account", "image_text_kb_cli_account", "image_text_full_acceptance_account")
    paths: list[str] = []
    if candidates_root.exists():
        for path in candidates_root.rglob("*"):
            if any(marker in path.name for marker in test_markers):
                paths.append(path.relative_to(root).as_posix())
    unique = sorted(set(paths))
    return {
        "errors": [f"candidate_test_artifact:{relative}" for relative in unique],
        "paths": unique,
    }


def validate_account_learning_pipeline(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("account_learning_pipeline_missing")
        return
    if payload.get("version") != "3.0":
        failed.append("account_learning_pipeline_version_invalid")
    expected_stages = [
        "stage0_account_overview",
        "stage1_parallel_extraction",
        "stage2_triple_verification",
        "stage3_ria_construction",
        "stage4_method_linking",
        "stage5_pressure_test",
        "stage6_learning_delivery",
    ]
    stages = payload.get("stages", [])
    stage_ids = [stage.get("id") for stage in stages if isinstance(stage, dict)]
    if stage_ids != expected_stages:
        failed.append("account_learning_pipeline_stage_order_invalid")
    if payload.get("formal_write_allowed") is not False:
        failed.append("account_learning_pipeline_must_be_candidate_only")
    gates = set(payload.get("confirmation_gates", []))
    if gates != {"stage0_account_overview", "stage2_triple_verification"}:
        failed.append("account_learning_pipeline_confirmation_gates_invalid")
    verification = payload.get("verification", {})
    if verification.get("v1_min_independent_sources", 0) < 3:
        failed.append("account_learning_pipeline_v1_gate_too_weak")
    if verification.get("v1_min_relation_or_scene_types", 0) < 2:
        failed.append("account_learning_pipeline_v1_context_gate_too_weak")
    if float(verification.get("pressure_test_min_pass_rate", 0)) < 1.0:
        failed.append("account_learning_pipeline_pressure_gate_too_weak")
    if set(verification.get("required_test_types", [])) != {
        "should_trigger",
        "should_not_trigger",
        "edge_case",
        "cross_scene_transfer",
        "commercial_contamination",
    }:
        failed.append("account_learning_pipeline_test_types_invalid")
    if set(verification.get("required_negative_decoy_kinds", [])) != {"lexical_overlap_without_mechanism"}:
        failed.append("account_learning_pipeline_lexical_decoy_missing")
    if verification.get("require_prompt_set_sha256") is not True or verification.get("require_per_case_results") is not True:
        failed.append("account_learning_pipeline_test_evidence_incomplete")
    consolidation = payload.get("candidate_consolidation", {})
    if consolidation.get("artifact") != "candidate_clusters.jsonl":
        failed.append("account_learning_pipeline_cluster_artifact_missing")
    if set(consolidation.get("cluster_types", [])) != {"method_candidate", "boundary_rule", "evidence_gate"}:
        failed.append("account_learning_pipeline_cluster_types_invalid")
    lifecycle = payload.get("method_lifecycle", {})
    if lifecycle.get("candidate_layer_callable") is not False or lifecycle.get("single_card_never_callable") is not True:
        failed.append("account_learning_pipeline_callable_boundary_invalid")
    if payload.get("card_contract") != "00_System/shareable/config/account_learning_card_contract.json":
        failed.append("account_learning_pipeline_card_contract_missing")
    observation = payload.get("stage1_deep_observation", {})
    if observation.get("publish_copy_schema_id") != "publish_copy_observation_v1":
        failed.append("account_learning_pipeline_publish_copy_observation_missing")
    if observation.get("image_text_visual_schema_id") != "image_text_visual_observation_v1":
        failed.append("account_learning_pipeline_image_text_visual_observation_missing")
    if (
        observation.get("production_reference_candidate_schema_id")
        != "production_visual_reference_candidate_v1"
    ):
        failed.append("account_learning_pipeline_visual_reference_observation_missing")
    required_publish_dimensions = {
        "title_promise_and_information_gap",
        "body_information_sequence",
        "operational_or_argument_detail_density",
        "lived_experience_signal",
        "closing_mode",
        "topic_strategy",
        "publish_visual_alignment",
    }
    if not required_publish_dimensions.issubset(set(observation.get("publish_copy_dimensions", []))):
        failed.append("account_learning_pipeline_publish_copy_dimensions_incomplete")
    required_visual_dimensions = {
        "cover_hook",
        "image_role_sequence",
        "composition_and_viewpoint",
        "subject_action_and_state_change",
        "text_annotation_design",
        "typography_hierarchy",
        "authenticity_cues",
        "cross_modal_alignment",
        "save_worthiness",
        "production_reference_candidate",
    }
    if not required_visual_dimensions.issubset(set(observation.get("image_text_visual_dimensions", []))):
        failed.append("account_learning_pipeline_image_text_visual_dimensions_incomplete")
    acceptance = payload.get("real_acceptance", {})
    required_strata = {
        "normal_visual",
        "normal_long_transcript",
        "product_ad",
        "platform_project",
        "collaboration_ownership",
        "low_information_or_asr_risk",
    }
    if acceptance.get("summary_artifact") != "REAL_ACCEPTANCE_SUMMARY.json":
        failed.append("account_learning_pipeline_acceptance_summary_missing")
    if set(acceptance.get("required_strata", [])) != required_strata:
        failed.append("account_learning_pipeline_acceptance_strata_invalid")
    if acceptance.get("require_expanded_audit_after_severe_issue") is not True:
        failed.append("account_learning_pipeline_expanded_audit_gate_missing")
    commercial = payload.get("commercial_learning", {})
    if commercial.get("separate_from_natural_v1") is not True:
        failed.append("account_learning_pipeline_commercial_v1_boundary_missing")
    if commercial.get("platform_projects_separate") is not True:
        failed.append("account_learning_pipeline_platform_boundary_missing")
    if commercial.get("visual_claim_requires_timecode_or_frame") is not True:
        failed.append("account_learning_pipeline_visual_coordinate_gate_missing")
    handoff = payload.get("stage6_account_skill_package", {})
    if handoff.get("required") is not True:
        failed.append("account_learning_pipeline_account_skill_package_missing")
    if handoff.get("manifest") != "account_skill_candidate/ACCOUNT_SKILL_MANIFEST.json":
        failed.append("account_learning_pipeline_account_skill_manifest_missing")
    if handoff.get("candidate_callable") is not False or handoff.get("user_review_required") is not True:
        failed.append("account_learning_pipeline_account_skill_gate_invalid")
    expression = payload.get("expression_asset_learning", {})
    if (
        expression.get("schema_id") != "expression_asset_learning_v3"
        or expression.get("contract_version") != "3.1"
        or expression.get("applies_to_new_workflows") is not True
        or expression.get("legacy_workflow_migration") != "explicit_only"
        or expression.get("candidate_only") is not True
        or expression.get("formal_write_allowed") is not False
        or expression.get("source_excerpt_generation_eligible") is not False
        or expression.get("abstract_pattern_production_eligible_before_approval") is not False
    ):
        failed.append("account_learning_pipeline_expression_lane_invalid")
    expression_stages = expression.get("stages", {}) if isinstance(expression, dict) else {}
    if set(expression_stages) != set(expected_stages):
        failed.append("account_learning_pipeline_expression_stage_mapping_invalid")
    stage1_expression = expression_stages.get("stage1_parallel_extraction", {})
    if not {"audit_report.json", "expression_assets.sample.jsonl", "source_registry.jsonl"}.issubset(
        set(map(str, stage1_expression.get("required_files", [])))
    ):
        failed.append("account_learning_pipeline_expression_sample_gate_missing")
    stage6_expression = expression_stages.get("stage6_learning_delivery", {})
    if not {
        "expression_assets.jsonl",
        "manifest.json",
        "表达资产总览.md",
        "发布层与视频层协同图谱.md",
        "单条内容拆解索引.md",
    }.issubset(set(map(str, stage6_expression.get("required_files", [])))):
        failed.append("account_learning_pipeline_expression_delivery_incomplete")
    expected_account_views = {
        "account_views/账号整体方法论.md",
        "account_views/内容生产使用说明.md",
        "account_views/减少AI味输出规则.md",
        "account_views/内容输出标准模板.md",
    }
    if set(handoff.get("required_account_views", [])) != expected_account_views:
        failed.append("account_learning_pipeline_account_views_invalid")
    migration = payload.get("historical_workflow_v29_migration", {})
    expected_migration = {
        "required_for_all_registered_accounts": True,
        "formal_upgrade_command": "tools.kb.cli account-skills-v29-upgrade --all --user-confirmed",
        "candidate_migration_command": "tools.kb.cli account-learning-migrate --all --force",
        "acceptance_command": "tools.kb.cli account-learning-v29-audit",
        "pipeline_state_version_required": "2.9",
        "stage6_compatibility_schema_required": "account_skill_upgrade_compatibility_v1",
        "formal_and_candidate_skill_snapshot_must_match": True,
        "publishing_copy_and_account_validators_must_sync": True,
        "account_change_proposals_must_sync": True,
        "one_workflow_per_registered_account": True,
        "same_account_sources_only": True,
        "deferred_evidence_must_be_isolated_and_fully_audited": True,
    }
    if not isinstance(migration, dict):
        failed.append("account_learning_pipeline_historical_v29_migration_missing")
    else:
        for field, expected in expected_migration.items():
            if migration.get(field) != expected:
                failed.append(f"account_learning_pipeline_historical_v29_migration_invalid:{field}")
        if set(map(str, migration.get("generated_garbage_forbidden", []))) != {
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".DS_Store",
        }:
            failed.append("account_learning_pipeline_historical_v29_garbage_gate_invalid")
    compatibility = payload.get("stage6_upgrade_compatibility", {})
    if compatibility.get("schema_id") != "account_skill_upgrade_compatibility_v1":
        failed.append("account_learning_pipeline_upgrade_compatibility_schema_missing")
    if compatibility.get("manifest") != "account_skill_candidate/UPGRADE_COMPATIBILITY.json":
        failed.append("account_learning_pipeline_upgrade_compatibility_manifest_missing")
    for field, expected in {
        "candidate_only": True,
        "formal_write_allowed": False,
        "user_review_required": True,
        "no_silent_capability_loss": True,
        "previous_ids_must_remain_in_inventory": True,
        "new_ids_must_equal_inventory_delta": True,
        "changed_capabilities_require_explicit_user_confirmation": True,
        "source_paths_same_account_only": True,
        "cross_account_merge_allowed": False,
        "system_contains_account_capabilities": False,
    }.items():
        if compatibility.get(field) is not expected:
            failed.append(f"account_learning_pipeline_upgrade_compatibility_invalid:{field}")
    visual = payload.get("stage6_visual_reference_package", {})
    if visual.get("schema_id") != "production_visual_reference_v1":
        failed.append("account_learning_pipeline_visual_reference_profile_missing")
    if visual.get("manifest_schema_id") != "production_visual_asset_manifest_v1":
        failed.append("account_learning_pipeline_visual_reference_manifest_missing")
    if int(visual.get("minimum_positive_assets", 0) or 0) < 3:
        failed.append("account_learning_pipeline_visual_reference_minimum_too_weak")
    expected_source_kinds = {
        "account_source_positive": "generation_reality_calibration_and_validation",
        "user_accepted_ai_output": "page_continuity_and_composition_regression_only",
        "user_rejected_output": "validation_only",
        "external_reference": "explicit_scope_only",
    }
    if visual.get("source_kinds") != expected_source_kinds:
        failed.append("account_learning_pipeline_visual_reference_sources_invalid")
    expected_visual_boundaries = {
        "system_contains_account_assets": False,
        "positive_assets_same_account_only": True,
        "account_assets_automatically_become_methods": False,
        "user_accepted_ai_output_becomes_reality_source": False,
        "user_accepted_ai_output_becomes_master_reference": False,
        "generated_output_can_self_bootstrap": False,
        "rejected_output_allowed_as_generation_reference": False,
        "absolute_nas_paths_in_portable_manifest": False,
        "role_and_risk_coverage_required": True,
    }
    boundaries = visual.get("required_boundaries", {})
    if any(boundaries.get(key) is not value for key, value in expected_visual_boundaries.items()):
        failed.append("account_learning_pipeline_visual_reference_boundaries_invalid")
    positive_origin = visual.get("positive_origin_contract", {})
    if (
        positive_origin.get("origin_kind") != "account_original"
        or not {"authenticity_authority", "realism_authority", "generation_reference_eligible"}.issubset(
            set(map(str, positive_origin.get("required_true_fields", [])))
        )
        or not {"ai_generated", "method_evidence_eligible"}.issubset(
            set(map(str, positive_origin.get("required_false_fields", [])))
        )
    ):
        failed.append("account_learning_pipeline_original_authority_contract_invalid")
    accepted = visual.get("accepted_ai_output_contract", {})
    if (
        accepted.get("source_kind") != "user_accepted_ai_output"
        or accepted.get("origin_kind") != "ai_generated"
        or accepted.get("reference_policy")
        != "page_continuity_and_composition_regression_only"
        or set(map(str, accepted.get("allowed_uses", [])))
        != {"page_continuity_regression", "composition_regression"}
        or accepted.get("user_acceptance_changes_origin") is not False
        or accepted.get("calibration_output_is_golden_positive") is not False
        or accepted.get("first_output_is_master_reference") is not False
    ):
        failed.append("account_learning_pipeline_accepted_ai_contract_invalid")
    required_false_fields = {
        "authenticity_authority",
        "realism_authority",
        "master_reference_eligible",
        "golden_positive_eligible",
        "method_evidence_eligible",
        "generation_reference_eligible",
    }
    if not required_false_fields.issubset(
        set(map(str, accepted.get("required_false_fields", [])))
    ):
        failed.append("account_learning_pipeline_accepted_ai_authority_guard_incomplete")
    forbidden_uses = set(map(str, accepted.get("forbidden_uses", [])))
    if not {
        "generation_reference",
        "food_realism",
        "camera_realism",
        "authenticity_reference",
        "master_reference",
        "golden_positive",
    }.issubset(forbidden_uses):
        failed.append("account_learning_pipeline_accepted_ai_forbidden_uses_incomplete")
    separation = visual.get("prompt_acceptance_separation", {})
    if (
        separation.get("generation_prompt_and_acceptance_rules_separate") is not True
        or separation.get("acceptance_artifact_may_embed_generation_prompt") is not False
        or separation.get("generation_stability_rules_scope") != "model_runtime_only"
        or separation.get("generation_stability_rules_may_become_account_method") is not False
    ):
        failed.append("account_learning_pipeline_prompt_acceptance_separation_invalid")


def validate_account_learning_card_contract(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("account_learning_card_contract_missing")
        return
    if payload.get("contract_id") != "unified_three_layer_v2":
        failed.append("account_learning_card_contract_id_invalid")
    expected_layers = ["evidence", "content_deconstruction", "cross_card_method"]
    layers = [item.get("id") for item in payload.get("layers", []) if isinstance(item, dict)]
    if layers != expected_layers:
        failed.append("account_learning_card_contract_layers_invalid")
    expected_sections = [
        "证据边界",
        "为什么值得学习",
        "多维分类与商业隔离",
        "核心观点",
        "内容结构",
        "发布内容层学习",
        "视频/图文表现层学习",
        "金句与表达素材",
        "可复用选题与案例",
        "方法候选与可复用方法论",
        "可复用模板",
        "证据缺口与候选判断",
    ]
    sections = [item.get("heading") for item in payload.get("card_sections", []) if isinstance(item, dict)]
    if sections != expected_sections:
        failed.append("account_learning_card_contract_sections_invalid")
    if set(payload.get("quote_types", [])) != {"原文金句", "提炼表达", "可复用句式"}:
        failed.append("account_learning_card_contract_quote_types_invalid")
    trigger_model = payload.get("trigger_model", {})
    if set(trigger_model.get("a2_required_fields", [])) != {
        "触发机制",
        "适用关系",
        "可迁移场景",
        "不触发条件",
    }:
        failed.append("account_learning_card_contract_trigger_fields_invalid")
    if not trigger_model.get("mechanism_match_dimensions") or not trigger_model.get("forbidden_triggers"):
        failed.append("account_learning_card_contract_trigger_model_incomplete")
    if payload.get("compatibility", {}).get("bulk_migration") is not False:
        failed.append("account_learning_card_contract_bulk_migration_must_be_false")
    image_text_requirements = payload.get("image_text_layer_requirements", {})
    publish_requirements = " ".join(image_text_requirements.get("publish_layer", []))
    visual_requirements = " ".join(image_text_requirements.get("visual_layer", []))
    if not all(marker in publish_requirements for marker in ("标题机制", "正文结构", "细节密度", "真人感", "话题策略")):
        failed.append("account_learning_card_contract_publish_layer_too_shallow")
    if not all(
        marker in visual_requirements
        for marker in (
            "逐图角色",
            "文字注释设计",
            "动作",
            "真人与生活感",
            "跨模态协同",
            "生产参考候选角色与风险",
        )
    ):
        failed.append("account_learning_card_contract_visual_layer_too_shallow")
    if "OCR" not in str(image_text_requirements.get("evidence_rule", "")):
        failed.append("account_learning_card_contract_ocr_boundary_missing")
    invariants = payload.get("invariants", [])
    if "系统规则不得包含任何账号专属内容" not in invariants:
        failed.append("account_learning_card_contract_generic_rule_missing")
    cross_outputs = set(map(str, payload.get("cross_card_outputs", [])))
    if not {
        "VISUAL_REFERENCE_PROFILE.json",
        "visual_reference_candidate/manifest.json",
        "account_skill_candidate/references/visual-evidence.md",
    }.issubset(cross_outputs):
        failed.append("account_learning_card_contract_visual_package_outputs_missing")
    if not any("反例只能用于验收" in str(rule) for rule in invariants):
        failed.append("account_learning_card_contract_visual_source_isolation_missing")
    if not any("用户认可不改变AI来源" in str(rule) for rule in invariants):
        failed.append("account_learning_card_contract_ai_origin_guard_missing")
    if not any("连续性和构图回归" in str(rule) for rule in invariants):
        failed.append("account_learning_card_contract_ai_regression_scope_missing")
    if not any("稳定性" in str(rule) and "账号内容规律" in str(rule) for rule in invariants):
        failed.append("account_learning_card_contract_model_stability_boundary_missing")


def validate_account_skill_contract(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("account_skill_contract_missing")
        return
    if payload.get("version") != 5:
        failed.append("account_skill_contract_version_invalid")
    visual = payload.get("conditional_visual_package", {})
    expected_separation = {
        "account_source_positive": "generation_reality_calibration_and_validation",
        "user_accepted_ai_output": "page_continuity_and_composition_regression_only",
        "user_rejected_output": "validation_only",
        "external_reference": "explicit_scope_only",
    }
    if not isinstance(visual, dict) or visual.get("source_separation") != expected_separation:
        failed.append("account_skill_contract_visual_source_separation_invalid")
        return
    policy = visual.get("accepted_ai_output_policy", {})
    if (
        policy.get("origin_kind") != "ai_generated"
        or set(map(str, policy.get("allowed_uses", [])))
        != {"page_continuity_regression", "composition_regression"}
        or policy.get("user_acceptance_changes_origin") is not False
        or policy.get("generated_output_can_self_bootstrap") is not False
    ):
        failed.append("account_skill_contract_accepted_ai_policy_invalid")
    required_forbidden_authority = {
        "authenticity_authority",
        "realism_authority",
        "master_reference_eligible",
        "golden_positive_eligible",
        "method_evidence_eligible",
        "generation_reference_eligible",
    }
    if not required_forbidden_authority.issubset(
        set(map(str, policy.get("forbidden_authority", [])))
    ):
        failed.append("account_skill_contract_accepted_ai_authority_guard_incomplete")
    boundaries = "\n".join(map(str, visual.get("hard_boundaries", [])))
    for marker in (
        "只有账号原图",
        "用户认可AI图只能用于页间连续性和构图回归",
        "禁止生成结果自举",
        "模型稳定性约束不得冒充账号内容规律",
    ):
        if marker not in boundaries:
            failed.append(f"account_skill_contract_visual_boundary_missing:{marker}")
    upgrade = payload.get("upgrade_compatibility", {})
    if not isinstance(upgrade, dict) or upgrade.get("schema_id") != "account_skill_upgrade_compatibility_v1":
        failed.append("account_skill_contract_upgrade_compatibility_missing")
        return
    if upgrade.get("formal_manifest") != "skill/UPGRADE_COMPATIBILITY.json":
        failed.append("account_skill_contract_upgrade_manifest_invalid")
    invariants = upgrade.get("invariants", {})
    expected_invariants = {
        "no_silent_capability_loss": True,
        "stable_capability_ids_required": True,
        "previous_ids_must_remain_in_inventory": True,
        "new_ids_must_equal_inventory_delta": True,
        "replaced_or_deprecated_requires_user_confirmation": True,
        "rollback_required": True,
        "source_snapshot_hashes_required": True,
        "source_paths_same_account_only": True,
        "change_proposals_same_account_only": True,
        "absolute_or_nas_paths_forbidden": True,
        "cross_account_merge_allowed": False,
        "one_manifest_per_account": True,
        "system_may_contain_account_specific_capabilities": False,
    }
    if not isinstance(invariants, dict) or any(invariants.get(key) is not value for key, value in expected_invariants.items()):
        failed.append("account_skill_contract_upgrade_invariants_invalid")
    multi = upgrade.get("multi_image_continuity", {})
    if (
        not isinstance(multi, dict)
        or multi.get("schema_id") != "account_visual_regression_package_v1"
        or multi.get("ordered_pages_required") is not True
        or multi.get("continuity_mother_required") is not True
        or multi.get("direct_parent_relation_required") is not True
        or multi.get("independent_regeneration_when_continuity_required") is not False
        or multi.get("source_kind") != "user_accepted_ai_output"
        or multi.get("origin_kind") != "ai_generated"
        or multi.get("reference_policy") != "page_continuity_and_composition_regression_only"
    ):
        failed.append("account_skill_contract_multi_image_continuity_invalid")
    required_false = {
        "authenticity_authority",
        "realism_authority",
        "master_reference_eligible",
        "golden_positive_eligible",
        "method_evidence_eligible",
        "generation_reference_eligible",
    }
    if not required_false.issubset(set(map(str, multi.get("required_false_fields", [])))):
        failed.append("account_skill_contract_multi_image_authority_guard_incomplete")


def validate_controller_routes(controller: dict[str, Any], failed: list[str]) -> dict[str, int]:
    agents = controller.get("agents", [])
    routes = controller.get("routes", [])
    if controller.get("default_entry") != "@知识库":
        failed.append("controller_missing_default_at_entry")
    if not controller.get("global_priority"):
        failed.append("controller_missing_global_priority")
    clarification_policy = controller.get("clarification_policy", {})
    if not isinstance(clarification_policy, dict) or not clarification_policy.get("rule"):
        failed.append("controller_missing_clarification_policy")
    if int(clarification_policy.get("max_questions", 0) or 0) not in {1, 2, 3}:
        failed.append("controller_clarification_question_limit_invalid")
    if not isinstance(agents, list) or len(agents) < 3:
        failed.append("controller_missing_agent_system")
    if controller.get("agent_model") and controller.get("agent_model") != "logical_roles":
        failed.append("controller_agent_model_not_logical_roles")
    if isinstance(agents, list):
        for agent in agents:
            if isinstance(agent, dict) and agent.get("kind") and agent.get("kind") != "logical_role":
                failed.append(f"controller_agent_not_logical_role:{agent.get('id', 'unknown')}")
    if not isinstance(routes, list) or len(routes) < 8:
        failed.append("controller_missing_route_system")
        routes = []
    required_routes = {
        "content_processing",
        "topic_generation",
        "script_generation",
        "account_learning",
        "content_review",
        "user_setup",
        "creator_db_export",
        "external_use",
        "system_audit",
        "formal_retrieval",
    }
    route_ids = {route.get("id") for route in routes if isinstance(route, dict)}
    for route_id in sorted(required_routes - route_ids):
        failed.append(f"controller_missing_route:{route_id}")
    for route in routes:
        if not isinstance(route, dict):
            failed.append("controller_route_not_object")
            continue
        for key in (
            "id",
            "triggers",
            "minimum_required",
            "clarify_when_missing",
            "agents",
            "read_first",
            "output_contract",
            "write_policy",
        ):
            if key not in route:
                failed.append(f"controller_route_missing_{key}:{route.get('id', 'unknown')}")
        route_id = route.get("id", "unknown")
        minimum_required = route.get("minimum_required", [])
        clarifications = route.get("clarify_when_missing", [])
        if not isinstance(minimum_required, list) or not minimum_required:
            failed.append(f"controller_route_empty_minimum_required:{route_id}")
        if not isinstance(clarifications, list) or not clarifications:
            failed.append(f"controller_route_empty_clarification:{route_id}")
        elif len(clarifications) > int(clarification_policy.get("max_questions", 3) or 3):
            failed.append(f"controller_route_too_many_clarifications:{route_id}")
    return {"route_count": len(routes), "agent_count": len(agents)}


def validate_search_terms(payload: dict[str, Any], failed: list[str]) -> None:
    groups = payload.get("synonym_groups")
    if not isinstance(groups, list) or not groups:
        failed.append("search_terms_missing_synonym_groups")
    elif not any(isinstance(group, list) and any(str(term).strip() for term in group) for group in groups):
        failed.append("search_terms_missing_synonym_groups")
    for index, group in enumerate(groups if isinstance(groups, list) else []):
        if not isinstance(group, list):
            failed.append(f"search_terms_synonym_group_not_list:{index}")
            continue
        for term in group:
            if not str(term).strip():
                failed.append(f"search_terms_empty_synonym:{index}")
    direction_terms = payload.get("direction_terms", {})
    if direction_terms and not isinstance(direction_terms, dict):
        failed.append("search_terms_direction_terms_not_object")
        return
    for direction, terms in direction_terms.items() if isinstance(direction_terms, dict) else []:
        if not isinstance(terms, list):
            failed.append(f"search_terms_direction_terms_not_list:{direction}")
            continue
        for term in terms:
            if not str(term).strip():
                failed.append(f"search_terms_empty_direction_term:{direction}")


def validate_formal_retrieval(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("formal_retrieval_missing_contract")
        return
    if payload.get("scope") != "formal_only":
        failed.append("formal_retrieval_scope_not_formal_only")
    allowed = [str(item).replace("\\", "/") for item in payload.get("allowed_roots", [])]
    if not allowed or any(not item.startswith("10_Knowledge/formal/") for item in allowed):
        failed.append("formal_retrieval_allowed_roots_invalid")
    forbidden = {str(item).replace("\\", "/") for item in payload.get("forbidden_prefixes", [])}
    required_forbidden = {
        "10_Knowledge/candidates/",
        "00_Inbox/",
        "数据/",
        "00_System/",
        "20_User/",
        "90_Temp/",
        "99_Archive/",
    }
    if not required_forbidden.issubset(forbidden):
        failed.append("formal_retrieval_forbidden_layers_incomplete")
    extensions = {str(item).lower() for item in payload.get("allowed_extensions", [])}
    if not extensions or not extensions.issubset({".md", ".json", ".jsonl", ".txt"}):
        failed.append("formal_retrieval_extensions_invalid")
    excluded = set(map(str, payload.get("excluded_path_fragments", [])))
    if not {"/轻量数据源/", "/skill/proposals/"}.issubset(excluded):
        failed.append("formal_retrieval_excluded_audit_paths_incomplete")
    chunk = payload.get("chunk", {})
    if not isinstance(chunk, dict) or int(chunk.get("max_chars", 0) or 0) < 100:
        failed.append("formal_retrieval_chunk_contract_invalid")
    vector = payload.get("vector", {})
    if not isinstance(vector, dict) or vector.get("backend") != "hashed_char_ngram_v1":
        failed.append("formal_retrieval_vector_backend_invalid")
    elif (
        vector.get("network_required") is not False
        or int(vector.get("dimensions", 0) or 0) < 8
        or not 8 <= int(vector.get("max_features", 0) or 0) <= int(vector.get("dimensions", 0) or 0)
    ):
        failed.append("formal_retrieval_vector_contract_invalid")
    weights = payload.get("weights", {})
    required_weights = {"keyword", "vector", "metadata", "rerank"}
    if not isinstance(weights, dict) or not required_weights.issubset(weights):
        failed.append("formal_retrieval_weights_incomplete")
    else:
        total = sum(float(weights.get(key, 0) or 0) for key in required_weights)
        if abs(total - 1.0) > 0.000001:
            failed.append("formal_retrieval_weights_must_sum_to_one")
    metadata = payload.get("metadata_filters", {})
    required_fields = {"account", "direction", "document_role"}
    if (
        not isinstance(metadata, dict)
        or metadata.get("mode") != "strict"
        or not required_fields.issubset(set(map(str, metadata.get("fields", []))))
    ):
        failed.append("formal_retrieval_metadata_filter_invalid")
    result = payload.get("result", {})
    result_fields = set(map(str, result.get("required_fields", []))) if isinstance(result, dict) else set()
    if not {"evidence_coordinate", "score_details", "chunk_sha256"}.issubset(result_fields):
        failed.append("formal_retrieval_result_traceability_incomplete")
    cache = payload.get("cache", {})
    if not isinstance(cache, dict) or not str(cache.get("location", "")).startswith("00_System/runtime/cache/"):
        failed.append("formal_retrieval_cache_not_runtime_only")
    invariants = set(map(str, payload.get("invariants", [])))
    if not any("候选资产不得进入" in item for item in invariants):
        failed.append("formal_retrieval_candidate_boundary_missing")
    if not any("原始资料不得进入" in item for item in invariants):
        failed.append("formal_retrieval_raw_boundary_missing")
    if not any("系统规则" in item and "不得进入" in item for item in invariants):
        failed.append("formal_retrieval_system_boundary_missing")
    if not any("Skill proposal" in item and "不得进入" in item for item in invariants):
        failed.append("formal_retrieval_proposal_boundary_missing")


def validate_expression_asset_contract(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("expression_asset_contract_missing")
        return
    if payload.get("version") != "3.1" or payload.get("scope") != "generic_contract_and_active_pipeline":
        failed.append("expression_asset_contract_version_or_scope_invalid")
    activation = payload.get("activation_boundary", {})
    if (
        not isinstance(activation, dict)
        or activation.get("active_account_learning_integration") is not True
        or activation.get("needs_user_confirmation") is not False
        or not str(activation.get("confirmed_scope", "")).strip()
        or not str(activation.get("proposal", "")).startswith("00_System/shareable/skills/proposals/")
    ):
        failed.append("expression_asset_activation_boundary_invalid")
    storage = payload.get("storage", {})
    if not isinstance(storage, dict):
        failed.append("expression_asset_storage_invalid")
    else:
        candidate_root = str(storage.get("candidate_root_template", ""))
        if not candidate_root.startswith("10_Knowledge/candidates/") or "{account_id}" not in candidate_root:
            failed.append("expression_asset_candidate_root_invalid")
        workflow_root = str(storage.get("workflow_root_template", ""))
        if not workflow_root.startswith("10_Knowledge/candidates/account_learning_workflows/") or "{workflow_id}" not in workflow_root:
            failed.append("expression_asset_workflow_root_invalid")
        if storage.get("formal_write_allowed") is not False or storage.get("system_write_allowed") is not False:
            failed.append("expression_asset_write_boundary_invalid")
        if storage.get("cross_account_merge_allowed") is not False:
            failed.append("expression_asset_cross_account_merge_not_forbidden")
        if (
            not storage.get("source_registry_file")
            or not storage.get("sample_acceptance_file")
            or not storage.get("retrieval_validation_file")
        ):
            failed.append("expression_asset_registry_or_sample_receipt_missing")
        if not str(storage.get("source_authority_root_template", "")).startswith("10_Knowledge/evidence/index/"):
            failed.append("expression_asset_source_authority_root_invalid")
        if not str(storage.get("performance_authority_root_template", "")).startswith("10_Knowledge/evidence/index/"):
            failed.append("expression_asset_performance_authority_root_invalid")
        if not str(storage.get("validation_evidence_root_template", "")).startswith("10_Knowledge/evidence/index/"):
            failed.append("expression_asset_validation_evidence_root_invalid")
        if not storage.get("validator_version"):
            failed.append("expression_asset_validator_version_missing")
    required_types = {
        "hook",
        "golden_line",
        "sentence_pattern",
        "structure_unit",
        "transition",
        "opening_move",
        "ending_move",
        "pain_point",
        "anti_pattern",
        "adaptation_template",
    }
    asset_types = payload.get("asset_types", {})
    if not isinstance(asset_types, dict) or not required_types.issubset(asset_types):
        failed.append("expression_asset_types_incomplete")
    required_fields = set(map(str, payload.get("required_record_fields", [])))
    if not {
        "account_id",
        "source_surface",
        "content_position",
        "functional_role",
        "knowledge_layer",
        "callable",
        "method_evidence_eligible",
        "generation_eligible",
        "transition_history",
        "gate_evidence",
        "source_excerpt",
        "abstracted_pattern",
        "pattern_variables",
        "adaptation_template",
        "source_usage",
        "pattern_usage",
        "structural_usefulness_score",
        "performance_evidence",
        "risk_flags",
    }.issubset(required_fields):
        failed.append("expression_asset_record_fields_incomplete")
    surfaces = payload.get("surface_contract", {})
    if not isinstance(surfaces, dict) or not {
        "publish_title",
        "publish_body_middle",
        "video_spoken_middle",
        "video_visual_opening",
        "cross_modal_coordination",
    }.issubset(set(map(str, surfaces.get("source_surfaces", [])))):
        failed.append("expression_asset_surface_contract_incomplete")
    if not isinstance(surfaces, dict) or not {
        "opening",
        "information_gap",
        "segment_transition",
        "conflict",
        "evidence",
        "reversal",
        "emotion",
        "ending",
    }.issubset(set(map(str, surfaces.get("hook_roles", [])))):
        failed.append("expression_asset_hook_roles_incomplete")
    usage = payload.get("usage_contract", {})
    if (
        not isinstance(usage, dict)
        or usage.get("source_generation_eligible") is not False
        or usage.get("candidate_pattern_production_eligible") is not False
        or usage.get("approved_pattern_requires_user_confirmation") is not True
    ):
        failed.append("expression_asset_usage_boundary_invalid")
    source = payload.get("source_contract", {})
    required_source_types = {
        "account_source_positive",
        "user_accepted_output",
        "user_rejected_output",
        "external_explicit_reference",
    }
    if not isinstance(source, dict) or not required_source_types.issubset(source.get("source_types", {})):
        failed.append("expression_asset_source_types_incomplete")
    elif not {
        "source_registry_id",
        "registry_record_sha256",
        "authority_manifest_path",
        "authority_record_id",
        "authority_record_sha256",
    }.issubset(set(map(str, source.get("required_fields", [])))):
        failed.append("expression_asset_source_registry_binding_incomplete")
    elif source.get("authority_required") is not True or source.get("source_file_hash_verification_required") is not True:
        failed.append("expression_asset_source_authority_not_required")
    lifecycle = payload.get("lifecycle", {})
    if not isinstance(lifecycle, dict):
        failed.append("expression_asset_lifecycle_invalid")
    else:
        states = set(map(str, lifecycle.get("states", [])))
        if not {"observed", "sampled", "retrieval_validated", "cross_card_verified", "pressure_tested", "rejected"}.issubset(states):
            failed.append("expression_asset_lifecycle_incomplete")
        if (
            lifecycle.get("candidate_state_callable") is not False
            or lifecycle.get("candidate_state_method_evidence_eligible") is not False
            or lifecycle.get("candidate_state_generation_eligible") is not False
        ):
            failed.append("expression_asset_candidate_defaults_unsafe")
    score = payload.get("score_contract", {})
    score = score if isinstance(score, dict) else {}
    statuses = set(map(str, score.get("performance_statuses", [])))
    if "not_claimed" not in statuses or "validated_with_evidence" not in statuses:
        failed.append("expression_asset_performance_statuses_incomplete")
    if not {
        "status",
        "evidence_coordinates",
        "evidence_kind",
        "metric",
        "sample_size",
        "observation_window",
        "source_hashes",
        "authority_manifest_path",
        "authority_record_ids",
    }.issubset(set(map(str, score.get("performance_required_fields", [])))):
        failed.append("expression_asset_performance_evidence_fields_incomplete")
    if "不得" not in str(score.get("forbidden_claim", "")):
        failed.append("expression_asset_performance_claim_boundary_missing")
    gates = payload.get("gates", {})
    try:
        sample_max = int(gates.get("sample_max_items", 0) or 0) if isinstance(gates, dict) else 0
    except (TypeError, ValueError):
        sample_max = 0
    if not isinstance(gates, dict) or not 1 <= sample_max <= 20:
        failed.append("expression_asset_sample_gate_invalid")
    elif gates.get("full_extraction_requires_sample_acceptance") is not True:
        failed.append("expression_asset_full_extraction_gate_missing")
    if not isinstance(gates, dict) or not gates.get("state_gate_evidence"):
        failed.append("expression_asset_state_gate_evidence_missing")
    if not isinstance(gates, dict) or not gates.get("sample_acceptance_required_fields"):
        failed.append("expression_asset_sample_acceptance_evidence_missing")
    elif "retrieval_validation_sha256" not in set(map(str, gates.get("sample_acceptance_required_fields", []))):
        failed.append("expression_asset_retrieval_receipt_binding_missing")
    invariants = set(map(str, payload.get("invariants", [])))
    if not any("系统配置不得包含" in item for item in invariants):
        failed.append("expression_asset_system_pollution_boundary_missing")
    if not any("跨账号" in item and "禁止" in item for item in invariants):
        failed.append("expression_asset_account_isolation_boundary_missing")
    if not any("本次系统升级" in item and "不得启动" in item for item in invariants):
        failed.append("expression_asset_system_only_upgrade_boundary_missing")
    if not any("原文资产" in item and "不得用于生成" in item for item in invariants):
        failed.append("expression_asset_source_generation_boundary_missing")
    if not any("历史工作流" in item and "静默" in item for item in invariants):
        failed.append("expression_asset_legacy_compatibility_boundary_missing")


def validate_system_version(root: Path, payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("system_version_missing")
        return
    if payload.get("system_version") != "3.1" or payload.get("release_version") != "3.1.0":
        failed.append("system_version_not_3_1")
    status = str(payload.get("status", ""))
    if status not in {"validating", "active"}:
        failed.append("system_version_status_invalid")
    record = str(payload.get("upgrade_record", ""))
    if not record or not (root / record).exists():
        failed.append("system_upgrade_record_missing")
    components = payload.get("components", [])
    component_ids = {str(item.get("id", "")) for item in components if isinstance(item, dict)}
    if component_ids != {"P0", "P1", "P2", "P3"}:
        failed.append("system_version_components_incomplete")
    p2 = next((item for item in components if isinstance(item, dict) and item.get("id") == "P2"), {})
    if (
        p2.get("status") != "completed_active_candidate_only"
        or p2.get("account_learning_version") != "3.0"
        or not str(p2.get("package_builder", "")).startswith("tools/")
    ):
        failed.append("system_version_expression_asset_component_incomplete")
    predecessor = payload.get("predecessor", {})
    if (
        not isinstance(predecessor, dict)
        or predecessor.get("system_version") != "3.0"
        or not re.fullmatch(r"[0-9a-f]{40}", str(predecessor.get("git_baseline", "")))
        or not (root / str(predecessor.get("upgrade_record", ""))).is_file()
    ):
        failed.append("system_version_predecessor_invalid")
    boundaries = payload.get("boundaries", {})
    required_false = {
        "web_or_multi_user_ui_in_scope",
        "account_learning_executed",
        "account_assets_generated",
        "account_specific_content_allowed_in_system",
        "raw_source_mutation_allowed",
    }
    if not isinstance(boundaries, dict) or any(boundaries.get(key) is not False for key in required_false):
        failed.append("system_version_boundaries_invalid")
    if not isinstance(boundaries, dict) or boundaries.get("active_account_learning_modified") is not True:
        failed.append("system_version_active_learning_skill_hardening_missing")
    if not isinstance(boundaries, dict) or boundaries.get("account_skill_upgrade_executed") is not True:
        failed.append("system_version_account_skill_upgrade_missing")
    pending = payload.get("pending_activations", [])
    if not isinstance(pending, list) or pending:
        failed.append("system_version_unexpected_pending_activation")
    validation = payload.get("validation", {})
    required_validation = {
        "targeted_unit_tests",
        "full_unit_test_suite",
        "system_validation",
        "runtime_doctor",
        "system_boundary_audit",
        "account_pollution_audit",
        "account_skill_upgrade_compatibility_tests",
        "account_skill_live_acceptance",
        "distribution_audit",
        "formal_retrieval_live_smoke_test",
        "change_scope_audit",
        "all_account_v29_learning_audit",
        "single_active_seven_stage_workflow_test",
        "expression_asset_package_test",
        "expression_asset_source_generation_boundary_test",
        "legacy_workflow_in_place_upgrade_test",
    }
    declared = set(map(str, validation.get("required", []))) if isinstance(validation, dict) else set()
    completed = set(map(str, validation.get("completed", []))) if isinstance(validation, dict) else set()
    if not required_validation.issubset(declared):
        failed.append("system_version_validation_matrix_incomplete")
    if status == "active":
        if validation.get("status") != "passed" or not required_validation.issubset(completed):
            failed.append("system_version_active_without_full_acceptance")
        if int(validation.get("test_count", 0) or 0) <= 0 or validation.get("failures"):
            failed.append("system_version_active_test_evidence_invalid")


def validate_output_contracts(payload: dict[str, Any], failed: list[str]) -> dict[str, int]:
    contracts = payload.get("contracts", [])
    if not isinstance(contracts, list):
        failed.append("output_contracts_missing_contract_list")
        return {"contract_count": 0}
    required = {
        "content_processing",
        "topic_generation",
        "script_generation",
        "account_learning",
        "content_review",
        "user_setup",
        "creator_db_export",
        "external_use",
        "system_audit",
        "formal_retrieval",
    }
    contract_ids = {item.get("route_id") for item in contracts if isinstance(item, dict)}
    for route_id in sorted(required - contract_ids):
        failed.append(f"output_contract_missing_route:{route_id}")
    for contract in contracts:
        if not isinstance(contract, dict):
            failed.append("output_contract_not_object")
            continue
        if not contract.get("required_fields"):
            failed.append(f"output_contract_missing_required_fields:{contract.get('route_id', 'unknown')}")
        if not contract.get("must_not"):
            failed.append(f"output_contract_missing_must_not:{contract.get('route_id', 'unknown')}")
    return {"contract_count": len(contracts)}


def validate_raw_blocked_index(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        return
    items = payload.get("items", [])
    if not isinstance(items, list):
        failed.append("raw_blocked_index_missing_items")
        return
    paths = [item.get("path", "") for item in items if isinstance(item, dict)]
    if "数据/" not in paths:
        failed.append("raw_blocked_index_missing_data_boundary")
    for path in paths:
        if path.startswith("数据/") and path != "数据/":
            failed.append("raw_blocked_index_expands_data")


def validate_layer_map(payload: dict[str, Any], failed: list[str]) -> None:
    required_keys = {
        "target_layers",
        "legacy_mapping",
        "share_exclusions",
        "default_blocked_dirs",
        "candidate_asset_roots",
        "formal_knowledge_roots",
        "system_skill_roots",
    }
    for key in sorted(required_keys - set(payload)):
        failed.append(f"layer_map_missing:{key}")
    target_layers = payload.get("target_layers", {})
    if not isinstance(target_layers, dict):
        failed.append("layer_map_target_layers_not_object")
        return
    for layer in ("00_System", "10_Knowledge", "20_User", "90_Temp", "99_Archive", "数据"):
        if layer not in target_layers:
            failed.append(f"layer_map_missing_target_layer:{layer}")
    share_exclusions = payload.get("share_exclusions", [])
    if isinstance(share_exclusions, list):
        for required in (
            "00_System/runtime/",
            "20_User/private/",
            "20_User/data/",
            "20_User/feedback/",
            "20_User/local/",
            "数据/",
        ):
            if required not in share_exclusions:
                failed.append(f"layer_map_missing_share_exclusion:{required}")
    else:
        failed.append("layer_map_share_exclusions_not_list")


def build_health_summary(root: Path, account_index: dict[str, Any], route_summary: dict[str, int]) -> dict[str, Any]:
    accounts = account_index.get("accounts", []) if isinstance(account_index.get("accounts"), list) else []
    proposals_dir = skill_proposals_dir(root)
    reports_dir = runtime_path(root, "reports")
    proposal_count = len([path for path in proposals_dir.glob("*.md") if path.name != "Skill提案模板.md"]) if proposals_dir.exists() else 0
    report_count = len(list(reports_dir.glob("*"))) if reports_dir.exists() else 0
    registry_exists = (runtime_path(root, "state") / "kb_registry.json").exists()
    dashboard_exists = (runtime_path(root, "reports") / "latest_kb_dashboard.md").exists()
    direction_count = 0
    for account in accounts:
        directions = account.get("directions", []) if isinstance(account, dict) else []
        if isinstance(directions, list):
            direction_count += len(directions)
    return {
        "route_count": route_summary.get("route_count", 0),
        "agent_count": route_summary.get("agent_count", 0),
        "account_count": len(accounts),
        "formal_direction_count": direction_count,
        "proposal_count": proposal_count,
        "report_count": report_count,
        "registry_exists": registry_exists,
        "dashboard_exists": dashboard_exists,
    }


def render_validation_report(failed: list[str], health: dict[str, Any]) -> str:
    lines = ["# 知识库系统验收报告", "", f"生成时间：{now_iso()}", "", f"结果：{'通过' if not failed else '未通过'}", ""]
    lines.extend(
        [
            "## 健康摘要",
            "",
            f"- 总控路由数：{health.get('route_count', 0)}",
            f"- 智能体角色数：{health.get('agent_count', 0)}",
            f"- 账号数：{health.get('account_count', 0)}",
            f"- 正式方向数：{health.get('formal_direction_count', 0)}",
            f"- Skill proposal 数：{health.get('proposal_count', 0)}",
            f"- 报告文件数：{health.get('report_count', 0)}",
            f"- 输出契约数：{health.get('contract_count', 0)}",
            f"- 账号 Skill 数：{health.get('account_skill_count', 0)}",
            f"- 账号学习工作流：{health.get('account_learning_workflow_count', 0)} 个，异常 {health.get('invalid_account_learning_workflow_count', 0)} 个",
            f"- 生产记忆数据库：{'正常' if health.get('production_memory_ok') else '异常'}",
            f"- 全局 Skill：{health.get('global_skill_status', 'unknown')}{'（已绑定当前知识库）' if health.get('global_skill_bound_to_root') else '（未绑定当前知识库）'}",
            f"- 可迁移层旧路径引用：{health.get('shareable_legacy_reference_count', 0)}",
            f"- 可迁移层本机绝对路径：{health.get('shareable_absolute_path_count', 0)}",
            f"- 活跃账号专用构建工具：{health.get('active_account_specific_tool_count', 0)}",
            f"- 正式层越界目录：{health.get('formal_layer_out_of_scope_count', 0)}",
            f"- 账号目录/索引结构错误：{health.get('account_structure_error_count', 0)}",
            f"- 账号索引失效路径：{health.get('account_index_missing_path_count', 0)}",
            f"- 废弃过程项目残留：{health.get('retired_process_residue_count', 0)}",
            f"- 候选层测试产物：{health.get('candidate_test_artifact_count', 0)}",
            f"- 独立系统包：{'可迁移' if health.get('distribution_portable') else '存在污染'}",
            f"- 开源发布：{'就绪' if health.get('open_source_ready') else '待选择 LICENSE' if health.get('legal_release_blocker') == 'missing_license' else '未就绪'}",
            f"- 注册表：{'已生成' if health.get('registry_exists') else '未生成'}",
            f"- 运行面板：{'已生成' if health.get('dashboard_exists') else '未生成'}",
            "",
        ]
    )
    if failed:
        lines.append("## 失败项")
        lines.extend(f"- {item}" for item in failed)
    else:
        lines.append("关键入口、总控路由、索引、Skill 入口、调用规则均已具备。候选资产、运行状态和最新报告属于运行产物，不要求进入 Git。")
    return "\n".join(lines) + "\n"
