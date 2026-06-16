from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .schemas import SYSTEM_DIR, as_posix, now_iso


KEEP_ROOT_NAMES = {
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "知识库入口.md",
    "requirements-ocr.txt",
    "requirements-video-learning.txt",
}

KEEP_ROOT_DIRS = {
    ".git",
    ".venv",
    "00_Inbox",
    "01_Case_Cleaning",
    "02_Viral_Methods",
    "03_Topic_Ideas",
    "04_Platform_Knowledge",
    "05_Sub_KB_Candidates",
    "06_Sub_KB",
    "07_Trend_Radar",
    "08_Content_Factory",
    "09_Performance_Feedback",
    "10_Weekly_Review",
    "11_Project_Use",
    "12_User_Preferences",
    "13_Evolving_Skills",
    "14_KB_System",
    "99_Archive",
    "tools",
    "tests",
    "docs",
    "数据",
}

RULE_FILES = {
    "JSON入库清洗规则.md",
    "Skill进化与回滚规则.md",
    "使用文档.md",
    "去重规则.md",
    "周复盘规则.md",
    "子知识库创建规则.md",
    "本机使用速查.md",
    "爆款方法论沉淀规则.md",
    "知识库运行规则.md",
    "选题生成规则.md",
}

DELETE_ALLOWLIST = {".DS_Store", "feishu-auth-qrcode.png"}


def classify_root_item(path: Path) -> dict[str, Any]:
    name = path.name
    if name in KEEP_ROOT_NAMES or name in KEEP_ROOT_DIRS:
        return {"path": name, "action": "keep_root", "target": name, "reason": "root_entry_or_primary_directory"}
    if name in RULE_FILES:
        return {"path": name, "action": "move", "target": f"{SYSTEM_DIR}/rules/{name}", "reason": "centralize_rules"}
    if name.startswith("验收报告_") and name.endswith(".md"):
        return {"path": name, "action": "move", "target": f"{SYSTEM_DIR}/reports/history/{name}", "reason": "historical_report"}
    if name == "feishu_doc_read":
        return {"path": name, "action": "move", "target": "99_Archive/feishu_doc_read", "reason": "import_artifact_not_formal_knowledge"}
    if name in DELETE_ALLOWLIST:
        return {"path": name, "action": "delete_candidate", "target": "", "reason": "explicit_cleanup_allowlist"}
    return {"path": name, "action": "manual_review", "target": "", "reason": "unknown_root_item"}


def plan_reorganization(root: Path) -> dict[str, Any]:
    root = root.resolve()
    actions = []
    for item in sorted(root.iterdir(), key=lambda value: value.name):
        if item.name in {".git", ".venv"}:
            continue
        action = classify_root_item(item)
        if action["action"] != "keep_root":
            actions.append(action)
    return {
        "generated_at": now_iso(),
        "root": str(root),
        "actions": actions,
        "summary": {
            "move": sum(1 for item in actions if item["action"] == "move"),
            "delete_candidate": sum(1 for item in actions if item["action"] == "delete_candidate"),
            "manual_review": sum(1 for item in actions if item["action"] == "manual_review"),
        },
    }


def write_reorganization_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    plan = plan_reorganization(root)
    report_dir = root / SYSTEM_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "latest_root_reorganization_plan.json"
    md_path = report_dir / "latest_root_reorganization_plan.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_plan(plan), encoding="utf-8")
    return {"plan_json": as_posix(json_path.relative_to(root)), "plan_report": as_posix(md_path.relative_to(root)), **plan["summary"]}


def render_plan(plan: dict[str, Any]) -> str:
    lines = [
        "# 根目录整理计划",
        "",
        f"生成时间：{plan['generated_at']}",
        "",
        "| 动作 | 路径 | 目标 | 原因 |",
        "| --- | --- | --- | --- |",
    ]
    for item in plan["actions"]:
        lines.append(f"| {item['action']} | {item['path']} | {item['target']} | {item['reason']} |")
    return "\n".join(lines) + "\n"


def apply_reorganization_plan(root: Path, plan_path: Path, allow_delete: bool = False) -> dict[str, Any]:
    root = root.resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    applied = []
    skipped = []
    for item in plan.get("actions", []):
        source = root / item["path"]
        target = root / item["target"] if item.get("target") else None
        if item["action"] == "move":
            if not source.exists():
                skipped.append({"path": item["path"], "reason": "missing_source"})
                continue
            assert target is not None
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                skipped.append({"path": item["path"], "reason": "target_exists"})
                continue
            shutil.move(str(source), str(target))
            applied.append(item)
        elif item["action"] == "delete_candidate":
            if allow_delete and source.exists() and source.name in DELETE_ALLOWLIST:
                if source.is_dir():
                    shutil.rmtree(source)
                else:
                    source.unlink()
                applied.append(item)
            else:
                skipped.append({"path": item["path"], "reason": "delete_not_allowed"})
    report_dir = root / SYSTEM_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest_root_reorganization_apply_report.md"
    report_path.write_text(render_apply_report(applied, skipped), encoding="utf-8")
    return {"applied": len(applied), "skipped": len(skipped), "report": as_posix(report_path.relative_to(root))}


def render_apply_report(applied: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> str:
    lines = ["# 根目录整理执行报告", "", f"生成时间：{now_iso()}", "", "## 已执行", ""]
    lines.extend(f"- {item['action']}: {item['path']} -> {item.get('target', '')}" for item in applied)
    lines.extend(["", "## 已跳过", ""])
    lines.extend(f"- {item['path']}: {item['reason']}" for item in skipped)
    return "\n".join(lines) + "\n"
