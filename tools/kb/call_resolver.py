from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .account_skills import resolve_account_skill
from .candidate_search import search_candidates
from .formal_search import search_formal
from .schemas import EVIDENCE_INDEX_DIR, SYSTEM_CONFIG_DIR, SYSTEM_INDEX_DIR


SEMANTIC_ROUTE_PATTERNS: dict[str, tuple[tuple[str, str], ...]] = {
    "content_processing": (
        ("语义:处理资料", r"(?:处理|清洗|扫描|粗学|下载|解析).{0,16}(?:资料|数据|视频|图文|链接|文件|内容)"),
        ("语义:资料处理", r"(?:资料|数据|视频|图文|链接|文件).{0,16}(?:处理|清洗|扫描|粗学|下载|解析)"),
    ),
    "account_learning": (
        ("语义:学习账号", r"(?:学习|深学|继续学|学完).{0,20}(?:账号|视频|图文|证据|资料)"),
        ("语义:账号学习", r"(?:账号|视频|图文|证据|资料).{0,20}(?:学习|深学|继续学|学完)"),
    ),
    "topic_generation": (("语义:生成选题", r"(?:生成|提供|给我|想要|出).{0,8}(?:选题|灵感)"),),
    "script_generation": (("语义:生产内容", r"(?:写|生成|生产).{0,12}(?:文案|口播|脚本|图文|标题|封面|内容)"),),
    "content_review": (("语义:复盘反馈", r"(?:复盘|诊断|分析).{0,16}(?:内容|数据|截图|表格|指标|评论|反馈)?"),),
    "formal_retrieval": (
        ("语义:正式知识检索", r"(?:查询|搜索|检索|查找).{0,8}(?:正式知识|知识库|方法|证据)"),
    ),
}

EXPLICIT_CANDIDATE_MARKERS = ("候选证据", "追溯候选", "检索候选", "从候选", "查候选")
OUTPUT_FORM_MARKERS = ("文案", "口播", "脚本", "图文", "标题", "封面", "视频", "长文案")
FEEDBACK_MARKERS = ("截图", "表格", "数据", "指标", "评论", "反馈", "播放", "点赞", "收藏", "人工")
SOURCE_SCOPE_MARKERS = (
    "链接",
    "sqlite",
    "数据库",
    "nas",
    "本地",
    "目录",
    "文件",
    "视频",
    "图文",
    "这批",
    "这些",
    "已处理",
    "处理好",
    "证据",
    "逐字稿",
    "ocr",
)


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default
    return payload if isinstance(payload, dict) else default


