from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import runtime_path
from .scanner import classify_file, scan_files
from .schemas import (
    BLOCKED_BY_DEFAULT_DIRS,
    BLOCKED_BY_DEFAULT_PREFIXES,
    FORMAL_KNOWLEDGE_DIRS,
    RAW_INPUT_DIRS,
    EVIDENCE_INDEX_DIR,
    SYSTEM_DIR,
    SYSTEM_INDEX_DIR,
    SYSTEM_RULES_DIR,
    SYSTEM_SKILL_PREFIXES,
    TARGET_CANDIDATE_ASSET_PREFIXES,
    TARGET_FORMAL_KNOWLEDGE_PREFIXES,
    as_posix,
    layer_prefixes,
    load_layer_map,
    now_iso,
)


def index_dir(root: Path) -> Path:
    return root / EVIDENCE_INDEX_DIR


def system_index_dir(root: Path) -> Path:
    return root / SYSTEM_INDEX_DIR


def has_prefix(relative_path: str, prefixes: tuple[str, ...]) -> bool:
    return any(relative_path.startswith(prefix) for prefix in prefixes)


def calling_scope(relative_path: str, layer_map: dict[str, Any] | None = None) -> str:
    layer_map = layer_map or {}
    first = relative_path.split("/", 1)[0]
    blocked_prefixes = layer_prefixes(layer_map, "default_blocked_dirs", tuple(f"{item}/" for item in BLOCKED_BY_DEFAULT_DIRS))
    blocked_prefixes = tuple(blocked_prefixes) + BLOCKED_BY_DEFAULT_PREFIXES
    if first in BLOCKED_BY_DEFAULT_DIRS or has_prefix(relative_path, blocked_prefixes):
        return "blocked_by_default"
    if (
        relative_path.startswith("00_System/shareable/skills/proposals/")
        or relative_path.startswith("00_System/shareable/skills/history/")
        or relative_path.startswith("13_Evolving_Skills/proposals/")
        or relative_path.startswith("13_Evolving_Skills/history/")
    ):
        return "internal_or_review"
    system_skill_roots = layer_prefixes(layer_map, "system_skill_roots", SYSTEM_SKILL_PREFIXES)
    if has_prefix(relative_path, system_skill_roots):
        return "system_internal"
    if first == SYSTEM_DIR or has_prefix(relative_path, ("00_System/shareable/", "tools/", "tests/", "docs/")):
        return "system_internal"
    formal_roots = layer_prefixes(
        layer_map,
        "formal_knowledge_roots",
        TARGET_FORMAL_KNOWLEDGE_PREFIXES + tuple(f"{item}/" for item in FORMAL_KNOWLEDGE_DIRS),
    )
    if has_prefix(relative_path, formal_roots) or relative_path in {
        "知识库入口.md",
        "README.md",
        f"{SYSTEM_RULES_DIR}/用户操作台.md",
        f"{SYSTEM_INDEX_DIR}/controller_routes.json",
        f"{SYSTEM_RULES_DIR}/本机使用速查.md",
        f"{SYSTEM_RULES_DIR}/知识库运行规则.md",
    }:
        return "allowed"
    if relative_path.startswith("20_User/syncable/"):
        return "allowed"
    return "internal_or_review"


def purpose_for_path(relative_path: str) -> str:
    if relative_path == "知识库入口.md":
        return "knowledge_base_entry"
    if relative_path.startswith("00_System/shareable/skills/active/"):
        return "system_skill"
    if relative_path.startswith("00_System/shareable/skills/"):
        return "system_skill_support"
    if relative_path.startswith("00_System/shareable/memory/"):
        return "memory_system_rule"
    if relative_path.startswith("00_System/shareable/agents/"):
        return "agent_system_rule"
    if relative_path.startswith("00_System/shareable/"):
        return "shareable_system"
    if relative_path.startswith("00_System/runtime/"):
        return "runtime_state"
    if relative_path.startswith("10_Knowledge/formal/accounts/"):
        return "formal_account_knowledge"
    if relative_path.startswith("10_Knowledge/formal/"):
        return "formal_knowledge"
    if relative_path.startswith("10_Knowledge/candidates/"):
        return "candidate_asset"
    if relative_path.startswith("10_Knowledge/evidence/"):
        return "memory_evidence" if relative_path.startswith("10_Knowledge/evidence/memory/") else "evidence_index"
    if relative_path.startswith("20_User/syncable/"):
        if relative_path.startswith("20_User/syncable/memory/"):
            return "syncable_user_memory"
        if relative_path.startswith("20_User/syncable/agents/"):
            return "syncable_agent_registry"
        return "syncable_user_preference"
    if relative_path.startswith("20_User/private/"):
        return "private_user_preference"
    if relative_path.startswith("80_Local/"):
        return "local_private_config"
    if relative_path.startswith("90_Temp/"):
        return "temporary_file"
    if relative_path.startswith("02_Viral_Methods/"):
        return "viral_method"
    if relative_path.startswith("03_Topic_Ideas/"):
        return "formal_topic_library"
    if relative_path.startswith("13_Evolving_Skills/active/"):
        return "system_skill"
    if relative_path.startswith(tuple(f"{item}/" for item in RAW_INPUT_DIRS)):
        return "raw_input"
    return "supporting_file"


