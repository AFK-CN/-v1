from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


DEFAULT_SELECTED_DIR = Path("01_Case_Cleaning/video_learning/selected_deep_cards")
DEFAULT_ARTIFACTS_DIR = Path("01_Case_Cleaning/video_learning/video_artifacts")

SECTION_TITLES = [
    "为什么值得学习",
    "核心观点",
    "内容结构",
    "表达素材与金句提炼",
    "视频层学习",
    "可复用案例",
    "可复用方法论",
    "可复用模板",
    "证据缺口/后续问题",
    "入库判断",
]
REQUIRED_METADATA = ["source_id", "原视频链接", "账号", "平台", "主方向", "辅方向", "学习批次", "状态"]
KEY_SIMILARITY_SECTIONS = ["核心观点", "可复用方法论", "可复用模板", "证据缺口/后续问题"]
ACTION_WORDS = {
    "先",
    "再",
    "记录",
    "验证",
    "拆",
    "写",
    "做",
    "问",
    "检查",
    "对照",
    "选择",
    "建立",
    "输出",
    "复盘",
    "调整",
    "提取",
    "列出",
    "找到",
    "判断",
    "测试",
    "发布",
    "交付",
    "回顾",
    "学习",
    "创造",
    "分享",
    "收集",
    "筛选",
    "改进",
    "校准",
    "理解",
    "连接",
    "生成",
    "落地",
}


@dataclass(frozen=True)
class AuditConfig:
    profile_id: str
    learned_base: Path
    scope_path: Path
    selected_dir: Path = DEFAULT_SELECTED_DIR
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR
    audit_dir: Path | None = None
    report_title: str | None = None

    @classmethod
    def for_profile(cls, profile_id: str) -> "AuditConfig":
        learned_base = Path("01_Case_Cleaning/video_learning/learned_cards") / profile_id
        return cls(
            profile_id=profile_id,
            learned_base=learned_base,
            scope_path=Path("01_Case_Cleaning/content_rough_scan") / profile_id / "deep_learning_scope.json",
            audit_dir=learned_base / "audit",
            report_title=f"{profile_id} 深度学习机器审计报告",
        )

    def resolved_audit_dir(self) -> Path:
        return self.audit_dir or self.learned_base / "audit"


@dataclass
class CardDocument:
    path: Path
    title: str
    metadata: dict[str, str]
    sections: dict[str, str]
    raw_text: str

    @property
    def source_id(self) -> str:
        return self.metadata.get("source_id", "")

    @property
    def direction(self) -> str:
        return self.metadata.get("主方向", "")


@dataclass
class EvidenceRecord:
    transcript_available: bool = False
    selected_card_available: bool = False
    scene_status: str = ""
    selected_card_path: str = ""
    transcript_paths: list[str] = field(default_factory=list)


@dataclass
class CardAudit:
    source_id: str
    direction: str
    card_path: str
    structure_errors: list[str] = field(default_factory=list)
    depth_risks: list[str] = field(default_factory=list)
    evidence_risks: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    machine_decision: str = "review"


@dataclass
class SimilarityPair:
    left_source_id: str
    right_source_id: str
    left_path: str
    right_path: str
    score: float
    section_scores: dict[str, float]


@dataclass
class RepeatedPassage:
    text: str
    normalized_text: str
    source_ids: list[str]
    card_paths: list[str]


def _normalize(text: str) -> str:
    text = re.sub(r"```.*?```", lambda match: match.group(0).replace("```text", "").replace("```", ""), text, flags=re.S)
    text = re.sub(r"source_id\s*[:：]\s*\d+", "", text)
    text = re.sub(r"主方向\s*[:：]\s*[^\n]+", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text.lower())
    return text


def parse_card(path: Path) -> CardDocument:
    text = path.read_text(encoding="utf-8", errors="ignore")
    title_match = re.search(r"^#\s*视频深度学习卡[:：]\s*(.+)$", text, re.M)
    title = title_match.group(1).strip() if title_match else ""
    metadata: dict[str, str] = {}
    for line in text.splitlines()[:45]:
        match = re.match(r"^(source_id|原视频链接|账号|平台|主方向|辅方向|学习批次|状态)[:：]\s*(.*)$", line.strip())
        if match:
            metadata[match.group(1)] = match.group(2).strip()
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+\d+\.\s+(.+?)\s*$", text, re.M))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[start:end].strip()
    return CardDocument(path=path, title=title, metadata=metadata, sections=sections, raw_text=text)


