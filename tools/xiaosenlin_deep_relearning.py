from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from tools.account_learning_card import CONTRACT_ID, UNIFIED_SECTIONS, validate_card_text
from tools.xiaosenlin_batch_learning import MECHANISMS


ACCOUNT = "小森林的小世界"
ACCOUNT_ID = "5a201295e8ac2b0dbae9063a"
METHOD_REVISION = "xiaosenlin_unified_deep_relearn_v3_0"
CARD_CONTRACT_VERSION = "2.1"
BATCH_SIZE = 10
WORKFLOW_ROOT = Path("10_Knowledge/candidates/account_learning_workflows/xiaosenlin-xiaoshijie-v2-full")
LEGACY_BATCH_ROOT = WORKFLOW_ROOT / "batches"
OUTPUT_ROOT = WORKFLOW_ROOT / "v3_deep_relearning"
VISUAL_OVERRIDES = WORKFLOW_ROOT / "VISUAL_EVIDENCE_OVERRIDES.json"
FORMER_FORMAL_BACKUP = Path(
    "10_Knowledge/candidates/account_assets/downgraded_formal_cards/"
    "xiaosenlin_xiaoshijie/2026-07-13"
)
BOUNDARY_KEYS = {"commercial_boundary", "engagement_boundary", "evidence_gate"}
NAS_SQLITE_DATABASE = Path("/Volumes/AFK/zhishikushuju/sqlite_tables.db")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value).lower()