def is_formal_knowledge_item(item: dict[str, Any], layer_map: dict[str, Any] | None = None) -> bool:
    layer_map = layer_map or {}
    path = item["path"]
    first = path.split("/", 1)[0]
    if (
        path.startswith("00_System/shareable/skills/proposals/")
        or path.startswith("00_System/shareable/skills/history/")
        or path.startswith("13_Evolving_Skills/proposals/")
        or path.startswith("13_Evolving_Skills/history/")
    ):
        return False
    if path.startswith("13_Evolving_Skills/active/"):
        return False
    formal_roots = layer_prefixes(
        layer_map,
        "formal_knowledge_roots",
        TARGET_FORMAL_KNOWLEDGE_PREFIXES + tuple(f"{item}/" for item in FORMAL_KNOWLEDGE_DIRS),
    )
    return has_prefix(path, formal_roots) or first in FORMAL_KNOWLEDGE_DIRS


def is_candidate_asset_item(item: dict[str, Any], layer_map: dict[str, Any] | None = None) -> bool:
    layer_map = layer_map or {}
    path = item["path"]
    if "video_artifacts/" in path:
        return False
    candidate_roots = layer_prefixes(
        layer_map,
        "candidate_asset_roots",
        TARGET_CANDIDATE_ASSET_PREFIXES
        + (
            "05_Sub_KB_Candidates/",
            "10_Knowledge/candidates/account_assets/content_rough_scan/",
            "10_Knowledge/candidates/learning_cards/deep_cards/",
            "10_Knowledge/candidates/learning_cards/learned_cards/",
            "10_Knowledge/candidates/learning_cards/selected_deep_cards/",
            "10_Knowledge/candidates/account_assets/account_cards/",
            "10_Knowledge/candidates/review_registers/plans/",
        ),
    )
    return has_prefix(path, candidate_roots)


def build_knowledge_index(root: Path, include_raw_inputs: bool = True) -> dict[str, Any]:
    layer_map = load_layer_map(root)
    scan = scan_files(root, include_raw_inputs=include_raw_inputs)
    indexed = []
    for item in scan["files"]:
        relative_path = item["path"]
        indexed.append(
            {
                "path": relative_path,
                "type": item["suffix"].lstrip(".") or "unknown",
                "purpose": purpose_for_path(relative_path),
                "content_status": "new" if item["is_raw_input"] else "approved",
                "calling_scope": calling_scope(relative_path, layer_map),
                "is_raw_input": item["is_raw_input"],
                "cleanup_candidate": item["cleanup_candidate"],
                "updated_at": item["modified_at"],
            }
        )
    return {
        "generated_at": now_iso(),
        "root": scan["root"],
        "layer_map_version": layer_map.get("version"),
        "files": indexed,
        "cleanup_candidates": scan["cleanup_candidates"],
    }


def compact_index_item(item: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "path": item["path"],
        "type": item["type"],
        "purpose": item["purpose"],
        "content_status": item["content_status"],
        "calling_scope": item["calling_scope"],
        "updated_at": item["updated_at"],
    }
    account_id = account_id_for_candidate_path(item["path"])
    if item["purpose"] == "candidate_asset" or account_id:
        compact["knowledge_layer"] = "candidate_knowledge"
    if account_id:
        compact["account_id"] = account_id
    return compact


def account_id_for_candidate_path(relative_path: str) -> str:
    prefixes = (
        "10_Knowledge/candidates/account_assets/content_rough_scan/",
        "10_Knowledge/candidates/learning_cards/learned_cards/",
    )
    for prefix in prefixes:
        if relative_path.startswith(prefix):
            remainder = relative_path[len(prefix) :]
            return remainder.split("/", 1)[0] if "/" in remainder else remainder
    return ""


