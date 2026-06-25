from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .candidate_search import search_candidates
from .schemas import SYSTEM_DIR


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
    controller = read_json(root / SYSTEM_DIR / "index" / "controller_routes.json", {"routes": []})
    account_index = read_json(root / SYSTEM_DIR / "index" / "account_knowledge_index.json", {"accounts": []})
    contracts = read_json(root / SYSTEM_DIR / "config" / "output_contracts.json", {"contracts": []})

    route = resolve_route(prompt, controller.get("routes", []))
    if not route:
        return {
            "ok": False,
            "errors": ["route_not_resolved"],
            "input": prompt,
            "route_id": "",
            "account_name": "",
            "direction": "",
            "requested_count": resolve_requested_count(prompt),
            "read_paths": [],
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
    return {
        "ok": True,
        "errors": [],
        "input": prompt,
        "route_id": route_id,
        "account_name": account_name,
        "direction": direction,
        "requested_count": requested_count,
        "read_paths": resolve_read_paths(root, route, account, direction),
        "search": search,
        "output_contract": contract,
        "knowledge_boundary": {
            "formal_account_knowledge": "allowed" if account else "not_resolved",
            "candidate_assets": "candidate_evidence_only",
            "raw_data": "blocked_by_default",
        },
    }


def resolve_route(prompt: str, routes: Any) -> dict[str, Any]:
    matches = []
    for route in routes if isinstance(routes, list) else []:
        if not isinstance(route, dict):
            continue
        triggers = [str(trigger) for trigger in route.get("triggers", []) if str(trigger)]
        matched = [trigger for trigger in triggers if trigger in prompt]
        if matched:
            is_generic_entry = route.get("id") == "external_use"
            matches.append((is_generic_entry, max(len(trigger) for trigger in matched), route))
    if not matches:
        return {}
    task_matches = [item for item in matches if not item[0]]
    selected = max(task_matches or matches, key=lambda item: item[1])
    return selected[2]


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
    candidates = []
    if isinstance(route, dict):
        candidates.extend(str(path) for path in route.get("read_first", []) if "{" not in str(path))
    formal_dir = str(account.get("formal_account_dir", "")) if isinstance(account, dict) else ""
    if formal_dir:
        candidates.extend(
            [
                f"{formal_dir}/账号索引.md",
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
    for relative in candidates:
        if relative not in result and (root / relative).exists():
            result.append(relative)
    return result
