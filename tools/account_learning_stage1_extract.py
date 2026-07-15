from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import CONTRACT_ID, detect_schema
from tools.account_learning_pipeline import load_config


LENSES = ("positioning", "topics", "structures", "expression", "counterexamples")
SECTION_HEADINGS = {
    "positioning": ("为什么值得学习", "核心观点", "证据边界"),
    "topics": ("核心观点", "可复用选题与案例", "可复用案例"),
    "structures": ("内容结构", "可复用模板"),
    "expression": (
        "发布内容层学习",
        "视频/图文表现层学习",
        "金句与表达素材",
        "表达素材与金句提炼",
        "发布资产学习",
    ),
    "counterexamples": (
        "证据缺口与候选判断",
        "证据缺口/后续问题",
        "入库判断",
        "方法候选与可复用方法论",
    ),
}

STRUCTURE_KEYWORDS = {
    "concrete_entry_or_commitment": ("黄金3秒", "开头", "承诺", "先给结果", "结果前置"),
    "initial_problem_or_context": ("问题", "背景", "语境", "设定", "处境"),
    "concrete_actions": ("行动", "步骤", "执行", "尝试", "做法", "操作"),
    "obstacle_or_conflict": ("冲突", "阻力", "失败", "困难", "卡住", "限制", "质疑"),
    "turning_point": ("转折", "变化", "后来", "直到", "反转", "转机"),
    "result_or_feedback": ("结果", "反馈", "验证", "数据", "效果", "回应"),
    "abstraction_entry": ("观点", "解释", "道理", "模型", "推演", "总结", "原因"),
    "beneficiary_closure": ("行动建议", "收尾", "互动", "观众", "你可以", "下一步", "帮助"),
}