def build_formal_knowledge_index(index: dict[str, Any], layer_map: dict[str, Any] | None = None) -> dict[str, Any]:
    items = [compact_index_item(item) for item in index["files"] if is_formal_knowledge_item(item, layer_map)]
    return {
        "generated_at": index["generated_at"],
        "source_index": "knowledge_index.json",
        "description": "正式可调用知识索引；不包含候选资产、原始资料、归档和系统运行产物。",
        "item_count": len(items),
        "items": items,
    }


def build_runtime_candidate_items(root: Path) -> list[dict[str, Any]]:
    assets = root / "10_Knowledge" / "candidates" / "generated_assets"
    if not assets.exists():
        return []
    items = []
    for path in sorted(candidate for candidate in assets.rglob("*") if candidate.is_file()):
        scanned = classify_file(root, path)
        items.append(
            {
                "path": scanned["path"],
                "type": scanned["suffix"].lstrip(".") or "unknown",
                "purpose": "candidate_asset",
                "content_status": "candidate",
                "calling_scope": "internal_or_review",
                "updated_at": scanned["modified_at"],
            }
        )
    return items


def build_candidate_asset_index(root: Path, index: dict[str, Any], layer_map: dict[str, Any] | None = None) -> dict[str, Any]:
    items = [compact_index_item(item) for item in index["files"] if is_candidate_asset_item(item, layer_map)]
    known_paths = {item["path"] for item in items}
    items.extend(item for item in build_runtime_candidate_items(root) if item["path"] not in known_paths)
    return {
        "generated_at": index["generated_at"],
        "source_index": "knowledge_index.json + 10_Knowledge/candidates/generated_assets",
        "description": "候选和待审核资产索引；候选资产属于知识层 candidates，不属于系统规则层；账号候选资产必须通过 account_id 隔离，默认不当作正式知识。",
        "item_count": len(items),
        "items": items,
    }


