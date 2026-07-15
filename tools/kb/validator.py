from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import (
    EVIDENCE_INDEX_DIR,
    EVIDENCE_MEMORY_DIR,
    SYSTEM_AGENTS_DIR,
    SYSTEM_CONFIG_DIR,
    SYSTEM_INDEX_DIR,
    SYSTEM_MEMORY_DIR,
    SYSTEM_RULES_DIR,
    SYSTEM_SKILL_PACKAGES_DIR,
    USER_SYNCABLE_AGENTS_DIR,
    USER_SYNCABLE_MEMORY_DIR,
    now_iso,
    skill_proposals_dir,
)
from .agent_registry import validate_agent_registry
from .skill_package import skill_package_drift
from .system_cleaner import audit_system_boundaries


REQUIRED_FILES = (
    "知识库入口.md",
    "README.md",
    "00_System/shareable/docs/project_use/项目调用规则.md",
    f"{SYSTEM_RULES_DIR}/用户操作台.md",
    f"{SYSTEM_RULES_DIR}/初始化生命周期.md",
    f"{SYSTEM_RULES_DIR}/输出契约.md",
    f"{SYSTEM_CONFIG_DIR}/output_contracts.json",
    f"{SYSTEM_CONFIG_DIR}/account_learning_pipeline.json",
    f"{SYSTEM_CONFIG_DIR}/account_learning_card_contract.json",
    f"{SYSTEM_CONFIG_DIR}/search_terms.json",
    f"{SYSTEM_CONFIG_DIR}/skill_contract.json",
    f"{SYSTEM_CONFIG_DIR}/layer_map.json",
    f"{SYSTEM_RULES_DIR}/规则权威源.md",
    f"{SYSTEM_RULES_DIR}/账号学习标准工作流.md",
    f"{SYSTEM_RULES_DIR}/统一学习卡产出标准.md",
    f"{SYSTEM_MEMORY_DIR}/memory_rules.md",
    f"{SYSTEM_MEMORY_DIR}/memory_schema.json",
    f"{SYSTEM_MEMORY_DIR}/retention_policy.md",
    f"{SYSTEM_MEMORY_DIR}/memory_workflow.md",
    f"{SYSTEM_AGENTS_DIR}/agent_registry_schema.json",
    f"{SYSTEM_AGENTS_DIR}/agent_capability_rules.md",
    f"{SYSTEM_INDEX_DIR}/controller_routes.json",
    f"{EVIDENCE_INDEX_DIR}/knowledge_index.json",
    f"{EVIDENCE_INDEX_DIR}/knowledge_index_summary.md",
    f"{EVIDENCE_INDEX_DIR}/formal_knowledge_index.json",
    f"{EVIDENCE_INDEX_DIR}/candidate_asset_index.json",
    f"{EVIDENCE_INDEX_DIR}/raw_blocked_index.json",
    f"{SYSTEM_INDEX_DIR}/task_entry_index.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/SKILL.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/agents/openai.yaml",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/references/calling-rules.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/知识库/SKILL.md",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/知识库/agents/openai.yaml",
    f"{SYSTEM_SKILL_PACKAGES_DIR}/知识库/references/calling-rules.md",
    f"{USER_SYNCABLE_MEMORY_DIR}/记忆总入口.md",
    f"{USER_SYNCABLE_MEMORY_DIR}/用户偏好与决策.md",
    f"{USER_SYNCABLE_AGENTS_DIR}/agent_registry.md",
    f"{EVIDENCE_MEMORY_DIR}/README.md",
    f"{EVIDENCE_MEMORY_DIR}/session_summaries/README.md",
    f"{EVIDENCE_MEMORY_DIR}/resolved_issues/README.md",
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
    zh_skill_text = read_text(root / SYSTEM_SKILL_PACKAGES_DIR / "知识库" / "SKILL.md")
    zh_skill_ui_text = read_text(root / SYSTEM_SKILL_PACKAGES_DIR / "知识库" / "agents" / "openai.yaml")
    task_index_text = read_text(root / SYSTEM_INDEX_DIR / "task_entry_index.md")
    user_console_text = read_text(root / SYSTEM_RULES_DIR / "用户操作台.md")
    output_contract_text = read_text(root / SYSTEM_RULES_DIR / "输出契约.md")
    account_workflow_text = read_text(root / SYSTEM_RULES_DIR / "账号学习标准工作流.md")
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
    search_terms = load_json(root / SYSTEM_CONFIG_DIR / "search_terms.json", failed, "search_terms_invalid_json")
    layer_map = load_json(root / SYSTEM_CONFIG_DIR / "layer_map.json", failed, "layer_map_invalid_json")
    memory_schema = load_json(root / SYSTEM_MEMORY_DIR / "memory_schema.json", failed, "memory_schema_invalid_json")
    agent_schema = load_json(root / SYSTEM_AGENTS_DIR / "agent_registry_schema.json", failed, "agent_registry_schema_invalid_json")
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
    if "输出契约" not in output_contract_text:
        failed.append("output_contract_doc_missing_title")
    validate_account_learning_workflow(account_workflow_text, failed)
    validate_account_learning_pipeline(account_learning_pipeline, failed)
    validate_account_learning_card_contract(account_learning_card_contract, failed)
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
    if memory_schema:
        validate_memory_schema(memory_schema, failed)
    if agent_schema:
        validate_agent_schema(agent_schema, failed)
    agent_registry_result = validate_agent_registry(root)
    failed.extend(agent_registry_result["failed"])
    boundary_result = audit_system_boundaries(root)
    for item in boundary_result.get("violations", []):
        failed.append(f"system_boundary:{item['type']}:{item['path']}:{item['token']}")
    for item in boundary_result.get("legacy_path_references", []):
        failed.append(f"legacy_path_reference:{item['path']}")
    if (root / SYSTEM_CONFIG_DIR / "skill_contract.json").exists():
        for relative in skill_package_drift(root):
            failed.append(f"skill_package_drift:{relative}")
    health = build_health_summary(root, account_index, route_summary)
    health["agent_registry_count"] = agent_registry_result.get("agent_count", 0)
    health["system_boundary_violation_count"] = len(boundary_result.get("violations", []))
    health["legacy_path_reference_count"] = len(boundary_result.get("legacy_path_references", []))
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


def validate_account_learning_workflow(text: str, failed: list[str]) -> None:
    required_phrases = {
        "account_workflow_missing_learning_phase": "## 一、学习阶段",
        "account_workflow_missing_production_review_phase": "## 二、生产复盘阶段",
        "account_workflow_missing_account_overview": "账号概述.md",
        "account_workflow_missing_rough_pool": "粗学与选题池.md",
        "account_workflow_missing_deep_plan": "deep_learning_plan.json",
        "account_workflow_missing_production_usage": "内容生产使用说明.md",
        "account_workflow_missing_output_template": "内容输出标准模板.md",
        "account_workflow_missing_ai_style": "减少AI味输出规则.md",
        "account_workflow_missing_nas_boundary": "NAS 只作为原始资产仓",
        "account_workflow_missing_process_artifact_boundary": "过程物",
        "account_workflow_missing_stage_gate": "缺任何一个都不能宣布粗学完成",
        "account_workflow_missing_triple_verification": "三重验证",
        "account_workflow_missing_pressure_test": "压力测试",
        "account_workflow_missing_rejected_audit": "rejected.jsonl",
        "account_workflow_missing_candidate_clusters": "candidate_clusters.jsonl",
        "account_workflow_missing_test_hash": "提示集哈希",
        "account_workflow_missing_callable_boundary": "callable=false",
        "account_workflow_missing_unified_card": "unified_three_layer_v2",
        "account_workflow_missing_three_layers": "证据层 + 内容拆解层",
        "account_workflow_missing_generic_rule": "系统规则不得包含账号专属内容",
    }
    for failure, phrase in required_phrases.items():
        if phrase not in text:
            failed.append(failure)


def validate_account_learning_pipeline(payload: dict[str, Any], failed: list[str]) -> None:
    if not payload:
        failed.append("account_learning_pipeline_missing")
        return
    if payload.get("version") != "2.2":
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
    invariants = payload.get("invariants", [])
    if "系统规则不得包含任何账号专属内容" not in invariants:
        failed.append("account_learning_card_contract_generic_rule_missing")


def validate_controller_routes(controller: dict[str, Any], failed: list[str]) -> dict[str, int]:
    agents = controller.get("agents", [])
    routes = controller.get("routes", [])
    if controller.get("default_entry") != "@知识库":
        failed.append("controller_missing_default_at_entry")
    if not controller.get("global_priority"):
        failed.append("controller_missing_global_priority")
    if not isinstance(agents, list) or len(agents) < 8:
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
        "topic_generation",
        "script_generation",
        "account_learning",
        "skill_evolution",
        "json_ingest",
        "screenshot_review",
        "table_review",
        "external_use",
        "system_audit",
        "memory_capture",
        "agent_registry",
    }
    route_ids = {route.get("id") for route in routes if isinstance(route, dict)}
    for route_id in sorted(required_routes - route_ids):
        failed.append(f"controller_missing_route:{route_id}")
    for route in routes:
        if not isinstance(route, dict):
            failed.append("controller_route_not_object")
            continue
        for key in ("id", "triggers", "agents", "read_first", "output_contract", "write_policy"):
            if key not in route:
                failed.append(f"controller_route_missing_{key}:{route.get('id', 'unknown')}")
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


