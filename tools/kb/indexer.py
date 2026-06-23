from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scanner import scan_files
from .schemas import FORMAL_KNOWLEDGE_DIRS, RAW_INPUT_DIRS, SYSTEM_DIR, as_posix, now_iso


def index_dir(root: Path) -> Path:
    return root / SYSTEM_DIR / "index"


def calling_scope(relative_path: str) -> str:
    first = relative_path.split("/", 1)[0]
    if first in RAW_INPUT_DIRS:
        return "blocked_by_default"
    if first == "99_Archive":
        return "blocked_by_default"
    if relative_path.startswith("13_Evolving_Skills/proposals/") or relative_path.startswith("13_Evolving_Skills/history/"):
        return "internal_or_review"
    if relative_path.startswith("13_Evolving_Skills/active/"):
        return "allowed"
    if first == SYSTEM_DIR:
        return "system_internal"
    if first in FORMAL_KNOWLEDGE_DIRS or relative_path in {
        "知识库入口.md",
        "README.md",
        "14_KB_System/rules/用户操作台.md",
        "14_KB_System/index/controller_routes.json",
        "14_KB_System/rules/本机使用速查.md",
        "14_KB_System/rules/知识库运行规则.md",
    }:
        return "allowed"
    return "internal_or_review"


def purpose_for_path(relative_path: str) -> str:
    if relative_path == "知识库入口.md":
        return "knowledge_base_entry"
    if relative_path.startswith("02_Viral_Methods/"):
        return "viral_method"
    if relative_path.startswith("03_Topic_Ideas/"):
        return "formal_topic_library"
    if relative_path.startswith("06_Sub_KB/"):
        return "confirmed_sub_knowledge_base"
    if relative_path.startswith("13_Evolving_Skills/active/"):
        return "active_skill"
    if relative_path.startswith(tuple(f"{item}/" for item in RAW_INPUT_DIRS)):
        return "raw_input"
    return "supporting_file"