def resolve_call(root: Path, text: str) -> dict[str, Any]:
    root = root.resolve()
    prompt = text.strip()
    controller = read_json(root / SYSTEM_INDEX_DIR / "controller_routes.json", {"routes": []})
    account_index = read_json(root / EVIDENCE_INDEX_DIR / "account_knowledge_index.json", {"accounts": []})
    contracts = read_json(root / SYSTEM_CONFIG_DIR / "output_contracts.json", {"contracts": []})

    route_result = resolve_route_result(prompt, controller.get("routes", []))
    route = route_result["route"]
    if route_result["status"] == "ambiguous":
        return {
            "ok": False,
            "errors": ["route_ambiguous"],
            "input": prompt,
            "route_id": "",
            "route_candidates": route_result["candidates"],
            "clarification_questions": ["请说明要处理资料、学习账号、出选题、写内容、复盘还是系统审计。"],
            "account_name": "",
            "direction": "",
            "requested_count": resolve_requested_count(prompt),
            "read_paths": [],
            "missing_read_paths": [],
            "search": {"items": [], "count": 0},
            "output_contract": {},
            "knowledge_boundary": {
                "formal_account_knowledge": "not_resolved",
                "candidate_assets": "not_read",
                "raw_data": "blocked_by_default",
            },
        }
    if not route:
        return {
            "ok": False,
            "errors": ["route_not_resolved"],
            "input": prompt,
            "route_id": "",
            "route_candidates": [],
            "clarification_questions": ["请说明要处理资料、学习账号、出选题、写内容、复盘还是系统审计。"],
            "account_name": "",
            "direction": "",
            "requested_count": resolve_requested_count(prompt),
            "read_paths": [],
            "missing_read_paths": [],
            "search": {"items": [], "count": 0},
            "output_contract": {},
            "knowledge_boundary": {
                "formal_account_knowledge": "not_resolved",
                "candidate_assets": "not_read",
                "raw_data": "blocked_by_default",
            },
        }
    account = resolve_account(prompt, account_index.get("accounts", []))
    direction = resolve_direction(prompt, account)
    requested_count = resolve_requested_count(prompt)
    account_name = str(account.get("account_name", "")) if account else ""
    route_id = str(route.get("id", ""))
    query = extract_query(prompt, route) if route_id == "formal_retrieval" else direction or extract_query(prompt, route)
    account_skill = resolve_account_skill(root, prompt) if route_id in {"topic_generation", "script_generation"} else {}
    max_questions = int(controller.get("clarification_policy", {}).get("max_questions") or 3)
    clarification_questions = resolve_clarification_questions(
        prompt,
        route_id,
        account,
        account_skill,
        direction,
    )[: max(max_questions, 1)]
    if route_id == "formal_retrieval" and not query:
        clarification_questions = ["要检索哪个主题、方法或问题？"]
    if clarification_questions:
        read_status = resolve_read_path_status(root, route, account, direction, account_skill)
        contract = next(
            (item for item in contracts.get("contracts", []) if isinstance(item, dict) and item.get("route_id") == route_id),
            {},
        )
        return {
            "ok": False,
            "errors": ["missing_required_input"],
            "input": prompt,
            "route_id": route_id,
            "route_candidates": [{"route_id": route_id, "matched_triggers": route_result["matched_triggers"]}],
            "clarification_questions": clarification_questions,
            "account_name": account_name,
            "direction": direction,
            "requested_count": explicit_requested_count(prompt) if route_id == "topic_generation" else requested_count,
            "read_paths": read_status["read_paths"],
            "missing_read_paths": read_status["missing_read_paths"],
            "search": {"status": "not_run_missing_input", "query": query, "count": 0, "items": []},
            "output_contract": contract,
            "account_skill": account_skill,
            "knowledge_boundary": {
                "formal_account_knowledge": "allowed" if account else "not_resolved",
                "candidate_assets": "not_read",
                "raw_data": "blocked_by_default",
            },
        }
    explicit_candidate_search = any(marker in prompt for marker in EXPLICIT_CANDIDATE_MARKERS)
    if route_id == "formal_retrieval":
        search = search_formal(
            root,
            query=query,
            account=account_name,
            direction=direction,
            limit=requested_count,
        )
    elif route_id in {"topic_generation", "script_generation"} and explicit_candidate_search:
        search = search_candidates(
            root,
            query=query,
            account_name=account_name,
            direction=direction,
            limit=requested_count,
        )
        search = compact_candidate_search(search)
    else:
        search = {
            "status": "not_requested" if route_id in {"topic_generation", "script_generation"} else "not_applicable",
            "query": query,
            "count": 0,
            "items": [],
        }
    contract = next(
        (item for item in contracts.get("contracts", []) if isinstance(item, dict) and item.get("route_id") == route_id),
        {},
    )
    read_status = resolve_read_path_status(root, route, account, direction, account_skill)
    return {
        "ok": True,
        "errors": [],
        "input": prompt,
        "route_id": route_id,
        "route_candidates": [{"route_id": route_id, "matched_triggers": route_result["matched_triggers"]}],
        "clarification_questions": [],
        "account_name": account_name,
        "direction": direction,
        "requested_count": requested_count,
        "read_paths": read_status["read_paths"],
        "missing_read_paths": read_status["missing_read_paths"],
        "search": search,
        "output_contract": contract,
        "account_skill": account_skill,
        "knowledge_boundary": {
            "formal_account_knowledge": "allowed" if account or route_id == "formal_retrieval" else "not_resolved",
            "candidate_assets": "candidate_evidence_only" if explicit_candidate_search else "not_read",
            "raw_data": "blocked_by_default",
        },
    }


def resolve_route(prompt: str, routes: Any) -> dict[str, Any]:
    return resolve_route_result(prompt, routes)["route"]


