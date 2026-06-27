from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.kb.runtime import mark_dirty


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


def _artifact_records(root: Path, config: AccountIngestConfig, source_id: str) -> tuple[list[dict[str, Any]], list[Path]]:
    artifact_dir = root / config.artifacts_dir / f"douyin_{source_id}"
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
        "1. `账号方法论总览.md`：先看账号整体方法。",
        "2. `内容生产使用说明.md`：会话外调用时先按这里确定读取路径和输出边界。",
        "3. `减少AI味输出规则.md`：写选题、文案、口播前必须读取。",
        "4. `内容输出标准模板.md`：按账号通用字段输出选题和文案。",
        "5. `directions/{方向}/方向方法论总结.md`：按方向调用方法论。",
        "6. `directions/{方向}/cards/`：需要证据时回到单卡。",
        "7. `directions/{方向}/粗扫内容和选题.md`：写选题和延展内容时调用。",
        "8. `directions/{方向}/transcripts/`：观点争议或证据不清时回溯逐字稿。",
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
            "- 粗扫文件用于发现高频主题、可延展选题和账号内容规律。",
            "- 逐字稿只在证据核查、观点争议、金句复核时读取。",
            "- 视频、音频、分镜图属于冷证据，不默认读取。",
        ]
    )
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
        "3. `账号方法论总览.md`：确认账号定位和使用边界。",
        "4. `减少AI味输出规则.md`：确认输出风格和禁用写法。",
        "5. `内容输出标准模板.md`：确认账号通用输出字段。",
        "6. `directions/{方向}/方向方法论总结.md`：调用方向方法论。",
        "7. `directions/{方向}/粗扫内容和选题.md`：寻找选题、对标内容和原链接。",
        "8. `directions/{方向}/cards/*.md`：需要已验证证据、案例和口播结构时读取。",
        "9. `directions/{方向}/transcripts/*`：只有观点争议、金句复核、证据不清时读取。",
        "",
        "## 禁止动作",
        "",
        "- 不要全扫候选区。",
        "- 不要默认读取视频、音频、分镜图。",
        "- 不要把粗扫候选内容当成已验证事实；粗扫只能作为选题雷达和候补线索。",
        "- 不要把同一套钩子、同一套故事、同一套观点机械复制给所有选题。",
        "",
        "## 已可调用方向",
        "",
        "| 方向 | 方法论 | 粗扫 |",
        "|---|---|---|",
    ]
    for direction in directions:
        base = Path(direction["formal_direction_dir"])
        lines.append(f"| {direction['direction']} | {as_posix(base / '方向方法论总结.md')} | {as_posix(base / '粗扫内容和选题.md')} |")
    return "\n".join(lines) + "\n"


def _render_anti_ai_style(config: AccountIngestConfig) -> str:
    return "\n".join(
        [
            f"# {config.account_name}减少AI味输出规则",
            "",
            "用途：账号级风格控制文件，跟随账号持续更新。每完成一个方向入库，都应该基于新单卡修订本文件。",
            "",
            "## 核心原则",
            "",
            "- 像人在解释一个具体问题，不像 AI 在总结一类概念。",
            "- 先给判断，再给原因，再给行动；不要堆抽象名词。",
            "- 用普通人场景承接方法论。",
            "- 允许短句、停顿和反问；不要把每段都写成整齐排比。",
            "- 案例要具体，但不要编造数据、身份、经历和外部事实。",
            "",
            "## 批量输出防偷懒规则",
            "",
            "- 禁止同一批选题使用同一种黄金3秒。",
            "- 禁止所有选题都复用同一个故事、同一个痛点、同一个结论。",
            "- 禁止只换关键词，不换角度。",
            "",
        ]
    )


