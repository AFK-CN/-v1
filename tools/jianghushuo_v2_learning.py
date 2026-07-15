from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import (
    CONTRACT_ID,
    meaningful_lines,
    parse_numbered_sections,
    validate_card_text,
)
from tools.jianghushuo_nas import CURRENT_ACCOUNT_DIR, evidence_ready, evidence_status, read_transcript_lines, transcript_path
from tools.video_learning import (
    candidate_topic_angle,
    detect_directions,
    first_sentence,
    golden_3s_hook,
    load_unique_records_detailed,
    records_by_source_id,
    reusable_template,
    run_selected_deep_learning,
    selected_deep_cards_dir,
)


ACCOUNT_ID = "jianghushuo"
ACCOUNT_NAME = "姜胡说"
WORKFLOW_ID = "jianghushuo-v2-full"
WORKFLOW_ROOT = Path("10_Knowledge/candidates/account_learning_workflows") / WORKFLOW_ID
DOWNGRADE_MANIFEST = Path(
    "10_Knowledge/candidates/account_assets/downgraded_formal_cards/jianghushuo/2026-07-12/downgrade_manifest.json"
)
ROUGH_INVENTORY = Path("10_Knowledge/candidates/account_assets/content_rough_scan/jianghushuo/all_content_inventory.jsonl")
DEFAULT_NAS_ROOT = CURRENT_ACCOUNT_DIR
LENSES = ("positioning", "topics", "structures", "expression", "counterexamples")
STRONG_AD = re.compile(
    r"本视频由.{1,40}赞助|感谢.{1,40}赞助|(?:本视频|本期|本条|本次).{0,30}"
    r"(?:品牌合作|广告合作|星图合作|商务合作|合作推广)|星图任务|广告植入"
)
PLATFORM_PROJECT = re.compile(r"挑战赛|平台活动|全民任务|抖音热点|话题活动|DOU来")
COLLABORATION = re.compile(r"合拍|连麦|对谈|采访|嘉宾|合作视频")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_jsonl_tolerant(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            values.append(item)
    return values


def first_legacy_line(section: str, fallback: str) -> str:
    lines = meaningful_lines(section)
    return lines[0] if lines else fallback


def legacy_field(section: str, label: str, fallback: str) -> str:
    match = re.search(rf"(?:^|\n)\s*-\s*{re.escape(label)}[:：]\s*(.+)", section)
    return match.group(1).strip() if match else fallback


def transcript_lines(path: Path) -> list[str]:
    return read_transcript_lines(path)


def transcript_coordinate(path: Path, excerpt: str) -> str:
    """Return a reproducible source line coordinate for a quoted transcript excerpt."""

    if not path.is_file():
        return "待补：逐字稿文件不存在"
    normalized_excerpt = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", excerpt).lower()
    raw_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line_number, raw in enumerate(raw_lines, 1):
        normalized_line = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", raw).lower()
        if len(normalized_line) < 4:
            continue
        if normalized_line in normalized_excerpt or normalized_excerpt[: min(len(normalized_excerpt), 24)] in normalized_line:
            return f"{path}:L{line_number}"
    return f"{path}:L?（需人工定位）"


def visual_coordinate(evidence: dict[str, Any]) -> str:
    """Return a frame/time coordinate without inventing a visual interpretation."""

    artifact_dir = Path(str(evidence.get("artifact_dir") or ""))
    for index_name in ("frames.codex.json", "frames.json"):
        index_path = artifact_dir / index_name
        if not index_path.is_file():
            continue
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        frames = payload.get("frames") if isinstance(payload, dict) else None
        if isinstance(frames, list) and frames:
            frame = frames[len(frames) // 2]
            if isinstance(frame, dict):
                frame_path = artifact_dir / str(frame.get("path") or "")
                second = frame.get("approx_second")
                if frame_path.is_file() and isinstance(second, (int, float)):
                    return f"{frame_path}（约 {float(second):.3f}s）"
    for folder in ("frames", "frames_codex", "keyframes"):
        frames = sorted(path for path in (artifact_dir / folder).glob("*") if path.is_file())
        if frames:
            return f"{frames[len(frames) // 2]}（仅帧号可回查，时间码待补）"
    return "待补：无可回查帧或时间码；不形成视觉结论"


def joined_excerpt(lines: list[str], start: int, count: int = 4) -> str:
    values = lines[start : start + count]
    return "，".join(values) if values else "未提取到可用逐字稿片段"


def transcript_excerpt_at(lines: list[str], ratio: float, count: int = 4) -> str:
    if not lines:
        return "未提取到可用逐字稿片段"
    start = max(min(int(len(lines) * ratio) - count // 2, max(len(lines) - count, 0)), 0)
    return joined_excerpt(lines, start, count)


def evidence_body(record_body: str, title: str, fallback: str) -> str:
    value = first_sentence(record_body, 260)
    normalized_value = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", value).lower()
    normalized_title = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", title).lower()
    if normalized_value in {"", "未提供正文", "无正文", "暂无正文", "null", "none"} or normalized_value == normalized_title:
        return fallback
    return value


def evidence_title(record_title: str, source_id: str, transcript_fallback: str) -> str:
    value = first_sentence(record_title, 160)
    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", value).lower()
    if normalized in {"", "未提供正文", "无正文", "暂无正文", "null", "none"}:
        return first_sentence(transcript_fallback, 120) or source_id
    return value


def review_reason_text(value: Any) -> str:
    reason = str(value or "").strip()
    return {
        "no_direction_signal": "发布层缺少明确方向信号",
        "low_score_margin": "方向评分接近，需要人工复核",
        "top_score_tied": "多个方向并列，需要人工复核",
        "rough_inventory_record_unavailable": "粗扫清单未提供可靠分类",
    }.get(reason, reason or "未注明原因")


def content_classification(record: Any) -> dict[str, Any]:
    """Classify with explicit publication-layer markers; discussion of ads alone is not an ad."""

    search_text = " ".join(
        (
            str(record.title or ""),
            str(record.body or ""),
            " ".join(map(str, record.tags or [])),
        )
    )
    explicit_ad_tags = {"品牌合作", "广告合作", "星图合作", "商务合作", "合作推广", "星图任务", "广告植入"}
    if STRONG_AD.search(search_text) or explicit_ad_tags & {str(tag).strip() for tag in record.tags or []}:
        return {
            "id": "product_ad",
            "label": "商品广告（明确商业合作标记）",
            "basis": "发布标题、正文或标签出现明确自披露商业合作标记。",
            "isolation": "独立进入商品广告学习轨，不计入自然选题频次和自然方法 V1。",
            "excluded_from_natural_v1": True,
        }
    if PLATFORM_PROJECT.search(search_text):
        return {
            "id": "platform_project",
            "label": "平台项目（明确活动标记）",
            "basis": "发布标题、正文或标签出现明确平台活动/任务标记。",
            "isolation": "独立进入平台项目学习轨，不计入自然选题频次和自然方法 V1。",
            "excluded_from_natural_v1": True,
        }
    if COLLABORATION.search(search_text):
        return {
            "id": "collaboration_ownership",
            "label": "协作/采访内容（归属待核验）",
            "basis": "发布标题、正文或标签出现采访、嘉宾、合拍等归属信号。",
            "isolation": "完成说话人和来源归属核验前，只作协作证据，不计入姜胡说自然方法 V1。",
            "excluded_from_natural_v1": True,
        }
    return {
        "id": "natural_content",
        "label": "自然内容（未发现明确商业、平台或协作标记）",
        "basis": "发布标题、正文和标签未出现明确自披露商业合作、平台项目或协作归属标记。",
        "isolation": "可进入自然内容候选池；仍须通过跨卡三重验证后才能形成稳定方法。",
        "excluded_from_natural_v1": False,
    }


def evidence_quote(legacy_structure: str, lines: list[str]) -> tuple[str, str]:
    transcript = "".join(lines)
    match = re.search(r"[“\"]([^”\"]{6,80})[”\"]", legacy_structure)
    if match and re.sub(r"\s+", "", match.group(1)) in re.sub(r"\s+", "", transcript):
        return match.group(1), "旧卡钩子已在 NAS 逐字稿中逐字回查"
    quote = "，".join(lines[: min(4, len(lines))]) if lines else "逐字稿不可用，不保留原文金句"
    return quote, "NAS ASR 原始片段；只作为可回查证据，不代表人工校正后的原话"


def render_upgraded_card(record: Any, item: dict[str, str], batch_id: str, evidence: dict[str, Any], legacy_text: str, srt_path: Path) -> str:
    sections = parse_numbered_sections(legacy_text)[0]
    why = sections.get("为什么值得学习", "")
    viewpoints = sections.get("核心观点", "")
    structure = sections.get("内容结构", "")
    expressions = sections.get("表达素材与金句提炼", "")
    media = sections.get("发布资产学习", "")
    cases = sections.get("可复用案例", "")
    methods = sections.get("可复用方法论", "")
    template = sections.get("可复用模板", "")
    gaps = sections.get("证据缺口/后续问题", "")
    direction = item["direction"]
    title = first_sentence(record.title, 160) or item["source_id"]
    lines = transcript_lines(srt_path)
    quote, quote_note = evidence_quote(structure, lines)
    core_lines = meaningful_lines(viewpoints)[:5]
    core_block = "\n".join(f"- {line}" for line in core_lines) or f"- 历史候选只确认本条围绕{direction}展开。\n- 需结合 NAS 证据重新解释。"
    golden = legacy_field(structure, "黄金 3 秒钩子", first_legacy_line(structure, title))
    evidence_case = legacy_field(structure, "论证方式", first_legacy_line(cases, "本条案例待复核"))
    ending = legacy_field(structure, "结尾行动指向", legacy_field(structure, "收尾/互动引导", "未明确"))
    distilled = legacy_field(expressions, "候选金句", first_legacy_line(viewpoints, "本条观点待复核"))
    reusable_sentence = legacy_field(expressions, "反常识表达", legacy_field(expressions, "候选短句", distilled))
    method_summary = first_legacy_line(methods, "本条方法候选等待跨卡验证")
    case_summary = first_legacy_line(cases, "本条来源案例")
    legacy_gap = first_legacy_line(gaps, "单卡证据不足以形成稳定方法")
    classification = content_classification(record)
    gap_summary = f"{legacy_gap}；本条《{first_sentence(title, 50)}》仍需复核跨卡重复性与机制稳定性。"
    template_text = template.strip() or "先提出具体问题，再给出来源案例、执行动作和适用边界。"
    tags = "、".join(record.tags) if record.tags else "未提取到显式标签"
    evidence_status = (
        f"video={'可用' if evidence.get('has_video') else '缺失'}；"
        f"transcript={'可用' if evidence.get('has_transcript') else '缺失'}；"
        f"keyframes={'可用' if evidence.get('has_keyframes') else '缺失'}；"
        f"scenes={'可用' if evidence.get('has_scenes') else '缺失'}"
    )
    text_coordinate = transcript_coordinate(srt_path, quote)
    frame_coordinate = visual_coordinate(evidence)
    return f"""# 姜胡说 2.2 升级学习卡：{title}

学习卡契约：{CONTRACT_ID}
source_id：{item['source_id']}
原内容链接：{record.url}
账号：{ACCOUNT_NAME}
平台：抖音
主方向：{direction}
学习批次：{batch_id}
状态：candidate_learned

## 1. 证据边界

- 主证据：NAS 原视频、完整逐字稿、场景切分和抽帧。
- 辅助证据：SQLite 发布标题、正文、标签和旧卡候选假设；旧卡不重复计为独立来源。
- 证据状态：{evidence_status}。
- 原文筛查：{quote_note}。
- 文本证据坐标：{text_coordinate}。
- 视觉证据坐标：{frame_coordinate}；本卡未对该帧作超出画面的品牌、商品或购买利益判断。

## 2. 为什么值得学习

{why.strip() or f'- 本条是{direction}方向的优先重学样本。'}
- 升级判断：旧卡只提供待复核假设，本轮重新以 NAS 证据建立单卡和五视角观察。

## 3. 多维分类与商业隔离

- 内容形态：知识/评论
- 主方向：{direction}
- 商业属性：{classification['label']}
- 分类依据：{classification['basis']}主方向由降级清单历史路由与当前发布层共同确定。
- 隔离判断：{classification['isolation']}

## 4. 核心观点

{core_block}

## 5. 内容结构

- 黄金3秒：{golden}
- 观点提出：{core_lines[0] if core_lines else title}
- 证据或案例：{evidence_case}
- 推演：{method_summary}
- 收尾：{ending}

## 6. 发布内容层学习

- 标题：{title}
- 正文或文案：{first_sentence(record.body, 220) or '未提取到有效正文或文案'}
- 话题或标签：{tags}
- 协同判断：标题负责承诺，正文展开案例和动作，标签只辅助限定主题，不单独触发方法。

## 7. 视频/图文表现层学习

- 媒体类型：视频。
- 分析状态：{evidence_status}。
- 可回查坐标：{frame_coordinate}。
- 表现学习：{first_legacy_line(media, '先看口播承诺、案例推进和行动收尾；镜头与节奏结论等待帧级复核。')}

## 8. 金句与表达素材

- 原文金句：{quote}
- 提炼表达（非原话）：{distilled}
- 可复用句式：{reusable_sentence}

## 9. 可复用选题与案例

- 可复用选题：围绕“{method_summary}”更换对象与场景，验证“{case_summary}”中的核心因果能否再次成立。
- 可复用案例：{case_summary}
- 复用边界：只复用问题、证据和行动之间的结构，不复制来源事实、身份和原句。

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。

### R - 原始证据

{quote}

### I - 初步解释

{method_summary}

### A1 - 本条案例

{case_summary}

### A2 - 未来触发场景

- 触发机制：新任务需要复用“{method_summary}”所描述的核心因果，并能提供新的案例与行动反馈时，才考虑本候选。
- 适用关系：来源人物关系只作为本条案例；更换关系后因果仍成立才能迁移。
- 可迁移场景：来源场景只作为 A1；更换场景后仍能复现“{method_summary}”的因果链时才能迁移。
- 不触发条件：只命中{direction}、人物、场景或道具词，但无法保留“{method_summary}”的核心机制时不得调用。

### E - 初步执行步骤

{template_text}

### B - 边界与反例

- {gap_summary}
- 单卡、旧卡和阶段 1 观察均不可直接调用；必须进入跨卡聚合、三重验证和压力测试。

## 11. 可复用模板

{template_text}

## 12. 证据缺口与候选判断

- 证据缺口：{gap_summary}
- 卡片判断：保留为统一三层候选卡，并进入五视角观察池。
- 跨卡状态：待验证；本批不形成稳定方法，不恢复正式知识。
"""


def render_nas_only_card(record: Any, item: dict[str, Any], batch_id: str, evidence: dict[str, Any], srt_path: Path) -> str:
    lines = transcript_lines(srt_path)
    direction = str(item.get("direction") or "待复核")
    opening = transcript_excerpt_at(lines, 0.0)
    title = evidence_title(record.title, str(item["source_id"]), opening)
    early = transcript_excerpt_at(lines, 0.25)
    middle = transcript_excerpt_at(lines, 0.5)
    late = transcript_excerpt_at(lines, 0.75)
    ending = transcript_excerpt_at(lines, 1.0)
    body = evidence_body(record.body, title, middle)
    topic = f"把《{first_sentence(title, 55)}》中的{direction}问题换一个对象或场景，验证“{first_sentence(early, 85)}”是否仍成立"
    method = f"以《{first_sentence(title, 55)}》提出承诺，用“{first_sentence(early, 75)}”建立问题，再以“{first_sentence(middle, 75)}”推进，最后用“{first_sentence(late, 75)}”形成判断。"
    gap_parts = []
    if item.get("needs_review"):
        gap_parts.append(f"粗扫分类待复核：{review_reason_text(item.get('review_reason'))}")
    if not evidence.get("has_keyframes"):
        gap_parts.append("抽帧缺失，视觉结论降级")
    if not evidence.get("has_scenes"):
        gap_parts.append("场景切分缺失，镜头节奏不作强结论")
    classification = content_classification(record)
    gap = "；".join(gap_parts) or f"《{first_sentence(title, 55)}》尚未进入跨卡验证，机制稳定性仍需复核"
    evidence_status = (
        f"video={'可用' if evidence.get('has_video') else '缺失'}；"
        f"transcript={'可用' if evidence.get('has_transcript') else '缺失'}；"
        f"keyframes={'可用' if evidence.get('has_keyframes') else '缺失'}；"
        f"scenes={'可用' if evidence.get('has_scenes') else '缺失'}"
    )
    tags = "、".join(record.tags) if record.tags else "未提取到显式标签"
    text_coordinate = transcript_coordinate(srt_path, opening)
    frame_coordinate = visual_coordinate(evidence)
    return f"""# 姜胡说 2.2 NAS 全量学习卡：{title}

学习卡契约：{CONTRACT_ID}
source_id：{item['source_id']}
原内容链接：{record.url}
账号：{ACCOUNT_NAME}
平台：抖音
主方向：{direction}
学习批次：{batch_id}
状态：candidate_learned

## 1. 证据边界

- 主证据：NAS 原视频、完整逐字稿、场景切分和抽帧。
- 辅助证据：SQLite 发布标题、正文、标签和粗扫分类；评论正文不参与学习。
- 证据状态：{evidence_status}。
- 证据限制：{gap}。
- 文本证据坐标：{text_coordinate}。
- 视觉证据坐标：{frame_coordinate}；仅用于回查媒体表现，不据此猜测品牌、商品或购买利益。

## 2. 为什么值得学习

- 本条来自 NAS 598 条完整计划，是此前未进入 127 张正式卡范围的扩展样本。
- 学习价值：用独立内容检查既有方法是否稳定，并补充反例、边界和长尾主题。
- 本条承诺：{title}
- 独立证据路线：开场“{first_sentence(opening, 70)}”→前段“{first_sentence(early, 70)}”→中段“{first_sentence(middle, 70)}”→后段“{first_sentence(late, 70)}”。

## 3. 多维分类与商业隔离

- 内容形态：知识/评论
- 主方向：{direction}
- 商业属性：{classification['label']}
- 分类依据：{classification['basis']}主方向由粗扫、发布标题、正文与逐字稿共同建立候选路由。
- 隔离判断：{classification['isolation']}

## 4. 核心观点

- 发布层明确观点：{title}
- 正文层展开：{body}
- 逐字稿前段证据：{early}
- 逐字稿中段证据：{middle}
- 逐字稿后段证据：{late}

## 5. 内容结构

- 黄金3秒：{opening}
- 观点提出：{title}
- 证据或案例：{early}
- 推演：{middle}；{late}
- 收尾：{ending}

## 6. 发布内容层学习

- 标题：{title}
- 正文或文案：{body}
- 话题或标签：{tags}
- 协同判断：标题给出承诺，正文与逐字稿提供解释，标签只限定主题，不单独触发方法。

## 7. 视频/图文表现层学习

- 媒体类型：视频。
- 分析状态：{evidence_status}。
- 可回查坐标：{frame_coordinate}。
- 表现学习：开头直接给出内容承诺，中段用口播证据推进，结尾按逐字稿实际内容收束；缺失的镜头信息不补造。

## 8. 金句与表达素材

- 原文金句：{opening}
- 提炼表达（非原话）：{first_sentence(body, 110)}
- 可复用句式：先提出“{first_sentence(title, 60)}”，再给出来源证据和可执行判断。

## 9. 可复用选题与案例

- 可复用选题：{topic}。
- 可复用案例：`douyin:{item['source_id']}` 通过《{first_sentence(title, 75)}》承载该问题。
- 复用边界：只复用问题—证据—判断结构，不复制来源事实、身份和原句。

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。

### R - 原始证据

{opening}；{early}；{middle}；{late}

### I - 初步解释

{method}

### A1 - 本条案例

本条以《{title}》提出问题，先用“{first_sentence(early, 90)}”建立语境，再用“{first_sentence(middle, 90)}”和“{first_sentence(late, 90)}”推进。

### A2 - 未来触发场景

- 触发机制：新任务需要复用“{method}”的核心因果，并能提供新的来源证据时才考虑本候选。
- 适用关系：《{first_sentence(title, 45)}》中的人物关系只作为证据；换关系后仍能验证“{first_sentence(body, 70)}”才能迁移。
- 可迁移场景：来源场景只作为 A1；更换场景后仍能复现“{method}”的承诺—证据—判断链时才能迁移。
- 不触发条件：只命中{direction}、人物、场景或道具词，但无法保留《{first_sentence(title, 45)}》的核心因果时不得调用。

### E - 初步执行步骤

1. 用一句话提出《{first_sentence(title, 65)}》对应的明确问题。
2. 用前段“{first_sentence(early, 70)}”确认问题起点，不用标题代替论证。
3. 对照中段“{first_sentence(middle, 70)}”与后段“{first_sentence(late, 70)}”，写出证据支持和不支持的部分。
4. 回查《{first_sentence(title, 55)}》的商业属性、反例和证据缺口，不把单例写成稳定规律。

### B - 边界与反例

- {gap}。
- 单卡与阶段 1 观察不可直接调用，必须进入跨卡聚合、三重验证和压力测试。

## 11. 可复用模板

```text
问题：{first_sentence(title, 70)}
证据：替换为目标任务中的真实案例、逐字稿或可验证结果。
判断：说明证据支持什么、不支持什么。
行动：给出一个可观察的下一步，并写明停止条件。
```

## 12. 证据缺口与候选判断

- 证据缺口：{gap}。
- 卡片判断：保留为 NAS 全量候选学习卡，参与五视角观察和反例筛查。
- 跨卡状态：待验证；不恢复正式知识，不直接用于内容生产。
"""


def source_id_from_path(path: str) -> str:
    match = re.search(r"/(?:\d+_)?(\d{10,})_", f"/{path}")
    if not match:
        raise ValueError(f"cannot parse source_id: {path}")
    return match.group(1)


def direction_from_path(path: str) -> str:
    parts = Path(path).parts
    try:
        index = parts.index("directions")
    except ValueError as exc:
        raise ValueError(f"cannot parse direction: {path}") from exc
    return parts[index + 1]


def relearning_sequence(root: Path) -> list[dict[str, str]]:
    manifest = read_json(root / DOWNGRADE_MANIFEST)
    grouped: dict[str, list[dict[str, str]]] = {}
    for entry in manifest.get("entries", []):
        backup = str(entry["backup"])
        direction = direction_from_path(backup)
        grouped.setdefault(direction, []).append(
            {
                "source_id": source_id_from_path(backup),
                "direction": direction,
                "legacy_candidate_path": backup,
            }
        )
    for values in grouped.values():
        values.sort(key=lambda item: item["legacy_candidate_path"])
    sequence: list[dict[str, str]] = []
    directions = sorted(grouped)
    for offset in range(max(len(values) for values in grouped.values())):
        for direction in directions:
            values = grouped[direction]
            if offset < len(values):
                sequence.append(values[offset])
    return sequence


def batch_items(root: Path, batch_number: int, batch_size: int) -> list[dict[str, str]]:
    start = (batch_number - 1) * batch_size
    return relearning_sequence(root)[start : start + batch_size]


def full_relearning_sequence(root: Path) -> list[dict[str, Any]]:
    priority = relearning_sequence(root)
    priority_ids = {item["source_id"] for item in priority}
    rough_rows = read_jsonl_tolerant(root / ROUGH_INVENTORY)
    rough_by_id = {str(item.get("source_id") or ""): item for item in rough_rows if item.get("source_id")}
    records, _, _, _ = load_unique_records_detailed(root)
    account_records = [
        record
        for record in records
        if ACCOUNT_NAME in {record.account_name, record.author_name} and record.platform == "douyin" and record.source_id
    ]
    plan_ids = sorted({record.source_id for record in account_records})
    if len(plan_ids) != 598:
        raise ValueError(f"database Jianghushuo scope mismatch: {len(plan_ids)}/598")
    by_id = records_by_source_id(records)
    expansion: list[dict[str, Any]] = []
    for source_id in plan_ids:
        if source_id in priority_ids:
            continue
        row = rough_by_id.get(source_id, {})
        record = by_id.get(source_id)
        detected = detect_directions(record) if record is not None else []
        direction = str(row.get("primary_direction") or (detected[0] if detected else "待复核"))
        expansion.append(
            {
                "source_id": source_id,
                "direction": direction,
                "legacy_candidate_path": "",
                "topic_summary": str(row.get("topic_summary") or (record.title if record is not None else "")),
                "needs_review": bool(row.get("needs_review")) or not bool(row),
                "review_reason": str(row.get("review_reason") or ("rough_inventory_record_unavailable" if not row else "")),
                "material_status": str(row.get("material_status") or "nas_indexed"),
            }
        )
    if len(priority) + len(expansion) != 598:
        raise ValueError(f"full relearning scope mismatch: {len(priority)}+{len(expansion)}")
    return [*priority, *expansion]


def full_batch_items(root: Path, batch_number: int, batch_size: int) -> list[dict[str, Any]]:
    start = (batch_number - 1) * batch_size
    return full_relearning_sequence(root)[start : start + batch_size]


def evidence_ready_sequence(root: Path, nas_root: Path | None = None) -> list[dict[str, Any]]:
    return [
        item
        for item in full_relearning_sequence(root)
        if evidence_ready(str(item["source_id"]), nas_root)
    ]


def evidence_ready_batch_items(
    root: Path, batch_number: int, batch_size: int, nas_root: Path | None = None
) -> list[dict[str, Any]]:
    start = (batch_number - 1) * batch_size
    return evidence_ready_sequence(root, nas_root)[start : start + batch_size]


def candidate_records(record: Any, item: dict[str, str], batch_id: str, evidence: dict[str, Any], legacy_text: str) -> dict[str, dict[str, Any]]:
    source_id = item["source_id"]
    detected = detect_directions(record)
    direction = item["direction"] or (detected[0] if detected else "待复核")
    title = first_sentence(record.title, 80) or source_id
    sections = parse_numbered_sections(legacy_text)[0]
    topic = first_legacy_line(sections.get("可复用案例", ""), candidate_topic_angle(direction, record))
    structure = first_legacy_line(sections.get("可复用方法论", ""), reusable_template(direction, record))
    hook = legacy_field(sections.get("内容结构", ""), "黄金 3 秒钩子", golden_3s_hook(record))
    positioning = first_legacy_line(sections.get("为什么值得学习", ""), f"本条从{direction}切入普通人的具体问题")
    expression = first_legacy_line(sections.get("表达素材与金句提炼", ""), hook)
    boundary = first_legacy_line(sections.get("证据缺口/后续问题", ""), "单卡不能直接形成稳定方法")
    classification = content_classification(record)
    transcript_state = "逐字稿可用" if evidence.get("has_transcript") else "逐字稿缺失"
    frame_state = "抽帧可用" if evidence.get("has_keyframes") else "抽帧缺失"
    shared = {
        "source_refs": [source_id],
        "batch_id": batch_id,
        "status": "candidate_observation",
        "callable": False,
    }
    return {
        "positioning": {
            "id": f"jh-{batch_id}-{source_id}-positioning",
            "title": f"从{direction}任务切入普通人的可执行问题",
            "type": "positioning",
            "summary": f"《{title}》的定位观察：{positioning}；目前只是一条内容证据。",
            "tags": ["定位观察", direction, "待跨卡验证"],
            **shared,
        },
        "topics": {
            "id": f"jh-{batch_id}-{source_id}-topics",
            "title": f"用具体问题承载{direction}主题的选题观察",
            "type": "topics",
            "summary": f"本条候选选题观察为“{topic}”；需要后续检查是否在不同内容和场景中重复成立。",
            "tags": ["选题观察", direction, "问题化"],
            **shared,
        },
        "structures": {
            "id": f"jh-{batch_id}-{source_id}-structures",
            "title": f"围绕{direction}组织观点证据与行动的结构观察",
            "type": "structures",
            "summary": f"本条暂按“{structure}”描述内容推进机制；来源人物、场景和题材词不能单独触发复用。",
            "tags": ["结构观察", direction, "机制候选"],
            **shared,
        },
        "expression": {
            "id": f"jh-{batch_id}-{source_id}-expression",
            "title": f"先给明确承诺再展开{direction}论证的表达观察",
            "type": "expression",
            "summary": f"本条表达观察为“{expression}”，开场承诺为“{hook}”；原话、停顿和论证密度仍需复核。",
            "tags": ["表达观察", "开场承诺", direction],
            **shared,
        },
        "counterexamples": {
            "id": f"jh-{batch_id}-{source_id}-counterexamples",
            "title": f"{direction}单卡不能直接晋升稳定方法的证据边界",
            "type": "counterexamples",
            "summary": (
                f"《{title}》当前边界为“{boundary}”；证据状态为{transcript_state}、{frame_state}；"
                f"商业分轨为{classification['label']}，跨卡重复性尚未验证。"
            ),
            "tags": ["反例边界", "证据缺口", classification["id"]],
            **shared,
        },
    }


def nas_candidate_records(record: Any, item: dict[str, Any], batch_id: str, evidence: dict[str, Any], srt_path: Path) -> dict[str, dict[str, Any]]:
    source_id = str(item["source_id"])
    direction = str(item.get("direction") or "待复核")
    lines = transcript_lines(srt_path)
    opening = transcript_excerpt_at(lines, 0.0)
    title = evidence_title(record.title, source_id, opening)
    early = transcript_excerpt_at(lines, 0.25)
    middle = transcript_excerpt_at(lines, 0.5)
    late = transcript_excerpt_at(lines, 0.75)
    body = evidence_body(record.body, title, middle)
    classification = content_classification(record)
    topic = f"把《{first_sentence(title, 55)}》中的{direction}问题换对象验证：{first_sentence(early, 85)}"
    method = f"以《{first_sentence(title, 50)}》提出承诺，用“{first_sentence(early, 65)}”建立问题，以“{first_sentence(middle, 65)}”推进，再用“{first_sentence(late, 65)}”形成判断。"
    gaps = []
    if item.get("needs_review"):
        gaps.append(f"粗扫分类待复核：{review_reason_text(item.get('review_reason'))}")
    if not evidence.get("has_keyframes"):
        gaps.append("抽帧缺失")
    if not evidence.get("has_scenes"):
        gaps.append("场景切分缺失")
    gap = "；".join(gaps) or f"《{first_sentence(title, 55)}》的跨卡稳定性待复核；商业分轨为{classification['label']}"
    shared = {"source_refs": [source_id], "batch_id": batch_id, "status": "candidate_observation", "callable": False}
    return {
        "positioning": {
            "id": f"jh-{batch_id}-{source_id}-positioning",
            "title": f"《{first_sentence(title, 35)}》的受众承诺观察",
            "type": "positioning",
            "summary": f"本条以《{title}》向{direction}受众提出承诺，并在前段用“{first_sentence(early, 90)}”限定问题；是否属于稳定账号定位仍需跨卡检查。",
            "tags": ["定位观察", direction, "NAS全量"],
            **shared,
        },
        "topics": {
            "id": f"jh-{batch_id}-{source_id}-topics",
            "title": f"《{first_sentence(title, 35)}》的选题母题观察",
            "type": "topics",
            "summary": f"候选选题为“{topic}”，中段证据是“{first_sentence(middle, 90)}”；需检查能否换对象与场景后仍成立。",
            "tags": ["选题观察", direction, "长尾样本"],
            **shared,
        },
        "structures": {
            "id": f"jh-{batch_id}-{source_id}-structures",
            "title": f"《{first_sentence(title, 35)}》的承诺证据结构观察",
            "type": "structures",
            "summary": f"本条结构候选为“{method}”；前中后证据不能互相替代。",
            "tags": ["结构观察", direction, "证据推进"],
            **shared,
        },
        "expression": {
            "id": f"jh-{batch_id}-{source_id}-expression",
            "title": f"《{first_sentence(title, 35)}》的原声开场观察",
            "type": "expression",
            "summary": f"原声开场为“{opening}”，后段转向“{first_sentence(late, 90)}”；需结合抽帧判断停顿、强调与口语密度。",
            "tags": ["表达观察", direction, "NAS原声"],
            **shared,
        },
        "counterexamples": {
            "id": f"jh-{batch_id}-{source_id}-counterexamples",
            "title": f"《{first_sentence(title, 35)}》的证据与分类边界",
            "type": "counterexamples",
            "summary": f"本条边界为“{gap}”；后段证据“{first_sentence(late, 90)}”仅属于本条，不能直接证明稳定方法或账号独特性。",
            "tags": ["反例边界", direction, "证据门", classification["id"]],
            **shared,
        },
    }
def sync_workflow_candidates(root: Path) -> None:
    workflow = root / WORKFLOW_ROOT
    for lens in LENSES:
        records: list[dict[str, Any]] = []
        for path in sorted((workflow / "batches").glob(f"batch_*/candidates/{lens}.jsonl")):
            records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        write_jsonl(workflow / "candidates" / f"{lens}.jsonl", records)


def run_batch(
    root: Path,
    nas_root: Path,
    batch_number: int,
    batch_size: int,
    force: bool = False,
    render_only: bool = False,
    full_scope: bool = False,
    evidence_ready_scope: bool = False,
    scope_sequence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    batch_id = f"batch_{batch_number:02d}"
    output = root / WORKFLOW_ROOT / "batches" / batch_id
    if (output / "audit.json").exists() and not force:
        raise FileExistsError(f"batch already exists: {batch_id}")
    if output.exists() and force:
        shutil.rmtree(output)
    if scope_sequence is not None:
        start = (batch_number - 1) * batch_size
        selected = scope_sequence[start : start + batch_size]
    elif full_scope:
        selected = full_batch_items(root, batch_number, batch_size)
    elif evidence_ready_scope:
        selected = evidence_ready_batch_items(root, batch_number, batch_size, nas_root)
    else:
        selected = batch_items(root, batch_number, batch_size)
    if not selected:
        raise ValueError(f"empty batch: {batch_id}")

    records, raw_counts, dedupe_stats, failed_files = load_unique_records_detailed(root)
    by_id = records_by_source_id(records)
    missing_records = [item["source_id"] for item in selected if item["source_id"] not in by_id]
    if missing_records:
        raise ValueError(f"records missing from current data source: {','.join(missing_records)}")

    source_ids = {item["source_id"] for item in selected}
    if render_only:
        learning_result: dict[str, Any] = {"render_only": True, "requested": len(source_ids), "missing": []}
    else:
        learning_result = run_selected_deep_learning(
            root,
            source_ids=source_ids,
            analyze_video=False,
            force=True,
            artifacts_dir=nas_root.resolve(),
            artifact_layout="account",
            account_name=ACCOUNT_NAME,
            mirror_nas_state=False,
        )
        if learning_result.get("missing"):
            raise RuntimeError(f"learning records missing: {learning_result['missing']}")

    card_errors: dict[str, list[str]] = {}
    candidates: dict[str, list[dict[str, Any]]] = {lens: [] for lens in LENSES}
    manifest_items: list[dict[str, Any]] = []
    for item in selected:
        source_id = item["source_id"]
        source_card = selected_deep_cards_dir(root) / f"douyin_{source_id}.md"
        evidence = evidence_status(source_id, nas_root)
        artifact_dir = Path(str(evidence["artifact_dir"]))
        srt_path = transcript_path(source_id, nas_root)
        target_card = output / "cards" / f"douyin_{source_id}.md"
        target_card.parent.mkdir(parents=True, exist_ok=True)
        legacy_path_value = str(item.get("legacy_candidate_path") or "")
        if legacy_path_value:
            legacy_text = (root / legacy_path_value).read_text(encoding="utf-8")
            card_text = render_upgraded_card(
                by_id[source_id], item, batch_id, evidence, legacy_text, srt_path
            )
            per_lens = candidate_records(by_id[source_id], item, batch_id, evidence, legacy_text)
        else:
            card_text = render_nas_only_card(by_id[source_id], item, batch_id, evidence, srt_path)
            per_lens = nas_candidate_records(by_id[source_id], item, batch_id, evidence, srt_path)
        target_card.write_text(card_text, encoding="utf-8")
        validation = validate_card_text(target_card.read_text(encoding="utf-8"))
        if not validation.valid:
            card_errors[source_id] = list(validation.errors)
        for lens in LENSES:
            candidates[lens].append(per_lens[lens])
        manifest_items.append(
            {
                **item,
                "card_path": target_card.relative_to(root).as_posix(),
                "card_contract": CONTRACT_ID,
                "card_valid": validation.valid,
                "nas_evidence": evidence,
            }
        )

    for lens in LENSES:
        write_jsonl(output / "candidates" / f"{lens}.jsonl", candidates[lens])
    write_json(output / "batch_manifest.json", {"batch_id": batch_id, "items": manifest_items})
    audit = {
        "ok": not card_errors and len(manifest_items) == len(selected),
        "batch_id": batch_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "expected_count": len(selected),
        "card_count": len(manifest_items),
        "unified_card_passed_count": sum(1 for item in manifest_items if item["card_valid"]),
        "candidate_counts": {lens: len(values) for lens, values in candidates.items()},
        "card_errors": card_errors,
        "formal_write_allowed": False,
        "stage1_scope_status": "partial_batch_in_progress",
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
    }
    write_json(output / "audit.json", audit)
    sync_workflow_candidates(root)

    if scope_sequence is not None:
        sequence = scope_sequence
    elif full_scope:
        sequence = full_relearning_sequence(root)
    elif evidence_ready_scope:
        sequence = evidence_ready_sequence(root, nas_root)
    else:
        sequence = relearning_sequence(root)
    sequence_ids = {str(item["source_id"]) for item in sequence}
    existing_ids = {
        path.stem.removeprefix("douyin_")
        for path in (root / WORKFLOW_ROOT / "batches").glob("batch_*/cards/douyin_*.md")
    }
    completed_cards = len(sequence_ids & existing_ids)
    status = {
        "workflow_id": WORKFLOW_ID,
        "status": "stage1_evidence_ready_in_progress" if evidence_ready_scope else ("stage1_full_scope_in_progress" if full_scope else "stage1_in_progress"),
        "completed_cards": completed_cards,
        "priority_relearning_scope": len(relearning_sequence(root)),
        "full_nas_plan_scope": 598,
        "latest_batch": batch_id,
        "latest_batch_ok": audit["ok"],
        "formal_write_allowed": False,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(root / WORKFLOW_ROOT / "LEARNING_STATUS.json", status)
    return {"ok": audit["ok"], "batch": audit, "status": status, "learning_result": learning_result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Jianghushuo v2.2 NAS relearning batch.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-root", default=str(DEFAULT_NAS_ROOT))
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--from-batch", type=int, default=0)
    parser.add_argument("--to-batch", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--scope", choices=["priority", "evidence_ready", "full"], default="priority")
    args = parser.parse_args()
    if args.from_batch:
        start = max(args.from_batch, 1)
        requested_end = max(args.to_batch or start, start)
        scope_root = Path(args.root).resolve()
        batch_size = max(args.batch_size, 1)
        if args.scope == "full":
            scope_items = full_relearning_sequence(scope_root)
        elif args.scope == "evidence_ready":
            scope_items = evidence_ready_sequence(scope_root, Path(args.nas_root))
        else:
            scope_items = relearning_sequence(scope_root)
        scope_count = len(scope_items)
        final_batch = (scope_count + batch_size - 1) // batch_size
        end = min(requested_end, final_batch)
        if args.force:
            batches_root = scope_root / WORKFLOW_ROOT / "batches"
            for path in batches_root.glob("batch_*"):
                match = re.fullmatch(r"batch_(\d+)", path.name)
                if match and int(match.group(1)) > final_batch:
                    shutil.rmtree(path)
        results: list[dict[str, Any]] = []
        for batch_number in range(start, end + 1):
            batch_result = run_batch(
                Path(args.root),
                Path(args.nas_root),
                batch_number,
                batch_size,
                force=args.force,
                render_only=args.render_only,
                full_scope=args.scope == "full",
                evidence_ready_scope=args.scope == "evidence_ready",
                scope_sequence=scope_items,
            )
            results.append(
                {
                    "batch_id": batch_result["batch"]["batch_id"],
                    "ok": batch_result["ok"],
                    "card_count": batch_result["batch"]["card_count"],
                    "candidate_counts": batch_result["batch"]["candidate_counts"],
                }
            )
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
        result = {
            "ok": all(item["ok"] for item in results),
            "batch_range": [start, end],
            "batches": results,
            "status": read_json(Path(args.root).resolve() / WORKFLOW_ROOT / "LEARNING_STATUS.json"),
        }
    else:
        result = run_batch(
            Path(args.root),
            Path(args.nas_root),
            max(args.batch, 1),
            max(args.batch_size, 1),
            force=args.force,
            render_only=args.render_only,
            full_scope=args.scope == "full",
            evidence_ready_scope=args.scope == "evidence_ready",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
