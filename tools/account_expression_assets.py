from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.kb.expression_assets import load_expression_asset_contract, validate_expression_asset_file


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        item = json.loads(raw)
        if not isinstance(item, dict):
            raise ValueError(f"record_not_object:{line_number}")
        records.append(item)
    return records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )


def _asset_lines(record: dict[str, Any]) -> list[str]:
    variables = record.get("pattern_variables", {})
    variable_text = "、".join(f"{key}={value}" for key, value in sorted(variables.items())) if isinstance(variables, dict) else ""
    return [
        f"### {record.get('asset_id', '')}",
        "",
        f"- 类型：`{record.get('asset_type', '')}`",
        f"- 来源层：`{record.get('source_surface', '')}`",
        f"- 位置：`{record.get('content_position', '')}`",
        f"- 功能：`{record.get('functional_role', '')}`",
        f"- 来源原文（只读/不可生成）：{record.get('source_excerpt', '')}",
        f"- 机制拆解：{record.get('abstracted_pattern', '')}",
        f"- 变量：{variable_text or '未声明' }",
        f"- 改编骨架：{record.get('adaptation_template', '')}",
        f"- 风险：{', '.join(map(str, record.get('risk_flags', []))) or '无显式风险标记'}",
        "",
    ]


def _render_group(title: str, purpose: str, records: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", purpose, "", "原文只用于查看和溯源，不得作为生成输入；后续生产只能使用经批准的抽象模式。", ""]
    if not records:
        lines.extend(["当前没有该类候选资产。", ""])
    for record in records:
        lines.extend(_asset_lines(record))
    return "\n".join(lines)


def _render_overview(records: list[dict[str, Any]], account_id: str) -> str:
    type_counts = Counter(str(item.get("asset_type", "")) for item in records)
    surface_counts = Counter(str(item.get("source_surface", "")) for item in records)
    lines = [
        "# 表达资产总览",
        "",
        f"- 账号隔离标识：`{account_id}`",
        f"- 候选资产数：{len(records)}",
        "- 状态：候选、不可调用、不可写正式层",
        "- 原文用途：仅展示与溯源，永远不可生成",
        "- 抽象模式用途：当前仅候选参考，需跨卡验证、压力测试和用户确认后另行晋升",
        "",
        "## 类型分布",
        "",
    ]
    lines.extend(f"- `{key}`：{value}" for key, value in sorted(type_counts.items()))
    lines.extend(["", "## 来源层分布", ""])
    lines.extend(f"- `{key}`：{value}" for key, value in sorted(surface_counts.items()))
    lines.extend(["", "## 三条并行链", "", "1. 证据链：来源登记、证据坐标、哈希与账号隔离。", "2. 表达资产链：逐条提取、拆解、聚合、检索与压力测试。", "3. 方法/Skill 链：跨卡验证后的方法构造和用户审核候选。", ""])
    return "\n".join(lines)


def _render_cross_surface(records: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("source_surface", "unknown"))].append(record)
    lines = [
        "# 发布层与视频层协同图谱",
        "",
        "发布标题、发布正文、口播、视觉和跨模态协同分别记录，禁止用其中一层替代另一层。",
        "",
    ]
    for surface, items in sorted(grouped.items()):
        lines.extend([f"## {surface}", ""])
        for item in items:
            lines.append(
                f"- `{item.get('asset_id', '')}`｜{item.get('content_position', '')}｜{item.get('functional_role', '')}｜{item.get('abstracted_pattern', '')}"
            )
        lines.append("")
    return "\n".join(lines)


def _render_usage() -> str:
    return """# 表达资产使用说明

## 检索

- 可按资产类型、来源层、内容位置、功能、风险和来源坐标检索。
- 钩子检索必须包含开头和内容过程，不得只返回前三秒。
- 返回结果必须同时显示来源原文与机制拆解，并明确两者用途不同。

## 改编

- 来源原文永远不可作为生成输入，也不能被改写后冒充模板。
- 候选抽象模式只能用于研究和人工审核，不得直接进入生产。
- 只有跨卡验证、压力测试、用户确认和正式 Skill 提案全部通过，抽象模式才可另行晋升。

## 隔离

- 单次包只能包含一个 account_id。
- 禁止借用其他账号样本补齐钩子、金句、句式或结构。
- 外部参考只保留用户明确指定的当次用途，不得成为账号规律。
"""


