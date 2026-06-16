from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import SYSTEM_DIR, now_iso


REQUIRED_FILES = (
    "知识库入口.md",
    "README.md",
    "11_Project_Use/项目调用规则.md",
    "14_KB_System/index/knowledge_index.json",
    "14_KB_System/index/task_entry_index.md",
    "14_KB_System/assets/candidate_topics.jsonl",
    "14_KB_System/reports/latest_kb_system_review_report.md",
)


def validate_system(root: Path) -> dict[str, Any]:
    root = root.resolve()
    failed = []
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            failed.append(f"missing:{relative}")
    entry_text = read_text(root / "知识库入口.md")
    project_use_text = read_text(root / "11_Project_Use" / "项目调用规则.md")
    if "索引" not in entry_text:
        failed.append("entry_missing_index_first_rule")
    if "禁止全盘扫库" not in project_use_text and "禁止全量扫库" not in project_use_text:
        failed.append("project_use_missing_no_full_scan_rule")
    if "数据" not in project_use_text:
        failed.append("project_use_missing_data_protection")
    report_dir = root / SYSTEM_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest_system_validation_report.md"
    report_path.write_text(render_validation_report(failed), encoding="utf-8")
    return {"ok": not failed, "failed": failed, "report": str(report_path.relative_to(root))}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def render_validation_report(failed: list[str]) -> str:
    lines = ["# 知识库系统验收报告", "", f"生成时间：{now_iso()}", "", f"结果：{'通过' if not failed else '未通过'}", ""]
    if failed:
        lines.append("## 失败项")
        lines.extend(f"- {item}" for item in failed)
    else:
        lines.append("关键入口、索引、候选资产、调用规则均已具备。")
    return "\n".join(lines) + "\n"

