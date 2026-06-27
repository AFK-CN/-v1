from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import EVIDENCE_INDEX_DIR, SYSTEM_CONFIG_DIR, SYSTEM_INDEX_DIR, SYSTEM_SKILL_PACKAGES_DIR, as_posix


CONTRACT_PATH = Path(SYSTEM_CONFIG_DIR) / "skill_contract.json"


def load_skill_contract(root: Path) -> dict[str, Any]:
    path = root.resolve() / CONTRACT_PATH
    if not path.exists():
        return {
            "version": 1,
            "kb_root_mode": "repository_root",
            "startup_read_order": ["知识库入口.md", f"{SYSTEM_INDEX_DIR}/task_entry_index.md"],
            "blocked_dirs": ["数据/", "00_Inbox/", "99_Archive/"],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("skill_contract must be a JSON object")
    payload.setdefault("kb_root_mode", "repository_root")
    payload.setdefault("startup_read_order", ["知识库入口.md", f"{SYSTEM_INDEX_DIR}/task_entry_index.md"])
    payload.setdefault("blocked_dirs", ["数据/", "00_Inbox/", "99_Archive/"])
    return payload


def expected_skill_package_files(root: Path) -> dict[str, str]:
    contract = load_skill_contract(root)
    startup = [str(item) for item in contract.get("startup_read_order", [])]
    blocked = list(dict.fromkeys(str(item) for item in contract.get("blocked_dirs", [])))
    return {
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/SKILL.md": render_skill("knowledge-base", startup, blocked, english=True),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/agents/openai.yaml": render_agent_yaml(),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/references/calling-rules.md": render_calling_rules(startup, blocked, english=True),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/知识库/SKILL.md": render_skill("知识库", startup, blocked, english=False),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/知识库/agents/openai.yaml": render_agent_yaml(),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/知识库/references/calling-rules.md": render_calling_rules(startup, blocked, english=False),
    }


def render_skill(name: str, startup: list[str], blocked: list[str], english: bool) -> str:
    startup_lines = "\n".join(f"- `<KB_ROOT>/{path}`" for path in startup)
    blocked_lines = ", ".join(f"`{path}`" for path in blocked)
    if english:
        return f"""---
name: {name}
description: Use the local Markdown knowledge base from its repository root. Route through indexes first and avoid raw protected data by default.
---

# Knowledge Base

Treat `<KB_ROOT>` as the repository root of this knowledge base. Start with the fixed entry files generated from `skill_contract.json`:

{startup_lines}

Do not scan the whole knowledge base by default. Do not read protected directories by default: {blocked_lines}.

Use `<KB_ROOT>/{SYSTEM_INDEX_DIR}/controller_routes.json` for routing. The agents listed there are logical AI roles, not independent processes or permission boundaries.

For candidate retrieval, use `search-candidates`; if it returns `requires_init`, stop and ask for `kb init` instead of reading legacy assets.
"""
    return f"""---
name: {name}
description: 使用本机 Markdown 知识库。先走索引和路由，不默认读取原始资料。
---

# 知识库

触发：`@知识库`、`使用知识库`、`调用知识库`、`读取知识库`。

`<KB_ROOT>` 表示当前知识库仓库根目录。固定入口文件来自 `skill_contract.json`：

{startup_lines}

默认禁止全盘扫库；默认不读取受保护目录：{blocked_lines}。

路由以 `<KB_ROOT>/{SYSTEM_INDEX_DIR}/controller_routes.json` 为准。里面的 Agent 是同一次 AI 调用中的逻辑职责，不是独立进程、权限隔离或安全边界。

候选检索使用 `search-candidates`；如果返回 `requires_init`，停止并提示先执行 `kb init`，不要回读旧 assets。
"""


def render_agent_yaml() -> str:
    return 'interface:\n  display_name: "知识库"\n  short_description: "总控：按索引、路由和输出契约调用本机知识库"\n'


def render_calling_rules(startup: list[str], blocked: list[str], english: bool = False) -> str:
    startup_lines = "\n".join(
        f"1. `<KB_ROOT>/{path}`" if index == 0 else f"{index + 1}. `<KB_ROOT>/{path}`"
        for index, path in enumerate(startup)
    )
    blocked_lines = "\n".join(f"- `{path}`" for path in blocked)
    title = "Knowledge-base calling rules" if english else "知识库调用规则"
    return f"""# {title}

## Entry order

`<KB_ROOT>` means the repository root of the knowledge base.

{startup_lines}

## Boundaries

Do not scan the whole knowledge base by default. 默认不读取：

{blocked_lines}

## Authority

- Routing: `<KB_ROOT>/{SYSTEM_INDEX_DIR}/controller_routes.json`
- Skill package source: `<KB_ROOT>/{SYSTEM_CONFIG_DIR}/skill_contract.json`
- Full machine index: `<KB_ROOT>/{EVIDENCE_INDEX_DIR}/knowledge_index.json`
- Runtime health/init: `tools.kb.runtime`
"""


def write_skill_packages(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = expected_skill_package_files(root)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {"written_count": len(files), "files": sorted(files)}


def skill_package_drift(root: Path) -> list[str]:
    root = root.resolve()
    drift: list[str] = []
    for relative, expected in expected_skill_package_files(root).items():
        path = root / relative
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drift.append(as_posix(relative))
    return drift