def build_raw_blocked_index(root: Path, index: dict[str, Any]) -> dict[str, Any]:
    layer_map = load_layer_map(root)
    configured = layer_prefixes(layer_map, "default_blocked_dirs", tuple(f"{item}/" for item in BLOCKED_BY_DEFAULT_DIRS))
    blocked_dirs = tuple(dict.fromkeys(configured + BLOCKED_BY_DEFAULT_PREFIXES))
    items = []
    for name in blocked_dirs:
        display = name if name.endswith("/") else f"{name}/"
        items.append(
            {
                "path": display,
                "calling_scope": "blocked_by_default",
                "reason": "默认禁止读取；只有用户明确要求处理、审核或追溯时才按需进入。",
                "expanded": False,
                "exists": (root / display.rstrip("/")).exists(),
            }
        )
    return {
        "generated_at": index["generated_at"],
        "source_index": "knowledge_index.json",
        "description": "默认禁止读取的原始资料和归档边界索引；记录目录边界，不展开受保护原始数据。",
        "item_count": len(items),
        "items": items,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_indexes(root: Path, include_raw_inputs: bool = True) -> dict[str, Any]:
    root = root.resolve()
    layer_map = load_layer_map(root)
    target = index_dir(root)
    system_target = system_index_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    system_target.mkdir(parents=True, exist_ok=True)
    index = build_knowledge_index(root, include_raw_inputs=include_raw_inputs)
    write_json(target / "knowledge_index.json", index)
    formal_index = build_formal_knowledge_index(index, layer_map)
    candidate_index = build_candidate_asset_index(root, index, layer_map)
    raw_blocked_index = build_raw_blocked_index(root, index)
    write_json(target / "formal_knowledge_index.json", formal_index)
    write_json(target / "candidate_asset_index.json", candidate_index)
    write_json(target / "raw_blocked_index.json", raw_blocked_index)
    write_json(target / "file_relation_index.json", build_file_relations(index))
    write_json(runtime_path(root, "state") / "content_state.json", build_content_state(index))
    (target / "knowledge_index_summary.md").write_text(
        render_knowledge_index_summary(index, formal_index, candidate_index, raw_blocked_index),
        encoding="utf-8",
    )
    (target / "知识库总索引.md").write_text(render_human_index(index), encoding="utf-8")
    (system_target / "task_entry_index.md").write_text(render_task_entry_index(), encoding="utf-8")
    return {
        "index_files": 8,
        "index_dir": as_posix(target.relative_to(root)),
        "file_count": len(index["files"]),
        "formal_knowledge_count": formal_index["item_count"],
        "candidate_asset_count": candidate_index["item_count"],
        "raw_blocked_count": raw_blocked_index["item_count"],
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
            {"from": "知识库入口.md", "to": f"{SYSTEM_RULES_DIR}/用户操作台.md", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": f"{SYSTEM_INDEX_DIR}/controller_routes.json", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": f"{SYSTEM_RULES_DIR}/本机使用速查.md", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": "README.md", "relation": "entry_requires"},
            {"from": "知识库入口.md", "to": f"{SYSTEM_RULES_DIR}/知识库运行规则.md", "relation": "entry_requires"},
            {"from": f"{SYSTEM_RULES_DIR}/选题生成规则.md", "to": "10_Knowledge/formal/topics/选题灵感库_v1.md", "relation": "defines_schema_for"},
            {"from": f"{SYSTEM_RULES_DIR}/周复盘规则.md", "to": "00_System/shareable/skills/proposals", "relation": "may_create_proposal"},
        ],
    }


def render_human_index(index: dict[str, Any]) -> str:
    lines = [
        "# 知识库总索引（全量审计用）",
        "",
        "默认不要读取本文件；日常调用先看 `knowledge_index_summary.md`、`task_entry_index.md` 和账号索引。",
        "",
        f"生成时间：{index['generated_at']}",
        f"文件数量：{len(index['files'])}",
        f"清理候选：{len(index['cleanup_candidates'])}",
        "",
        "## 重要入口",
        "",
        "- `知识库入口.md`：主入口。",
        f"- `{SYSTEM_RULES_DIR}/用户操作台.md`：用户可复制入口。",
        f"- `{SYSTEM_INDEX_DIR}/controller_routes.json`：总控路由表。",
        "- `00_System/shareable/docs/project_use/项目调用规则.md`：其他项目调用入口。",
        "- `00_System/shareable/`：可分享系统底座。",
        "- `10_Knowledge/candidates/`：候选知识资产目标层；旧候选目录继续兼容。",
        "",
        "## 文件清单",
        "",
        "| 路径 | 用途 | 状态 | 调用范围 |",
        "| --- | --- | --- | --- |",
    ]
    for item in index["files"]:
        lines.append(f"| {item['path']} | {item['purpose']} | {item['content_status']} | {item['calling_scope']} |")
    return "\n".join(lines) + "\n"


def render_knowledge_index_summary(
    index: dict[str, Any],
    formal_index: dict[str, Any],
    candidate_index: dict[str, Any],
    raw_blocked_index: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# 知识库索引摘要",
            "",
            "这是给 Codex 和人工快速判断状态的轻量索引。默认不要读取全量索引 `knowledge_index.json` 或全量审计索引 `知识库总索引.md`。",
            "",
            f"生成时间：{index['generated_at']}",
            f"全量文件数：{len(index['files'])}",
            f"正式知识条目：{formal_index['item_count']}",
            f"候选资产条目：{candidate_index['item_count']}",
            f"默认禁止读取边界：{raw_blocked_index['item_count']}",
            f"清理候选：{len(index['cleanup_candidates'])}",
            "",
            "## 默认读取顺序",
            "",
            "1. `知识库入口.md`",
            f"2. `{SYSTEM_RULES_DIR}/用户操作台.md`",
            f"3. `{SYSTEM_INDEX_DIR}/controller_routes.json`",
            f"4. `{SYSTEM_INDEX_DIR}/task_entry_index.md`",
            f"5. `{EVIDENCE_INDEX_DIR}/knowledge_index_summary.md`",
            "",
            "## 分层索引",
            "",
            "- `knowledge_index.json`：全量机器索引，只给脚本和全量审计使用。",
            "- `knowledge_index_summary.md`：轻量状态摘要，给 Codex 和人工默认查看。",
            "- `task_entry_index.md`：任务入口索引。",
            "- `account_knowledge_index.json/md`：账号中心索引。",
            "- `formal_knowledge_index.json`：正式知识索引。",
            "- `candidate_asset_index.json`：候选资产索引。",
            "- `raw_blocked_index.json`：默认禁止读取目录边界。",
            "- `知识库总索引.md`：全量人类审计索引，默认不读。",
            "",
        ]
    )


