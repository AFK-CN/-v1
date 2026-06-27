from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import SYSTEM_INDEX_DIR, USER_SYNCABLE_AGENTS_DIR, as_posix, now_iso


SENSITIVE_PATTERN = re.compile(
    r"(password|token|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|密钥|密码)",
    re.IGNORECASE,
)


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default
    return payload if isinstance(payload, dict) else default


def controller_agents(root: Path) -> list[dict[str, Any]]:
    payload = read_json(root / SYSTEM_INDEX_DIR / "controller_routes.json", {"agents": []})
    agents = payload.get("agents", [])
    return [agent for agent in agents if isinstance(agent, dict)]


def build_agent_registry(root: Path) -> list[dict[str, Any]]:
    rows = []
    for agent in controller_agents(root):
        agent_id = str(agent.get("id", "")).strip()
        if not agent_id:
            continue
        rows.append(
            {
                "agent_id": agent_id,
                "agent_name": str(agent.get("name", agent_id)),
                "agent_type": str(agent.get("kind", "logical_role")),
                "owner_layer": "00_System/shareable",
                "primary_function": str(agent.get("responsibility", "")),
                "capabilities": infer_capabilities(agent_id),
                "entry_command": "@知识库",
                "service": "local_knowledge_base",
                "auth_required": "no",
                "auth_status": "not_required",
                "credential_location_hint": "",
                "allowed_actions": infer_allowed_actions(agent_id),
                "blocked_actions": infer_blocked_actions(agent_id),
                "memory_scope": infer_memory_scope(agent_id),
                "last_verified_at": "",
                "notes": "由 controller_routes.json 生成；当前为逻辑角色，不是独立登录实体。",
            }
        )
    return rows


def infer_capabilities(agent_id: str) -> str:
    mapping = {
        "controller": "意图识别、路由选择、任务调度",
        "planner": "任务拆解、步骤规划",
        "retriever": "索引检索、候选证据检索",
        "workflow_runner": "本地脚本调用、任务状态维护",
        "account_knowledge": "账号中心维护、方向知识读取",
        "content_generator": "选题、文案、脚本生成",
        "skill_evolution": "规则沉淀 proposal",
        "review": "截图/表格/表现复盘",
        "auditor": "系统验证、边界审计",
    }
    return mapping.get(agent_id, "按系统路由定义执行")


def infer_allowed_actions(agent_id: str) -> str:
    if agent_id == "workflow_runner":
        return "写 runtime、候选报告和任务状态；按规则调用本地脚本"
    if agent_id == "skill_evolution":
        return "写 Skill proposal 和复盘建议"
    if agent_id == "content_generator":
        return "基于正式知识和候选证据生成内容"
    if agent_id == "retriever":
        return "读取允许范围内的索引、正式知识和候选证据"
    return "按 controller_routes.json 中的路由边界执行"


def infer_blocked_actions(agent_id: str) -> str:
    common = "不得读取默认禁止目录；不得写真实凭证；不得绕过正式入库审核"
    if agent_id == "content_generator":
        return f"{common}；不得直接反写正式知识"
    if agent_id == "skill_evolution":
        return f"{common}；不得直接覆盖 active Skill"
    return common


def infer_memory_scope(agent_id: str) -> str:
    if agent_id in {"controller", "auditor"}:
        return "可读取记忆总入口和系统记忆规则；写入需走候选"
    if agent_id == "skill_evolution":
        return "可生成规则记忆候选和 Skill proposal"
    if agent_id == "review":
        return "可生成 resolved issue 和复盘记忆候选"
    return "只读必要记忆入口；默认不写长期记忆"


def render_agent_registry(rows: list[dict[str, Any]]) -> str:
    headers = [
        "agent_id",
        "agent_name",
        "agent_type",
        "owner_layer",
        "primary_function",
        "capabilities",
        "entry_command",
        "service",
        "auth_required",
        "auth_status",
        "credential_location_hint",
        "allowed_actions",
        "blocked_actions",
        "memory_scope",
        "last_verified_at",
        "notes",
    ]
    lines = [
        "# 智能体登记表",
        "",
        f"更新时间：{now_iso()}",
        "",
        "当前登记表记录智能体功能、ID、能力和记忆边界；真实登录状态放在 `20_User/private/agents/`。",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [escape_cell(str(row.get(header, ""))) for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_agent_registry(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rows = build_agent_registry(root)
    target = root / USER_SYNCABLE_AGENTS_DIR / "agent_registry.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_agent_registry(rows), encoding="utf-8")
    validation = validate_agent_registry(root)
    return {
        "ok": validation["ok"],
        "written": as_posix(target.relative_to(root)),
        "agent_count": len(rows),
        "failed": validation["failed"],
    }


def validate_agent_registry(root: Path) -> dict[str, Any]:
    root = root.resolve()
    failed: list[str] = []
    registry = root / USER_SYNCABLE_AGENTS_DIR / "agent_registry.md"
    if not registry.exists():
        failed.append("missing:20_User/syncable/agents/agent_registry.md")
        return {"ok": False, "failed": failed, "agent_count": 0}
    text = registry.read_text(encoding="utf-8")
    if SENSITIVE_PATTERN.search(text):
        failed.append("agent_registry_contains_sensitive_term")
    missing = []
    for agent in controller_agents(root):
        agent_id = str(agent.get("id", "")).strip()
        if agent_id and f"| {agent_id} |" not in text:
            missing.append(agent_id)
    for agent_id in missing:
        failed.append(f"agent_registry_missing_controller_agent:{agent_id}")
    return {"ok": not failed, "failed": failed, "agent_count": len(controller_agents(root))}