def resolve_route_result(prompt: str, routes: Any) -> dict[str, Any]:
    matches = []
    for route in routes if isinstance(routes, list) else []:
        if not isinstance(route, dict):
            continue
        triggers = [str(trigger) for trigger in route.get("triggers", []) if str(trigger)]
        matched = [trigger for trigger in triggers if trigger in prompt]
        matched.extend(semantic_route_matches(prompt, str(route.get("id", ""))))
        matched = list(dict.fromkeys(matched))
        if matched:
            is_generic_entry = route.get("id") == "external_use"
            matches.append(
                {
                    "is_generic_entry": is_generic_entry,
                    "max_trigger_length": max(len(trigger) for trigger in matched),
                    "matched_triggers": matched,
                    "route": route,
                }
            )
    if not matches:
        return {"status": "not_found", "route": {}, "candidates": [], "matched_triggers": []}
    task_matches = [item for item in matches if not item["is_generic_entry"]]
    candidates = task_matches or matches
    preferred = prefer_post_topic_image_text_generation(prompt, candidates)
    if preferred:
        return {
            "status": "resolved",
            "route": preferred["route"],
            "candidates": [],
            "matched_triggers": preferred["matched_triggers"],
        }
    best_length = max(int(item["max_trigger_length"]) for item in candidates)
    best = [item for item in candidates if int(item["max_trigger_length"]) == best_length]
    if len(best) == 1:
        return {"status": "resolved", "route": best[0]["route"], "candidates": [], "matched_triggers": best[0]["matched_triggers"]}
    trigger_counts: dict[str, int] = {}
    for item in best:
        for trigger in item["matched_triggers"]:
            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
    specific = [item for item in best if any(trigger_counts[trigger] == 1 for trigger in item["matched_triggers"])]
    if len(specific) == 1:
        return {
            "status": "resolved",
            "route": specific[0]["route"],
            "candidates": [],
            "matched_triggers": specific[0]["matched_triggers"],
        }
    return {
        "status": "ambiguous",
        "route": {},
        "matched_triggers": [],
        "candidates": [
            {
                "route_id": str(item["route"].get("id", "")),
                "matched_triggers": item["matched_triggers"],
            }
            for item in best
        ],
    }


def semantic_route_matches(prompt: str, route_id: str) -> list[str]:
    normalized = re.sub(r"[，。！？、,;；:\s]+", "", prompt.lower())
    matches = []
    for label, pattern in SEMANTIC_ROUTE_PATTERNS.get(route_id, ()):
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            matches.append(label)
    return matches


def resolve_clarification_questions(
    prompt: str,
    route_id: str,
    account: dict[str, Any],
    account_skill: dict[str, Any],
    direction: str,
) -> list[str]:
    lowered = prompt.lower()
    questions: list[str] = []
    has_source_scope = bool(account) or any(marker in lowered for marker in SOURCE_SCOPE_MARKERS)
    if route_id == "content_processing":
        if not has_source_scope:
            questions.append("要处理哪个账号或哪批资料？")
        if not any(marker in lowered for marker in SOURCE_SCOPE_MARKERS):
            questions.append("资料来自链接、SQLite、NAS 还是本地目录？")
    elif route_id == "account_learning":
        if not account:
            questions.append("要学习哪个账号？")
        if not any(marker in lowered for marker in SOURCE_SCOPE_MARKERS):
            questions.append("要学习哪批已经处理完成的证据？")
    elif route_id == "topic_generation":
        if not account_skill.get("ok"):
            questions.append("使用哪个正式账号 Skill？")
        if explicit_requested_count(prompt) is None:
            questions.append("需要生成多少个选题？")
        if not direction and not any(marker in prompt for marker in ("关于", "围绕", "主题", "方向", "人群", "问题")):
            questions.append("选题的主题、方向或目标人群是什么？")
    elif route_id == "script_generation":
        if not account_skill.get("ok"):
            questions.append("使用哪个正式账号 Skill？")
        has_topic = bool(direction) or bool(
            re.search(r"(?:topic[_-]?[a-z0-9_-]+|选题[:：]|这个选题|已确认选题|基于选题|关于|围绕)", lowered)
        )
        if not has_topic:
            questions.append("基于哪个 topic_id 或已经确认的选题？")
        if not any(marker in prompt for marker in OUTPUT_FORM_MARKERS):
            questions.append("要输出哪个平台和什么形式？")
    elif route_id == "content_review":
        if not re.search(r"content[_-]?[a-z0-9_-]+", lowered):
            questions.append("要复盘哪个 content_id？")
        if not any(marker in prompt for marker in FEEDBACK_MARKERS):
            questions.append("反馈来自截图、表格、评论、平台指标还是人工判断？")
    elif route_id == "creator_db_export" and not account:
        questions.append("要导出哪个博主？")
    elif route_id == "external_use":
        questions.append("你要处理资料、学习账号、调用账号 Skill、复盘还是审计系统？")
    return list(dict.fromkeys(questions))


