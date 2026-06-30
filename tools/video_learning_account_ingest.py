from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.kb.runtime import mark_dirty, runtime_path


def as_posix(path: Path) -> str:
    return path.as_posix()


@dataclass(frozen=True)
class AccountIngestConfig:
    profile_id: str
    account_id: str
    account_name: str
    formal_account_dir: Path
    platform: str = "抖音"
    learned_base: Path | None = None
    artifacts_dir: Path = Path("00_System/runtime/cache/video_learning/video_artifacts")
    global_account_index_md: Path = Path("10_Knowledge/evidence/index/account_knowledge_index.md")
    global_account_index_json: Path = Path("10_Knowledge/evidence/index/account_knowledge_index.json")

    @classmethod
    def for_profile(
        cls,
        *,
        profile_id: str,
        account_id: str,
        account_name: str,
        formal_account_dir: Path,
        platform: str = "抖音",
    ) -> "AccountIngestConfig":
        return cls(
            profile_id=profile_id,
            account_id=account_id,
            account_name=account_name,
            platform=platform,
            formal_account_dir=formal_account_dir,
            learned_base=Path("10_Knowledge/candidates/learning_cards/learned_cards") / profile_id,
        )

    def resolved_learned_base(self) -> Path:
        return self.learned_base or Path("10_Knowledge/candidates/learning_cards/learned_cards") / self.profile_id


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_file(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def _write_transformed(source: Path, target: Path, transform) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(transform(source.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
    return True


def parse_card_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    metadata: dict[str, str] = {}
    title_match = re.search(r"^#\s*视频深度学习卡[:：]\s*(.+)$", text, re.M)
    if title_match:
        metadata["标题"] = title_match.group(1).strip()
    for line in text.splitlines()[:45]:
        match = re.match(r"^(source_id|原视频链接|账号|平台|主方向|辅方向|学习批次|状态)[:：]\s*(.*)$", line.strip())
        if match:
            metadata[match.group(1)] = match.group(2).strip()
    return metadata


def _formalize_card_text(text: str) -> str:
    text = re.sub(r"^#\s*视频深度学习卡[:：]", "# 账号发布资产学习卡：", text, count=1, flags=re.MULTILINE)
    text = text.replace("## 5. 视频层学习", "## 5. 发布资产学习")
    text = re.sub(
        r"^- 收尾/互动引导：.*评论引导.*$",
        "- 收尾/互动引导：只学习发布内容本身的收尾设计；不基于评论正文补写引导。",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^- 评论区可能触发点：.*$",
        "- 评论边界：不学习评论正文，不从评论区提炼观点、痛点或话术；评论数量只作为互动指标。",
        text,
        flags=re.MULTILINE,
    )
    text = text.replace("、评论语义", "")
    text = text.replace("评论语义和", "")
    text = text.replace("结尾无明确评论引导", "结尾无明确互动引导")
    text = re.sub(r"^状态[:：]\s*[^\n]+$", "状态：formal_ingested", text, count=1, flags=re.MULTILINE)
    section_match = re.search(r"(^## 10\. 入库判断\s*$)(.*)\Z", text, flags=re.MULTILINE | re.DOTALL)
    if not section_match:
        return text
    body_lines: list[str] = []
    for line in section_match.group(2).splitlines():
        stripped = line.strip()
        if not stripped:
            body_lines.append(line)
            continue
        if stripped.startswith("- 当前") and any(token in stripped for token in ("候选", "审核", "仍停留", "正式入库需")):
            continue
        if stripped.startswith("- 待验证："):
            content = stripped.removeprefix("- 待验证：")
            content = re.sub(r"^保留为", "沉淀", content)
            content = re.sub(r"^保留", "沉淀", content)
            content = content.replace("候选学习卡", "正式知识卡").replace("候选卡", "正式知识卡")
            content = content.replace("候选模型", "方法模型").replace("候选模块", "正式模块")
            content = re.sub(r"；?(?:方向完成|在所属方向完成|创业方向完成|技能沉淀方向完成)[^。]*?(?:正式知识库|正式账号中心)。?", "。", content)
            content = re.sub(r"，?正式入库(?:仍)?需用户审核。?", "。", content)
            body_lines.append(f"- 可正式入库：{content}")
            continue
        line = line.replace("可入库候选：", "可正式入库：")
        line = line.replace("正式入库候选", "正式入库内容")
        line = line.replace("方法论候选", "方法论")
        body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not body:
        body = "- 可正式入库：本卡已通过全量深度学习审计；具体方法、案例和证据边界以上述章节为准。"
    return text[: section_match.start(2)] + "\n\n" + body + "\n"


def _formalize_summary_text(text: str) -> str:
    text = re.sub(r"^学习状态[:：].*$", "学习状态：formal_ingested", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"^正式入库状态[:：].*$", "正式入库状态：formal_ingested", text, flags=re.MULTILINE)
    text = text.replace("当前仍在候选学习区，尚未写入正式账号中心。", "当前方向已正式写入账号中心。")
    text = text.replace("需用户审核后，再决定是否更新正式方向方法论和出内容模板。", "后续按新增证据与内容反馈迭代方向方法论。")
    text = re.sub(
        r"当前结论来自本方向\s*(\d+)\s*张候选学习卡，仍属于候选学习区，不代表正式知识。",
        r"当前结论来自本方向 \1 张正式学习卡，已写入正式账号中心。",
        text,
    )
    text = text.replace("候选模型：", "正式模型：")
    text = text.replace("候选模板：", "正式模板：")
    text = text.replace("候选规则：", "正式规则：")
    text = text.replace("- 用户确认后再考虑正式账号中心入库。", "- 后续按新增证据和发布反馈继续迭代。")
    return text


def _formalize_rough_learning_pool_text(text: str, formal_card_count: int) -> str:
    text = text.replace("粗扫内容和选题", "粗学与选题池")
    text = text.replace("粗扫范围：", "粗学范围：")
    text = re.sub(r"^状态[:：].*$", "状态：formal_learning_pool", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"- 已确认深学(?:卡)?[:：]\s*\d+条。", f"- 已确认深学卡：{formal_card_count}条。", text)
    legacy_scope_line = "- " + "学习范围：" + "标题、正文/文案、话题/标签、内容结构协同。"
    text = text.replace(
        legacy_scope_line,
        "- 粗学重点：发布内容层，包括标题、正文/文案、话题/标签、内容结构协同。\n- 视频边界：粗扫阶段未下载视频，不学习逐字稿、抽帧或分镜；需要进入深度学习后补齐视频内容层。",
    )
    if "粗学重点：发布内容层" not in text:
        text = text.replace(
            "## 2. 全部粗学素材清单",
            "## 2. 全部粗学素材清单",
            1,
        )
        marker = re.search(r"(## 1\. 方向素材总览\n\n(?:- .+\n)+)", text)
        if marker:
            insert = (
                "- 粗学重点：发布内容层，包括标题、正文/文案、话题/标签、内容结构协同。\n"
                "- 视频边界：粗扫阶段未下载视频，不学习逐字稿、抽帧或分镜；需要进入深度学习后补齐视频内容层。\n"
                "- 评论处理：不学习评论正文；评论数只作为平台互动指标保留。\n"
            )
            text = text[: marker.end(1)] + insert + text[marker.end(1) :]
    if "## 13. 评论边界" not in text:
        text = text.rstrip() + "\n\n## 13. 评论边界\n\n- 不学习评论正文，不从评论区提炼观点、痛点或话术。\n- 评论数量只作为平台互动指标，不进入标题、正文、话题或方法论学习。\n"
    return text


def _card_rows(root: Path, config: AccountIngestConfig, direction: str) -> list[dict[str, str]]:
    cards_dir = root / config.resolved_learned_base() / direction / "cards"
    rows: list[dict[str, str]] = []
    for card_path in sorted(cards_dir.glob("*.md")):
        metadata = parse_card_metadata(card_path)
        source_id = metadata.get("source_id", "")
        if not source_id:
            continue
        rows.append(
            {
                "source_id": source_id,
                "title": metadata.get("标题", card_path.stem),
                "source_url": metadata.get("原视频链接", ""),
                "card_filename": card_path.name,
                "candidate_card_path": as_posix(card_path.relative_to(root)),
            }
        )
    return rows


def _file_record(root: Path, path: Path, tier: str, action: str, note: str) -> dict[str, Any]:
    return {
        "path": as_posix(path.relative_to(root)),
        "tier": tier,
        "action": action,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "note": note,
    }


def _artifact_dir_for_source(root: Path, config: AccountIngestConfig, source_id: str) -> Path:
    platform = config.platform.lower()
    if "小红书" in config.platform or platform in {"xhs", "xiaohongshu"}:
        preferred_prefixes = ["xhs", "douyin"]
    else:
        preferred_prefixes = ["douyin", "xhs"]
    for prefix in preferred_prefixes:
        candidate = root / config.artifacts_dir / f"{prefix}_{source_id}"
        if candidate.exists():
            return candidate
    return root / config.artifacts_dir / f"{preferred_prefixes[0]}_{source_id}"


def _artifact_records(root: Path, config: AccountIngestConfig, source_id: str) -> tuple[list[dict[str, Any]], list[Path]]:
    artifact_dir = _artifact_dir_for_source(root, config, source_id)
    records: list[dict[str, Any]] = []
    transcript_paths: list[Path] = []
    for name in ("transcript.srt", "transcript.json"):
        path = artifact_dir / name
        if path.exists():
            transcript_paths.append(path)
    if artifact_dir.exists():
        for path in sorted(item for item in artifact_dir.iterdir() if item.is_file()):
            if path.name in {"transcript.srt", "transcript.json"}:
                records.append(_file_record(root, path, "formal_hot", "copy_to_formal_account", "逐字稿跟随单卡入库，便于写作回溯。"))
            elif path.suffix.lower() in {".mp4", ".wav", ".jpg", ".jpeg", ".png"} or path.name.endswith("-Scenes.csv"):
                records.append(_file_record(root, path, "cloud_candidate", "keep_original_until_cloud_or_delete_review", "大体积或中间证据，不进入热知识区。"))
            else:
                records.append(_file_record(root, path, "local_evidence", "keep_original_until_cleanup_review", "机器分析中间产物，只在核查时读取。"))
    return records, transcript_paths


def _render_account_index(config: AccountIngestConfig, directions: list[dict[str, Any]]) -> str:
    lines = [
        f"# {config.account_name}账号索引",
        "",
        "用途：按账号进入知识，不需要重新扫描候选区或全量原始资料。",
        "",
        "## 读取顺序",
        "",
        "1. `账号概述.md`：先看账号状态、资料范围、证据地址和当前缺口。",
        "2. `账号方法论总览.md`：读取深学后的账号级方法论。",
        "3. `账号整体方法论.md`：兼容旧调用，读取账号级总结、跨方向模型和内容资产规律。",
        "4. `内容生产使用说明.md`：会话外调用时先按这里确定读取路径和输出边界。",
        "5. `减少AI味输出规则.md`：写选题、文案或脚本前必须读取。",
        "6. `内容输出标准模板.md`：按账号通用字段输出完整内容包。",
        "7. `directions/{方向}/方向方法论总结.md`：按方向调用方法论。",
        "8. `directions/{方向}/cards/`：需要证据时回到单卡。",
        "9. `directions/{方向}/粗扫内容和选题.md`：正式粗学与选题池，写选题和延展内容时调用。",
        "10. `directions/{方向}/transcripts/`：仅在视频证据争议或文案复核时回溯；图文/元数据卡不强求逐字稿。",
        "",
        "## 方向入口",
        "",
        "| 方向 | 状态 | 单卡 | 逐字稿文件 | 入口 |",
        "|---|---|---:|---:|---|",
    ]
    for direction in directions:
        lines.append(
            f"| {direction['direction']} | {direction['status']} | {direction['card_count']} | "
            f"{direction['transcript_file_count']} | {direction['formal_direction_dir']} |"
        )
    return "\n".join(lines) + "\n"


def _render_account_status_overview(config: AccountIngestConfig, directions: list[dict[str, Any]]) -> str:
    lines = [
        f"# {config.account_name}账号概述",
        "",
        "用途：账号学习和生产调用的状态面板。这里只放摘要、状态和入口，不堆完整证据。",
        "",
        f"- 账号：{config.account_name}",
        f"- 平台：{config.platform}",
        "- 学习状态：formal_ingested",
        "- 资料范围：以已入库方向、学习卡和账号索引登记为准",
        "- 原始证据/NAS 地址：如有外部原始仓，只记录地址和状态，不把 NAS 当第二知识库",
        "- 当前缺口：按方向方法论、学习卡和证据缺口清单继续更新",
        "",
        "## 方向总览",
        "",
        "| 方向 | 状态 | 单卡 | 入口 |",
        "|---|---|---:|---|",
    ]
    for direction in directions:
        lines.append(f"| {direction['direction']} | {direction['status']} | {direction['card_count']} | {direction['formal_direction_dir']} |")
    lines.extend(
        [
            "",
            "## 调用提醒",
            "",
            "- 内容生产前先读本文件确认账号状态，再读方法论、生产说明、输出模板和风格规则。",
            "- 粗学判断必须标注为待深学验证；深学结论必须能回到学习卡、source_id 和原链接。",
            "- 过程物如入库回执、验收报告、存储分层清单只作为审计材料，不作为长期必读知识。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_account_overview(config: AccountIngestConfig, directions: list[dict[str, Any]]) -> str:
    lines = [
        f"# {config.account_name}账号方法论总览",
        "",
        "定位：以正式入库方向为依据的账号级方法论入口。",
        "",
        "## 已入库方向",
        "",
        "| 方向 | 核心用途 | 正式入口 |",
        "|---|---|---|",
    ]
    for direction in directions:
        lines.append(f"| {direction['direction']} | 内容选题、文案结构、案例回溯、方法论复用 | {direction['formal_direction_dir']} |")
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 方向方法论用于快速调用框架；单卡用于查证来源和具体案例。",
            "- 粗学与选题池用于学习方向下所有素材的发布内容层：标题、正文/文案、话题/标签和内容结构协同。",
            "- 粗学阶段不学习逐字稿、抽帧或分镜；视频内容层必须进入深度学习后再学习。",
            "- 评论正文不纳入账号学习；评论数量只作为平台互动指标。",
            "- 逐字稿只在视频证据核查、观点争议、金句复核时读取；图文/元数据卡以标题、正文/文案和话题为主。",
            "- 视频、音频、分镜图属于冷证据，不默认读取。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_account_summary(config: AccountIngestConfig, directions: list[dict[str, Any]]) -> str:
    direction_names = [direction["direction"] for direction in directions]
    lines = [
        f"# {config.account_name}账号整体方法论",
        "",
        f"账号：{config.account_name}",
        f"平台：{config.platform}",
        f"正式方向数：{len(directions)}",
        f"正式方向：{'、'.join(direction_names)}",
        "状态：formal_ingested",
        "",
        "## 1. 账号级核心判断",
        "",
        "- 本文件是账号级综合入口，结论必须来自本账号正式方向总结、学习卡、标题、正文/文案、话题和必要证据索引。",
        "- 系统不按方向词预设账号风格；任何表达结构、选题偏好、口吻和禁用写法，都要能回到本账号证据。",
        "- 如果某条判断只来自粗学池，必须标注为粗学判断或待深学验证，不能写成已验证方法论。",
        "",
        "## 2. 跨方向归纳框架",
        "",
        "- 先比较各方向的标题、正文/文案、话题标签、内容结构和学习卡证据，再总结跨方向共性。",
        "- 只记录在多个方向或多张正式学习卡中重复出现的稳定规律；单条爆款只作为案例，不直接上升为账号规律。",
        "- 对无法确认的口吻、结构、受众、场景和证据缺口，保留为待补项，不用其他账号模板补齐。",
        "",
        "## 3. 内容资产学习口径",
        "",
        "- 粗学与选题池覆盖方向下所有素材的发布内容层，学习标题、正文/文案、话题/标签和内容结构协同。",
        "- 深度学习卡完整学习发布内容层和视频内容层，包含标题、正文/文案、话题、逐字稿、抽帧/分镜和证据边界。",
        "- 评论正文不纳入学习范围，不能从评论区提炼观点、痛点或话术。",
        "- 评论数量、点赞、收藏、分享只作为平台互动指标和热度参考。",
        "",
        "## 4. 账号表达规则",
        "",
        "- 从本账号正式单卡和方向总结抽取表达规则，不复制其他账号的风格文件。",
        "- 写作时优先保留本账号已验证的标题习惯、开头方式、转折方式、例子来源和收尾方式。",
        "- 没有证据支持的表达偏好，不写入正式规则；需要继续观察的写入账号概述缺口或复盘待补项。",
        "",
        "## 5. 调用边界",
        "",
        "- 正式调用时先读账号概述和本文件，再按方向读取方向方法论、粗学与选题池和单卡证据。",
        "- 不把别的账号经验、平台通用经验或系统默认模板当成本账号规律。",
        "- 涉及效果、收益、健康、消费、投资等高风险表达时，只能按证据边界写，不能承诺结果。",
        "",
        "## 6. 正式方向入口",
        "",
        "| 方向 | 单卡 | 入口 |",
        "|---|---:|---|",
    ]
    for direction in directions:
        lines.append(f"| {direction['direction']} | {direction['card_count']} | {direction['formal_direction_dir']} |")
    return "\n".join(lines) + "\n"


def _render_content_usage(config: AccountIngestConfig, directions: list[dict[str, Any]]) -> str:
    lines = [
        f"# {config.account_name}内容生产使用说明",
        "",
        "用途：让项目/会话外的 AI 能稳定调用账号正式知识出选题、文案和内容方案，避免重新全扫候选区。",
        "",
        "## 会话外调用入口",
        "",
        "1. `10_Knowledge/evidence/index/account_knowledge_index.md`：确认账号中心位置。",
        "2. `账号索引.md`：确认账号内有哪些方向已经正式入库。",
        "3. `账号概述.md`：确认账号状态、资料范围、证据地址和当前缺口。",
        "4. `账号方法论总览.md`：确认深学后的账号定位和使用边界。",
        "5. `账号整体方法论.md`：兼容旧调用，确认账号级核心判断、跨方向模型和内容资产学习口径。",
        "6. `减少AI味输出规则.md`：确认输出风格和禁用写法。",
        "7. `内容输出标准模板.md`：确认单条内容完整交付字段。",
        "8. `directions/{方向}/方向方法论总结.md`：调用方向方法论。",
        "9. `directions/{方向}/粗扫内容和选题.md`：寻找选题、对标内容和原链接。",
        "10. `directions/{方向}/cards/*.md`：需要已验证证据、案例和内容结构时读取。",
        "11. `directions/{方向}/transcripts/*`：只有视频证据争议、金句复核、文案不清时读取；图文/元数据卡不强求逐字稿。",
        "",
        "## 禁止动作",
        "",
        "- 不要全扫候选区。",
        "- 不要默认读取视频、音频、分镜图。",
        "- 不要学习评论正文，不从评论区提炼观点、痛点或话术。",
        "- 不要把粗学池里的非深学素材当成已验证事实；粗学池只用于发布内容层学习和选题线索。",
        "- 不要把同一套钩子、同一套故事、同一套观点机械复制给所有选题。",
        "",
        "## 已可调用方向",
        "",
        "| 方向 | 方法论 | 粗学与选题池 |",
        "|---|---|---|",
    ]
    for direction in directions:
        base = Path(direction["formal_direction_dir"])
        lines.append(f"| {direction['direction']} | {as_posix(base / '方向方法论总结.md')} | {as_posix(base / '粗扫内容和选题.md')} |")
    return "\n".join(lines) + "\n"


def _render_anti_ai_style(config: AccountIngestConfig, directions: list[dict[str, Any]] | None = None) -> str:
    lines = [
        f"# {config.account_name}减少AI味输出规则",
        "",
        "用途：账号级风格控制文件。必须从本账号正式单卡、方向总结、标题、正文/文案、话题和复盘反馈中归纳，不复制其他账号规则。",
        "",
        "## 核心原则",
        "",
        "- 使用本账号自己的标题、正文/文案、话题和内容结构特征；没有证据的风格判断先写为待补项。",
        "- 每条输出都要能回到正式学习卡、方向总结或粗学池来源；粗学池线索必须标注为粗学，不能当成已深学结论。",
        "- 保留具体场景、对象、动作、证据和边界，少用空泛总结词。",
        "- 不学习评论正文；评论数量只作为互动指标。",
        "- 不编造数据、身份、经历、产品效果、收入结果、医学结论或外部事实。",
        "",
        "## 禁用写法",
        "",
        "- 禁止把其他账号的口吻、故事、结构或禁用词复制到本账号。",
        "- 禁止只换关键词批量复用同一个钩子、故事、痛点和结论。",
        "- 禁止把单条爆款写成账号稳定规律；必须有多条证据或复盘反馈支撑。",
        "- 涉及效果、收益、健康、消费、投资等高风险表达时，禁止承诺结果。",
        "",
        "## 批量输出防偷懒规则",
        "",
        "- 同一批内容必须区分选题角度、开头方式、证据来源和收尾方式。",
        "- 每条都要标注借鉴学习卡、source_id、来源层级和原内容链接。",
        "- 如果只能找到粗学线索，输出中必须提示该内容仍需深学验证。",
        "",
    ]
    return "\n".join(lines)


def _source_link_label(config: AccountIngestConfig) -> str:
    platform = config.platform.lower()
    if "小红书" in config.platform or platform in {"xhs", "xiaohongshu"}:
        return "原小红书链接"
    return "原抖音链接"


def _render_account_content_template(config: AccountIngestConfig) -> str:
    source_link_label = _source_link_label(config)
    return "\n".join(
        [
            f"# {config.account_name}内容输出标准模板",
            "",
            "用途：账号通用的单条内容交付模板。括号内说明是给 AI 的生成要求，最终输出内容时不要展示说明。",
            "",
            "## 选题",
            "",
            "（说明：一句话说明这条内容解决什么问题，必须贴合账号方向。）",
            "",
            "## 发布标题",
            "",
            "（说明：按本账号标题习惯写，不要泛营销标题。）",
            "",
            "## 发布文案",
            "",
            "（说明：平台发布区文案，承接标题，不重复正文。）",
            "",
            "## 话题标签",
            "",
            "（说明：包含平台标签、方向标签、场景标签。）",
            "",
            "## 黄金3s",
            "",
            "（说明：开头第一句话/第一幕/第一屏，直接给问题、结果或冲突。）",
            "",
            "## 正文内容",
            "",
            "（说明：按该账号常用结构写完整内容。）",
            "",
            "## 互动收尾",
            "",
            "（说明：轻提问或收藏引导，不要强行硬广。）",
            "",
            "## 借鉴学习卡",
            "",
            "（说明：列文件名、source_id、来源层级；优先使用正式单卡，粗学线索必须标注为粗学。）",
            "",
            "## 对标知识库内容",
            "",
            "（说明：写清方向方法论、粗学与选题池或单卡路径。）",
            "",
            f"## {source_link_label}",
            "",
            "（说明：列对应原内容发布链接，不要编造链接。）",
            "",
        ]
    )


def _render_receipt(config: AccountIngestConfig, result: dict[str, Any], rows: list[dict[str, str]]) -> str:
    lines = [
        "# 入库回执",
        "",
        f"入库时间：{result['generated_at']}",
        f"账号：{config.account_name}",
        f"方向：{result['direction']}",
        f"单卡数：{result['card_count']}",
        f"逐字稿文件数：{result['transcript_file_count']}",
        "",
        "## 单卡来源",
        "",
        "| source_id | 标题 | 原链接 |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['source_id']} | {row['title']} | {row['source_url']} |")
    return "\n".join(lines) + "\n"


def _render_storage_manifest_md(manifest: dict[str, Any]) -> str:
    lines = [
        "# 存储分层清单",
        "",
        "| 分层 | 操作 | 文件 | 大小 | 说明 |",
        "|---|---|---|---:|---|",
    ]
    for item in manifest["items"]:
        lines.append(f"| {item['tier']} | {item['action']} | {item['path']} | {item['size_bytes']} | {item['note']} |")
    return "\n".join(lines) + "\n"


def _process_report_dir(root: Path, config: AccountIngestConfig, direction: str) -> Path:
    return runtime_path(root, "reports") / "account_ingest" / config.profile_id / direction


def _write_global_account_index(root: Path, config: AccountIngestConfig, direction_entries: list[dict[str, Any]]) -> None:
    payload = {"generated_at": datetime.now().isoformat(timespec="seconds"), "accounts": []}
    existing_path = root / config.global_account_index_json
    if existing_path.exists():
        try:
            payload = json.loads(existing_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"generated_at": datetime.now().isoformat(timespec="seconds"), "accounts": []}
    accounts = [account for account in payload.get("accounts", []) if account.get("account_id") != config.account_id]
    account = {
        "account_id": config.account_id,
        "account_name": config.account_name,
        "platform": config.platform,
        "formal_account_dir": as_posix(config.formal_account_dir),
        "directions": direction_entries,
        "knowledge_layers": [
            {"layer": "account_overview", "path": as_posix(config.formal_account_dir / "账号方法论总览.md"), "description": "账号整体方法和读取边界。"},
            {"layer": "account_status_overview", "path": as_posix(config.formal_account_dir / "账号概述.md"), "description": "账号学习状态、资料范围、证据地址和当前缺口。"},
            {"layer": "account_summary", "path": as_posix(config.formal_account_dir / "账号整体方法论.md"), "description": "账号级总结、跨方向模型和内容资产学习口径。"},
            {"layer": "content_usage", "path": as_posix(config.formal_account_dir / "内容生产使用说明.md"), "description": "会话外调用和内容生产读取规则。"},
            {"layer": "anti_ai_style", "path": as_posix(config.formal_account_dir / "减少AI味输出规则.md"), "description": "账号级风格控制和批量输出防雷同规则。"},
            {"layer": "account_content_template", "path": as_posix(config.formal_account_dir / "内容输出标准模板.md"), "description": "账号通用单条内容完整交付模板。"},
        ],
        "storage_policy": "热知识进账号中心；大体积媒体留原地址并登记为云端候选。",
    }
    for direction_entry in direction_entries:
        direction_dir = Path(direction_entry["formal_direction_dir"])
        account["knowledge_layers"].extend(
            [
                {"layer": "direction_method", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "方向方法论总结.md"), "description": "方向级方法论总结。"},
                {"layer": "single_cards", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "cards"), "description": "一视频一文件知识卡。"},
                {"layer": "rough_learning_pool", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "粗扫内容和选题.md"), "description": "方向全量素材的发布内容层粗学和选题池；不包含视频内容层。"},
                {"layer": "transcripts", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "transcripts"), "description": "视频证据回溯用逐字稿；图文或元数据卡不强求。"},
            ]
        )
    accounts.append(account)
    payload["generated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["accounts"] = accounts
    _write_json(root / config.global_account_index_json, payload)
    lines = [
        "# 账号知识总索引",
        "",
        "| 账号 | 平台 | 正式目录 | 已入库方向 |",
        "|---|---|---|---|",
    ]
    for item in accounts:
        directions = "、".join(direction["direction"] for direction in item.get("directions", []))
        lines.append(f"| {item['account_name']} | {item['platform']} | {item['formal_account_dir']} | {directions} |")
    (root / config.global_account_index_md).parent.mkdir(parents=True, exist_ok=True)
    (root / config.global_account_index_md).write_text("\n".join(lines) + "\n", encoding="utf-8")


def ingest_direction_package(root: Path, config: AccountIngestConfig, direction: str, approved_ids: set[str] | None = None) -> dict[str, Any]:
    root = root.resolve()
    source_dir = root / config.resolved_learned_base() / direction
    formal_dir = root / config.formal_account_dir / "directions" / direction
    formal_cards = formal_dir / "cards"
    formal_transcripts = formal_dir / "transcripts"
    rows = _card_rows(root, config, direction)
    if not rows:
        raise FileNotFoundError(f"No learned cards found for direction: {direction}")
    if approved_ids is not None:
        unapproved = sorted(row["source_id"] for row in rows if row["source_id"] not in approved_ids)
        if unapproved:
            raise ValueError(f"Cards not approved for formal ingest in {direction}: {unapproved}")
    if not _write_transformed(source_dir / "方向方法论总结.md", formal_dir / "方向方法论总结.md", _formalize_summary_text):
        raise FileNotFoundError(f"Missing required direction file: {source_dir / '方向方法论总结.md'}")
    rough_source = source_dir / "粗扫内容和选题.md"
    if not _write_transformed(rough_source, formal_dir / "粗扫内容和选题.md", lambda text: _formalize_rough_learning_pool_text(text, len(rows))):
        raise FileNotFoundError(f"Missing required direction file: {source_dir / '粗扫内容和选题.md'}")
    storage_items: list[dict[str, Any]] = []
    transcript_file_count = 0
    for row in rows:
        _write_transformed(source_dir / "cards" / row["card_filename"], formal_cards / row["card_filename"], _formalize_card_text)
        storage_items.append(_file_record(root, formal_cards / row["card_filename"], "formal_hot", "copied_to_formal_account", "单卡进入正式账号中心。"))
        records, transcript_paths = _artifact_records(root, config, row["source_id"])
        storage_items.extend(records)
        for transcript in transcript_paths:
            target = formal_transcripts / f"{row['source_id']}_{transcript.name}"
            _copy_file(transcript, target)
            transcript_file_count += 1
            storage_items.append(_file_record(root, target, "formal_hot", "copied_to_formal_account", "逐字稿正式副本。"))
    generated_at = datetime.now().isoformat(timespec="seconds")
    direction_entry = {
        "direction": direction,
        "status": "formal_ingested",
        "card_count": len(rows),
        "transcript_file_count": transcript_file_count,
        "formal_direction_dir": as_posix(formal_dir.relative_to(root)),
    }
    result = {
        "generated_at": generated_at,
        "profile_id": config.profile_id,
        "account_id": config.account_id,
        "account_name": config.account_name,
        **direction_entry,
    }
    manifest = {
        "generated_at": generated_at,
        "profile_id": config.profile_id,
        "account": config.account_name,
        "direction": direction,
        "policy": "正式热知识保留；大体积证据登记云端候选；候选区原件待迁移/删除审核。",
        "items": storage_items,
    }
    process_dir = _process_report_dir(root, config, direction)
    _copy_file(source_dir / "方向验收报告.md", process_dir / "方向验收报告.md")
    _write_json(process_dir / "存储分层清单.json", manifest)
    (process_dir / "存储分层清单.md").write_text(_render_storage_manifest_md(manifest), encoding="utf-8")
    (process_dir / "入库回执.md").write_text(_render_receipt(config, result, rows), encoding="utf-8")
    stale_direction_template = formal_dir / "出内容标准模板.md"
    if stale_direction_template.exists():
        stale_direction_template.unlink()
    return result


def _approved_ids_from_register(root: Path, audit_register: Path | None) -> set[str] | None:
    if audit_register is None:
        return None
    register_path = audit_register if audit_register.is_absolute() else root / audit_register
    payload = json.loads(register_path.read_text(encoding="utf-8"))
    if "cards" in payload:
        return {
            str(item.get("source_id", ""))
            for item in payload.get("cards", [])
            if item.get("machine_decision") == "pass"
        }
    return {str(item.get("source_id", "")) for item in payload.get("items", []) if item.get("decision") == "pass"}


def _approved_directions_from_register(root: Path, audit_register: Path) -> list[str]:
    register_path = audit_register if audit_register.is_absolute() else root / audit_register
    payload = json.loads(register_path.read_text(encoding="utf-8"))
    if "cards" in payload:
        return list(
            dict.fromkeys(
                str(item.get("direction", ""))
                for item in payload.get("cards", [])
                if item.get("machine_decision") == "pass" and item.get("direction")
            )
        )
    return list(
        dict.fromkeys(
            str(item.get("direction", ""))
            for item in payload.get("items", [])
            if item.get("decision") == "pass" and item.get("direction")
        )
    )


def ingest_directions(
    root: Path,
    config: AccountIngestConfig,
    directions: list[str],
    *,
    audit_register: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    ordered_directions = list(dict.fromkeys(directions))
    if not ordered_directions:
        raise ValueError("No directions supplied for formal ingest")
    approved_ids = _approved_ids_from_register(root, audit_register)
    previews: list[dict[str, Any]] = []
    for direction in ordered_directions:
        source_dir = root / config.resolved_learned_base() / direction
        for name in ("方向方法论总结.md", "粗扫内容和选题.md"):
            if not (source_dir / name).exists():
                raise FileNotFoundError(f"Missing required direction file: {source_dir / name}")
        rows = _card_rows(root, config, direction)
        if not rows:
            raise FileNotFoundError(f"No learned cards found for direction: {direction}")
        if approved_ids is not None:
            unapproved = sorted(row["source_id"] for row in rows if row["source_id"] not in approved_ids)
            if unapproved:
                raise ValueError(f"Cards not approved for formal ingest in {direction}: {unapproved}")
        transcript_count = sum(
            1
            for row in rows
            for name in ("transcript.srt", "transcript.json")
            if (_artifact_dir_for_source(root, config, row["source_id"]) / name).exists()
        )
        previews.append({"direction": direction, "card_count": len(rows), "transcript_file_count": transcript_count})
    if dry_run:
        return {
            "dry_run": True,
            "profile_id": config.profile_id,
            "direction_count": len(previews),
            "card_count": sum(item["card_count"] for item in previews),
            "transcript_file_count": sum(item["transcript_file_count"] for item in previews),
            "directions": previews,
        }
    results = [ingest_direction_package(root, config, direction, approved_ids) for direction in ordered_directions]
    direction_entries = [
        {
            "direction": result["direction"],
            "status": result["status"],
            "card_count": result["card_count"],
            "transcript_file_count": result["transcript_file_count"],
            "formal_direction_dir": result["formal_direction_dir"],
        }
        for result in results
    ]
    account_dir = root / config.formal_account_dir
    account_dir.mkdir(parents=True, exist_ok=True)
    (account_dir / "账号索引.md").write_text(_render_account_index(config, direction_entries), encoding="utf-8")
    (account_dir / "账号概述.md").write_text(_render_account_status_overview(config, direction_entries), encoding="utf-8")
    (account_dir / "账号方法论总览.md").write_text(_render_account_overview(config, direction_entries), encoding="utf-8")
    (account_dir / "账号整体方法论.md").write_text(_render_account_summary(config, direction_entries), encoding="utf-8")
    (account_dir / "内容生产使用说明.md").write_text(_render_content_usage(config, direction_entries), encoding="utf-8")
    (account_dir / "减少AI味输出规则.md").write_text(_render_anti_ai_style(config, direction_entries), encoding="utf-8")
    (account_dir / "内容输出标准模板.md").write_text(_render_account_content_template(config), encoding="utf-8")
    _write_global_account_index(root, config, direction_entries)
    mark_dirty(
        root,
        "formal_account_ingest",
        [str(config.formal_account_dir), str(config.global_account_index_json)],
    )
    return {
        "dry_run": False,
        "profile_id": config.profile_id,
        "direction_count": len(results),
        "card_count": sum(result["card_count"] for result in results),
        "transcript_file_count": sum(result["transcript_file_count"] for result in results),
        "directions": results,
    }


def _config_from_args(args: argparse.Namespace) -> AccountIngestConfig:
    return AccountIngestConfig(
        profile_id=args.profile,
        account_id=args.account_id,
        account_name=args.account_name,
        platform=args.platform,
        formal_account_dir=Path(args.formal_account_dir),
        learned_base=Path(args.learned_base) if args.learned_base else Path("10_Knowledge/candidates/learning_cards/learned_cards") / args.profile,
        artifacts_dir=Path(args.artifacts_dir),
        global_account_index_md=Path(args.global_account_index_md),
        global_account_index_json=Path(args.global_account_index_json),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest profile-based video learning directions into a formal account center.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--platform", default="抖音")
    parser.add_argument("--formal-account-dir", required=True)
    parser.add_argument("--learned-base")
    parser.add_argument("--artifacts-dir", default="00_System/runtime/cache/video_learning/video_artifacts")
    parser.add_argument("--global-account-index-md", default="10_Knowledge/evidence/index/account_knowledge_index.md")
    parser.add_argument("--global-account-index-json", default="10_Knowledge/evidence/index/account_knowledge_index.json")
    parser.add_argument("--direction", action="append")
    parser.add_argument("--all-approved", action="store_true")
    parser.add_argument("--audit-register")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    audit_register = Path(args.audit_register) if args.audit_register else None
    directions = args.direction or []
    if args.all_approved:
        if audit_register is None:
            parser.error("--all-approved requires --audit-register")
        directions = _approved_directions_from_register(root, audit_register)
    if not directions:
        parser.error("provide --direction or --all-approved")
    print(json.dumps(ingest_directions(root, _config_from_args(args), directions, audit_register=audit_register, dry_run=args.dry_run), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