def _meaningful_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        value = stripped.strip(" -*`\t")
        if value:
            lines.append(value)
    return lines


def audit_card(card: CardDocument, evidence: EvidenceRecord) -> CardAudit:
    structure_errors: list[str] = []
    depth_risks: list[str] = []
    evidence_risks: list[str] = []
    for field_name in REQUIRED_METADATA:
        if not card.metadata.get(field_name):
            structure_errors.append(f"missing_metadata:{field_name}")
    for section in SECTION_TITLES:
        if section not in card.sections:
            structure_errors.append(f"missing_section:{section}")
        elif not _meaningful_lines(card.sections[section]):
            structure_errors.append(f"empty_section:{section}")
    if "收尾/互动引导" not in card.sections.get("内容结构", ""):
        structure_errors.append("missing_field:收尾/互动引导")

    core = card.sections.get("核心观点", "")
    method = card.sections.get("可复用方法论", "")
    template = card.sections.get("可复用模板", "")
    ingest = card.sections.get("入库判断", "")
    if core and _normalize(core) == _normalize(card.title):
        depth_risks.append("core_repeats_title")
    if method and not any(word in method for word in ACTION_WORDS):
        depth_risks.append("method_lacks_action")
    if template and len(_meaningful_lines(template)) < 2:
        depth_risks.append("template_too_shallow")
    if ingest and len(_normalize(ingest)) < 18:
        depth_risks.append("ingest_judgement_too_shallow")
    for section_name in ("核心观点", "可复用案例", "可复用方法论"):
        content = card.sections.get(section_name, "")
        if content and len(_normalize(content)) < 24:
            depth_risks.append(f"section_too_short:{section_name}")

    video_layer = card.sections.get("视频层学习", "")
    if evidence.scene_status.endswith("scene_failed") and re.search(r"切换到|字幕变成|红色字幕|办公室|地铁|特写|远景", video_layer):
        evidence_risks.append("unsupported_scene_detail")
    if not evidence.transcript_available:
        evidence_risks.append("transcript_missing")
    if not evidence.selected_card_available:
        evidence_risks.append("selected_card_missing")

    machine_decision = "pass" if not (structure_errors or depth_risks or evidence_risks) else "review"
    return CardAudit(
        source_id=card.source_id,
        direction=card.direction,
        card_path=card.path.as_posix(),
        structure_errors=sorted(set(structure_errors)),
        depth_risks=sorted(set(depth_risks)),
        evidence_risks=sorted(set(evidence_risks)),
        evidence=asdict(evidence),
        machine_decision=machine_decision,
    )


def _section_similarity(left: str, right: str) -> float:
    left_norm = _normalize(left)
    right_norm = _normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm, autojunk=False).ratio()


def text_support_score(claim: str, evidence: str) -> float:
    claim_norm = _normalize(claim)
    evidence_norm = _normalize(evidence)
    if len(claim_norm) < 2 or len(evidence_norm) < 2:
        return 0.0
    claim_pairs = {claim_norm[index : index + 2] for index in range(len(claim_norm) - 1)}
    evidence_pairs = {evidence_norm[index : index + 2] for index in range(len(evidence_norm) - 1)}
    return len(claim_pairs & evidence_pairs) / len(claim_pairs) if claim_pairs else 0.0


