from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SOURCE_CONFIG = "00_System/shareable/config/graph_sources.json"
VIEW_CONFIG = "00_System/shareable/config/graph_views.json"
DEFAULT_OUTPUT = "00_System/runtime/graphify"

DEFAULT_SOURCE_CONFIG: dict[str, Any] = {
    "version": "1.0",
    "engine": {"package": "graphifyy", "pinned_version": "0.9.15"},
    "output_root": DEFAULT_OUTPUT,
    "formal_index": "10_Knowledge/evidence/index/formal_knowledge_index.json",
    "candidate_index": "10_Knowledge/evidence/index/candidate_asset_index.json",
    "blocked_prefixes": [
        "数据/",
        "00_Inbox/",
        "99_Archive/",
        "80_Local/",
        "20_User/private/",
        "00_System/runtime/",
        "10_Knowledge/candidates/",
        "90_Temp/",
    ],
    "system_roots": [
        "00_System/shareable/config/",
        "00_System/shareable/agents/",
        "00_System/shareable/index/",
        "00_System/shareable/memory/",
        "00_System/shareable/rules/",
        "00_System/shareable/schemas/",
        "00_System/shareable/skills/active/",
        "00_System/shareable/docs/",
        "tools/kb/",
    ],
    "system_files": ["知识库入口.md", "00_System/shareable/skill_packages/知识库/SKILL.md"],
    "allowed_extensions": [".md", ".py", ".json"],
    "graphify_extract_extensions": [".md", ".py"],
    "max_extract_bytes": 1_048_576,
    "candidate_policy": "summary_only",
    "formal_policy": "index_only",
}

DEFAULT_VIEW_CONFIG: dict[str, Any] = {
    "version": "1.0",
    "default_view": "system",
    "views": [
        {"id": "system", "name": "系统", "description": "入口、路由、规则、配置、工具与执行关系"},
        {"id": "knowledge", "name": "正式知识", "description": "正式知识文件、章节、来源与所属领域"},
        {"id": "accounts", "name": "账号", "description": "账号中心、方向、方法与正式证据"},
        {"id": "workflows", "name": "流程", "description": "学习阶段、确认门、工具和产出物"},
        {"id": "cross_layer", "name": "跨层关系", "description": "系统如何调用知识、流程如何连接知识"},
    ],
    "layers": {
        "system": "#3b82f6",
        "formal_knowledge": "#10b981",
        "account": "#8b5cf6",
        "workflow": "#f59e0b",
        "candidate_summary": "#64748b",
    },
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def load_source_config(root: Path) -> dict[str, Any]:
    value = _read_json(root.resolve() / SOURCE_CONFIG, DEFAULT_SOURCE_CONFIG)
    return value if isinstance(value, dict) else dict(DEFAULT_SOURCE_CONFIG)


def load_view_config(root: Path) -> dict[str, Any]:
    value = _read_json(root.resolve() / VIEW_CONFIG, DEFAULT_VIEW_CONFIG)
    return value if isinstance(value, dict) else dict(DEFAULT_VIEW_CONFIG)


def output_root(root: Path, config: dict[str, Any] | None = None) -> Path:
    config = config or load_source_config(root)
    return root.resolve() / str(config.get("output_root") or DEFAULT_OUTPUT)


def normalize_relative(value: str | Path) -> str:
    text = Path(str(value)).as_posix().lstrip("./")
    return text.rstrip("/") + ("/" if str(value).replace("\\", "/").endswith("/") else "")


def is_blocked(relative: str, config: dict[str, Any]) -> bool:
    path = normalize_relative(relative).rstrip("/")
    for raw_prefix in config.get("blocked_prefixes") or []:
        prefix = normalize_relative(str(raw_prefix)).rstrip("/")
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def safe_repo_path(root: Path, relative: str, config: dict[str, Any]) -> Path | None:
    if not relative or is_blocked(relative, config):
        return None
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate
