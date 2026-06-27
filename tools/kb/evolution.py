from __future__ import annotations

from pathlib import Path

from .runtime import runtime_path
from .schemas import SYSTEM_DIR, now_iso


def write_evolution_report(root: Path) -> dict[str, str | int]:
    root = root.resolve()
    assets_path = root.resolve() / "10_Knowledge" / "candidates" / "generated_assets" / "candidate_topics.jsonl"
    if not assets_path.exists():
        assets_path = root / SYSTEM_DIR / "assets" / "candidate_topics.jsonl"
    topic_count = 0
    if assets_path.exists():
        topic_count = len([line for line in assets_path.read_text(encoding="utf-8").splitlines() if line.strip()])
    report_dir = runtime_path(root, "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest_evolution_candidate_report.md"
    report_path.write_text(
        "\n".join(
            [
                "# 知识库自我进化候选报告",
                "",
                f"生成时间：{now_iso()}",
                "",
                "本报告只生成候选，不修改正式知识库，不修改 active Skill。",
                "",
                f"- 候选选题数量：{topic_count}",
                "- 方法论沉淀：等待 Codex 审核候选资产后写入正式目录。",
                "- Skill 进化：只允许生成 `00_System/shareable/skills/proposals/` 提案，不能自动覆盖 active。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"report": str(report_path.relative_to(root)), "candidate_topics": topic_count}
