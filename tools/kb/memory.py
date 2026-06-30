from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from .schemas import (
    EVIDENCE_MEMORY_DIR,
    USER_SYNCABLE_MEMORY_DIR,
    as_posix,
    now_iso,
)


SENSITIVE_PATTERN = re.compile(
    r"(password|token|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|密钥|密码)",
    re.IGNORECASE,
)


CATEGORY_TARGETS = {
    "session_summary": "knowledge_evidence",
    "resolved_issue": "knowledge_evidence",
    "user_preference": "user_syncable",
    "decision": "user_syncable",
    "agent_boundary": "user_syncable",
    "workflow": "knowledge_evidence",
}

SIGNAL_RULES = (
    ("user_correction", ("不应该", "应该", "不能", "不要", "必须", "边界", "归到", "放在"), 2, "decision"),
    ("future_preference", ("以后", "下次", "以后都", "默认", "长期", "固定"), 2, "user_preference"),
    ("verified_solution", ("已验证", "通过", "测试通过", "解决了", "修复", "验证结果"), 2, "resolved_issue"),
    ("workflow_pattern", ("流程", "每次", "先", "再", "最后", "检查", "验收"), 1, "workflow"),
    ("agent_boundary", ("智能体", "agent", "登录表", "授权", "权限", "功能表"), 2, "agent_boundary"),
    ("layer_boundary", ("系统层", "用户层", "知识层", "私有", "可分享", "runtime", "运行态"), 2, "decision"),
    ("explicit_memory", ("记住", "沉淀", "写入记忆", "记忆候选", "会话总结"), 3, "session_summary"),
)

SKIP_HINTS = ("不用记", "不要记", "先不沉淀", "不用沉淀")
WEAKEN_HINTS = ("临时", "一次性", "随便")
CAPTURE_THRESHOLD = 3


def runtime_memory_dir(root: Path) -> Path:
    return root.resolve() / "00_System" / "runtime" / "memory"


def pending_path(root: Path) -> Path:
    return runtime_memory_dir(root) / "pending_session_extracts.jsonl"


def write_log_path(root: Path) -> Path:
    return runtime_memory_dir(root) / "memory_write_log.jsonl"


def contains_sensitive_text(value: str) -> bool:
    return bool(SENSITIVE_PATTERN.search(value))


def suggest_target(category: str) -> str:
    return CATEGORY_TARGETS.get(category, "runtime_pending")


def create_memory_candidate(
    root: Path,
    title: str,
    content: str,
    category: str = "session_summary",
    source: str = "manual",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    memory_id = f"mem_{uuid.uuid4().hex[:12]}"
    has_sensitive = contains_sensitive_text(f"{title}\n{content}")
    item = {
        "memory_id": memory_id,
        "title": title.strip(),
        "category": category,
        "status": "pending",
        "source": source,
        "target_layer": "user_private" if has_sensitive else suggest_target(category),
        "content": content.strip(),
        "created_at": now_iso(),
        "sensitive_warning": has_sensitive,
    }
    if extra:
        item.update(extra)
    path = pending_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"ok": True, "candidate": item, "pending_file": as_posix(path.relative_to(root))}


def evaluate_memory_capture(
    root: Path,
    text: str,
    source: str = "auto",
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    normalized = text.strip()
    if not normalized:
        return {"ok": True, "status": "skipped", "score": 0, "reasons": [], "skipped_reasons": ["empty_text"]}

    skipped_reasons = [hint for hint in SKIP_HINTS if hint in normalized]
    weaken_reasons = [hint for hint in WEAKEN_HINTS if hint in normalized]
    score = 0
    reasons: list[str] = []
    category_scores: dict[str, int] = {}
    for rule_id, terms, weight, category in SIGNAL_RULES:
        matched = [term for term in terms if term in normalized]
        if not matched:
            continue
        score += weight
        category_scores[category] = category_scores.get(category, 0) + weight
        reasons.append(f"{rule_id}:{','.join(matched[:3])}")

    has_sensitive = contains_sensitive_text(normalized)
    if has_sensitive:
        score += 1
        reasons.append("sensitive_boundary_required")
    if weaken_reasons:
        score = max(score - 2, 0)
        reasons.append(f"weaken:{','.join(weaken_reasons[:3])}")

    if skipped_reasons:
        return {
            "ok": True,
            "status": "skipped",
            "score": score,
            "reasons": reasons,
            "skipped_reasons": skipped_reasons,
            "weaken_reasons": weaken_reasons,
            "threshold": CAPTURE_THRESHOLD,
        }
    if score < CAPTURE_THRESHOLD:
        return {
            "ok": True,
            "status": "skipped",
            "score": score,
            "reasons": reasons,
            "skipped_reasons": ["below_threshold"],
            "weaken_reasons": weaken_reasons,
            "threshold": CAPTURE_THRESHOLD,
        }

    category = max(category_scores, key=category_scores.get) if category_scores else "session_summary"
    title = build_candidate_title(normalized, category)
    if dry_run:
        return {
            "ok": True,
            "status": "would_capture",
            "score": score,
            "threshold": CAPTURE_THRESHOLD,
            "category": category,
            "title": title,
            "target_layer": "user_private" if has_sensitive else suggest_target(category),
            "reasons": reasons,
            "sensitive_warning": has_sensitive,
        }
    result = create_memory_candidate(
        root,
        title,
        normalized,
        category=category,
        source=source,
        extra={
            "capture_mode": "auto_evaluated",
            "capture_score": score,
            "capture_threshold": CAPTURE_THRESHOLD,
            "capture_reasons": reasons,
        },
    )
    return {
        "ok": True,
        "status": "captured",
        "score": score,
        "threshold": CAPTURE_THRESHOLD,
        "reasons": reasons,
        **result,
    }


def build_candidate_title(text: str, category: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    compact = compact.replace("\n", " ")
    if len(compact) > 36:
        compact = compact[:36].rstrip() + "..."
    labels = {
        "resolved_issue": "问题复盘",
        "user_preference": "用户偏好",
        "decision": "项目决策",
        "agent_boundary": "智能体边界",
        "workflow": "流程记忆",
        "session_summary": "会话摘要",
    }
    return f"{labels.get(category, '记忆候选')}：{compact}"


def list_memory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rows = read_jsonl(pending_path(root))
    pending = [item for item in rows if item.get("status") == "pending"]
    locations = {
        "memory_entry": "20_User/syncable/memory/记忆总入口.md",
        "user_syncable": USER_SYNCABLE_MEMORY_DIR,
        "knowledge_evidence": EVIDENCE_MEMORY_DIR,
        "runtime_pending": "00_System/runtime/memory/pending_session_extracts.jsonl",
        "agent_registry": "20_User/syncable/agents/agent_registry.md",
        "private_agent_auth_template": "20_User/private/agents/agent_auth_registry.template.md",
        "private_agent_auth": "20_User/private/agents/agent_auth_registry.md",
        "private_memory_constraints": "20_User/private/memory/private_constraints.md",
    }
    existing = {name: (root / relative).exists() for name, relative in locations.items()}
    return {
        "ok": True,
        "pending_count": len(pending),
        "pending_sensitive_count": sum(1 for item in pending if item.get("sensitive_warning")),
        "total_candidate_count": len(rows),
        "reviewed_candidate_count": len(rows) - len(pending),
        "locations": locations,
        "existing": existing,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows
