from __future__ import annotations

import argparse
import hashlib
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

PUBLISH_COPY_KEYWORDS = {
    "title_promise_and_information_gap": ("标题机制", "标题：", "标题:", "承诺", "信息差", "点击理由"),
    "title_specificity_and_voice": ("标题具体", "具体度", "标题语气", "叙事距离"),
    "opening_entry": ("正文入口", "开头", "从结果", "从处境", "从问题", "从经历"),
    "body_information_sequence": ("正文结构", "正文或文案", "文案学习", "信息推进", "段落推进", "步骤顺序"),
    "operational_or_argument_detail_density": ("细节密度", "数量", "单位", "时长", "状态判断", "限制条件"),
    "story_explanation_balance": ("故事", "解释", "步骤", "论证", "案例"),
    "lived_experience_signal": ("真人感", "生活痕迹", "自我修正", "偏好", "犹豫"),
    "closing_mode": ("结尾方式", "自然停住", "行动提醒", "情绪落点", "互动"),
    "topic_strategy": ("话题策略", "话题或标签", "话题学习", "检索词", "分类标签", "系列标签"),
    "publish_visual_alignment": ("协同判断", "发布视觉协同", "文图协同", "组图分工", "标题、正文"),
}

IMAGE_TEXT_VISUAL_KEYWORDS = {
    "cover_hook": ("封面钩子", "封面承诺", "第一眼"),
    "image_role_sequence": ("逐图角色", "分图顺序", "页序", "组图状态"),
    "composition_and_viewpoint": ("构图与视角", "景别", "机位", "裁切", "视觉动线"),
    "subject_action_and_state_change": ("动作与状态", "主体动作", "状态变化", "结果呈现"),
    "visual_hierarchy": ("视觉层级", "视觉焦点", "信息层级"),
    "text_annotation_design": ("文字注释设计", "贴纸", "底板", "指向关系"),
    "typography_hierarchy": ("字形字号层级", "字重", "字号", "字体层级"),
    "color_light_texture": ("色彩光线质感", "色调", "光源", "质感"),
    "authenticity_cues": ("真人与生活感", "生活感", "使用痕迹", "轻微不完美"),
    "cross_modal_alignment": ("跨模态协同", "对齐检查", "文图一致", "发布视觉协同"),
    "save_worthiness": ("收藏理由", "回看", "判断标准", "参考模板"),
}

