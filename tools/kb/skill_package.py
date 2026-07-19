from __future__ import annotations

import json
import os
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
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/agents/openai.yaml": render_agent_yaml("knowledge-base", english=True),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base/references/calling-rules.md": render_calling_rules(startup, blocked, english=True),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base-zh/SKILL.md": render_skill("knowledge-base-zh", startup, blocked, english=False),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base-zh/agents/openai.yaml": render_agent_yaml("knowledge-base-zh", english=False),
        f"{SYSTEM_SKILL_PACKAGES_DIR}/knowledge-base-zh/references/calling-rules.md": render_calling_rules(startup, blocked, english=False),
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

Treat `<KB_ROOT>` as the repository root of this knowledge base. Resolve it in this order: use the current repository when it contains `00_System/shareable/config/skill_contract.json`; otherwise read `references/kb-root.json` from this installed Skill; otherwise use the `KB_ROOT` environment variable. If none resolves to a valid repository, stop and ask for the local knowledge-base root.

Start with the fixed entry files generated from `skill_contract.json`:

{startup_lines}

Do not scan the whole knowledge base by default. Do not read protected directories by default: {blocked_lines}.

Use `<KB_ROOT>/{SYSTEM_INDEX_DIR}/controller_routes.json` for routing. The agents listed there are logical AI roles, not independent processes or permission boundaries.

The portable system has three workflows: `content-processing`, `account-learning`, and `content-review`. Content production resolves an account Skill through `20_User/config/account_skill_registry.json`; local production memory is queried by code and never loaded in full.

For candidate retrieval, use `search-candidates`; if it returns `requires_init`, stop and ask for `kb init` instead of reading legacy assets.
"""
    return f"""---
name: {name}
description: 使用本机 Markdown 知识库。先走索引和路由，不默认读取原始资料。
---

# 知识库

触发：`@知识库`、`使用知识库`、`调用知识库`、`读取知识库`。

`<KB_ROOT>` 表示当前知识库仓库根目录。按以下顺序解析：当前目录包含 `00_System/shareable/config/skill_contract.json` 时使用当前仓库；否则读取本全局 Skill 的 `references/kb-root.json`；再否则读取环境变量 `KB_ROOT`。都无法定位时停止并询问本机知识库根目录。

固定入口文件来自 `skill_contract.json`：

{startup_lines}

默认禁止全盘扫库；默认不读取受保护目录：{blocked_lines}。

路由以 `<KB_ROOT>/{SYSTEM_INDEX_DIR}/controller_routes.json` 为准。里面的 Agent 是同一次 AI 调用中的逻辑职责，不是独立进程、权限隔离或安全边界。

可迁移系统只包含三条主流程：`content-processing`、`account-learning`、`content-review`。内容生产通过 `20_User/config/account_skill_registry.json` 解析账号 Skill；本机生产记忆由代码查重，不加载完整数据库。

候选检索使用 `search-candidates`；如果返回 `requires_init`，停止并提示先执行 `kb init`，不要回读旧 assets。
"""


def render_agent_yaml(name: str, *, english: bool) -> str:
    default_prompt = (
        f"Use ${name} to route this request through the local knowledge base without scanning protected data."
        if english
        else f"使用 ${name} 按索引和路由处理当前需求，不扫描受保护原始资料。"
    )
    return (
        'interface:\n'
        '  display_name: "知识库"\n'
        '  short_description: "总控：按索引、路由和输出契约调用本机知识库"\n'
        f'  default_prompt: "{default_prompt}"\n'
    )


def render_calling_rules(startup: list[str], blocked: list[str], english: bool = False) -> str:
    startup_lines = "\n".join(
        f"1. `<KB_ROOT>/{path}`" if index == 0 else f"{index + 1}. `<KB_ROOT>/{path}`"
        for index, path in enumerate(startup)
    )
    blocked_lines = "\n".join(f"- `{path}`" for path in blocked)
    title = "Knowledge-base calling rules" if english else "知识库调用规则"
    return f"""# {title}

## Entry order

Resolve `<KB_ROOT>` from the current repository first, then `references/kb-root.json` in the installed Skill, then the `KB_ROOT` environment variable. Stop when none points to a repository containing `00_System/shareable/config/skill_contract.json`.

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


def default_installed_skills_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    return codex_home / "skills"


def _installed_relative(relative: str) -> Path:
    return Path(relative).relative_to(SYSTEM_SKILL_PACKAGES_DIR)


def installed_skill_package_status(root: Path, target_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    target_root = (target_root or default_installed_skills_root()).expanduser().resolve()
    drift: list[str] = []
    missing_packages: list[str] = []
    bound_locator_count = 0
    files = expected_skill_package_files(root)
    for package in ("knowledge-base", "knowledge-base-zh"):
        if not (target_root / package / "SKILL.md").exists():
            missing_packages.append(package)
    for relative, expected in files.items():
        installed = target_root / _installed_relative(relative)
        if not installed.exists() or installed.read_text(encoding="utf-8") != expected:
            drift.append(as_posix(installed.relative_to(target_root)))
    locator_drift: list[str] = []
    for package in ("knowledge-base", "knowledge-base-zh"):
        locator = target_root / package / "references" / "kb-root.json"
        if not locator.exists():
            locator_drift.append(f"{package}/references/kb-root.json")
            continue
        try:
            payload = json.loads(locator.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        locator_root = str(payload.get("kb_root") or "") if isinstance(payload, dict) else ""
        if locator_root and Path(locator_root).expanduser().resolve() == root:
            bound_locator_count += 1
        else:
            locator_drift.append(f"{package}/references/kb-root.json")
    return {
        "ok": not drift and not locator_drift,
        "status": "not_installed" if missing_packages else ("drift" if drift or locator_drift else "synced"),
        "target_root": str(target_root),
        "missing_packages": missing_packages,
        "bound_to_root": bound_locator_count == 2,
        "drift": drift,
        "locator_drift": locator_drift,
    }


def sync_installed_skill_packages(
    root: Path,
    target_root: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    target_root = (target_root or default_installed_skills_root()).expanduser().resolve()
    changes: list[str] = []
    for relative, content in expected_skill_package_files(root).items():
        installed = target_root / _installed_relative(relative)
        if not installed.exists() or installed.read_text(encoding="utf-8") != content:
            changes.append(as_posix(installed.relative_to(target_root)))
            if not dry_run:
                installed.parent.mkdir(parents=True, exist_ok=True)
                installed.write_text(content, encoding="utf-8")
    locator_payload = json.dumps(
        {"version": 1, "kb_root": str(root), "source": "tools.kb.cli skill-install"},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    for package in ("knowledge-base", "knowledge-base-zh"):
        locator = target_root / package / "references" / "kb-root.json"
        if not locator.exists() or locator.read_text(encoding="utf-8") != locator_payload:
            changes.append(as_posix(locator.relative_to(target_root)))
            if not dry_run:
                locator.parent.mkdir(parents=True, exist_ok=True)
                locator.write_text(locator_payload, encoding="utf-8")
    status = (
        {"ok": True, "status": "dry_run", "target_root": str(target_root), "changes": changes}
        if dry_run
        else installed_skill_package_status(root, target_root)
    )
    status["changed_file_count"] = len(changes)
    status["changes"] = changes
    return status
