from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import SYSTEM_DIR, as_posix, now_iso
from .validator import validate_system


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def active_skills(root: Path) -> list[str]:
    active_dir = root / "13_Evolving_Skills" / "active"
    if not active_dir.exists():
        return []
    return sorted(path.name for path in active_dir.glob("*.md"))


def pending_proposals(root: Path) -> list[str]:
    proposals_dir = root / "13_Evolving_Skills" / "proposals"
    if not proposals_dir.exists():
        return []
    return sorted(path.name for path in proposals_dir.glob("*.md") if path.name != "Skill提案模板.md")


def task_counts(root: Path) -> dict[str, int]:
    base = runtime_path(root, "tasks")
    counts: dict[str, int] = {}
    for status in ("pending", "running", "stale", "done", "failed", "paused"):
        current = base / status
        counts[status] = len([path for path in current.iterdir() if path.is_dir()]) if current.exists() else 0
    return counts


def account_summary(root: Path) -> dict[str, Any]:
    payload = read_json(root / SYSTEM_DIR / "index" / "account_knowledge_index.json", {"accounts": []})
    accounts = payload.get("accounts", []) if isinstance(payload.get("accounts"), list) else []
    result = []
    direction_count = 0
    for account in accounts:
        directions = account.get("directions", []) if isinstance(account, dict) else []
        direction_count += len(directions) if isinstance(directions, list) else 0
        result.append(
            {
                "account_id": account.get("account_id", ""),
                "account_name": account.get("account_name", ""),
                "platform": account.get("platform", ""),
                "direction_count": len(directions) if isinstance(directions, list) else 0,
            }
        )
    return {"account_count": len(result), "formal_direction_count": direction_count, "accounts": result}


def candidate_summary(root: Path) -> dict[str, Any]:
    path = runtime_path(root, "cache") / "assets" / "candidate_topics.jsonl"
    if not path.exists():
        path = root / SYSTEM_DIR / "assets" / "candidate_topics.jsonl"
    if not path.exists():
        return {"candidate_topic_count": 0, "unique_source_count": 0, "top_directions": []}
    count = 0
    source_ids: set[str] = set()
    directions: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            if row.get("source_id"):
                source_ids.add(str(row["source_id"]))
            direction = str(row.get("领域") or "未归类")
            directions[direction] = directions.get(direction, 0) + 1
    top = sorted(directions.items(), key=lambda item: item[1], reverse=True)[:10]
    return {"candidate_topic_count": count, "unique_source_count": len(source_ids), "top_directions": [{"direction": k, "count": v} for k, v in top]}


def learning_summary(root: Path) -> dict[str, Any]:
    manifest = read_json(root / "01_Case_Cleaning" / "video_learning" / "state" / "learning_manifest.json", {"items": {}})
    items = manifest.get("items", {}) if isinstance(manifest, dict) else {}
    status_counts: dict[str, int] = {}
    if isinstance(items, dict):
        iterable = items.values()
    elif isinstance(items, list):
        iterable = items
    else:
        iterable = []
    for item in iterable:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {"manifest_item_count": sum(status_counts.values()), "status_counts": status_counts}


def registry(root: Path) -> dict[str, Any]:
    accounts = account_summary(root)
    candidates = candidate_summary(root)
    learning = learning_summary(root)
    active = active_skills(root)
    proposals = pending_proposals(root)
    return {
        "generated_at": now_iso(),
        "source": "tools.kb.dashboard",
        "active_skills": active,
        "pending_proposals": proposals,
        "accounts": accounts,
        "candidates": candidates,
        "learning": learning,
        "tasks": task_counts(root),
    }


def next_actions(data: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if not validation.get("ok"):
        actions.append("先修复 validate-system 失败项。")
    if data["pending_proposals"]:
        actions.append("处理待确认 Skill proposal。")
    running = data["tasks"].get("running", 0)
    pending = data["tasks"].get("pending", 0)
    if running or pending:
        actions.append("检查 pending/running 任务状态，必要时暂停或收尾。")
    if data["candidates"].get("candidate_topic_count", 0):
        actions.append("抽查候选资产，确认是否需要进入账号学习或正式入库审核。")
    if not actions:
        actions.append("系统状态正常；下一步可直接进行内容生产、账号学习或复盘。")
    return actions


def render_dashboard(data: dict[str, Any], validation: dict[str, Any]) -> str:
    lines = [
        "# 知识库运行面板",
        "",
        f"生成时间：{data['generated_at']}",
        "",
        "## 1. 系统入口",
        "",
        f"- validate-system：{'通过' if validation.get('ok') else '未通过'}",
        f"- 失败项：{', '.join(validation.get('failed', [])) or '无'}",
        "",
        "## 2. Active Skill",
        "",
    ]
    lines.extend(f"- {name}" for name in data["active_skills"])
    lines.extend(["", "## 3. 待确认 Proposal", ""])
    if data["pending_proposals"]:
        lines.extend(f"- {name}" for name in data["pending_proposals"])
    else:
        lines.append("- 无")
    accounts = data["accounts"]
    lines.extend(
        [
            "",
            "## 4. 账号中心",
            "",
            f"- 账号数：{accounts['account_count']}",
            f"- 正式方向数：{accounts['formal_direction_count']}",
        ]
    )
    for account in accounts["accounts"]:
        lines.append(f"- {account['account_name']} / {account['platform']}：{account['direction_count']} 个方向")
    candidates = data["candidates"]
    lines.extend(
        [
            "",
            "## 5. 候选与注册表",
            "",
            f"- 候选主题行数：{candidates['candidate_topic_count']}",
            f"- 唯一 source_id 数：{candidates['unique_source_count']}",
        ]
    )
    for item in candidates["top_directions"][:5]:
        lines.append(f"- {item['direction']}：{item['count']}")
    learning = data["learning"]
    lines.extend(["", "## 6. 最近学习状态", "", f"- manifest 条目数：{learning['manifest_item_count']}"])
    for status, count in sorted(learning["status_counts"].items()):
        lines.append(f"- {status}：{count}")
    lines.extend(["", "## 7. 任务状态", ""])
    for status, count in data["tasks"].items():
        lines.append(f"- {status}：{count}")
    lines.extend(["", "## 8. 建议下一步", ""])
    lines.extend(f"- {action}" for action in next_actions(data, validation))
    return "\n".join(lines) + "\n"


def write_dashboard(root: Path) -> dict[str, Any]:
    root = root.resolve()
    validation = validate_system(root)
    data = registry(root)
    data["validation"] = {"ok": validation.get("ok"), "failed": validation.get("failed", [])}
    registry_path = runtime_path(root, "state") / "kb_registry.json"
    report_json = runtime_path(root, "reports") / "latest_kb_dashboard.json"
    report_md = runtime_path(root, "reports") / "latest_kb_dashboard.md"
    write_json(registry_path, data)
    write_json(report_json, data)
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(render_dashboard(data, validation), encoding="utf-8")
    return {
        "ok": bool(validation.get("ok")),
        "registry": as_posix(registry_path.relative_to(root)),
        "dashboard_json": as_posix(report_json.relative_to(root)),
        "dashboard": as_posix(report_md.relative_to(root)),
        "active_skill_count": len(data["active_skills"]),
        "pending_proposal_count": len(data["pending_proposals"]),
        "candidate_topic_count": data["candidates"]["candidate_topic_count"],
        "unique_source_count": data["candidates"]["unique_source_count"],
    }