def _render_account_content_template(config: AccountIngestConfig) -> str:
    return "\n".join(
        [
            f"# {config.account_name}内容输出标准模板",
            "",
            "用途：账号通用模板。字段可以按用户要求增减，但不能省略证据来源。",
            "",
            "## 1. 选题输出模板",
            "",
            "| 字段 | 要求 |",
            "|---|---|",
            "| 选题标题 | 一句话表达具体问题或具体收益，不写空泛大词。 |",
            "| 对应方法论 | 写清来自方向方法论中的哪个模型。 |",
            "| 受众痛点 | 写具体人群的具体卡点。 |",
            "| 钩子角度 | 说明黄金3秒角度。 |",
            "| 核心观点 | 一句话讲清这条内容要证明什么。 |",
            "| 可引用案例 | 优先引用正式单卡；粗扫线索必须标注为粗扫。 |",
            "| 对标知识库内容 | 写文件名、source_id、来源层级。 |",
            "| 原抖音链接 | 附上原视频链接。 |",
            "",
            "## 2. 文案输出模板",
            "",
            "```text",
            "黄金3s：",
            "完整文案：",
            "互动收尾：",
            "证据来源：",
            "- 对标知识库内容：文件名/source_id/来源层级",
            "- 原抖音链接：链接",
            "```",
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
            {"layer": "content_usage", "path": as_posix(config.formal_account_dir / "内容生产使用说明.md"), "description": "会话外调用和内容生产读取规则。"},
            {"layer": "anti_ai_style", "path": as_posix(config.formal_account_dir / "减少AI味输出规则.md"), "description": "账号级风格控制和批量输出防雷同规则。"},
            {"layer": "account_content_template", "path": as_posix(config.formal_account_dir / "内容输出标准模板.md"), "description": "账号通用选题和文案输出模板。"},
        ],
        "storage_policy": "热知识进账号中心；大体积媒体留原地址并登记为云端候选。",
    }
    for direction_entry in direction_entries:
        direction_dir = Path(direction_entry["formal_direction_dir"])
        account["knowledge_layers"].extend(
            [
                {"layer": "direction_method", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "方向方法论总结.md"), "description": "方向级方法论总结。"},
                {"layer": "single_cards", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "cards"), "description": "一视频一文件知识卡。"},
                {"layer": "rough_scan", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "粗扫内容和选题.md"), "description": "高频主题和选题规律。"},
                {"layer": "transcripts", "direction": direction_entry["direction"], "path": as_posix(direction_dir / "transcripts"), "description": "证据回溯用逐字稿。"},
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
    if not _copy_file(source_dir / "粗扫内容和选题.md", formal_dir / "粗扫内容和选题.md"):
        raise FileNotFoundError(f"Missing required direction file: {source_dir / '粗扫内容和选题.md'}")
    _copy_file(source_dir / "方向验收报告.md", formal_dir / "方向验收报告.md")
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
    _write_json(formal_dir / "存储分层清单.json", manifest)
    (formal_dir / "存储分层清单.md").write_text(_render_storage_manifest_md(manifest), encoding="utf-8")
    (formal_dir / "入库回执.md").write_text(_render_receipt(config, result, rows), encoding="utf-8")
    stale_direction_template = formal_dir / "出内容标准模板.md"
    if stale_direction_template.exists():
        stale_direction_template.unlink()
    return result


def _approved_ids_from_register(root: Path, audit_register: Path | None) -> set[str] | None:
    if audit_register is None:
        return None
    register_path = audit_register if audit_register.is_absolute() else root / audit_register
    payload = json.loads(register_path.read_text(encoding="utf-8"))
    return {str(item.get("source_id", "")) for item in payload.get("items", []) if item.get("decision") == "pass"}


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
            if (root / config.artifacts_dir / f"douyin_{row['source_id']}" / name).exists()
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
    (account_dir / "账号方法论总览.md").write_text(_render_account_overview(config, direction_entries), encoding="utf-8")
    (account_dir / "内容生产使用说明.md").write_text(_render_content_usage(config, direction_entries), encoding="utf-8")
    (account_dir / "减少AI味输出规则.md").write_text(_render_anti_ai_style(config), encoding="utf-8")
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
        register_path = audit_register if audit_register.is_absolute() else root / audit_register
        payload = json.loads(register_path.read_text(encoding="utf-8"))
        directions = list(dict.fromkeys(str(item.get("direction", "")) for item in payload.get("items", []) if item.get("decision") == "pass"))
    if not directions:
        parser.error("provide --direction or --all-approved")
    print(json.dumps(ingest_directions(root, _config_from_args(args), directions, audit_register=audit_register, dry_run=args.dry_run), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