def build_knowledge_index(root: Path) -> dict[str, Any]:
    scan = scan_files(root)
    indexed = []
    for item in scan["files"]:
        relative_path = item["path"]
        indexed.append(
            {
                "path": relative_path,
                "type": item["suffix"].lstrip(".") or "unknown",
                "purpose": purpose_for_path(relative_path),
                "content_status": "new" if item["is_raw_input"] else "approved",
                "calling_scope": calling_scope(relative_path),
                "is_raw_input": item["is_raw_input"],
                "cleanup_candidate": item["cleanup_candidate"],
                "updated_at": item["modified_at"],
            }
        )
    return {
        "generated_at": now_iso(),
        "root": scan["root"],
        "files": indexed,
        "cleanup_candidates": scan["cleanup_candidates"],
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_indexes(root: Path) -> dict[str, Any]:
    root = root.resolve()
    target = index_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    index = build_knowledge_index(root)
    write_json(target / "knowledge_index.json", index)
    write_json(target / "file_relation_index.json", build_file_relations(index))
    write_json(root / SYSTEM_DIR / "state" / "content_state.json", build_content_state(index))
    (target / "知识库总索引.md").write_text(render_human_index(index), encoding="utf-8")
    (target / "task_entry_index.md").write_text(render_task_entry_index(), encoding="utf-8")
    return {
        "index_files": 4,
        "index_dir": as_posix(target.relative_to(root)),
        "file_count": len(index["files"]),
        "cleanup_candidate_count": len(index["cleanup_candidates"]),
    }


def build_content_state(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": index["generated_at"],
        "items": [
            {
                "path": item["path"],
                "content_status": item["content_status"],
                "calling_scope": item["calling_scope"],
                "is_raw_input": item["is_raw_input"],
                "cleanup_candidate": item["cleanup_candidate"],
            }
            for item in index["files"]
        ],
    }


def build_file_relations(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": index["generated_at"],
        "relations": [
            {"from": "知识库入口.md", "to": "14_KB_System/rules/用户操作台.md", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": "14_KB_System/index/controller_routes.json", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": "14_KB_System/rules/本机使用速查.md", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": "README.md", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": "14_KB_System/rules/知识库运行规则.md", "relation": "entry_requires"},
            {"from": "14_KB_System/rules/选题生成规则.md", "to": "03_Topic_Ideas/选题灵感库_v1.md", "relation": "defines_schema_for"},
            {"from": "14_KB_System/rules/周复盘规则.md", "to": "13_Evolving_Skills/proposals", "relation": "may_create_proposal"},
        ],
    }


def render_human_index(index: dict[str, Any]) -> str:
    lines = [
        "# 知识库总索引",
        "",
        f"生成时间：{index['generated_at']}",
        f"文件数量：{len(index['files'])}",
        f"清理候选：{len(index['cleanup_candidates'])}",
        "",
        "## 重要入口",
        "",
        "- `知识库入口.md`：主入口。",
        "- `14_KB_System/rules/用户操作台.md`：用户可复制入口。",
        "- `14_KB_System/index/controller_routes.json`：总控路由表。",
        "- `11_Project_Use/项目调用规则.md`：其他项目调用入口。",
        "- `14_KB_System/`：系统操作层，只存放索引、状态、任务、日志、报告和候选资产。",
        "",
        "## 文件清单",
        "",
        "| 路径 | 用途 | 状态 | 调用范围 |",
        "| --- | --- | --- | --- |",
    ]
    for item in index["files"]:
        lines.append(f"| {item['path']} | {item['purpose']} | {item['content_status']} | {item['calling_scope']} |")
    return "\n".join(lines) + "\n"


def render_task_entry_index() -> str:
    return """# 任务入口索引

## 通用使用

- 先读：`知识库入口.md`、`14_KB_System/rules/用户操作台.md`、`14_KB_System/index/controller_routes.json`、`14_KB_System/rules/本机使用速查.md`。
- 默认入口：`@知识库 + 需求`。兼容入口：`knowledge-base + 需求`。
- 总控优先：先用 `controller_routes.json` 判断任务类型，再按本索引读取少量相关文件。

## 内容创作

- 读取：`02_Viral_Methods/`、`03_Topic_Ideas/`、`04_Platform_Knowledge/`、`08_Content_Factory/`。
- 知识成长/自媒体方向额外读取：`06_Sub_KB/知识成长自媒体方法论/`。
- 当用户提到账号名、知识成长、自媒体、赚钱方向、出选题、写文案、口播、对标账号时，先读取：`14_KB_System/index/account_knowledge_index.md`。
- 如命中账号中心，例如姜胡说，继续读取：`06_Sub_KB/知识成长自媒体方法论/账号中心/{账号}/账号索引.md`、`内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`，再按方向读取 `方向方法论总结.md`、`粗扫内容和选题.md`。
- 账号中心调用默认禁止全扫候选区；需要证据时再读取正式单卡，需要核查时再读取逐字稿。
- 内容生成不能直接反写正式知识；可沉淀的规则进入复盘或 Skill proposal。

## 账号学习

- 读取：`14_KB_System/index/account_knowledge_index.md`、`14_KB_System/index/controller_routes.json`、`13_Evolving_Skills/active/视频深度学习Skill_v1.md`。
- 工作流：粗扫 -> 深度学习 -> 候选卡 -> 审核 -> 用户确认 -> 正式账号中心。
- 脚本只能生成候选资产、学习卡、报告和状态；正式账号知识必须经过审核。

## 复盘和自我学习

- 读取：`14_KB_System/rules/周复盘规则.md`、`10_Weekly_Review/`、`09_Performance_Feedback/`、`12_User_Preferences/`。
- Skill 更新只能写入 `13_Evolving_Skills/proposals/`。
- 当用户说“以后都这样”“沉淀成规则”“更新 Skill”时，进入 Skill 沉淀路由，只生成 proposal，不直接改 active。

## 其他项目调用

- 读取：`11_Project_Use/项目调用规则.md`。
- 默认禁止调用：`00_Inbox/`、`数据/`、`99_Archive/`、未确认 Skill 提案。
- 其他项目优先调用全局 `@知识库` Skill；若入口失效，回退到读取 `知识库入口.md`。

## 代码批处理

- 读取：`14_KB_System/tasks/`、`14_KB_System/reports/`、`14_KB_System/logs/`。
- 代码只能生成候选资产和报告，不能直接写正式知识。

## 系统审计

- 读取：`14_KB_System/index/controller_routes.json`、`14_KB_System/index/knowledge_index.json`、`14_KB_System/index/account_knowledge_index.json`、`14_KB_System/config/output_contracts.json`。
- 运行：`.venv/bin/python -m tools.kb.cli --root . validate-system` 或 `.venv/bin/python -m tools.kb.cli --root . dashboard`。
- 输出：入口、索引、路由、Skill 包、账号中心、proposal、候选注册表、输出契约和报告状态。
"""