def validate_output_contracts(payload: dict[str, Any], failed: list[str]) -> dict[str, int]:
    contracts = payload.get("contracts", [])
    if not isinstance(contracts, list):
        failed.append("output_contracts_missing_contract_list")
        return {"contract_count": 0}
    required = {
        "topic_generation",
        "script_generation",
        "account_learning",
        "json_ingest",
        "screenshot_review",
        "table_review",
        "skill_evolution",
        "external_use",
        "system_audit",
        "memory_capture",
        "agent_registry",
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
    for layer in ("00_System", "10_Knowledge", "20_User", "80_Local", "90_Temp", "99_Archive", "数据"):
        if layer not in target_layers:
            failed.append(f"layer_map_missing_target_layer:{layer}")
    share_exclusions = payload.get("share_exclusions", [])
    if isinstance(share_exclusions, list):
        for required in ("00_System/runtime/", "80_Local/", "20_User/private/", "数据/"):
            if required not in share_exclusions:
                failed.append(f"layer_map_missing_share_exclusion:{required}")
    else:
        failed.append("layer_map_share_exclusions_not_list")


def validate_memory_schema(payload: dict[str, Any], failed: list[str]) -> None:
    required = set(payload.get("required_fields", [])) if isinstance(payload.get("required_fields"), list) else set()
    for field in ("memory_id", "title", "category", "target_layer", "content", "created_at"):
        if field not in required:
            failed.append(f"memory_schema_missing_required_field:{field}")
    categories = payload.get("categories", [])
    if not isinstance(categories, list) or "session_summary" not in categories or "resolved_issue" not in categories:
        failed.append("memory_schema_missing_core_categories")
    layers = payload.get("target_layers", [])
    if not isinstance(layers, list) or "user_private" not in layers or "knowledge_evidence" not in layers:
        failed.append("memory_schema_missing_core_layers")


def validate_agent_schema(payload: dict[str, Any], failed: list[str]) -> None:
    required = set(payload.get("required_fields", [])) if isinstance(payload.get("required_fields"), list) else set()
    for field in ("agent_id", "primary_function", "auth_status", "memory_scope", "blocked_actions"):
        if field not in required:
            failed.append(f"agent_schema_missing_required_field:{field}")
    statuses = payload.get("auth_statuses", [])
    if not isinstance(statuses, list) or "not_required" not in statuses or "configured" not in statuses:
        failed.append("agent_schema_missing_auth_statuses")


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
