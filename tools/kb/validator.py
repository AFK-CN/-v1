from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import SYSTEM_DIR, now_iso
from .skill_package import skill_package_drift


REQUIRED_FILES = (
    "知识库入口.md",
    "README.md",
    "11_Project_Use/项目调用规则.md",
    "14_KB_System/rules/用户操作台.md",
    "14_KB_System/rules/初始化生命周期.md",
    "14_KB_System/rules/输出契约.md",
    "14_KB_System/config/output_contracts.json",
    "14_KB_System/config/search_terms.json",
    "14_KB_System/config/skill_contract.json",
    "14_KB_System/rules/规则权威源.md",
    "14_KB_System/index/controller_routes.json",
    "14_KB_System/index/knowledge_index.json",
    "14_KB_System/index/knowledge_index_summary.md",
    "14_KB_System/index/formal_knowledge_index.json",
    "14_KB_System/index/candidate_asset_index.json",
    "14_KB_System/index/raw_blocked_index.json",
    "14_KB_System/index/task_entry_index.md",
    "14_KB_System/skill_packages/knowledge-base/SKILL.md",
    "14_KB_System/skill_packages/knowledge-base/agents/openai.yaml",
    "14_KB_System/skill_packages/knowledge-base/references/calling-rules.md",
    "14_KB_System/skill_packages/知识库/SKILL.md",
    "14_KB_System/skill_packages/知识库/agents/openai.yaml",
    "14_KB_System/skill_packages/知识库/references/calling-rules.md",
)


def validate_system(root: Path, write_report: bool = False) -> dict[str, Any]:
    root = root.resolve()
    failed = []
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            failed.append(f"missing:{relative}")
    entry_text = read_text(root / "知识库入口.md")
    project_use_text = read_text(root / "11_Project_Use" / "项目调用规则.md")
    skill_text = read_text(root / "14_KB_System" / "skill_packages" / "knowledge-base" / "SKILL.md")
    skill_ui_text = read_text(root / "14_KB_System" / "skill_packages" / "knowledge-base" / "agents" / "openai.yaml")
    zh_skill_text = read_text(root / "14_KB_System" / "skill_packages" / "知识库" / "SKILL.md")
    zh_skill_ui_text = read_text(root / "14_KB_System" / "skill_packages" / "知识库" / "agents" / "openai.yaml")
    task_index_text = read_text(root / "14_KB_System" / "index" / "task_entry_index.md")
    user_console_text = read_text(root / "14_KB_System" / "rules" / "用户操作台.md")
    output_contract_text = read_text(root / "14_KB_System" / "rules" / "输出契约.md")
    controller = load_json(root / "14_KB_System" / "index" / "controller_routes.json", failed, "controller_routes_invalid_json")
    output_contracts = load_json(root / "14_KB_System" / "config" / "output_contracts.json", failed, "output_contracts_invalid_json")
    search_terms = load_json(root / "14_KB_System" / "config" / "search_terms.json", failed, "search_terms_invalid_json")
    account_index = load_json(root / "14_KB_System" / "index" / "account_knowledge_index.json", failed, "account_index_invalid_json")
    raw_blocked_index = load_json(root / "14_KB_System" / "index" / "raw_blocked_index.json", failed, "raw_blocked_index_invalid_json")
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
    if (root / "14_KB_System" / "config" / "skill_contract.json").exists():
        for relative in skill_package_drift(root):
            failed.append(f"skill_package_drift:{relative}")
    health = build_health_summary(root, account_index, route_summary)
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


def build_health_summary(root: Path, account_index: dict[str, Any], route_summary: dict[str, int]) -> dict[str, Any]:
    accounts = account_index.get("accounts", []) if isinstance(account_index.get("accounts"), list) else []
    proposals_dir = root / "13_Evolving_Skills" / "proposals"
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
