from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .candidate_search import search_candidates
from .schemas import EVIDENCE_INDEX_DIR, SYSTEM_CONFIG_DIR, SYSTEM_INDEX_DIR


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
            "clarification_questions": ["你要走哪个入口？请补充截图复盘、表格复盘、出选题、写文案等具体动作。"],
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
            "clarification_questions": ["请补充你要做的动作，例如出选题、写文案、查账号、JSON 入库或复盘。"],
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
    query = direction or extract_query(prompt, route)
    route_id = str(route.get("id", ""))
    if route_id in {"topic_generation", "script_generation"}:
        search = search_candidates(
            root,
            query=query,
            account_name=account_name,
            direction=direction,
            limit=requested_count,
        )
    else:
        search = {
            "status": "not_applicable",
            "query": query,
            "count": 0,
            "items": [],
        }
    contract = next(
        (item for item in contracts.get("contracts", []) if isinstance(item, dict) and item.get("route_id") == route_id),
        {},
    )
    read_status = resolve_read_path_status(root, route, account, direction)
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
        "knowledge_boundary": {
            "formal_account_knowledge": "allowed" if account else "not_resolved",
            "candidate_assets": "candidate_evidence_only",
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


def resolve_requested_count(prompt: str) -> int:
    match = re.search(r"(\d+)\s*个", prompt)
    return max(int(match.group(1)), 1) if match else 10


def extract_query(prompt: str, route: dict[str, Any]) -> str:
    cleaned = prompt.replace("@知识库", " ")
    for trigger in route.get("triggers", []) if isinstance(route, dict) else []:
        cleaned = cleaned.replace(str(trigger), " ")
    cleaned = re.sub(r"\d+\s*个", " ", cleaned)
    cleaned = re.sub(r"[，。！？、,\s]+", " ", cleaned).strip()
    return cleaned


def resolve_read_paths(root: Path, route: dict[str, Any], account: dict[str, Any], direction: str) -> list[str]:
    return resolve_read_path_status(root, route, account, direction)["read_paths"]


def resolve_read_path_status(root: Path, route: dict[str, Any], account: dict[str, Any], direction: str) -> dict[str, list[str]]:
    candidates = []
    if isinstance(route, dict):
        candidates.extend(str(path) for path in route.get("read_first", []) if "{" not in str(path))
    formal_dir = str(account.get("formal_account_dir", "")) if isinstance(account, dict) else ""
    if formal_dir:
        candidates.extend(
            [
                f"{formal_dir}/账号索引.md",
                f"{formal_dir}/账号概述.md",
                f"{formal_dir}/账号方法论总览.md",
                f"{formal_dir}/账号整体方法论.md",
                f"{formal_dir}/内容生产使用说明.md",
                f"{formal_dir}/减少AI味输出规则.md",
                f"{formal_dir}/内容输出标准模板.md",
            ]
        )
    for item in account.get("directions", []) if isinstance(account, dict) else []:
        if not isinstance(item, dict) or item.get("direction") != direction:
            continue
        direction_dir = str(item.get("formal_direction_dir", ""))
        if direction_dir:
            candidates.extend(
                [
                    f"{direction_dir}/方向方法论总结.md",
                    f"{direction_dir}/粗扫内容和选题.md",
                ]
            )
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