def find_similarity_pairs(cards: list[CardDocument], threshold: float = 0.92) -> list[SimilarityPair]:
    pairs: list[SimilarityPair] = []
    for left_index, left in enumerate(cards):
        for right in cards[left_index + 1 :]:
            scores = {
                section: _section_similarity(left.sections.get(section, ""), right.sections.get(section, ""))
                for section in KEY_SIMILARITY_SECTIONS
            }
            passing_scores = sorted((value for value in scores.values() if value >= threshold), reverse=True)
            score = passing_scores[2] if len(passing_scores) >= 3 else 0.0
            semantic_anchor = max(scores.get("核心观点", 0.0), scores.get("可复用方法论", 0.0))
            if score >= threshold and semantic_anchor >= 0.97:
                pairs.append(
                    SimilarityPair(
                        left_source_id=left.source_id,
                        right_source_id=right.source_id,
                        left_path=left.path.as_posix(),
                        right_path=right.path.as_posix(),
                        score=round(score, 4),
                        section_scores={key: round(value, 4) for key, value in scores.items()},
                    )
                )
    return sorted(pairs, key=lambda pair: pair.score, reverse=True)


def find_repeated_passages(cards: list[CardDocument], min_cards: int = 3) -> list[RepeatedPassage]:
    occurrences: dict[str, dict[str, Any]] = {}
    for card in cards:
        seen_in_card: set[str] = set()
        for section in card.sections.values():
            for line in _meaningful_lines(section):
                normalized = _normalize(line)
                if len(normalized) < 24 or normalized in {"未明确", "暂无明确证据"} or normalized in seen_in_card:
                    continue
                seen_in_card.add(normalized)
                entry = occurrences.setdefault(normalized, {"text": line, "source_ids": [], "card_paths": []})
                entry["source_ids"].append(card.source_id)
                entry["card_paths"].append(card.path.as_posix())
    passages = [
        RepeatedPassage(
            text=value["text"],
            normalized_text=normalized,
            source_ids=value["source_ids"],
            card_paths=value["card_paths"],
        )
        for normalized, value in occurrences.items()
        if len(value["source_ids"]) >= min_cards
    ]
    return sorted(passages, key=lambda passage: (-len(passage.source_ids), passage.normalized_text))


def _evidence_for(root: Path, config: AuditConfig, source_id: str) -> EvidenceRecord:
    selected_path = root / config.selected_dir / f"douyin_{source_id}.md"
    artifact_dir = root / config.artifacts_dir / f"douyin_{source_id}"
    transcript_paths = [path for path in (artifact_dir / "transcript.json", artifact_dir / "transcript.srt") if path.exists()]
    scene_status = ""
    if selected_path.exists():
        match = re.search(r"video_analysis_status:\s*([^\n]+)", selected_path.read_text(encoding="utf-8", errors="ignore"))
        scene_status = match.group(1).strip() if match else ""
    return EvidenceRecord(
        transcript_available=bool(transcript_paths),
        selected_card_available=selected_path.exists(),
        scene_status=scene_status,
        selected_card_path=selected_path.relative_to(root).as_posix() if selected_path.exists() else "",
        transcript_paths=[path.relative_to(root).as_posix() for path in transcript_paths],
    )


def _load_scope(root: Path, config: AuditConfig) -> list[dict[str, Any]]:
    payload = json.loads((root / config.scope_path).read_text(encoding="utf-8"))
    return payload.get("items", payload) if isinstance(payload, dict) else payload


