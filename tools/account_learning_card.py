from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRACT_ID = "unified_three_layer_v2"
UNIFIED_SECTIONS = (
    "证据边界",
    "为什么值得学习",
    "多维分类与商业隔离",
    "核心观点",
    "内容结构",
    "发布内容层学习",
    "视频/图文表现层学习",
    "金句与表达素材",
    "可复用选题与案例",
    "方法候选与可复用方法论",
    "可复用模板",
    "证据缺口与候选判断",
)
LEGACY_RICH_SECTIONS = (
    "为什么值得学习",
    "核心观点",
    "内容结构",
    "表达素材与金句提炼",
    "可复用案例",
    "可复用方法论",
    "可复用模板",
    "证据缺口/后续问题",
    "入库判断",
)
METHOD_CANDIDATE_SECTIONS = (
    "R - 原始证据",
    "I - 初步解释",
    "A1 - 本条案例",
    "A2 - 未来触发场景",
    "E - 初步执行步骤",
    "B - 边界与反例",
)
REQUIRED_METADATA = (
    "学习卡契约",
    "source_id",
    "原内容链接",
    "账号",
    "平台",
    "主方向",
    "学习批次",
    "状态",
)


@dataclass(frozen=True)
class CardContractValidation:
    schema: str
    errors: tuple[str, ...]
    sections: dict[str, str]
    metadata: dict[str, str]

    @property
    def valid(self) -> bool:
        return not self.errors


def meaningful_lines(text: str) -> list[str]:
    values: list[str] = []
    for raw in text.splitlines():
        value = raw.strip().strip("-*`> \t")
        if value and not value.startswith("#") and not set(value) <= {"-", "|", " "}:
            values.append(value)
    return values


def parse_numbered_sections(text: str) -> tuple[dict[str, str], list[str]]:
    matches = list(re.finditer(r"^##\s+\d+\.\s+(.+?)\s*$", text, re.M))
    sections: dict[str, str] = {}
    duplicates: list[str] = []
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if name in sections:
            duplicates.append(name)
        sections[name] = text[start:end].strip()
    return sections, duplicates


def parse_metadata(text: str) -> dict[str, str]:
    aliases = {
        "原视频链接": "原内容链接",
        "原图文链接": "原内容链接",
        "原链接": "原内容链接",
    }
    metadata: dict[str, str] = {}
    for raw in text.splitlines()[:45]:
        match = re.match(r"^([^#\s][^:：]{0,24})[:：]\s*(.*?)\s*$", raw.strip())
        if not match:
            continue
        key = aliases.get(match.group(1).strip(), match.group(1).strip())
        metadata[key] = match.group(2).strip()
    return metadata


def detect_schema(text: str, sections: dict[str, str] | None = None, metadata: dict[str, str] | None = None) -> str:
    sections = sections if sections is not None else parse_numbered_sections(text)[0]
    metadata = metadata if metadata is not None else parse_metadata(text)
    if metadata.get("学习卡契约") == CONTRACT_ID:
        return CONTRACT_ID
    if "方法候选与可复用方法论" in sections or "金句与表达素材" in sections:
        return CONTRACT_ID
    if all(section in sections for section in LEGACY_RICH_SECTIONS):
        return "legacy_rich_v1"
    if "证据边界" in sections and "多维分类" in sections:
        return "evidence_card_v1"
    return "unknown"


def _require_terms(section: str, content: str, terms: tuple[str, ...], errors: list[str]) -> None:
    for term in terms:
        if term not in content:
            errors.append(f"{section}:missing_{term}")


def _content_form(sections: dict[str, str]) -> str:
    match = re.search(r"内容形态[:：]\s*([^\n]+)", sections.get("多维分类与商业隔离", ""))
    return match.group(1).strip() if match else ""


def _method_subsections(content: str) -> dict[str, str]:
    matches = list(re.finditer(r"^###\s+(.+?)\s*$", content, re.M))
    values: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        values[match.group(1).strip()] = content[start:end].strip()
    return values