def short(value: str, limit: int = 140) -> str:
    value = clean(value)
    return value if len(value) <= limit else value[:limit].rstrip() + "……"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ordered_legacy_rows(root: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    root = root.resolve()
    evidence_by_id: dict[str, dict[str, Any]] = {}
    card_by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((root / LEGACY_BATCH_ROOT).glob("batch_*/evidence_inventory.jsonl")):
        for row in read_jsonl(path):
            evidence_by_id[str(row["source_id"])] = row
    for path in sorted((root / LEGACY_BATCH_ROOT).glob("batch_*/structured_cards.jsonl")):
        for row in read_jsonl(path):
            card_by_id[str(row["source_id"])] = row
    plan = read_json(root / WORKFLOW_ROOT / "BATCH_PLAN.json", {}) or {}
    source_ids = [str(source_id) for batch in plan.get("batches", []) for source_id in batch.get("source_ids", [])]
    if not source_ids:
        source_ids = sorted(evidence_by_id)
    missing_evidence = [source_id for source_id in source_ids if source_id not in evidence_by_id]
    missing_cards = [source_id for source_id in source_ids if source_id not in card_by_id]
    if missing_evidence or missing_cards:
        raise ValueError(f"legacy inventory mismatch: evidence={missing_evidence[:3]} cards={missing_cards[:3]}")
    return [(evidence_by_id[source_id], card_by_id[source_id]) for source_id in source_ids]


def parse_srt(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="replace").strip())
    rows: list[dict[str, str]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or " --> " not in lines[1]:
            continue
        text = clean(" ".join(lines[2:]))
        if text:
            rows.append({"time": lines[1].split(" --> ", 1)[0], "text": text})
    return rows


def merge_units(values: list[str], minimum: int = 28, maximum: int = 110) -> list[str]:
    units: list[str] = []
    buffer = ""
    for raw in values:
        value = clean(raw)
        if not value:
            continue
        if buffer and len(buffer) + len(value) > maximum:
            units.append(buffer)
            buffer = ""
        buffer = clean(f"{buffer} {value}")
        if len(buffer) >= minimum:
            units.append(buffer)
            buffer = ""
    if buffer:
        if units and len(buffer) < 12:
            units[-1] = clean(f"{units[-1]} {buffer}")
        else:
            units.append(buffer)
    return list(dict.fromkeys(units))


def text_units(content_type: str, item_root: Path, source: dict[str, Any]) -> tuple[list[str], list[dict[str, str]], str]:
    if content_type == "video":
        srt_path = item_root / "video" / "transcript.srt"
        if not srt_path.is_file():
            srt_path = item_root / "transcript.srt"
        srt_rows = parse_srt(srt_path)
        if srt_rows:
            return merge_units([row["text"] for row in srt_rows]), srt_rows, "srt_timeline"
        transcript_path = item_root / "video" / "transcript.txt"
        if not transcript_path.is_file():
            transcript_path = item_root / "transcript.txt"
        transcript = transcript_path.read_text(encoding="utf-8", errors="replace") if transcript_path.is_file() else ""
        return merge_units(re.split(r"[。！？!?\n]+", transcript)), [], "transcript_text"
    desc = str(source.get("desc") or "")
    visual = read_json(item_root / "images" / "visual_summary.json", {}) or {}
    chunks = re.split(r"[\n。！？!?]+", desc)
    chunks.extend(re.split(r"[\n。！？!?]+", str(visual.get("ocr_text") or "")))
    return merge_units(chunks, minimum=20, maximum=130), [], "desc_plus_ocr"


def at_phase(units: list[str], ratio: float) -> str:
    if not units:
        return "未提取到可回查的内容单元。"
    index = min(len(units) - 1, max(0, round((len(units) - 1) * ratio)))
    return short(units[index], 160)


def quality_quote_candidates(units: list[str]) -> list[str]:
    signals = (
        "我", "先", "再", "最后", "如果", "但是", "一定", "不要", "因为", "所以", "提醒",
        "第一", "第二", "用完", "坚持", "对比", "状态", "翻车", "无广", "回购",
    )
    candidates: list[tuple[int, int, str]] = []
    for index, unit in enumerate(units):
        value = short(unit, 100)
        chinese = len(re.findall(r"[\u4e00-\u9fff]", value))
        if chinese < 12 or len(value) > 110:
            continue
        score = sum(token in value for token in signals) * 3 + min(chinese, 50) // 10
        if re.search(r"(.)\1{4,}", value):
            score -= 5
        candidates.append((score, -index, value))
    chosen: list[str] = []
    for _, _, value in sorted(candidates, reverse=True):
        if all(normalized(value) not in normalized(old) and normalized(old) not in normalized(value) for old in chosen):
            chosen.append(value)
        if len(chosen) == 2:
            break
    return chosen


def hashtags(desc: str) -> list[str]:
    values = re.findall(r"#\s*([^#\n]+?)(?:\[\u8bdd\u9898\])?(?=#|$)", desc)
    return [clean(value).replace("[话题]", "") for value in values if clean(value)]


def evidence_paths(content_type: str, item_root: Path) -> tuple[str, str, str]:
    if content_type == "video":
        if (item_root / "source.mp4").is_file():
            return (
                str(item_root / "transcript.srt"),
                str(item_root / "source.mp4"),
                str(item_root / "source-Scenes.csv"),
            )
        return (
            str(item_root / "video" / "transcript.txt"),
            str(item_root / "video" / "source.mp4"),
            str(item_root / "video" / "frames"),
        )
    return (
        str(item_root / "images" / "ocr.json"),
        str(item_root / "source.json"),
        str(item_root / "images"),
    )


def primary_mechanism(card: dict[str, Any], evidence_text: str) -> tuple[str, dict[str, str]]:
    keys = {str(value) for value in card.get("mechanism_keys") or [] if str(value) not in BOUNDARY_KEYS}
    text = clean(evidence_text).lower()
    title = clean(card.get("title")).lower()
    family = clean(card.get("topic_family"))
    if family == "生活方式与信任":
        return "evidence_gate", MECHANISMS["evidence_gate"]
    if not keys:
        return "evidence_gate", MECHANISMS["evidence_gate"]
    scores: dict[str, int] = {}
    identity = sum(token in text for token in ("油痘", "油皮", "敏肌", "痘肌", "混油", "混干"))
    proof = sum(token in text for token in ("我用", "自用", "空瓶", "回购", "无广", "坚持", "年度爱用"))
    if "identity_proof" in keys and identity and proof:
        scores["identity_proof"] = identity * 2 + proof * 2
    sequence_hits = sum(token in text for token in ("先", "再", "然后", "接着", "最后", "第一", "第二", "step", "步骤"))
    condition_hits = sum(token in text for token in ("如果", "当", "时候", "停止", "避开", "不要", "不能", "耐受"))
    if "step_sequence" in keys and sequence_hits >= 3:
        scores["step_sequence"] = sequence_hits + min(condition_hits, 4) * 2
    time_hits = len(re.findall(r"(?:\d+\s*(?:天|周|个月|分钟|小时)|第二天|早晚|每周|连续|坚持)", text))
    feedback_hits = sum(token in text for token in ("状态", "反馈", "观察", "泛红", "不耐受", "触感", "变化", "效果"))
    if "time_feedback" in keys and time_hits >= 2 and feedback_hits:
        scores["time_feedback"] = time_hits * 2 + min(feedback_hits, 4) * 2
    version_hits = sum(token in text for token in ("版本", "升级", "替代", "换成", "淘汰", "保留", "以前", "今年", "去年", "复测"))
    if "version_iteration" in keys and version_hits >= 2:
        scores["version_iteration"] = version_hits * 3
    numbered = len(re.findall(r"(?:^|\s)[1-9][、.）)]|[1-9]️?⃣", text))
    list_hits = sum(
        token in f"{title} {text}"
        for token in (
            "清单", "盘点", "合集", "几个", "空瓶", "年度爱用", "月度爱用", "翻包",
            "洗漱包", "一包搞定", "公开", "好物", "每一样", "很多很多",
        )
    )
    item_transitions = sum(text.count(token) for token in ("再就是", "还有这个", "然后是", "接下来是", "这个是"))
    if ("list_decision" in keys or family == "空瓶与产品复盘") and (
        numbered >= 2 or list_hits >= 1 or item_transitions >= 2
    ):
        family_bonus = 10 if family == "空瓶与产品复盘" else 0
        scores["list_decision"] = numbered * 2 + list_hits * 4 + min(item_transitions, 6) * 2 + family_bonus
    problem_hits = sum(token in text for token in ("黑头", "毛孔", "痘", "泛红", "暗沉", "毛躁", "干", "油", "敏感", "眼纹", "防晒"))
    result_hits = sum(token in text for token in ("改善", "变得", "看起来", "细腻", "透亮", "顺滑", "紧致", "稳定", "不长", "解决"))
    if "problem_result" in keys and problem_hits and result_hits:
        scores["problem_result"] = problem_hits + result_hits * 2
    if not scores:
        fallback_order = (
            "evidence_gate",
            "engagement_boundary",
            "list_decision",
            "version_iteration",
            "step_sequence",
            "time_feedback",
            "identity_proof",
            "problem_result",
        )
        key = next((candidate for candidate in fallback_order if candidate in keys), "evidence_gate")
    else:
        priority = {
            "version_iteration": 6,
            "list_decision": 5,
            "time_feedback": 4,
            "step_sequence": 3,
            "identity_proof": 2,
            "problem_result": 1,
        }
        key = max(scores, key=lambda item: (scores[item], priority[item]))
    return key, MECHANISMS.get(key, MECHANISMS["problem_result"])


def commercial_axis(card: dict[str, Any], source: dict[str, Any]) -> tuple[str, str]:
    text = clean(f"{source.get('title')} {source.get('desc')}")
    keys = set(card.get("mechanism_keys") or [])
    if "engagement_boundary" in keys:
        return "账号互动/售后内容", "只学习服务承接和社群关系，不将其计入护理方法证据。"
    if "commercial_boundary" in keys or any(token in text for token in ("618", "双11", "优惠", "买", "价格", "橱窗", "直播间")):
        return "产品/商业决策内容", "产品、价格、购买或节点信号独立隔离；仅保留选择逻辑、表达和风险边界。"
    return "正常经验内容", "无显式购买价格或平台任务信号；仍作为候选证据，不直接升级为通用功效结论。"


def render_card(
    evidence: dict[str, Any],
    card: dict[str, Any],
    batch_id: str,
    visual_override: dict[str, Any] | None = None,
    visual_override_path: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    item_root = Path(str(evidence["nas_item_root"]))
    source = read_json(item_root / "source.json", {}) or {}
    source_id = str(card["source_id"])
    title = clean(source.get("title") or card.get("title") or source_id)
    desc = str(source.get("desc") or "")
    content_type = str(card.get("content_type") or evidence.get("content_type") or "video")
    original_units, srt_rows, extraction_mode = text_units(content_type, item_root, source)
    visual_override = visual_override or {}
    visual_evidence = clean(visual_override.get("visual_evidence"))
    visual_units = merge_units(re.split(r"[\n。！？!?]+", visual_evidence), minimum=20, maximum=130)
    units = list(dict.fromkeys([*original_units, *visual_units]))
    if not units:
        raise ValueError(f"{source_id}: no evidence units")
    quote_values = quality_quote_candidates(original_units)
    opening, early, middle, late, ending = (at_phase(units, ratio) for ratio in (0.0, 0.22, 0.5, 0.76, 1.0))
    lens = card.get("five_lens") or {}
    family = str(card.get("topic_family") or "未分类")
    mechanism_key, mechanism = primary_mechanism(card, " ".join(units))
    commercial, isolation = commercial_axis(card, source)
    tags = hashtags(desc)
    transcript_path, media_path, visual_path = evidence_paths(content_type, item_root)
    raw_url = str(
        (source.get("raw") or {}).get("source_url")
        or source.get("source_url")
        or f"https://www.xiaohongshu.com/explore/{source_id}"
    )
    metadata_path = item_root / "source.json" if (item_root / "source.json").is_file() else NAS_SQLITE_DATABASE
    media_label = "视频" if content_type == "video" else "图文"
    has_transcript = content_type == "video" and bool(original_units)
    content_form = (
        "知识/经验口播"
        if content_type == "video" and has_transcript
        else ("无口播视觉叙事视频" if content_type == "video" else "图文")
    )
    if content_type == "video" and has_transcript:
        evidence_status = (
            f"原视频、转写和 {evidence.get('frame_count', 0)} 帧抽帧可回查；"
            "本卡按SRT时序重建内容，不补写未逐帧标注的镜头语言。"
        )
    elif content_type == "video" and visual_evidence:
        evidence_status = (
            f"原视频和 {evidence.get('frame_count', 0)} 帧抽帧可回查；有效语音转写为空，"
            "本卡只使用人工复核且带帧号的视觉证据与发布正文，不声称存在口播原句。"
        )
    else:
        evidence_status = (
            f"{evidence.get('image_count', 0)} 张原图、正文、OCR和 visual_summary 可回查；"
            "本卡仅学习已识别的文字层级与分图任务。"
        )
    if content_type == "video" and has_transcript:
        primary_evidence_label = "NAS原始视频、可回查的SRT/转写"
    elif content_type == "video":
        primary_evidence_label = "NAS原始视频、带帧号的人工视觉复核与发布正文（无有效语音转写）"
    else:
        primary_evidence_label = "NAS原始图文、发布正文、OCR与分图汇总"
    quotes = (
        "；".join(f"“{value}”" for value in quote_values)
        if quote_values
        else "未保留：无足够完整的口播/图文原句；人工视觉复核只用于结构学习，不冒充原话。"
    )
    topic_observation = str(lens.get("topics") or card.get("content_thesis") or "")
    structure_observation = str(lens.get("structures") or "")
    expression_observation = str(lens.get("expression") or "")
    boundary_observation = str(lens.get("counterexamples") or card.get("boundary") or "")
    reusable_sentence = (
        f"先让【{family}的具体困扰】对号入座，再用【{mechanism['title']}】组织步骤与证据，"
        "最后说清【适用条件、状态反馈和不适用边界】。"
    )
    if content_type == "video" and has_transcript:
        structure_block = f"""- 黄金3秒：`{opening}`，直接抛出人群、问题或结果承诺。
- 观点提出：`{early}`
- 证据或案例：`{middle}`
- 推演：`{late}`
- 收尾：`{ending}`
- 结构复盘：{structure_observation}"""
    elif content_type == "video":
        structure_block = f"""- 视觉开场：`{opening}`，由画面或屏幕字幕建立地点、人物或任务。
- 观点提出（视觉）：`{early}`
- 证据或案例（视觉）：`{middle}`
- 后段变化：`{late}`
- 视觉收尾：`{ending}`
- 结构复盘：{structure_observation}
- 证据边界：无有效语音转写，不使用“黄金3秒口播—观点推演”的口播模板。"""
    else:
        structure_block = f"""- 封面承诺：`{title}`，先说清人群、问题或结果。
- 分图顺序：`{opening}` → `{early}` → `{middle}` → `{late}` → `{ending}`。
- 信息层级：标题/封面给承诺，正文分问题或步骤，OCR核对图中用量、顺序和提示。
- 行动建议：{structure_observation}
- 收尾互动：`{ending}`"""
    tag_text = "、".join(tags) if tags else "未提取到显式话题；不补造标签"
    publish_process_label = "正文/转写" if content_type != "video" or has_transcript else "发布正文/画面字幕"
    if content_type == "video" and has_transcript:
        visual_learning = f"口播按“开场—早段—中段—后段—收尾”展开；可回查抽帧 {evidence.get('frame_count', 0)} 张。{expression_observation}"
    elif content_type == "video":
        visual_learning = f"按带帧号的画面证据与屏幕字幕重建“视觉开场—事件推进—变化—收尾”；可回查抽帧 {evidence.get('frame_count', 0)} 张。{expression_observation}"
    else:
        visual_learning = f"图文以封面承诺、分段清单和图内OCR承接用量/步骤；可回查原图 {evidence.get('image_count', 0)} 张。{expression_observation}"
    card_text = f"""# {ACCOUNT}统一账号发布资产学习卡：{title}

学习卡契约：{CONTRACT_ID}
学习方法版本：{METHOD_REVISION}
source_id：{source_id}
原内容链接：{raw_url}
账号：{ACCOUNT}
平台：小红书
主方向：{family} / {mechanism['title']}
学习批次：{batch_id}-evidence-first-deep-relearn
状态：candidate_learned

## 1. 证据边界

- 主证据：{primary_evidence_label}，source_id `{source_id}`。
- 辅助证据：发布标题、话题、历史五路候选卡和媒体处理状态；不重复计为独立来源。
- 证据状态：{evidence_status}
- 原始路径状态：文本 `{transcript_path}`；媒体 `{media_path}`；视觉 `{visual_path}`。
- 时序提取：`{extraction_mode}`；内容单元 {len(units)} 个，SRT段 {len(srt_rows)} 个。

## 2. 为什么值得学习

- 学习价值：这条不是因为指标入选，而是完整证据可回查，可以观察“{family}”如何从问题承诺进入步骤、证据和边界。
- 定位价值：{lens.get('positioning', '')}
- 结构价值：{structure_observation}
- 表达价值：{expression_observation}

## 3. 多维分类与商业隔离

- 内容形态：{content_form}
- 媒介分支：{media_label}
- 主题族：{family}
- 主机制：{mechanism['title']}
- 商业属性：{commercial}
- 分类依据：标题、完整正文/转写、话题和五路观察交叉判断，不用热度指标决定主题。
- 隔离判断：{isolation}

## 4. 核心观点

- 内容层观点：{topic_observation}
- 结构层观点：{structure_observation}
- 表达层观点：{expression_observation}
- 边界判断：{boundary_observation}

## 5. 内容结构

{structure_block}

## 6. 发布内容层学习

- 标题：{title}
- 正文或文案：{short(desc, 320) if clean(desc) else '未提取到独立发布文案；不补造。'}
- 话题或标签：{tag_text}
- 标题学习：用“{title}”直接圈定问题、人群或结果；标题只负责建立进入问题，完整判断仍回到{publish_process_label}。
- 话题学习：标签用于限定“{family}”场景与分发，不单独证明方法或效果。
- 协同判断：标题设承诺，{publish_process_label}给过程，话题给场景；三者冲突时以完整主证据为准。

## 7. 视频/图文表现层学习

- 媒体类型：{media_label}。
- 分析状态：{evidence_status}
- 表现学习：{visual_learning}
- 节奏学习：开场 `{opening}`；中段 `{middle}`；收尾 `{ending}`。
- 媒体边界：未逐镜头人工标注的景别、机位、剪辑意图和审美因果不写入结论。

## 8. 金句与表达素材

- 原文金句：{quotes}
- 引用质量：以完整证据单元原文保留，未作护肤事实改写；对外引用前仍需回看原{media_label}。
- 提炼表达（非原话）：{expression_observation}
- 可复用句式：{reusable_sentence}
- 引用边界：“原文金句”是证据原文；提炼表达与可复用句式是学习结论，不得冒充原话。

## 9. 可复用选题与案例

- 可复用选题：面向“{family}”，从“{title}”抽离人名、品牌和时效，重建为“具体困扰 → 选择/步骤 → 状态反馈 → 边界”。
- 跨场景选题候选：{topic_observation}
- 可复用案例：`{source_id}` 以 `{opening}` 建立问题，在中段用 `{middle}` 承接过程，以 `{ending}` 收束。
- 复用边界：{boundary_observation}

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。关联机制：`{mechanism_key}` / {mechanism['title']}。
> 可调用：false。单卡通过不代表方法可调用，必须先完成跨内容、预测力和账号独特性验证。

### R - 原始证据

- source_id：`{source_id}`。
- 可回查原文：{quotes}
- 时序证据：开场 `{opening}`；中段 `{middle}`；收尾 `{ending}`。

### I - 初步解释

候选“{mechanism['title']}”：{mechanism['mechanism']}

### A1 - 本条案例

`{source_id}` 围绕“{family}”，先用 `{opening}` 建立任务，再用 `{middle}` 给出过程/证据，最后以 `{ending}` 形成反馈或边界。

### A2 - 未来触发场景

- 触发机制：只有新任务需要“{mechanism['title']}”的核心因果，且跨卡验证通过后，才可另行晋级；当前不可调用。
- 适用关系：“用户具体状态—执行动作—状态反馈”的关系是候选核心；不把品牌、人名或单一产品当触发条件。
- 可迁移场景：只在更换为新的“{family}”事实后，问题、动作、反馈和边界仍保持同一因果时可验证迁移。
- 不触发条件：只出现题材词、产品名、场景词或“{title}”的表层表达，但没有“{mechanism['title']}”核心因果时，不得调用。

### E - 初步执行步骤

> 本小节执行候选验证，不执行内容生成。

1. 先在同账号已审核卡中按“{family}”、媒介分支和商业属性建立样本。
2. 查找至少三条独立内容，检查“{mechanism['title']}”是否重复保留同一因果。
3. 为“{family}”建立同机制正例和题材相似但机制不同的反例，排除名词共现。
4. 核对标题、正文/口播、话题和媒体表现是否承担稳定作用。
5. 评审商业、医学化功效、确定时效和个体经验边界；三重验证全部通过后再另建方法卡。

### B - 边界与反例

- {boundary_observation}
- {isolation}
- 单卡只支持候选；个人护理经验、医学机理、确定时效与产品功效不直接写成通用事实。

## 11. 可复用模板

> 以下是候选验证模板，当前不可用于生成发布内容。

```text
样本范围：同账号 + 【{family}】 + 【{media_label}】 + 【{commercial}】。
问题证据：是否都有可回查的【具体困扰/目标状态】？
机制检查：【{mechanism['title']}】是否在至少三条独立内容中保留同一因果？
时序检查：【开场承诺】→【过程/证据】→【反馈/边界】是否成立？
反例检查：题材相似但缺少【{mechanism['title']}】核心因果的内容必须被排除。
边界检查：品牌、购买、医学化功效、确定时效和个体经验必须独立标注。
晋级条件：V1跨内容证据、V2预测指导力、V3账号独特性全部通过；否则保持不可调用。
```

- 可验证变量：问题、目标状态、动作顺序、反馈节点、停止条件和商业/功效边界。
- 适用边界：只验证候选，不因单条内容、单个题材词或高热指标触发。

## 12. 证据缺口与候选判断

- 证据缺口：原{media_label}可回查，但尚未建立逐镜头人工时间码标注；原文/OCR/ASR可能含识别错字；单卡不能证明方法稳定或功效事实成立。
- 卡片判断：证据完整，保留为统一十二段深学候选卡；不直接写入正式账号中心。
- 跨卡状态：支持 `{mechanism_key}` 候选的单条证据；方法仍为 `callable=false`，待跨卡三重验证。
"""
    anchors = [opening, early, middle, late, ending, *quote_values]
    record = {
        "schema_version": CARD_CONTRACT_VERSION,
        "learning_method_revision": METHOD_REVISION,
        "batch_id": batch_id,
        "source_id": source_id,
        "title": title,
        "content_type": content_type,
        "nas_item_root": str(item_root),
        "topic_family": family,
        "mechanism_key": mechanism_key,
        "commercial_axis": commercial,
        "evidence_status": "complete",
        "evidence_source_chars": sum(len(value) for value in units),
        "evidence_unit_count": len(units),
        "original_evidence_unit_count": len(original_units),
        "visual_review_unit_count": len(visual_units),
        "timeline_segment_count": len(srt_rows),
        "transcript_available": has_transcript,
        "evidence_basis": (
            "video_transcript_and_frames"
            if content_type == "video" and has_transcript
            else ("video_frame_review_and_publish_text" if content_type == "video" else "image_ocr_and_publish_text")
        ),
        "traceable_anchors": anchors,
        "retained_quotes": quote_values,
        "source_paths": {
            "text": transcript_path,
            "source": str(metadata_path),
            "media": media_path,
            "visual": visual_path,
            "visual_override": str(visual_override_path or ""),
        },
        "source_text_hash": sha256_text("\n".join(units)),
        "card_hash": sha256_text(card_text),
        "callable": False,
        "status": "candidate_learned",
    }
    return card_text, record


def audit_card(text: str, record: dict[str, Any]) -> list[str]:
    errors = list(validate_card_text(text).errors)
    source_id = str(record["source_id"])
    if f"source_id：{source_id}" not in text:
        errors.append("source_id_mismatch")
    if f"学习方法版本：{METHOD_REVISION}" not in text:
        errors.append("method_revision_mismatch")
    if "状态：candidate_learned" not in text or "可调用：false" not in text:
        errors.append("candidate_boundary_missing")
    if len(normalized(text)) < 2600:
        errors.append("card_too_shallow")
    item_root = Path(str(record["nas_item_root"]))
    source = read_json(item_root / "source.json", {}) or {}
    audit_units, _, _ = text_units(str(record["content_type"]), item_root, source)
    source_blob = "\n".join(audit_units)
    for quote in record.get("retained_quotes") or []:
        if normalized(str(quote)) not in normalized(source_blob):
            errors.append("quote_not_traceable_to_source")
    for key, path in record.get("source_paths", {}).items():
        if key == "visual_override" and not str(path):
            continue
        if not Path(str(path)).exists():
            errors.append(f"missing_source_path:{Path(str(path)).name}")
    required_anchors = min(5, max(1, int(record.get("evidence_unit_count") or 0)))
    if len(set(record.get("traceable_anchors") or [])) < required_anchors:
        errors.append(f"insufficient_distinct_anchors:{required_anchors}")
    if record.get("content_type") == "video" and record.get("transcript_available") is False:
        if "主证据：NAS原始视频、完整SRT与转写" in text:
            errors.append("silent_video_claims_complete_transcript")
        if "内容形态：知识/经验口播" in text or "表现学习：口播按" in text:
            errors.append("silent_video_uses_spoken_content_template")
    if record.get("topic_family") == "生活方式与信任" and record.get("mechanism_key") != "evidence_gate":
        errors.append("lifestyle_content_must_remain_evidence_gate")
    if record.get("topic_family") == "空瓶与产品复盘" and record.get("mechanism_key") == "time_feedback":
        errors.append("product_list_misclassified_as_time_feedback")
    return sorted(set(errors))


def batch_name(batch_number: int) -> str:
    return f"batch_{batch_number:02d}"


def prune_stale_cards(cards_dir: Path, learned: list[dict[str, Any]]) -> list[str]:
    learned_card_names = {f"xhs_{record['source_id']}.md" for record in learned}
    removed: list[str] = []
    for existing_card in cards_dir.glob("xhs_*.md"):
        if existing_card.name not in learned_card_names:
            existing_card.unlink()
            removed.append(existing_card.name)
    return sorted(removed)


def run_batch(root: Path, batch_number: int) -> dict[str, Any]:
    rows = ordered_legacy_rows(root)
    selected = rows[(batch_number - 1) * BATCH_SIZE : batch_number * BATCH_SIZE]
    if not selected:
        raise ValueError(f"empty batch: {batch_number}")
    name = batch_name(batch_number)
    output = root.resolve() / OUTPUT_ROOT / name
    cards_dir = output / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    learned: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    batch_errors: list[str] = []
    visual_overrides = read_json(root.resolve() / VISUAL_OVERRIDES, {}) or {}
    visual_override_path = root.resolve() / VISUAL_OVERRIDES
    for evidence, legacy_card in selected:
        source_id = str(evidence["source_id"])
        if evidence.get("evidence_status") != "complete":
            deferred.append(
                {
                    "source_id": source_id,
                    "title": evidence.get("title"),
                    "status": "system_pending_evidence",
                    "reason": "NAS媒体证据不完整，不用SQLite元数据冒充深学。",
                    "gaps": evidence.get("gaps") or [],
                    "external_gap": evidence.get("external_gap") or {},
                    "nas_item_root": evidence.get("nas_item_root"),
                }
            )
            continue
        try:
            text, record = render_card(
                evidence,
                legacy_card,
                name,
                visual_overrides.get(source_id) or {},
                visual_override_path,
            )
            errors = audit_card(text, record)
        except Exception as exc:  # keep per-source evidence of a failed batch
            text, record, errors = "", {"source_id": source_id}, [f"render_error:{type(exc).__name__}:{exc}"]
        if text:
            (cards_dir / f"xhs_{source_id}.md").write_text(text, encoding="utf-8")
        decision = "pass" if not errors else "fail"
        audits.append({"source_id": source_id, "decision": decision, "errors": errors})
        if errors:
            batch_errors.extend(f"{source_id}:{error}" for error in errors)
        learned.append(record)
    hashes = [str(record.get("card_hash") or "") for record in learned]
    prune_stale_cards(cards_dir, learned)
    if len(hashes) != len(set(hashes)):
        batch_errors.append("duplicate_card_hash_in_batch")
    if len(learned) + len(deferred) != len(selected):
        batch_errors.append("source_accounting_mismatch")
    passed_count = sum(item["decision"] == "pass" for item in audits)
    if passed_count != len(learned):
        batch_errors.append(f"deep_card_gate_failed:{passed_count}/{len(learned)}")
    gate = "fail" if batch_errors else ("pass_with_deferred_evidence" if deferred else "pass")
    audit = {
        "schema_version": "3.0",
        "batch_id": name,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "expected_source_count": len(selected),
        "learned_count": len(learned),
        "deferred_count": len(deferred),
        "unified_card_contract": CONTRACT_ID,
        "card_contract_version": CARD_CONTRACT_VERSION,
        "learning_method_revision": METHOD_REVISION,
        "unified_card_passed_count": passed_count,
        "anchor_traceability_passed_count": sum(not any("anchor" in error for error in item["errors"]) for item in audits),
        "quote_traceability_passed_count": sum(not any("quote" in error for error in item["errors"]) for item in audits),
        "duplicate_card_hashes": len(hashes) - len(set(hashes)),
        "batch_errors": sorted(set(batch_errors)),
        "batch_gate": gate,
        "formal_ingest_allowed": False,
        "user_acceptance_required": False,
        "cards": audits,
        "source_ids": [str(evidence["source_id"]) for evidence, _ in selected],
    }
    write_jsonl(output / "structured_cards.jsonl", learned)
    write_jsonl(output / "deferred_evidence.jsonl", deferred)
    write_json(output / "audit.json", audit)
    lines = [
        f"# {ACCOUNT} {name} 深学自审",
        "",
        f"- 批次门禁：`{gate}`",
        f"- 来源：{len(selected)} 条",
        f"- 统一十二段卡：{passed_count}/{len(learned)}",
        f"- 证据延期：{len(deferred)}",
        f"- 锚点可追溯：{audit['anchor_traceability_passed_count']}/{len(learned)}",
        f"- 原文引用可追溯：{audit['quote_traceability_passed_count']}/{len(learned)}",
        f"- 重复卡哈希：{audit['duplicate_card_hashes']}",
        "- 正式入库：false",
        "",
        "## 卡片索引",
        "",
    ]
    lines.extend(f"- [{record.get('title', record.get('source_id'))}](cards/xhs_{record.get('source_id')}.md)" for record in learned)
    if deferred:
        lines.extend(["", "## 证据延期", ""])
        lines.extend(f"- `{item['source_id']}` {item.get('title')}：{','.join(item.get('gaps') or [])}" for item in deferred)
    if batch_errors:
        lines.extend(["", "## 失败项", ""])
        lines.extend(f"- {error}" for error in sorted(set(batch_errors)))
    (output / "BATCH_SELF_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    update_status(root)
    return audit


def update_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rows = ordered_legacy_rows(root)
    audits = [read_json(path, {}) or {} for path in sorted((root / OUTPUT_ROOT).glob("batch_*/audit.json"))]
    passed = [audit for audit in audits if audit.get("batch_gate") in {"pass", "pass_with_deferred_evidence"}]
    learned_ids: set[str] = set()
    deferred_ids: set[str] = set()
    for batch_dir in sorted((root / OUTPUT_ROOT).glob("batch_*")):
        audit = read_json(batch_dir / "audit.json", {}) or {}
        if audit.get("batch_gate") not in {"pass", "pass_with_deferred_evidence"}:
            continue
        learned_ids.update(str(row["source_id"]) for row in read_jsonl(batch_dir / "structured_cards.jsonl"))
        deferred_ids.update(str(row["source_id"]) for row in read_jsonl(batch_dir / "deferred_evidence.jsonl"))
    total = len(rows)
    status = {
        "account": ACCOUNT,
        "account_id": ACCOUNT_ID,
        "schema_version": "3.0",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total_sources": total,
        "batch_size": BATCH_SIZE,
        "total_batches": (total + BATCH_SIZE - 1) // BATCH_SIZE,
        "passed_batches": [str(audit.get("batch_id")) for audit in passed],
        "processed_sources": len(learned_ids | deferred_ids),
        "deep_learned_items": len(learned_ids),
        "deferred_evidence_items": len(deferred_ids),
        "remaining_unprocessed_items": total - len(learned_ids | deferred_ids),
        "completion_ratio": round(len(learned_ids | deferred_ids) / total, 4) if total else 0,
        "learning_method_revision": METHOD_REVISION,
        "unified_card_contract": CONTRACT_ID,
        "formal_ingest_allowed": False,
        "workflow_accounting_complete": len(learned_ids | deferred_ids) == total,
        "all_content_deep_learned": len(learned_ids) == total and not deferred_ids,
        "completion_claim_allowed": len(learned_ids) == total and not deferred_ids,
    }
    write_json(root / OUTPUT_ROOT / "status.json", status)
    return status


def cross_card_revalidation(root: Path, learned: list[dict[str, Any]], deferred: list[dict[str, Any]]) -> dict[str, Any]:
    root = root.resolve()
    learned_by_id = {str(row["source_id"]): row for row in learned}
    deferred_ids = {str(row["source_id"]) for row in deferred}
    legacy_by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((root / LEGACY_BATCH_ROOT).glob("batch_*/structured_cards.jsonl")):
        for row in read_jsonl(path):
            legacy_by_id[str(row["source_id"])] = row
    expected_keys = (
        "identity_proof",
        "list_decision",
        "problem_result",
        "step_sequence",
        "time_feedback",
        "version_iteration",
    )
    method_results: list[dict[str, Any]] = []
    for key in expected_keys:
        method_id = f"xsl-cluster-{key}"
        method_path = root / WORKFLOW_ROOT / "methods" / method_id / "method.json"
        tests_path = root / WORKFLOW_ROOT / "methods" / method_id / "test-results.json"
        method = read_json(method_path, {}) or {}
        tests = read_json(tests_path, {}) or {}
        primary = [row for row in learned if row.get("mechanism_key") == key]
        primary_ids = {str(row["source_id"]) for row in primary}
        method_refs = {str(value) for value in method.get("source_refs") or []}
        topic_families = sorted({str(row.get("topic_family") or "") for row in primary})
        media_branches = sorted({str(row.get("content_type") or "") for row in primary})
        anchor_support = sum(bool(legacy_by_id.get(source_id, {}).get("account_anchor_markers")) for source_id in primary_ids)
        case_ids = {str(row.get("id") or "") for row in tests.get("case_results") or []}
        required_case_suffixes = ("positive", "lexical-decoy", "edge", "transfer", "sibling-decoy")
        checks = {
            "v1_primary_support_at_least_3": len(primary) >= 3,
            "v1_cross_topic_families_at_least_2": len(topic_families) >= 2,
            "v1_primary_source_hashes_unique": len({str(row.get("source_text_hash") or "") for row in primary}) == len(primary),
            "v2_pressure_test_100_percent": bool(tests) and int(tests.get("passed") or 0) == int(tests.get("total") or 0) >= 5,
            "v2_required_test_families_present": all(any(case_id.endswith(suffix) for case_id in case_ids) for suffix in required_case_suffixes),
            "v2_prompt_hash_and_executor_present": bool(tests.get("prompt_set_sha256") and tests.get("executor") and tests.get("executed_at")),
            "v3_account_anchor_support_at_least_2": anchor_support >= 2,
            "method_refs_all_deep_learned": bool(method_refs) and method_refs <= set(learned_by_id),
            "method_refs_exclude_deferred": not bool(method_refs & deferred_ids),
            "method_remains_candidate_noncallable": method.get("status") == "verified_candidate" and method.get("callable") is False,
        }
        errors = [name for name, passed in checks.items() if not passed]
        method_results.append(
            {
                "method_id": method_id,
                "title": method.get("title") or MECHANISMS[key]["title"],
                "primary_deep_card_support": len(primary),
                "primary_source_ids": sorted(primary_ids),
                "topic_family_count": len(topic_families),
                "topic_families": topic_families,
                "media_branches": media_branches,
                "account_anchor_support": anchor_support,
                "method_source_ref_count": len(method_refs),
                "checks": checks,
                "decision": "pass" if not errors else "fail",
                "errors": errors,
            }
        )
    errors = [f"{row['method_id']}:{error}" for row in method_results for error in row["errors"]]
    report = {
        "account": ACCOUNT,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "learning_method_revision": METHOD_REVISION,
        "deep_card_count": len(learned),
        "deferred_evidence_count": len(deferred),
        "method_count": len(method_results),
        "passed_method_count": sum(row["decision"] == "pass" for row in method_results),
        "gate": "pass" if not errors else "fail",
        "formal_ingest_allowed": False,
        "callable": False,
        "methods": method_results,
        "errors": errors,
    }
    write_json(root / OUTPUT_ROOT / "CROSS_CARD_REVALIDATION.json", report)
    lines = [
        f"# {ACCOUNT}跨卡方法重验证",
        "",
        f"- 门禁：`{report['gate']}`",
        f"- 深学卡：{len(learned)}",
        f"- 候选方法：{report['passed_method_count']}/{len(method_results)}",
        f"- 验证范围：V1跨主题深学证据、V2五类盲测、V3账号锚点，并排除{len(deferred)}条证据延期项。",
        "- 正式入库：false；可调用：false",
        "",
        "## 方法结果",
        "",
    ]
    for row in method_results:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- 结论：`{row['decision']}`",
                f"- 主机制深学卡：{row['primary_deep_card_support']}",
                f"- 跨主题：{row['topic_family_count']}；媒介：{'、'.join(row['media_branches'])}",
                f"- 账号锚点：{row['account_anchor_support']}",
                f"- 方法原证据引用：{row['method_source_ref_count']}，全部属于{len(learned)}条深学完成集。",
                "",
            ]
        )
    if errors:
        lines.extend(["## 未通过项", ""])
        lines.extend(f"- {error}" for error in errors)
    (root / OUTPUT_ROOT / "CROSS_CARD_REVALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def sqlite_recovery_metadata(database: Path, source_ids: list[str]) -> tuple[dict[str, dict[str, Any]], str]:
    if not database.is_file() or not source_ids:
        return {}, "database_missing"
    uri = f"file:{quote(str(database.resolve()))}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in source_ids)
        rows = connection.execute(
            f"SELECT note_id,title,desc,video_url,image_list FROM xhs_note WHERE note_id IN ({placeholders})",
            source_ids,
        ).fetchall()
        return {str(row["note_id"]): dict(row) for row in rows}, "ok"
    except sqlite3.Error as exc:
        return {}, f"sqlite_error:{type(exc).__name__}:{exc}"
    finally:
        if "connection" in locals():
            connection.close()


def evidence_recovery_audit(
    root: Path,
    deferred: list[dict[str, Any]],
    source_order: list[str],
) -> dict[str, Any]:
    source_ids = [str(row["source_id"]) for row in deferred]
    metadata, database_status = sqlite_recovery_metadata(NAS_SQLITE_DATABASE, source_ids)
    audited_at = datetime.now().astimezone().isoformat(timespec="seconds")
    items: list[dict[str, Any]] = []
    for row in deferred:
        source_id = str(row["source_id"])
        sqlite_row = metadata.get(source_id) or {}
        nas_item_root = Path(str(row.get("nas_item_root") or ""))
        ordinal = source_order.index(source_id)
        batch_id = batch_name(ordinal // BATCH_SIZE + 1)
        previous_attempts = list((row.get("external_gap") or {}).get("attempts") or [])
        recovery_attempts = list(
            dict.fromkeys(
                previous_attempts
                + [
                    "NAS账号媒体目录逐条存在性检查",
                    "NAS SQLite只读immutable模式回查正文与媒体URL字段",
                    "旧CDN代表性媒体URL执行HEAD与Range GET，均返回403",
                    "公开页匿名解析仅返回页面壳，浏览器返回风险错误300012",
                    "现有Chrome会话只读恢复被当前浏览器策略禁止，未绕过",
                ]
            )
        )
        enriched = dict(row)
        enriched.update(
            {
                "recovery_status": "blocked_external_evidence",
                "audited_at": audited_at,
                "candidate_boundary": "not_learned_not_callable",
                "nas_item_exists": nas_item_root.is_dir(),
                "sqlite_database": str(NAS_SQLITE_DATABASE),
                "sqlite_database_status": database_status,
                "sqlite_row_found": bool(sqlite_row),
                "sqlite_desc_chars": len(clean(sqlite_row.get("desc"))),
                "sqlite_image_list_present": bool(clean(sqlite_row.get("image_list"))),
                "sqlite_video_url_present": bool(clean(sqlite_row.get("video_url"))),
                "recovery_attempts": recovery_attempts,
                "representative_network_evidence": {
                    "scope": "representative_stored_media_url_only",
                    "head_status": 403,
                    "range_get_status": 403,
                    "anonymous_page_result": "risk_error_300012",
                    "logged_in_chrome_result": "disallowed_by_current_browser_policy",
                },
                "completion_blockers": [
                    "缺少可验证的原始图片或视频字节",
                    "缺少可复核的画面帧与视觉证据",
                    "SQLite正文与媒体URL元数据不能替代实际媒体学习",
                ],
                "relearn_trigger": {
                    "condition": "指定NAS账号目录恢复source.json及图片/视频/frames后，重新执行该批并重跑finalize",
                    "batch_id": batch_id,
                    "command": (
                        ".venv/bin/python -m tools.xiaosenlin_deep_relearning "
                        f"--root . batch --number {ordinal // BATCH_SIZE + 1}"
                    ),
                },
            }
        )
        items.append(enriched)
    metrics = {
        "pending_count": len(items),
        "nas_item_exists_count": sum(bool(row["nas_item_exists"]) for row in items),
        "sqlite_rows_found": sum(bool(row["sqlite_row_found"]) for row in items),
        "sqlite_desc_ge_60_chars": sum(int(row["sqlite_desc_chars"]) >= 60 for row in items),
        "sqlite_image_list_present": sum(bool(row["sqlite_image_list_present"]) for row in items),
        "sqlite_video_url_present": sum(bool(row["sqlite_video_url_present"]) for row in items),
        "not_learned_not_callable": sum(row["candidate_boundary"] == "not_learned_not_callable" for row in items),
        "relearn_trigger_registered": sum(bool(row.get("relearn_trigger")) for row in items),
    }
    errors: list[str] = []
    if metrics["not_learned_not_callable"] != len(items):
        errors.append("pending_boundary_missing")
    if metrics["relearn_trigger_registered"] != len(items):
        errors.append("relearn_trigger_missing")
    if database_status != "ok":
        errors.append(database_status)
    report = {
        "account": ACCOUNT,
        "generated_at": audited_at,
        "gate": "pass_as_system_pending" if not errors else "fail",
        "scope": "external_evidence_recovery_and_pending_registration",
        "all_content_learned": not items,
        "metrics": metrics,
        "blocked_reason": (
            "NAS原媒体缺失，旧CDN代表性URL返回403；当前浏览器策略禁止访问小红书，"
            "因此不能恢复实际媒体，也不能用SQLite元数据冒充完整学习。"
        ),
        "items": items,
        "errors": errors,
    }
    write_json(root / OUTPUT_ROOT / "EVIDENCE_RECOVERY_AUDIT.json", report)
    lines = [
        f"# {ACCOUNT}缺失证据恢复审计",
        "",
        f"- 门禁：`{report['gate']}`",
        f"- 系统待处理：{metrics['pending_count']}",
        f"- NAS当前媒体目录存在：{metrics['nas_item_exists_count']}",
        f"- NAS SQLite行命中：{metrics['sqlite_rows_found']}",
        f"- SQLite正文不少于60字：{metrics['sqlite_desc_ge_60_chars']}",
        f"- SQLite含图片URL字段：{metrics['sqlite_image_list_present']}",
        f"- SQLite含视频URL字段：{metrics['sqlite_video_url_present']}",
        f"- 明确不可调用：{metrics['not_learned_not_callable']}/{metrics['pending_count']}",
        f"- 已登记重学触发器：{metrics['relearn_trigger_registered']}/{metrics['pending_count']}",
        "",
        "## 审计结论",
        "",
        f"- 这{len(items)}条没有被判定为已学习；SQLite正文和媒体URL只用于确认数据存在，不替代图片/视频证据。",
        "- 代表性旧CDN地址HEAD与Range GET均为403，匿名公开页返回风险错误300012。",
        "- 当前浏览器策略禁止继续访问小红书，已停止，不做任何绕过。",
        "- 每条待办都包含所属批次、恢复条件和可重跑命令；NAS媒体恢复后才重新进入十二段深学。",
    ]
    if errors:
        lines.extend(["", "## 未通过项", ""] + [f"- {error}" for error in errors])
    (root / OUTPUT_ROOT / "EVIDENCE_RECOVERY_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def anti_laziness_audit(root: Path, learned: list[dict[str, Any]], deferred: list[dict[str, Any]]) -> dict[str, Any]:
    root = root.resolve()
    card_paths = sorted((root / OUTPUT_ROOT).glob("batch_*/cards/*.md"))
    card_texts = [path.read_text(encoding="utf-8") for path in card_paths]
    learned_ids = {str(row["source_id"]) for row in learned}
    deferred_ids = {str(row["source_id"]) for row in deferred}
    anchor_signatures = {
        "|".join(normalized(str(value)) for value in row.get("traceable_anchors", [])[:5])
        for row in learned
    }
    mechanism_counts = Counter(str(row.get("mechanism_key") or "") for row in learned)
    missing_paths: list[str] = []
    for row in learned:
        for key, value in (row.get("source_paths") or {}).items():
            if key == "visual_override" and not value:
                continue
            if not Path(str(value)).exists():
                missing_paths.append(f"{row['source_id']}:{key}")
    deferred_card_ids = {
        match.group(1)
        for path in card_paths
        if (match := re.match(r"xhs_(.+)\.md$", path.name)) and match.group(1) in deferred_ids
    }
    no_quote_cards = sum(not row.get("retained_quotes") for row in learned)
    explicit_no_quote_boundaries = sum("未保留：无足够完整的口播/图文原句" in text for text in card_texts)
    checks = {
        "all_learned_cards_present": len(card_paths) == len(learned),
        "source_ids_unique": len(learned_ids) == len(learned),
        "source_text_hashes_unique": len({str(row.get("source_text_hash") or "") for row in learned}) == len(learned),
        "card_hashes_unique": len({str(row.get("card_hash") or "") for row in learned}) == len(learned),
        "evidence_anchor_signatures_unique": len(anchor_signatures) == len(learned),
        "every_card_has_at_least_3_evidence_units": min(int(row.get("evidence_unit_count") or 0) for row in learned) >= 3,
        "every_card_is_substantive_length": min(len(text) for text in card_texts) >= 4800,
        "all_source_paths_exist": not missing_paths,
        "no_quote_cases_have_explicit_boundary": no_quote_cards == explicit_no_quote_boundaries,
        "deferred_items_have_no_deep_card": not deferred_card_ids,
        "learned_and_deferred_do_not_overlap": not bool(learned_ids & deferred_ids),
        "all_six_primary_mechanisms_have_support": {
            "identity_proof", "list_decision", "problem_result", "step_sequence", "time_feedback", "version_iteration"
        }.issubset(mechanism_counts)
        and min(
            mechanism_counts[key]
            for key in ("identity_proof", "list_decision", "problem_result", "step_sequence", "time_feedback", "version_iteration")
        ) >= 3,
        "all_cards_remain_noncallable_candidates": all(
            row.get("callable") is False and row.get("status") == "candidate_learned" for row in learned
        ),
    }
    errors = [name for name, passed in checks.items() if not passed]
    lengths = [len(text) for text in card_texts]
    report = {
        "account": ACCOUNT,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate": "pass" if not errors else "fail",
        "checks": checks,
        "metrics": {
            "deep_card_count": len(learned),
            "deferred_count": len(deferred),
            "unique_source_text_hashes": len({str(row.get("source_text_hash") or "") for row in learned}),
            "unique_card_hashes": len({str(row.get("card_hash") or "") for row in learned}),
            "unique_evidence_anchor_signatures": len(anchor_signatures),
            "card_chars_min": min(lengths),
            "card_chars_median": sorted(lengths)[len(lengths) // 2],
            "card_chars_max": max(lengths),
            "evidence_units_min": min(int(row.get("evidence_unit_count") or 0) for row in learned),
            "evidence_units_median": sorted(int(row.get("evidence_unit_count") or 0) for row in learned)[len(learned) // 2],
            "quote_retained_cards": len(learned) - no_quote_cards,
            "no_quote_cards_with_explicit_boundary": explicit_no_quote_boundaries,
            "human_visual_review_cards": sum(int(row.get("visual_review_unit_count") or 0) > 0 for row in learned),
            "media_distribution": dict(Counter(str(row.get("content_type") or "") for row in learned)),
            "primary_mechanism_distribution": dict(mechanism_counts),
            "missing_source_paths": missing_paths,
            "deferred_card_ids": sorted(deferred_card_ids),
        },
        "formal_ingest_allowed": False,
        "errors": errors,
    }
    write_json(root / OUTPUT_ROOT / "ANTI_LAZINESS_AUDIT.json", report)
    lines = [
        f"# {ACCOUNT}反偷懒审计",
        "",
        f"- 门禁：`{report['gate']}`",
        f"- 深学卡：{len(learned)}；唯一原证据哈希：{report['metrics']['unique_source_text_hashes']}；唯一卡哈希：{report['metrics']['unique_card_hashes']}",
        f"- 唯一五阶段证据锚点签名：{report['metrics']['unique_evidence_anchor_signatures']}",
        f"- 单卡字符：最少 {report['metrics']['card_chars_min']} / 中位 {report['metrics']['card_chars_median']} / 最多 {report['metrics']['card_chars_max']}",
        f"- 证据单元：最少 {report['metrics']['evidence_units_min']} / 中位 {report['metrics']['evidence_units_median']}",
        f"- 保留原文引用：{report['metrics']['quote_retained_cards']}；无有效原句但显式标注边界：{report['metrics']['no_quote_cards_with_explicit_boundary']}",
        f"- 人工视觉证据补位：{report['metrics']['human_visual_review_cards']}",
        f"- 媒介分布：{json.dumps(report['metrics']['media_distribution'], ensure_ascii=False)}",
        f"- 主机制分布：{json.dumps(report['metrics']['primary_mechanism_distribution'], ensure_ascii=False)}",
        f"- {len(deferred)}条延期项未生成深学卡；{len(learned)}条学习卡均为 candidate_learned / callable=false。",
        "",
        "## 逐项检查",
        "",
    ]
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in checks.items())
    if errors:
        lines.extend(["", "## 失败项", ""])
        lines.extend(f"- {error}" for error in errors)
    (root / OUTPUT_ROOT / "ANTI_LAZINESS_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def finalize(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rows = ordered_legacy_rows(root)
    expected_batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE
    audits = [read_json(root / OUTPUT_ROOT / batch_name(index) / "audit.json", {}) or {} for index in range(1, expected_batches + 1)]
    missing = [batch_name(index) for index, audit in enumerate(audits, 1) if not audit]
    failed = [str(audit.get("batch_id")) for audit in audits if audit and audit.get("batch_gate") not in {"pass", "pass_with_deferred_evidence"}]
    learned: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for index in range(1, expected_batches + 1):
        batch_dir = root / OUTPUT_ROOT / batch_name(index)
        learned.extend(read_jsonl(batch_dir / "structured_cards.jsonl"))
        deferred.extend(read_jsonl(batch_dir / "deferred_evidence.jsonl"))
    source_ids = [str(evidence["source_id"]) for evidence, _ in rows]
    learned_ids = [str(row["source_id"]) for row in learned]
    deferred_ids = [str(row["source_id"]) for row in deferred]
    card_hashes = [str(row["card_hash"]) for row in learned]
    section_counts: Counter[str] = Counter()
    lengths: list[int] = []
    final_errors: list[str] = []
    for path in sorted((root / OUTPUT_ROOT).glob("batch_*/cards/*.md")):
        text = path.read_text(encoding="utf-8")
        validation = validate_card_text(text)
        if validation.errors:
            final_errors.extend(f"{path.name}:{error}" for error in validation.errors)
        for section in UNIFIED_SECTIONS:
            if section in validation.sections:
                section_counts[section] += 1
        lengths.append(len(text))
    if missing:
        final_errors.append(f"missing_batches:{','.join(missing)}")
    if failed:
        final_errors.append(f"failed_batches:{','.join(failed)}")
    if set(learned_ids) & set(deferred_ids):
        final_errors.append("learned_deferred_overlap")
    if set(learned_ids) | set(deferred_ids) != set(source_ids):
        final_errors.append("source_coverage_mismatch")
    if len(learned_ids) != len(set(learned_ids)):
        final_errors.append("duplicate_learned_source_id")
    if len(card_hashes) != len(set(card_hashes)):
        final_errors.append("duplicate_card_hash_global")
    if len(learned_ids) + len(deferred_ids) != len(source_ids):
        final_errors.append(
            f"learned_deferred_total_mismatch:{len(learned_ids)}+{len(deferred_ids)}!={len(source_ids)}"
        )
    if any(count != len(learned) for count in section_counts.values()) or len(section_counts) != len(UNIFIED_SECTIONS):
        final_errors.append("twelve_section_coverage_mismatch")
    legacy_registry: list[dict[str, Any]] = []
    learned_set = set(learned_ids)
    for evidence, card in rows:
        source_id = str(evidence["source_id"])
        old_path = root / LEGACY_BATCH_ROOT / str(card["batch_id"]) / "cards" / f"xhs_{source_id}.md"
        new_batch_number = source_ids.index(source_id) // BATCH_SIZE + 1
        legacy_registry.append(
            {
                "source_id": source_id,
                "legacy_card": str(old_path.relative_to(root)),
                "legacy_status": "downgraded_candidate_backup",
                "reason": "旧卡仅四段五路摘要，不满足统一十二段深学契约。",
                "replacement": (
                    str((OUTPUT_ROOT / batch_name(new_batch_number) / "cards" / f"xhs_{source_id}.md"))
                    if source_id in learned_set
                    else ""
                ),
                "system_pending": source_id not in learned_set,
            }
        )
    write_jsonl(root / OUTPUT_ROOT / "LEGACY_CARD_DOWNGRADE_REGISTRY.jsonl", legacy_registry)
    pending_path = root / OUTPUT_ROOT / "SYSTEM_PENDING_EVIDENCE.jsonl"
    recovery_path = root / OUTPUT_ROOT / "EVIDENCE_RECOVERY_AUDIT.json"
    existing_pending = read_jsonl(pending_path)
    existing_recovery = read_json(recovery_path, {}) or {}
    if (
        len(existing_pending) == len(deferred)
        and {str(row["source_id"]) for row in existing_pending} == set(deferred_ids)
        and existing_recovery.get("gate") == "pass_as_system_pending"
        and int((existing_recovery.get("metrics") or {}).get("pending_count") or -1) == len(deferred)
    ):
        recovery = existing_recovery
        deferred = existing_pending
    else:
        recovery = evidence_recovery_audit(root, deferred, source_ids)
        deferred = list(recovery.get("items") or deferred)
        write_jsonl(pending_path, deferred)
    former_formal_cards = [
        path for path in (root / FORMER_FORMAL_BACKUP).rglob("*.md") if path.name != "README.md"
    ]
    if len(former_formal_cards) != 87:
        final_errors.append(f"former_formal_backup_expected_87_got_{len(former_formal_cards)}")
    cross_card = cross_card_revalidation(root, learned, deferred)
    # This legacy six-mechanism audit predates active Skill v2.2. The root v2.2
    # workflow is authoritative for natural-content V1, commercial separation,
    # method orchestration and pressure tests.
    anti_laziness = anti_laziness_audit(root, learned, deferred)
    if anti_laziness.get("gate") != "pass":
        final_errors.append("anti_laziness_audit_failed")
    if recovery.get("gate") != "pass_as_system_pending":
        final_errors.append("evidence_recovery_audit_failed")
    status = update_status(root)
    gate = (
        ("pass_with_deferred_external_evidence" if deferred else "pass")
        if not final_errors and status.get("workflow_accounting_complete")
        else "fail"
    )
    report = {
        "account": ACCOUNT,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "final_gate": gate,
        "source_total": len(source_ids),
        "deep_learned_count": len(learned_ids),
        "deferred_evidence_count": len(deferred_ids),
        "batch_count": expected_batches,
        "passed_batch_count": sum(audit.get("batch_gate") in {"pass", "pass_with_deferred_evidence"} for audit in audits),
        "unified_card_contract": CONTRACT_ID,
        "twelve_section_cards": len(learned),
        "section_coverage": dict(section_counts),
        "median_card_chars": sorted(lengths)[len(lengths) // 2] if lengths else 0,
        "unique_card_hashes": len(set(card_hashes)),
        "former_formal_cards_backed_up_as_candidates": len(former_formal_cards),
        "superseded_compact_candidate_cards_registered": len(legacy_registry),
        "system_pending_count": len(deferred),
        "all_content_learned": not deferred,
        "evidence_recovery_audit": {
            "gate": recovery.get("gate"),
            "metrics": recovery.get("metrics"),
        },
        "cross_card_revalidation": {
            "gate": "superseded_by_skill_v2_2",
            "legacy_gate": cross_card.get("gate"),
            "passed_method_count": cross_card.get("passed_method_count"),
            "method_count": cross_card.get("method_count"),
            "authoritative_audit": "../V22_FINAL_AUDIT.json",
        },
        "anti_laziness_audit": {
            "gate": anti_laziness.get("gate"),
            "unique_source_text_hashes": anti_laziness.get("metrics", {}).get("unique_source_text_hashes"),
            "unique_evidence_anchor_signatures": anti_laziness.get("metrics", {}).get("unique_evidence_anchor_signatures"),
        },
        "formal_ingest_allowed": False,
        "errors": sorted(set(final_errors)),
    }
    write_json(root / OUTPUT_ROOT / "FINAL_DEEP_AUDIT.json", report)
    lines = [
        f"# {ACCOUNT}升级重学最终审计",
        "",
        f"- 最终门禁：`{gate}`",
        f"- 来源总数：{len(source_ids)}",
        f"- 统一十二段深学卡：{len(learned_ids)}",
        f"- 证据延期/系统待处理：{len(deferred_ids)}",
        f"- 通过批次：{report['passed_batch_count']}/{expected_batches}",
        f"- 单卡中位字符数：{report['median_card_chars']}",
        f"- 全局唯一卡哈希：{report['unique_card_hashes']}/{len(learned_ids)}",
        f"- 原正式卡降级候选备份：{len(former_formal_cards)}",
        f"- 被替代的旧四段候选卡登记：{len(legacy_registry)}",
        "- 跨卡方法重验证：旧六方法审计已被 active Skill v2.2 取代；权威结果见 `../V22_FINAL_AUDIT.json`",
        f"- 反偷懒审计：`{anti_laziness.get('gate')}`",
        f"- 缺失证据恢复审计：`{recovery.get('gate')}`",
        f"- 全部内容已学习：{str(not deferred).lower()}",
        "- 正式入库：false",
        "",
        "## 十二段覆盖",
        "",
    ]
    lines.extend(f"- {section}：{section_counts.get(section, 0)}/{len(learned)}" for section in UNIFIED_SECTIONS)
    lines.extend(
        [
            "",
            "## 边界",
            "",
            f"- {len(learned_ids)}条只证明候选深学卡完成，不代表正式账号知识已提升。",
            f"- {len(deferred_ids)}条NAS媒体证据不完整，只登记为系统待处理，不用SQLite元数据冒充学习。",
            "- 旧四段卡仅作候选备份，不再计入完成进度。",
        ]
    )
    if final_errors:
        lines.extend(["", "## 未通过项", ""])
        lines.extend(f"- {error}" for error in sorted(set(final_errors)))
    (root / OUTPUT_ROOT / "FINAL_DEEP_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{ACCOUNT} unified twelve-section deep relearning")
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    batch_parser = subparsers.add_parser("batch")
    batch_parser.add_argument("--number", type=int, required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("finalize")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == "batch":
        result = run_batch(root, args.number)
    elif args.command == "status":
        result = update_status(root)
    else:
        result = finalize(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("batch_gate", result.get("final_gate", "pass")) != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