def run_audit(root: Path, config: AuditConfig) -> dict[str, Any]:
    root = root.resolve()
    scope = _load_scope(root, config)
    cards: list[CardDocument] = []
    audits: list[CardAudit] = []
    missing_paths: list[str] = []
    for item in scope:
        card_path = str(item.get("card_path", ""))
        path = root / card_path
        if not card_path or not path.exists():
            missing_paths.append(str(item.get("source_id", "")))
            continue
        card = parse_card(path)
        cards.append(card)
        audits.append(audit_card(card, _evidence_for(root, config, card.source_id)))

    pairs = find_similarity_pairs(cards)
    repeated_passages = find_repeated_passages(cards)
    pair_counts: dict[str, int] = {}
    for pair in pairs:
        pair_counts[pair.left_source_id] = pair_counts.get(pair.left_source_id, 0) + 1
        pair_counts[pair.right_source_id] = pair_counts.get(pair.right_source_id, 0) + 1
    repeated_counts: dict[str, int] = {}
    for passage in repeated_passages:
        for source_id in passage.source_ids:
            repeated_counts[source_id] = repeated_counts.get(source_id, 0) + 1
    for audit in audits:
        if pair_counts.get(audit.source_id):
            audit.depth_risks.append(f"high_similarity_pairs:{pair_counts[audit.source_id]}")
        if repeated_counts.get(audit.source_id):
            audit.depth_risks.append(f"repeated_passages:{repeated_counts[audit.source_id]}")
        if audit.depth_risks:
            audit.depth_risks = sorted(set(audit.depth_risks))
            audit.machine_decision = "review"

    output_dir = root / config.resolved_audit_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile_id": config.profile_id,
        "scope_path": config.scope_path.as_posix(),
        "learned_base": config.learned_base.as_posix(),
        "scope_count": len(scope),
        "card_count": len(cards),
        "missing_card_source_ids": missing_paths,
        "machine_pass_count": sum(a.machine_decision == "pass" for a in audits),
        "machine_review_count": sum(a.machine_decision != "pass" for a in audits),
        "similarity_pair_count": len(pairs),
        "repeated_passage_count": len(repeated_passages),
        "cards": [asdict(audit) for audit in audits],
    }
    (output_dir / "machine_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "similarity_pairs.json").write_text(json.dumps([asdict(pair) for pair in pairs], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "repeated_passages.json").write_text(json.dumps([asdict(passage) for passage in repeated_passages], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    title = config.report_title or f"{config.profile_id} 深度学习机器审计报告"
    lines = [
        f"# {title}",
        "",
        f"生成时间：{payload['generated_at']}",
        f"profile：{payload['profile_id']}",
        f"权威范围：{payload['scope_count']}",
        f"找到卡片：{payload['card_count']}",
        f"机器通过：{payload['machine_pass_count']}",
        f"需人工复核：{payload['machine_review_count']}",
        f"高相似卡对：{payload['similarity_pair_count']}",
        f"跨卡重复长句：{payload['repeated_passage_count']}",
        "",
        "| source_id | 方向 | 机器结论 | 结构问题 | 深度风险 | 证据风险 |",
        "|---|---|---|---|---|---|",
    ]
    for audit in audits:
        lines.append(
            f"| {audit.source_id} | {audit.direction} | {audit.machine_decision} | "
            f"{'；'.join(audit.structure_errors) or '-'} | {'；'.join(audit.depth_risks) or '-'} | "
            f"{'；'.join(audit.evidence_risks) or '-'} |"
        )
    (output_dir / "machine_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def _config_from_args(args: argparse.Namespace) -> AuditConfig:
    config = AuditConfig.for_profile(args.profile)
    if args.scope:
        config = AuditConfig(**{**asdict(config), "scope_path": Path(args.scope)})
    if args.learned_base:
        config = AuditConfig(**{**asdict(config), "learned_base": Path(args.learned_base)})
    if args.selected_dir:
        config = AuditConfig(**{**asdict(config), "selected_dir": Path(args.selected_dir)})
    if args.artifacts_dir:
        config = AuditConfig(**{**asdict(config), "artifacts_dir": Path(args.artifacts_dir)})
    if args.audit_dir:
        config = AuditConfig(**{**asdict(config), "audit_dir": Path(args.audit_dir)})
    if args.report_title:
        config = AuditConfig(**{**asdict(config), "report_title": args.report_title})
    return config


def main(default_profile: str = "jianghushuo") -> int:
    parser = argparse.ArgumentParser(description="Audit profile-based video deep-learning cards for structure, depth, similarity and evidence risks.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", default=default_profile)
    parser.add_argument("--scope")
    parser.add_argument("--learned-base")
    parser.add_argument("--selected-dir")
    parser.add_argument("--artifacts-dir")
    parser.add_argument("--audit-dir")
    parser.add_argument("--report-title")
    parser.add_argument("--register")
    args = parser.parse_args()
    result = run_audit(Path(args.root), _config_from_args(args))
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "profile_id",
                    "scope_count",
                    "card_count",
                    "machine_pass_count",
                    "machine_review_count",
                    "similarity_pair_count",
                    "repeated_passage_count",
                    "missing_card_source_ids",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["card_count"] == result["scope_count"] and not result["missing_card_source_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