def validate_unified_text(text: str) -> CardContractValidation:
    sections, duplicates = parse_numbered_sections(text)
    metadata = parse_metadata(text)
    errors: list[str] = [f"duplicate_section:{name}" for name in duplicates]
    for field in REQUIRED_METADATA:
        if not metadata.get(field):
            errors.append(f"missing_metadata:{field}")
    if metadata.get("学习卡契约") and metadata.get("学习卡契约") != CONTRACT_ID:
        errors.append("invalid_contract_id")
    for index, section in enumerate(UNIFIED_SECTIONS, 1):
        if section not in sections:
            errors.append(f"missing_section:{index}:{section}")
        elif not meaningful_lines(sections[section]):
            errors.append(f"empty_section:{index}:{section}")

    evidence = sections.get("证据边界", "")
    _require_terms("证据边界", evidence, ("主证据", "辅助证据", "证据状态"), errors)
    classification = sections.get("多维分类与商业隔离", "")
    _require_terms("多维分类与商业隔离", classification, ("内容形态", "商业属性", "隔离判断"), errors)
    viewpoints = sections.get("核心观点", "")
    if len(meaningful_lines(viewpoints)) < 2:
        errors.append("核心观点:requires_2_points")

    structure = sections.get("内容结构", "")
    content_form = _content_form(sections)
    if any(token in content_form for token in ("剧情", "合拍", "唱演", "故事")):
        _require_terms("内容结构", structure, ("开头设定", "核心冲突", "转折或笑点", "收尾"), errors)
    elif "图文" in content_form:
        _require_terms("内容结构", structure, ("封面承诺", "分图顺序", "信息层级", "收尾互动"), errors)
    else:
        _require_terms("内容结构", structure, ("黄金3秒", "观点提出", "证据或案例", "收尾"), errors)

    publish = sections.get("发布内容层学习", "")
    _require_terms("发布内容层学习", publish, ("标题", "正文或文案", "话题或标签"), errors)
    media = sections.get("视频/图文表现层学习", "")
    _require_terms("视频/图文表现层学习", media, ("媒体类型", "分析状态", "表现学习"), errors)
    if "图文" in content_form:
        _require_terms(
            "发布内容层学习",
            publish,
            (
                "标题原文",
                "标题机制",
                "正文原文",
                "正文结构",
                "细节密度",
                "真人感",
                "结尾方式",
                "话题策略",
                "发布视觉协同",
            ),
            errors,
        )
        _require_terms(
            "视频/图文表现层学习",
            media,
            (
                "封面钩子",
                "逐图角色",
                "分图顺序",
                "构图与视角",
                "动作与状态",
                "文字注释设计",
                "字形字号层级",
                "色彩光线质感",
                "真人与生活感",
                "跨模态协同",
                "收藏理由",
            ),
            errors,
        )
        if any(placeholder in publish or placeholder in media for placeholder in ("待补充", "待分析", "待学习")):
            errors.append("image_text_layers:placeholder_not_allowed")
    quotes = sections.get("金句与表达素材", "")
    _require_terms("金句与表达素材", quotes, ("原文金句", "提炼表达", "可复用句式"), errors)
    topics_cases = sections.get("可复用选题与案例", "")
    _require_terms("可复用选题与案例", topics_cases, ("可复用选题", "可复用案例"), errors)
    method = sections.get("方法候选与可复用方法论", "")
    for item in METHOD_CANDIDATE_SECTIONS:
        if not re.search(rf"^###\s+{re.escape(item)}\s*$", method, re.M):
            errors.append(f"方法候选与可复用方法论:missing_{item}")
    method_subsections = _method_subsections(method)
    a2 = method_subsections.get("A2 - 未来触发场景", "")
    _require_terms(
        "A2 - 未来触发场景",
        a2,
        ("触发机制", "适用关系", "可迁移场景", "不触发条件"),
        errors,
    )
    template = sections.get("可复用模板", "")
    if len(meaningful_lines(template)) < 2:
        errors.append("可复用模板:too_shallow")
    gaps = sections.get("证据缺口与候选判断", "")
    _require_terms("证据缺口与候选判断", gaps, ("证据缺口", "卡片判断", "跨卡状态"), errors)
    return CardContractValidation(CONTRACT_ID, tuple(sorted(set(errors))), sections, metadata)


def validate_legacy_rich_text(text: str) -> CardContractValidation:
    sections, duplicates = parse_numbered_sections(text)
    metadata = parse_metadata(text)
    errors: list[str] = [f"duplicate_section:{name}" for name in duplicates]
    for section in LEGACY_RICH_SECTIONS:
        if section not in sections:
            errors.append(f"missing_legacy_section:{section}")
    if "视频层学习" not in sections and "发布资产学习" not in sections:
        errors.append("missing_legacy_media_section")
    return CardContractValidation("legacy_rich_v1", tuple(sorted(set(errors))), sections, metadata)


def validate_card_text(text: str) -> CardContractValidation:
    sections, _ = parse_numbered_sections(text)
    metadata = parse_metadata(text)
    schema = detect_schema(text, sections, metadata)
    if schema == CONTRACT_ID:
        return validate_unified_text(text)
    if schema == "legacy_rich_v1":
        return validate_legacy_rich_text(text)
    if schema == "evidence_card_v1":
        return CardContractValidation(schema, (), sections, metadata)
    return CardContractValidation(schema, ("unknown_card_schema",), sections, metadata)


def contract_summary() -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "required_sections": list(UNIFIED_SECTIONS),
        "required_metadata": list(REQUIRED_METADATA),
        "method_candidate_sections": list(METHOD_CANDIDATE_SECTIONS),
    }


def validate_card_file(path: Path, root: Path | None = None) -> dict[str, Any]:
    path = path.resolve()
    text = path.read_text(encoding="utf-8", errors="ignore")
    result = validate_card_text(text)
    display_path = path.as_posix()
    if root is not None:
        try:
            display_path = path.relative_to(root.resolve()).as_posix()
        except ValueError:
            display_path = path.as_posix()
    return {
        "ok": result.valid,
        "path": display_path,
        "schema": result.schema,
        "contract_id": CONTRACT_ID,
        "section_count": len(result.sections),
        "errors": list(result.errors),
    }