EXPRESSION_KEYWORDS = {
    "opening_voice": ("黄金3秒", "开头", "起话", "直接说", "先说"),
    "sentence_rhythm": ("短句", "长句", "停顿", "节奏", "断句"),
    "oral_connectors": ("口语", "反问", "插话", "自我修正", "转折", "接话"),
    "audience_relationship": ("观众", "读者", "你", "大家", "我们"),
    "concrete_detail": ("具体", "数字", "年限", "动作", "场景", "细节", "经历"),
    "story_explanation_balance": ("故事", "案例", "经历", "解释", "观点", "论证"),
    "abstraction_timing": ("观点", "道理", "模型", "抽象", "总结", "解释"),
    "beneficiary_landing": ("建议", "行动", "下一步", "帮助", "可复用", "收尾"),
    "anti_template_signal": ("自然", "口语", "不端着", "自我修正", "具体经历", "去模板"),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def field(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def card_title(text: str, path: Path) -> str:
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if "：" in first:
        return first.split("：", 1)[1].strip()
    return path.stem


def named_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(?:\d+\.\s+)?(.+?)\s*$", text, re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[start:end].strip()
    return sections


def evidence_summary(text: str, headings: tuple[str, ...], *, limit: int = 900) -> str:
    sections = named_sections(text)
    values: list[str] = []
    for heading in headings:
        content = sections.get(heading, "")
        bullets = [line.removeprefix("- ").strip() for line in content.splitlines() if line.strip().startswith("- ")]
        values.extend(bullets[:3])
    compact = "；".join(value for value in values if value)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact[:limit]


def _evidence_lines(text: str, headings: tuple[str, ...], path: Path, root: Path) -> list[dict[str, str | int]]:
    sections = named_sections(text)
    try:
        card_ref = path.relative_to(root).as_posix()
    except ValueError:
        card_ref = path.as_posix()
    rows: list[dict[str, str | int]] = []
    order = 0
    for heading in headings:
        content = sections.get(heading, "")
        for raw in content.splitlines():
            value = raw.strip().removeprefix("- ").strip()
            if not value or value.startswith("#"):
                continue
            rows.append(
                {
                    "text": value,
                    "order": order,
                    "coordinate": f"card:{card_ref}#section:{heading}",
                }
            )
            order += 1
    if not rows:
        rows.append({"text": "", "order": 0, "coordinate": f"card:{card_ref}"})
    return rows


def _derive_observation(
    *,
    lens: str,
    text: str,
    path: Path,
    root: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    is_structure = lens == "structures"
    dimensions_key = "structure_dimensions" if is_structure else "expression_dimensions"
    dimensions = [str(item) for item in contract.get(dimensions_key, [])]
    keyword_map = STRUCTURE_KEYWORDS if is_structure else EXPRESSION_KEYWORDS
    lines = _evidence_lines(text, SECTION_HEADINGS[lens], path, root)
    observed: list[dict[str, Any]] = []
    missing: list[str] = []
    label_key = "unit" if is_structure else "signal"
    for dimension in dimensions:
        keywords = keyword_map.get(dimension, ())
        match = next(
            (
                row
                for row in lines
                if row["text"] and any(keyword in str(row["text"]) for keyword in keywords)
            ),
            None,
        )
        if match is None:
            missing.append(dimension)
            continue
        observed.append(
            {
                label_key: dimension,
                "evidence": str(match["text"])[:280],
                "source_coordinate": str(match["coordinate"]),
                "_order": int(match["order"]),
            }
        )
    observed.sort(key=lambda item: item["_order"])
    for item in observed:
        item.pop("_order", None)
    labels = [str(item[label_key]) for item in observed]
    coordinates = list(dict.fromkeys(str(item["source_coordinate"]) for item in observed))
    if not coordinates:
        coordinates = [str(lines[0]["coordinate"])]
    fingerprint = ">".join(labels) if labels else "未形成可证据化序列"
    fingerprint += "；单卡草案，待多卡验证"
    observation: dict[str, Any] = {
        "status": str(contract.get("candidate_status") or "single_card_observation"),
        "dimensions_considered": dimensions,
        "evidence_coordinates": coordinates,
    }
    if is_structure:
        observation.update(
            {
                "observed_units": observed,
                "unit_order": labels,
                "missing_or_uncertain_units": missing,
                "structure_fingerprint": fingerprint,
            }
        )
    else:
        observation.update(
            {
                "observed_signals": observed,
                "missing_or_uncertain_signals": missing,
                "expression_fingerprint": fingerprint,
            }
        )
    return observation


def lens_title(lens: str, direction: str, title: str) -> str:
    templates = {
        "positioning": "以{direction}问题建立经验型定位：{title}",
        "topics": "把具体问题写成结果承诺的选题观察：{title}",
        "structures": "{direction}的标题—步骤—边界结构观察：{title}",
        "expression": "{direction}的具体经历与结果表达观察：{title}",
        "counterexamples": "{direction}证据边界与过度外推风险：{title}",
    }
    return templates[lens].format(direction=direction or "待判定方向", title=title)


def lens_tags(lens: str, direction: str, *, compatibility_mode: str) -> list[str]:
    labels = {
        "positioning": "定位观察",
        "topics": "选题观察",
        "structures": "结构观察",
        "expression": "表达观察",
        "counterexamples": "反例边界",
    }
    source_tag = "统一卡派生观察" if compatibility_mode == "unified_card" else "兼容旧卡读取"
    return [labels[lens], direction or "待判定方向", source_tag, "待跨卡验证"]


def extract_stage1_candidates(
    root: Path,
    *,
    workflow_id: str,
    card_root: Path,
    inventory_path: Path,
    apply: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    card_root = (root / card_root).resolve() if not card_root.is_absolute() else card_root.resolve()
    inventory_path = (root / inventory_path).resolve() if not inventory_path.is_absolute() else inventory_path.resolve()
    workflow = root / "10_Knowledge/candidates/account_learning_workflows" / workflow_id
    state_path = workflow / "PIPELINE_STATE.json"
    if not state_path.exists():
        raise FileNotFoundError(f"workflow state not found: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("current_stage") != "stage1_parallel_extraction":
        raise ValueError("workflow must be in stage1_parallel_extraction")
    config = load_config(root)
    observation_contract = config.get("stage1_deep_observation", {})
    observation_schema = str(observation_contract.get("schema_id") or "")

    inventory = read_jsonl(inventory_path)
    inventory_ids = {str(row.get("source_id")) for row in inventory if row.get("source_id")}
    cards = sorted(card_root.glob("directions/*/cards/*.md"))
    outputs: dict[str, list[dict[str, Any]]] = {lens: [] for lens in LENSES}
    missing_inventory: list[str] = []
    direction_counts: Counter[str] = Counter()

    for path in cards:
        text = path.read_text(encoding="utf-8")
        source_id = field(text, "source_id")
        if not source_id:
            raise ValueError(f"source_id missing: {path}")
        title = card_title(text, path)
        direction = field(text, "主方向") or path.parents[1].name
        card_schema = detect_schema(text)
        compatibility_mode = "unified_card" if card_schema == CONTRACT_ID else "downgraded_legacy_card"
        direction_counts[direction] += 1
        if source_id not in inventory_ids:
            missing_inventory.append(source_id)
        for lens in LENSES:
            summary = evidence_summary(text, SECTION_HEADINGS[lens])
            if not summary:
                summary = f"《{title}》属于{direction}方向；当前只保留为兼容旧卡观察，等待新流程补齐证据。"
            if lens == "counterexamples":
                summary += "；旧卡已降级，单卡结论、功效表述和商业属性均不得直接晋升为稳定方法。"
            else:
                summary += "；该观察来自降级后的兼容旧卡，只是阶段 1 候选，不做录取判断。"
            candidate = {
                    "id": f"obs-{source_id}-{lens}",
                    "title": lens_title(lens, direction, title),
                    "type": lens,
                    "source_refs": [source_id],
                    "summary": summary,
                    "tags": lens_tags(lens, direction, compatibility_mode=compatibility_mode),
                    "status": "candidate_observation",
                    "callable": False,
                    "compatibility_mode": compatibility_mode,
                    "card_schema": card_schema,
                }
            if lens in {"structures", "expression"} and observation_schema:
                candidate["observation_schema"] = observation_schema
                candidate["observation"] = _derive_observation(
                    lens=lens,
                    text=text,
                    path=path,
                    root=root,
                    contract=observation_contract,
                )
            outputs[lens].append(candidate)

    result = {
        "ok": True,
        "status": "applied" if apply else "dry_run",
        "workflow_id": workflow_id,
        "inventory_count": len(inventory),
        "compatibility_card_count": len(cards),
        "pending_full_evidence_count": max(len(inventory_ids) - len(cards), 0),
        "candidate_count": sum(len(rows) for rows in outputs.values()),
        "lens_counts": {lens: len(outputs[lens]) for lens in LENSES},
        "direction_counts": dict(sorted(direction_counts.items())),
        "card_ids_missing_from_inventory": sorted(missing_inventory),
        "formal_write_allowed": False,
    }
    if not apply:
        return result

    for lens, rows in outputs.items():
        write_jsonl(workflow / "candidates" / f"{lens}.jsonl", rows)
    report_path = workflow / "STAGE1_EXTRACTION_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                f"# {state.get('account_name') or workflow_id}阶段 1 五视角提取报告",
                "",
                f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
                f"- 候选资料范围：{len(inventory)} 条",
                f"- 兼容读取的降级旧卡：{len(cards)} 张",
                f"- 五视角候选：{result['candidate_count']} 条（每视角 {len(cards)} 条）",
                f"- 尚待补完整证据：{result['pending_full_evidence_count']} 条",
                "- 状态：阶段 1 候选观察；不代表方法录取，不可调用，不写正式知识。",
                "",
                "## 证据边界",
                "",
                "- 旧卡按 active Skill 的兼容模式读取，但其历史 formal_ingested 标记不再生效。",
                "- 每个视角从不同卡片章节独立提取，不沿用其他视角的录取判断。",
                "- 视频下载、逐字稿、抽帧和图文 OCR 缺口继续保留，阶段 2 不得把缺证据记录伪装为已验证。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result["report"] = report_path.relative_to(root).as_posix()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract five independent stage-1 lenses from downgraded account cards.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = extract_stage1_candidates(
            Path(args.root),
            workflow_id=args.workflow_id,
            card_root=Path(args.card_root),
            inventory_path=Path(args.inventory),
            apply=args.apply,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
