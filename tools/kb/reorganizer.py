from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .schemas import as_posix, load_layer_map, now_iso


KEEP_ROOT_NAMES = {
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "ENVIRONMENT.md",
    "requirements.txt",
    "知识库入口.md",
    "requirements-ocr.txt",
    "requirements-video-learning.txt",
}

KEEP_ROOT_DIRS = {
    ".git",
    ".github",
    ".venv",
    "00_Inbox",
    "00_System",
    "10_Knowledge",
    "20_User",
    "90_Temp",
    "99_Archive",
    "tools",
    "tests",
    "数据",
}

LEGACY_ROOT_TARGETS = {
    "02_Viral_Methods": "99_Archive/legacy_formal_libraries/methods",
    "03_Topic_Ideas": "99_Archive/legacy_formal_libraries/topics",
    "04_Platform_Knowledge": "99_Archive/legacy_formal_libraries/platforms",
    "05_Sub_KB_Candidates": "10_Knowledge/candidates/sub_kbs",
    "06_Sub_KB": "99_Archive/legacy_formal_libraries/sub_kbs",
    "07_Trend_Radar": "99_Archive/system_rules_legacy/trend_radar",
    "08_Content_Factory": "99_Archive/content_factory",
    "09_Performance_Feedback": "99_Archive/legacy_formal_libraries/reviews/feedback",
    "10_Weekly_Review": "99_Archive/legacy_formal_libraries/reviews/weekly",
    "12_User_Preferences": "20_User/config/preferences",
    "13_Evolving_Skills": "00_System/shareable/skills",
    "11_Project_Use": "00_System/shareable/docs/project_use",
    "docs": "00_System/shareable/docs",
    "01_Case_Cleaning": "99_Archive/system_rules_legacy/case_cleaning",
    "80_Local": "20_User/local/legacy_80_local",
}

RULE_FILE_TARGETS = {
    "JSON入库清洗规则.md": "00_System/shareable/skills/active/content-processing/references/json-cleaning.md",
    "去重规则.md": "00_System/shareable/skills/active/content-processing/references/deduplication.md",
    "本机使用速查.md": "00_System/shareable/docs/project_use/本机使用速查.md",
}

DELETE_ALLOWLIST = {".DS_Store", "feishu-auth-qrcode.png"}
TARGET_LAYER_DIRS = (
    "00_System/shareable",
    "00_System/runtime/state",
    "00_System/runtime/cache",
    "00_System/runtime/reports",
    "00_System/runtime/logs",
    "00_System/runtime/tasks",
    "00_System/runtime/locks",
    "00_System/runtime/quarantine",
    "10_Knowledge/formal",
    "10_Knowledge/candidates",
    "10_Knowledge/evidence",
    "20_User/config",
    "20_User/data",
    "20_User/feedback",
    "20_User/private",
    "20_User/local",
    "90_Temp/inbox",
    "90_Temp/drafts",
    "90_Temp/exports",
    "90_Temp/scratch",
    "90_Temp/trash_review",
)


def classify_root_item(path: Path) -> dict[str, Any]:
    name = path.name
    if name in LEGACY_ROOT_TARGETS:
        return {"path": name, "action": "move", "target": LEGACY_ROOT_TARGETS[name], "reason": "legacy_root_to_target_layer"}
    if name in KEEP_ROOT_NAMES or name in KEEP_ROOT_DIRS:
        return {"path": name, "action": "keep_root", "target": name, "reason": "root_entry_or_primary_directory"}
    if name in RULE_FILE_TARGETS:
        return {"path": name, "action": "move", "target": RULE_FILE_TARGETS[name], "reason": "route_rule_to_owner"}
    if name.startswith("验收报告_") and name.endswith(".md"):
        return {"path": name, "action": "move", "target": f"00_System/runtime/reports/history/{name}", "reason": "historical_report"}
    if name == "feishu_doc_read":
        return {"path": name, "action": "delete_candidate", "target": "", "reason": "one_time_import_artifact"}
    if name in DELETE_ALLOWLIST:
        return {"path": name, "action": "delete_candidate", "target": "", "reason": "explicit_cleanup_allowlist"}
    return {"path": name, "action": "manual_review", "target": "", "reason": "unknown_root_item"}


def plan_reorganization(root: Path) -> dict[str, Any]:
    root = root.resolve()
    layer_map = load_layer_map(root)
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
        "migration_preview": build_migration_preview(root, layer_map),
        "summary": {
            "move": sum(1 for item in actions if item["action"] == "move"),
            "delete_candidate": sum(1 for item in actions if item["action"] == "delete_candidate"),
            "manual_review": sum(1 for item in actions if item["action"] == "manual_review"),
        },
    }


def build_migration_preview(root: Path, layer_map: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = layer_map.get("legacy_mapping", {})
    if not isinstance(mapping, dict):
        return []
    preview = []
    for source, target in sorted(mapping.items()):
        source_path = root / source
        preview.append(
            {
                "source": source,
                "target": str(target),
                "exists": source_path.exists(),
                "action": "planned_gradual_migration",
            }
        )
    return preview


def write_reorganization_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    plan = plan_reorganization(root)
    report_dir = runtime_path(root, "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "latest_root_reorganization_plan.json"
    md_path = report_dir / "latest_root_reorganization_plan.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_plan(plan), encoding="utf-8")
    return {"plan_json": as_posix(json_path.relative_to(root)), "plan_report": as_posix(md_path.relative_to(root)), **plan["summary"]}


def initialize_layer_structure(root: Path) -> dict[str, Any]:
    root = root.resolve()
    created = []
    existing = []
    for relative in TARGET_LAYER_DIRS:
        path = root / relative
        if path.exists():
            existing.append(relative)
            continue
        path.mkdir(parents=True, exist_ok=True)
        created.append(relative)
    report_dir = runtime_path(root, "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest_layer_init_report.md"
    report_path.write_text(render_layer_init_report(created, existing), encoding="utf-8")
    return {
        "created": len(created),
        "existing": len(existing),
        "report": as_posix(report_path.relative_to(root)),
    }


def render_layer_init_report(created: list[str], existing: list[str]) -> str:
    lines = ["# 分层目录初始化报告", "", f"生成时间：{now_iso()}", "", "## 新建目录", ""]
    lines.extend(f"- {item}" for item in created)
    lines.extend(["", "## 已存在目录", ""])
    lines.extend(f"- {item}" for item in existing)
    return "\n".join(lines) + "\n"


def render_plan(plan: dict[str, Any]) -> str:
    lines = [
        "# 根目录整理计划",
        "",
        f"生成时间：{plan['generated_at']}",
        "",
        "## 渐进迁移预览",
        "",
        "| 旧路径 | 目标层级 | 存在 | 动作 |",
        "| --- | --- | --- | --- |",
    ]
    for item in plan.get("migration_preview", []):
        lines.append(f"| {item['source']} | {item['target']} | {item['exists']} | {item['action']} |")
    lines.extend([
        "",
        "## 根目录清理动作",
        "",
        "| 动作 | 路径 | 目标 | 原因 |",
        "| --- | --- | --- | --- |",
    ])
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
    report_dir = runtime_path(root, "reports")
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