def compact_candidate_search(search: dict[str, Any], *, max_text: int = 240) -> dict[str, Any]:
    compact = dict(search)
    items = []
    for item in search.get("items", []) if isinstance(search.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        if len(title) > max_text:
            title = title[: max_text - 1].rstrip() + "…"
        items.append(
            {
                "source_id": item.get("source_id", ""),
                "source_url": item.get("source_url", ""),
                "account_name": item.get("account_name", ""),
                "direction": item.get("direction", ""),
                "title": title,
                "match_score": item.get("match_score", 0),
                "matched_terms": item.get("matched_terms", []),
            }
        )
    compact["items"] = items
    compact["count"] = len(items)
    compact["token_boundary"] = "compact_candidate_summaries_only"
    return compact


def prefer_post_topic_image_text_generation(prompt: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    route_ids = {str(item["route"].get("id", "")) for item in candidates}
    if not {"topic_generation", "script_generation"}.issubset(route_ids):
        return {}
    if any(trigger in prompt for trigger in ("出选题", "我要出选题", "生成选题", "给我选题")):
        return {}
    has_confirmed_topic = any(
        marker in prompt
        for marker in (
            "确认的选题",
            "已确认选题",
            "选题确认",
            "基于选题",
            "基于刚才确认的选题",
            "刚才的选题",
            "这个选题",
        )
    )
    has_image_text_output = any(marker in prompt for marker in ("图文", "小红书图文", "image2", "生图"))
    if not (has_confirmed_topic and has_image_text_output):
        return {}
    return next((item for item in candidates if str(item["route"].get("id", "")) == "script_generation"), {})


def resolve_account(prompt: str, accounts: Any) -> dict[str, Any]:
    candidates = [
        account
        for account in accounts if isinstance(accounts, list) and isinstance(account, dict)
        if str(account.get("account_name", "")) and str(account.get("account_name", "")) in prompt
    ]
    return max(candidates, key=lambda item: len(str(item.get("account_name", "")))) if candidates else {}


def resolve_direction(prompt: str, account: dict[str, Any]) -> str:
    directions = account.get("directions", []) if isinstance(account, dict) else []
    names = [
        str(item.get("direction", ""))
        for item in directions
        if isinstance(item, dict) and item.get("direction") and str(item.get("direction")) in prompt
    ]
    return max(names, key=len) if names else ""


def explicit_requested_count(prompt: str) -> int | None:
    units = r"(?:个|条|篇|份|组|套|张|则)"
    match = re.search(rf"(?<!\d)(\d{{1,4}})\s*{units}", prompt)
    if match:
        return max(int(match.group(1)), 1)
    chinese = re.search(rf"([一二两三四五六七八九十]{{1,3}})\s*{units}", prompt)
    if not chinese:
        return None
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    value = chinese.group(1)
    if value == "十":
        return 10
    if "十" in value:
        tens, ones = value.split("十", 1)
        return (digits.get(tens, 1) * 10) + digits.get(ones, 0)
    return digits.get(value)


def resolve_requested_count(prompt: str) -> int:
    return explicit_requested_count(prompt) or 10


def extract_query(prompt: str, route: dict[str, Any]) -> str:
    cleaned = prompt.replace("@知识库", " ")
    for trigger in route.get("triggers", []) if isinstance(route, dict) else []:
        cleaned = cleaned.replace(str(trigger), " ")
    cleaned = re.sub(r"\d+\s*个", " ", cleaned)
    cleaned = re.sub(r"[，。！？、,\s]+", " ", cleaned).strip()
    return cleaned


def resolve_read_paths(root: Path, route: dict[str, Any], account: dict[str, Any], direction: str) -> list[str]:
    return resolve_read_path_status(root, route, account, direction)["read_paths"]


def resolve_read_path_status(
    root: Path,
    route: dict[str, Any],
    account: dict[str, Any],
    direction: str,
    account_skill: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    candidates = []
    route_id = str(route.get("id", "")) if isinstance(route, dict) else ""
    if isinstance(route, dict):
        candidates.extend(str(path) for path in route.get("read_first", []) if "{" not in str(path))
    # 生产调用只读取账号 Skill 入口。Skill 内部按需加载 references；旧账号根目录文档
    # 不再由总控批量注入，避免重复上下文和账号之间互相污染。
    if route_id in {"topic_generation", "script_generation"}:
        resolved = account_skill or {}
        skill_path = str(resolved.get("skill_path") or "")
        if not skill_path:
            formal_dir = str(account.get("formal_account_dir", "")) if isinstance(account, dict) else ""
            fallback = f"{formal_dir}/skill/SKILL.md" if formal_dir else ""
            if fallback and (root / fallback).exists():
                skill_path = fallback
        if skill_path:
            candidates.append(skill_path)
    result = []
    missing = []
    for relative in candidates:
        if relative in result or relative in missing:
            continue
        if (root / relative).exists():
            result.append(relative)
        else:
            missing.append(relative)
    return {"read_paths": result, "missing_read_paths": missing}
