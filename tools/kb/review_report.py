from __future__ import annotations

import json
from pathlib import Path

from .runtime import runtime_path
from .schemas import SYSTEM_DIR, now_iso


def write_review_report(root: Path) -> dict[str, str]:
    root = root.resolve()
    reports = runtime_path(root, "reports")
    reports.mkdir(parents=True, exist_ok=True)
    index_path = root / SYSTEM_DIR / "index" / "knowledge_index.json"
    topics_path = root.resolve() / "10_Knowledge" / "candidates" / "generated_assets" / "candidate_topics.jsonl"
    if not topics_path.exists():
        topics_path = root / SYSTEM_DIR / "assets" / "candidate_topics.jsonl"
    file_count = 0
    cleanup_count = 0
    topic_count = 0
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        file_count = len(index.get("files", []))
        cleanup_count = len(index.get("cleanup_candidates", []))
    if topics_path.exists():
        topic_count = len([line for line in topics_path.read_text(encoding="utf-8").splitlines() if line.strip()])
    report = reports / "latest_kb_system_review_report.md"
    report.write_text(
        "\n".join(
            [
                "# 知识库底座审核报告",
                "",
                f"生成时间：{now_iso()}",
                "",
                f"- 索引文件数：{file_count}",
                f"- 清理候选数：{cleanup_count}",
                f"- 候选选题数：{topic_count}",
                "",
                "## Codex 审核建议",
                "",
                "- 先看清理候选，不直接删除。",
                "- 再看候选 Top10，判断分类和证据是否合理。",
                "- 通过后再决定是否沉淀到正式知识目录。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"report": str(report.relative_to(root))}