def _render_item_index(records: list[dict[str, Any]]) -> str:
    source_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        source = record.get("source", {}) if isinstance(record.get("source"), dict) else {}
        source_groups[str(source.get("source_id", "unknown"))].append(record)
    lines = ["# 单条内容拆解索引", "", "按 source_id 查看同一条内容中开头、过程和结尾的全部表达资产。", ""]
    for source_id, items in sorted(source_groups.items()):
        lines.extend([f"## {source_id}", ""])
        for item in sorted(items, key=lambda value: (str(value.get("content_position", "")), str(value.get("asset_id", "")))):
            lines.append(
                f"- `{item.get('asset_id', '')}`｜{item.get('asset_type', '')}｜{item.get('source_surface', '')}｜{item.get('content_position', '')}｜{item.get('functional_role', '')}"
            )
        lines.append("")
    return "\n".join(lines)


def build_expression_asset_package(
    root: Path,
    full_file: Path,
    *,
    expected_account_id: str,
    expected_workflow_id: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    target = (full_file if full_file.is_absolute() else root / full_file).resolve()
    validation = validate_expression_asset_file(
        root,
        target,
        expected_account_id=expected_account_id,
        expected_workflow_id=expected_workflow_id,
    )
    if not validation.get("ok"):
        return {"ok": False, "status": "validation_failed", "validation": validation}
    contract = load_expression_asset_contract(root)
    records = _read_jsonl(target)
    output_root = target.parent
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("asset_type", ""))].append(record)

    generated: list[Path] = []
    derived = contract.get("storage", {}).get("derived_jsonl_files", {})
    for asset_type, filename in sorted(derived.items()):
        path = output_root / str(filename)
        _write_jsonl(path, grouped.get(str(asset_type), []))
        generated.append(path)

    hook_records = grouped.get("hook", []) + grouped.get("opening_move", []) + grouped.get("ending_move", [])
    golden_records = grouped.get("golden_line", []) + grouped.get("sentence_pattern", [])
    structure_records = grouped.get("structure_unit", []) + grouped.get("transition", []) + grouped.get("opening_move", []) + grouped.get("ending_move", [])
    anti_records = grouped.get("anti_pattern", [])
    views = {
        "表达资产总览.md": _render_overview(records, expected_account_id),
        "钩子与留存机制图谱.md": _render_group("钩子与留存机制图谱", "覆盖开头、信息差、段落转场、冲突、证据、反转、情绪和结尾钩子。", hook_records),
        "金句与句式图谱.md": _render_group("金句与句式图谱", "逐条保留位置、功能、机制、变量、改编骨架和风险。", golden_records),
        "内容结构完整图谱.md": _render_group("内容结构完整图谱", "把开头、过程、转场、证据、反转、结果和结尾放回完整内容序列。", structure_records),
        "发布层与视频层协同图谱.md": _render_cross_surface(records),
        "表达资产使用说明.md": _render_usage(),
        "反例与慎用表达.md": _render_group("反例与慎用表达", "反例只用于验收和风险识别，禁止作为生成参考。", anti_records),
        "单条内容拆解索引.md": _render_item_index(records),
    }
    for filename, text in views.items():
        path = output_root / filename
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        generated.append(path)

    links_path = output_root / "asset_method_links.jsonl"
    if links_path.is_file():
        generated.append(links_path)
    files = [
        {"path": path.name, "sha256": _sha256_file(path)}
        for path in sorted(generated, key=lambda item: item.name)
    ]
    manifest = {
        "schema_version": "expression_asset_package_v1",
        "status": "ready_for_review",
        "account_id": expected_account_id,
        "workflow_id": expected_workflow_id,
        "record_count": len(records),
        "asset_type_counts": dict(sorted(Counter(str(item.get("asset_type", "")) for item in records).items())),
        "full_file": target.name,
        "full_file_sha256": _sha256_file(target),
        "files": files,
        "boundaries": {
            "candidate_only": True,
            "formal_write": False,
            "callable": False,
            "source_generation_eligible": False,
            "cross_account_merge": False,
        },
    }
    manifest_path = output_root / "manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "ok": True,
        "status": "ready_for_review",
        "record_count": len(records),
        "output_dir": str(output_root.relative_to(root)),
        "manifest": str(manifest_path.relative_to(root)),
    }