def render_task_entry_index() -> str:
    return """# 任务入口索引

## 通用使用

- 先读：`知识库入口.md`、`00_System/shareable/rules/用户操作台.md`、`00_System/shareable/index/controller_routes.json`、`00_System/shareable/rules/本机使用速查.md`。
- 默认入口：`@知识库 + 需求`。兼容入口：`knowledge-base + 需求`。
- 总控优先：先用 `controller_routes.json` 判断任务类型，再按本索引读取少量相关文件。
- 分层权威源：`00_System/shareable/config/layer_map.json`。`00_System/shareable/` 才是可分享系统底座；`00_System/runtime/`、`80_Local/`、`20_User/private/`、`数据/` 默认阻断。

## 内容创作

- 读取：`10_Knowledge/formal/methods/`、`10_Knowledge/formal/topics/`、`10_Knowledge/formal/platforms/`、`10_Knowledge/formal/content_factory/`。
- 当用户提到账号名、对标账号、出选题、写文案、口播或账号风格时，先读取：`10_Knowledge/evidence/index/account_knowledge_index.md`。
- 只有账号索引命中正式账号中心后，才继续读取该账号的 `账号索引.md`、`账号概述.md`、`账号方法论总览.md`、`账号整体方法论.md`、`内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`，再按方向读取 `方向方法论总结.md`、`粗扫内容和选题.md`。
- `知识成长`、`赚钱`、`护肤`、`生活方式` 等只是可能的账号方向词，不是通用系统默认路由；不得因为某个方向词直接套用单一账号模板。
- 账号中心调用默认禁止全扫候选区；需要证据时再读取正式单卡，需要核查时再读取逐字稿。
- 内容生成不能直接反写正式知识；可沉淀的规则进入复盘或 Skill proposal。

## 账号学习

- 读取：`10_Knowledge/evidence/index/account_knowledge_index.md`、`00_System/shareable/index/controller_routes.json`、`00_System/shareable/skills/active/视频深度学习Skill_v1.md`。
- 工作流分两大阶段：学习阶段、生产复盘阶段。学习阶段包含粗学与深学计划、深度学习总结、综合入库；生产复盘阶段包含内容生产、反馈复盘、针对性强化。
- 粗学完成必须有 `账号概述.md`、`粗学与选题池.md`、`deep_learning_plan.json`；缺任何一个都要提醒用户，不宣布完成。
- 脚本只能生成候选资产、学习卡、报告和状态；候选资产目标层是 `10_Knowledge/candidates/`，正式账号知识必须经过审核。
- 默认使用通用 profile 化工具；旧账号专属命令只作为兼容入口，不作为新账号学习标准。

## 复盘和自我学习

- 读取：`00_System/shareable/rules/周复盘规则.md`、`10_Knowledge/formal/reviews/`、`20_User/syncable/`。
- Skill 更新只能写入系统级 proposal：`00_System/shareable/skills/proposals/`。
- 当用户说“以后都这样”“沉淀成规则”“更新 Skill”时，进入 Skill 沉淀路由，只生成 proposal，不直接改 active。

## 其他项目调用

- 读取：`00_System/shareable/docs/project_use/项目调用规则.md`。
- 默认禁止调用：`00_Inbox/`、`数据/`、`99_Archive/`、`80_Local/`、`20_User/private/`、runtime、未确认 Skill 提案。
- 其他项目优先调用全局 `@知识库` Skill；若入口失效，回退到读取 `知识库入口.md`。

## 代码批处理

- 读取 runtime tasks、reports、logs。旧路径兼容：`00_System/runtime/`。
- 代码只能生成候选资产和报告，不能直接写正式知识。

## 博主数据导出

- 触发：`导出{博主}内容`、`导出博主数据到飞书`、`返回飞书链接`、`导出评论`。
- 运行：`.venv/bin/python -m tools.kb.cli --root . export-creator-db --creator "{博主名}" --to-feishu --public-share`。
- 可选：不导出评论时加 `--no-comments`；指定平台时加 `--platform douyin/xhs/weibo/bilibili/kuaishou/tieba/zhihu`。
- 边界：`数据/sqlite_tables.db` 只读；只写 `90_Temp/exports/creator_db/` 导出文件和用户明确要求创建的飞书表格。
- 输出：飞书链接、内容数量、评论数量、分享权限读回状态、本地 manifest 路径；脚本返回前不需要实时陪跑。

## 系统审计

- 日常调用先运行 `.venv/bin/python -m tools.kb.cli --root . health-gate`；该命令禁止遍历正式知识文件。
- 新机器、runtime/凭证缺失、schema 不匹配或旧目录待迁移时运行 `kb init`。
- 目标分层目录缺失时运行 `.venv/bin/python -m tools.kb.cli --root . init-layers`。
- 读取：`00_System/shareable/index/controller_routes.json`、`10_Knowledge/evidence/index/knowledge_index_summary.md`、`10_Knowledge/evidence/index/account_knowledge_index.json`、`00_System/shareable/config/output_contracts.json`。
- `10_Knowledge/evidence/index/knowledge_index.json` 是全量机器索引，只在脚本验证、全量审计或用户明确要求时读取。
- 运行：`.venv/bin/python -m tools.kb.cli --root . validate-system` 或 `.venv/bin/python -m tools.kb.cli --root . dashboard`。
- 输出：入口、索引、路由、Skill 包、账号中心、proposal、候选注册表、输出契约和报告状态。
"""