EXPRESSION_SURFACES = (
    "publish_title",
    "publish_body_opening",
    "publish_body_middle",
    "publish_body_ending",
    "publish_topic",
    "video_spoken_opening",
    "video_spoken_middle",
    "video_spoken_ending",
    "video_visual_cover",
    "video_visual_opening",
    "video_visual_middle",
    "video_visual_ending",
    "cross_modal_coordination",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def field(text: str, name: str) -> str:
    match = re.search(rf"^(?:[-*]\s*)?{re.escape(name)}\s*[：:]\s*(.+?)\s*$", text, re.MULTILINE)
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


def card_content_form(text: str) -> str:
    classification = named_sections(text).get("多维分类与商业隔离", "")
    match = re.search(r"内容形态[:：]\s*([^\n]+)", classification)
    return match.group(1).strip() if match else ""


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


def _derive_signal_observation(
    *,
    schema_id: str,
    dimensions: list[str],
    keyword_map: dict[str, tuple[str, ...]],
    headings: tuple[str, ...],
    fingerprint_key: str,
    text: str,
    path: Path,
    root: Path,
    status: str,
) -> dict[str, Any]:
    lines = _evidence_lines(text, headings, path, root)
    observed: list[dict[str, Any]] = []
    missing: list[str] = []
    for dimension in dimensions:
        keywords = keyword_map.get(dimension, ())
        matches = [
            row
            for row in lines
            if row["text"] and any(keyword in str(row["text"]) for keyword in keywords)
        ]
        if not matches:
            missing.append(dimension)
            continue
        match = matches[0]
        observed.append(
            {
                "signal": dimension,
                "evidence": str(match["text"])[:360],
                "source_coordinate": str(match["coordinate"]),
                "_order": int(match["order"]),
            }
        )
    observed.sort(key=lambda item: item["_order"])
    for item in observed:
        item.pop("_order", None)
    labels = [str(item["signal"]) for item in observed]
    coordinates = list(dict.fromkeys(str(item["source_coordinate"]) for item in observed))
    if not coordinates:
        coordinates = [str(lines[0]["coordinate"])]
    return {
        "schema": schema_id,
        "status": status,
        "dimensions_considered": dimensions,
        "observed_signals": observed,
        "missing_or_uncertain_signals": missing,
        "evidence_coordinates": coordinates,
        fingerprint_key: (">".join(labels) if labels else "未形成可证据化序列") + "；单卡草案，待多卡验证",
    }


PUBLISH_FACET_PREFIXES = {
    "title": ("标题原文", "标题"),
    "body": ("正文原文", "正文或文案", "发布文案", "正文", "文案学习"),
    "topics": ("话题或标签", "话题标签", "话题学习", "话题"),
    "coordination": ("协同判断", "发布协同", "发布层协同", "发布视觉协同", "协同关系"),
}
PUBLISH_EXPLICIT_MISSING_PATTERN = re.compile(
    r"^(?:原文)?(?:没有显式|无显式|未提供|缺失|不存在|没有单独|无单独|未单独提供|无)(?:话题|标签|标题|正文|文案|协同|$)"
)


def _relative_card_ref(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _expression_audit_surfaces(text: str, content_form: str) -> list[str]:
    sections = named_sections(text)
    publish = sections.get("发布内容层学习", "") + "\n" + sections.get("发布资产学习", "")
    performance = sections.get("视频/图文表现层学习", "")
    structure = sections.get("内容结构", "")
    golden = sections.get("金句与表达素材", "") + "\n" + sections.get("表达素材与金句提炼", "")
    surfaces: list[str] = []
    if re.search(r"(?:^|\n)\s*[-*]?\s*标题(?:原文)?\s*[：:]", publish):
        surfaces.append("publish_title")
    if any(marker in publish for marker in ("正文", "文案")):
        surfaces.append("publish_body_middle")
    if any(marker in publish for marker in ("正文入口", "发布开头", "开头方式")):
        surfaces.append("publish_body_opening")
    if any(marker in publish for marker in ("结尾方式", "正文结尾", "发布结尾")):
        surfaces.append("publish_body_ending")
    if any(marker in publish for marker in ("话题", "标签")):
        surfaces.append("publish_topic")
    is_image_text = "图文" in content_form
    if performance:
        if not is_image_text:
            surfaces.append("video_visual_middle")
            if any(marker in performance for marker in ("封面", "首帧", "第一眼")):
                surfaces.extend(["video_visual_cover", "video_visual_opening"])
            if any(marker in performance for marker in ("结尾", "末帧", "收束")):
                surfaces.append("video_visual_ending")
        if any(marker in performance for marker in ("协同", "文图一致", "对齐")):
            surfaces.append("cross_modal_coordination")
    if not is_image_text and (structure or golden):
        surfaces.append("video_spoken_middle")
        if any(marker in structure + golden for marker in ("开头", "黄金3秒", "起话", "第一句")):
            surfaces.append("video_spoken_opening")
        if any(marker in structure + golden for marker in ("结尾", "收束", "最后一句")):
            surfaces.append("video_spoken_ending")
    return list(dict.fromkeys(surfaces))


def _facet_status(label: str, value: str) -> str:
    if PUBLISH_EXPLICIT_MISSING_PATTERN.search(value.strip()):
        return "explicitly_missing"
    if label in {"文案学习", "话题学习", "协同判断", "发布协同", "发布层协同", "发布视觉协同", "协同关系"}:
        return "observed_analysis"
    return "observed_raw"


def _publish_facet(
    *,
    facet: str,
    lines: list[dict[str, str | int]],
    card_ref: str,
    text: str,
    section_present: bool,
) -> dict[str, str]:
    prefixes = PUBLISH_FACET_PREFIXES[facet]
    for row in lines:
        value = str(row.get("text") or "").strip()
        for prefix in prefixes:
            match = re.match(rf"^{re.escape(prefix)}\s*[：:]\s*(.*)$", value)
            if not match:
                continue
            evidence = match.group(1).strip() or value
            return {
                "status": _facet_status(prefix, evidence),
                "evidence": evidence[:1200],
                "source_coordinate": str(row.get("coordinate") or f"card:{card_ref}#section:发布内容层学习"),
            }
    if facet == "title":
        metadata_title = field(text, "标题")
        if metadata_title:
            return {
                "status": "observed_raw",
                "evidence": metadata_title[:1200],
                "source_coordinate": f"card:{card_ref}#metadata:标题",
            }
    missing_labels = {
        "title": "未提供可回查标题证据",
        "body": "未提供独立正文或发布文案证据",
        "topics": "未提供显式话题或标签证据",
        "coordination": "未提供标题、正文和话题的协同判断",
    }
    return {
        "status": "explicitly_missing" if section_present else "evidence_unavailable",
        "evidence": missing_labels[facet],
        "source_coordinate": f"card:{card_ref}#section:发布内容层学习",
    }


def derive_publish_copy_observation(
    *,
    schema_id: str,
    dimensions: list[str],
    text: str,
    path: Path,
    root: Path,
    status: str,
) -> dict[str, Any]:
    observation = _derive_signal_observation(
        schema_id=schema_id,
        dimensions=dimensions,
        keyword_map=PUBLISH_COPY_KEYWORDS,
        headings=("发布内容层学习",),
        fingerprint_key="publish_copy_fingerprint",
        text=text,
        path=path,
        root=root,
        status=status,
    )
    section_present = bool(named_sections(text).get("发布内容层学习", "").strip())
    lines = _evidence_lines(text, ("发布内容层学习",), path, root)
    card_ref = _relative_card_ref(path, root)
    source_facets = {
        facet: _publish_facet(
            facet=facet,
            lines=lines,
            card_ref=card_ref,
            text=text,
            section_present=section_present,
        )
        for facet in ("title", "body", "topics", "coordination")
    }
    coordinates = list(
        dict.fromkeys(
            [str(value) for value in observation.get("evidence_coordinates", []) if str(value)]
            + [record["source_coordinate"] for record in source_facets.values()]
        )
    )
    observation.update(
        {
            "publish_layer_status": "observed" if section_present else "missing",
            "source_facets": source_facets,
            "evidence_coordinates": coordinates,
        }
    )
    return observation


def publish_copy_observation_complete(observation: dict[str, Any]) -> bool:
    if observation.get("publish_layer_status") != "observed":
        return False
    facets = observation.get("source_facets")
    if not isinstance(facets, dict) or set(facets) != {"title", "body", "topics", "coordination"}:
        return False
    allowed = {"observed_raw", "observed_analysis", "explicitly_missing"}
    statuses: list[str] = []
    for facet in facets.values():
        if not isinstance(facet, dict):
            return False
        if not all(str(facet.get(key) or "").strip() for key in ("status", "evidence", "source_coordinate")):
            return False
        statuses.append(str(facet["status"]))
    return set(statuses).issubset(allowed) and any(value.startswith("observed") for value in statuses)


def make_publish_copy_record(
    *,
    source_id: str,
    expression_candidate_ids: list[str],
    card_path: Path,
    card_text: str,
    root: Path,
    schema_id: str,
    dimensions: list[str],
    status: str,
) -> dict[str, Any]:
    observation = derive_publish_copy_observation(
        schema_id=schema_id,
        dimensions=dimensions,
        text=card_text,
        path=card_path,
        root=root,
        status=status,
    )
    complete = publish_copy_observation_complete(observation)
    return {
        "id": f"publish-copy-{source_id}",
        "type": "publish_copy_observation",
        "source_refs": [source_id],
        "expression_candidate_ids": sorted(set(expression_candidate_ids)),
        "card_path": _relative_card_ref(card_path, root),
        "card_schema": detect_schema(card_text),
        "content_form": card_content_form(card_text),
        "compatibility_mode": "unified_card" if detect_schema(card_text) == CONTRACT_ID else "legacy_publish_evidence",
        "status": "candidate_observation" if complete else "deferred_evidence",
        "callable": False,
        "publish_copy_observation": observation,
    }


def summarize_publish_copy_records(
    *,
    workflow_id: str,
    account_name: str,
    records: list[dict[str, Any]],
    expected_source_ids: set[str],
    study_schema: str,
    observation_schema: str,
) -> dict[str, Any]:
    completed = [item for item in records if item.get("status") == "candidate_observation"]
    completed_ids = {
        str(source_id)
        for item in completed
        for source_id in item.get("source_refs", [])
        if str(source_id)
    }
    dimensions: Counter[str] = Counter()
    missing_dimensions: Counter[str] = Counter()
    facet_statuses: dict[str, Counter[str]] = {
        facet: Counter() for facet in ("title", "body", "topics", "coordination")
    }
    patterns: dict[tuple[str, ...], list[str]] = {}
    for item in completed:
        observation = item.get("publish_copy_observation", {})
        labels = tuple(
            str(signal.get("signal"))
            for signal in observation.get("observed_signals", [])
            if isinstance(signal, dict) and signal.get("signal")
        )
        source_id = str((item.get("source_refs") or [""])[0])
        patterns.setdefault(labels, []).append(source_id)
        dimensions.update(labels)
        missing_dimensions.update(map(str, observation.get("missing_or_uncertain_signals", [])))
        facets = observation.get("source_facets", {})
        if isinstance(facets, dict):
            for facet, counter in facet_statuses.items():
                value = facets.get(facet, {})
                if isinstance(value, dict):
                    counter.update([str(value.get("status") or "missing")])
    pattern_candidates = []
    for labels, source_ids in sorted(patterns.items(), key=lambda item: (-len(item[1]), item[0])):
        pattern_id = hashlib.sha256("|".join(labels).encode("utf-8")).hexdigest()[:12]
        pattern_candidates.append(
            {
                "id": f"publish-pattern-{pattern_id}",
                "signals": list(labels),
                "source_count": len(source_ids),
                "source_refs": sorted(source_ids),
                "status": "candidate_only",
                "callable": False,
                "triple_verification_required": True,
            }
        )
    deferred_ids = sorted(expected_source_ids - completed_ids)
    return {
        "schema_version": study_schema,
        "workflow_id": workflow_id,
        "account_name": account_name,
        "status": "completed" if not deferred_ids else "completed_with_deferred_evidence",
        "observation_schema": observation_schema,
        "observation_file": "candidates/publish_copy_observations.jsonl",
        "observation_sha256": "",
        "expected_source_count": len(expected_source_ids),
        "completed_source_count": len(completed_ids),
        "deferred_source_count": len(deferred_ids),
        "deferred_source_ids": deferred_ids,
        "unified_card_count": sum(item.get("compatibility_mode") == "unified_card" for item in completed),
        "legacy_publish_evidence_count": sum(
            item.get("compatibility_mode") == "legacy_publish_evidence" for item in completed
        ),
        "dimension_coverage": {
            dimension: {
                "observed_source_count": dimensions[dimension],
                "missing_source_count": missing_dimensions[dimension],
            }
            for dimension in sorted(set(dimensions) | set(missing_dimensions))
        },
        "facet_coverage": {
            facet: dict(sorted(counter.items())) for facet, counter in facet_statuses.items()
        },
        "cross_card_pattern_candidates": pattern_candidates,
        "formal_write": False,
        "callable": False,
        "user_review_required": True,
    }


def render_publish_copy_study(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {payload.get('account_name') or payload.get('workflow_id')}发布文案专项学习报告",
            "",
            f"- workflow_id: `{payload.get('workflow_id')}`",
            f"- 状态: `{payload.get('status')}`",
            f"- 专项观察: {payload.get('completed_source_count')} / {payload.get('expected_source_count')}",
            f"- 证据延期: {payload.get('deferred_source_count')}",
            f"- 统一卡: {payload.get('unified_card_count')}；旧卡发布层兼容证据: {payload.get('legacy_publish_evidence_count')}",
            "- 学习范围: 标题、正文或文案、话题或标签及三者协同；缺失项显式记录，不补造。",
            "- 跨卡聚合只形成待三重验证候选，不自动修改正式账号 Skill。",
            "- 写入边界: formal_write=false、callable=false、user_review_required=true。",
            "",
        ]
    )


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
    publish_copy_schema = str(observation_contract.get("publish_copy_schema_id") or "")
    publish_copy_study_schema = str(observation_contract.get("publish_copy_study_schema_id") or "")
    image_text_visual_schema = str(observation_contract.get("image_text_visual_schema_id") or "")
    publish_copy_dimensions = [str(value) for value in observation_contract.get("publish_copy_dimensions", [])]

    inventory = read_jsonl(inventory_path)
    inventory_ids = {str(row.get("source_id")) for row in inventory if row.get("source_id")}
    cards = sorted(card_root.glob("directions/*/cards/*.md"))
    outputs: dict[str, list[dict[str, Any]]] = {lens: [] for lens in LENSES}
    missing_inventory: list[str] = []
    direction_counts: Counter[str] = Counter()
    compatibility_counts: Counter[str] = Counter()
    publish_copy_records: list[dict[str, Any]] = []
    expression_lane = config.get("expression_asset_learning", {})
    expression_lane_enabled = bool(
        expression_lane.get("schema_id")
        and state.get("expression_asset_schema") == expression_lane.get("schema_id")
    )
    expression_audit_items: list[dict[str, Any]] = []
    expression_surface_coverage: Counter[str] = Counter({surface: 0 for surface in EXPRESSION_SURFACES})

    for path in cards:
        text = path.read_text(encoding="utf-8")
        source_id = field(text, "source_id")
        if not source_id:
            raise ValueError(f"source_id missing: {path}")
        title = card_title(text, path)
        direction = field(text, "主方向") or path.parents[1].name
        content_form = card_content_form(text)
        card_schema = detect_schema(text)
        compatibility_mode = "unified_card" if card_schema == CONTRACT_ID else "downgraded_legacy_card"
        compatibility_counts[compatibility_mode] += 1
        direction_counts[direction] += 1
        if source_id not in inventory_ids:
            missing_inventory.append(source_id)
        if expression_lane_enabled:
            surfaces = _expression_audit_surfaces(text, content_form)
            expression_surface_coverage.update(surfaces)
            expression_audit_items.append(
                {
                    "source_id": source_id,
                    "card_path": _relative_card_ref(path, root),
                    "content_form": content_form or "unknown",
                    "available_surfaces": surfaces,
                    "status": "awaiting_expression_deconstruction",
                    "required_asset_types": [
                        "hook",
                        "golden_line",
                        "sentence_pattern",
                        "structure_unit",
                        "transition",
                        "opening_move",
                        "ending_move",
                        "pain_point",
                        "adaptation_template",
                        "anti_pattern",
                    ],
                }
            )
        for lens in LENSES:
            summary = evidence_summary(text, SECTION_HEADINGS[lens])
            if not summary:
                if compatibility_mode == "unified_card":
                    summary = f"《{title}》属于{direction}方向；统一卡当前章节没有可提取的项目，保留缺口等待复核。"
                else:
                    summary = f"《{title}》属于{direction}方向；当前只保留为兼容旧卡观察，等待新流程补齐证据。"
            if lens == "counterexamples" and compatibility_mode == "unified_card":
                summary += "；本项只保留为单卡边界观察，单卡结论、功效表述和商业属性均不得直接晋升为稳定方法。"
            elif lens == "counterexamples":
                summary += "；旧卡已降级，单卡结论、功效表述和商业属性均不得直接晋升为稳定方法。"
            elif compatibility_mode == "unified_card":
                summary += "；该观察由统一学习卡的对应证据章节独立派生，只是阶段 1 候选，不做录取判断。"
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
                    "content_form": content_form,
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
            if lens == "expression" and publish_copy_schema:
                candidate["publish_copy_observation"] = derive_publish_copy_observation(
                        schema_id=publish_copy_schema,
                        dimensions=publish_copy_dimensions,
                        text=text,
                        path=path,
                        root=root,
                        status=str(observation_contract.get("candidate_status") or "single_card_observation"),
                    )
                publish_copy_records.append(
                    make_publish_copy_record(
                        source_id=source_id,
                        expression_candidate_ids=[str(candidate["id"])],
                        card_path=path,
                        card_text=text,
                        root=root,
                        schema_id=publish_copy_schema,
                        dimensions=publish_copy_dimensions,
                        status=str(observation_contract.get("candidate_status") or "single_card_observation"),
                    )
                )
                candidate["publish_copy_observation_refs"] = [f"publish-copy-{source_id}"]
            if compatibility_mode == "unified_card" and "图文" in content_form:
                if lens == "structures" and image_text_visual_schema:
                    candidate["image_text_visual_observation"] = _derive_signal_observation(
                        schema_id=image_text_visual_schema,
                        dimensions=[str(value) for value in observation_contract.get("image_text_visual_dimensions", [])],
                        keyword_map=IMAGE_TEXT_VISUAL_KEYWORDS,
                        headings=("内容结构", "视频/图文表现层学习"),
                        fingerprint_key="visual_sequence_fingerprint",
                        text=text,
                        path=path,
                        root=root,
                        status=str(observation_contract.get("candidate_status") or "single_card_observation"),
                    )
            outputs[lens].append(candidate)

    publish_copy_study = summarize_publish_copy_records(
        workflow_id=workflow_id,
        account_name=str(state.get("account_name") or workflow_id),
        records=publish_copy_records,
        expected_source_ids={
            str(source_id)
            for record in publish_copy_records
            for source_id in record.get("source_refs", [])
            if str(source_id)
        },
        study_schema=publish_copy_study_schema,
        observation_schema=publish_copy_schema,
    )

    result = {
        "ok": True,
        "status": "applied" if apply else "dry_run",
        "workflow_id": workflow_id,
        "inventory_count": len(inventory),
        "compatibility_card_count": len(cards),
        "unified_card_count": compatibility_counts["unified_card"],
        "downgraded_legacy_card_count": compatibility_counts["downgraded_legacy_card"],
        "pending_full_evidence_count": max(len(inventory_ids) - len(cards), 0),
        "candidate_count": sum(len(rows) for rows in outputs.values()),
        "lens_counts": {lens: len(outputs[lens]) for lens in LENSES},
        "direction_counts": dict(sorted(direction_counts.items())),
        "card_ids_missing_from_inventory": sorted(missing_inventory),
        "publish_copy_expected_count": publish_copy_study["expected_source_count"],
        "publish_copy_completed_count": publish_copy_study["completed_source_count"],
        "publish_copy_deferred_count": publish_copy_study["deferred_source_count"],
        "formal_write_allowed": False,
        "expression_asset_audit_source_count": len(expression_audit_items),
        "expression_asset_sample_generated": False,
    }
    if not apply:
        return result

    for lens, rows in outputs.items():
        write_jsonl(workflow / "candidates" / f"{lens}.jsonl", rows)
    publish_copy_path = workflow / "candidates/publish_copy_observations.jsonl"
    write_jsonl(publish_copy_path, publish_copy_records)
    publish_copy_study["observation_sha256"] = hashlib.sha256(publish_copy_path.read_bytes()).hexdigest()
    (workflow / "PUBLISH_COPY_SPECIAL_STUDY.json").write_text(
        json.dumps(publish_copy_study, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (workflow / "PUBLISH_COPY_SPECIAL_STUDY.md").write_text(
        render_publish_copy_study(publish_copy_study),
        encoding="utf-8",
    )
    state["publish_copy_observation_schema"] = publish_copy_schema
    state["publish_copy_study_schema"] = publish_copy_study_schema
    state["publish_copy_expected_count"] = publish_copy_study["expected_source_count"]
    state["publish_copy_completed_count"] = publish_copy_study["completed_source_count"]
    state["publish_copy_deferred_count"] = publish_copy_study["deferred_source_count"]
    if expression_lane_enabled:
        expression_root = workflow / str(expression_lane.get("root") or "expression_assets")
        expression_root.mkdir(parents=True, exist_ok=True)
        audit = {
            "schema_version": "expression_asset_audit_v1",
            "status": "completed",
            "workflow_id": workflow_id,
            "account_id": str(state.get("account_id") or state.get("profile_id") or workflow_id),
            "source_count": len(expression_audit_items),
            "surface_coverage": dict(sorted(expression_surface_coverage.items())),
            "extraction_started": False,
            "queue_file": "extraction_queue.jsonl",
            "sample_max_items": 20,
            "formal_write": False,
            "callable": False,
            "account_assets_generated": False,
        }
        (expression_root / "audit_report.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_jsonl(expression_root / "extraction_queue.jsonl", expression_audit_items)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = workflow / "STAGE1_EXTRACTION_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                f"# {state.get('account_name') or workflow_id}阶段 1 五视角提取报告",
                "",
                f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
                f"- 候选资料范围：{len(inventory)} 条",
                f"- 读取学习卡：{len(cards)} 张（统一卡 {compatibility_counts['unified_card']}；降级旧卡 {compatibility_counts['downgraded_legacy_card']}）",
                f"- 五视角候选：{result['candidate_count']} 条（每视角 {len(cards)} 条）",
                f"- 尚待补完整证据：{result['pending_full_evidence_count']} 条",
                f"- 发布文案专项观察：{publish_copy_study['completed_source_count']} / {publish_copy_study['expected_source_count']}；延期 {publish_copy_study['deferred_source_count']}",
                "- 状态：阶段 1 候选观察；不代表方法录取，不可调用，不写正式知识。",
                "",
                "## 证据边界",
                "",
                "- 统一卡从对应证据章节派生；旧卡仅按 active Skill 的兼容模式读取，其历史 formal_ingested 标记不再生效。",
                "- 每个视角从不同卡片章节独立提取，不沿用其他视角的录取判断。",
                "- 视频下载、逐字稿、抽帧和图文 OCR 缺口继续保留，阶段 2 不得把缺证据记录伪装为已验证。",
                "- 所有内容形态都生成发布文案专项观察；统一图文卡额外生成图片深度派生观察。两者仍归入 expression 与 structures，不增加视角，也不自动晋升方法。",
                "- 表达资产链只生成证据覆盖审计与待拆解队列；小样本必须逐条拆解、绑定来源权威并通过校验，代码不会用关键词冒充钩子或金句。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result["report"] = report_path.relative_to(root).as_posix()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract five independent stage-1 lenses from unified or downgraded account cards.")
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
