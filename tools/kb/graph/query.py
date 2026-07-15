from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from .config import load_source_config, output_root


VALID_VIEWS = {"system", "knowledge", "accounts", "workflows", "cross_layer"}


def _load_graph(root: Path) -> dict[str, Any]:
    path = output_root(root, load_source_config(root)) / "graph.json"
    if not path.exists():
        raise RuntimeError("graph_not_built: run tools.kb.cli graph build")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("graph_invalid: rebuild the knowledge graph") from exc
    if not isinstance(value, dict):
        raise RuntimeError("graph_invalid: expected an object")
    return value


def _terms(text: str) -> set[str]:
    lowered = text.lower().strip()
    terms = {item for item in re.findall(r"[a-z0-9_./:-]+", lowered) if len(item) > 1}
    for block in re.findall(r"[\u3400-\u9fff]+", lowered):
        terms.add(block)
        if len(block) > 1:
            terms.update(block[index : index + 2] for index in range(len(block) - 1))
        if len(block) > 2:
            terms.update(block[index : index + 3] for index in range(len(block) - 2))
    return terms


def _node_score(node: dict[str, Any], question: str, terms: set[str]) -> float:
    label = str(node.get("label") or "").lower()
    source = str(node.get("source_file") or "").lower()
    purpose = str(node.get("purpose") or "").lower()
    domain = str(node.get("domain") or "").lower()
    haystack = " ".join((label, source, purpose, domain))
    score = 0.0
    lowered = question.lower().strip()
    if lowered and lowered in label:
        score += 25.0
    if lowered and lowered in haystack:
        score += 12.0
    for term in terms:
        if term in label:
            score += 5.0 + min(len(term), 6) * 0.2
        elif term in source:
            score += 2.5
        elif term in haystack:
            score += 1.0
    if node.get("node_kind") in {"route", "workflow_stage", "account"}:
        score += 0.25
    return score


def query_graph(
    root: Path,
    question: str,
    *,
    view: str = "cross_layer",
    depth: int = 2,
    limit: int = 24,
) -> dict[str, Any]:
    if view not in VALID_VIEWS:
        raise ValueError(f"unknown graph view: {view}")
    data = _load_graph(root.resolve())
    nodes = [item for item in data.get("nodes") or [] if isinstance(item, dict)]
    links = [item for item in data.get("links") or [] if isinstance(item, dict)]
    visible = {str(node.get("id")): node for node in nodes if view in (node.get("views") or [])}
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {node_id: [] for node_id in visible}
    visible_links: list[dict[str, Any]] = []
    for link in links:
        source, target = str(link.get("source")), str(link.get("target"))
        if source not in visible or target not in visible:
            continue
        adjacency[source].append((target, link))
        adjacency[target].append((source, link))
        visible_links.append(link)

    terms = _terms(question)
    ranked = sorted(
        ((node_id, _node_score(node, question, terms)) for node_id, node in visible.items()),
        key=lambda item: (-item[1], str(visible[item[0]].get("label") or item[0])),
    )
    seeds = [node_id for node_id, score in ranked[:8] if score > 0]
    if not seeds:
        return {
            "ok": True,
            "question": question,
            "view": view,
            "message": "图谱中没有找到相关节点；请换一个更具体的系统、账号、流程或知识关键词。",
            "nodes": [],
            "relations": [],
            "sources": [],
        }

    max_depth = max(0, min(int(depth), 4))
    max_nodes = max(1, min(int(limit), 200))
    visited: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seeds)
    while queue and len(visited) < max_nodes:
        node_id, current_depth = queue.popleft()
        if node_id in visited and visited[node_id] <= current_depth:
            continue
        visited[node_id] = current_depth
        if current_depth >= max_depth:
            continue
        neighbors = sorted(
            adjacency.get(node_id, []),
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(str(item[1].get("confidence")), 3),
                str(visible[item[0]].get("label") or item[0]),
            ),
        )
        for neighbor_id, _ in neighbors:
            if neighbor_id not in visited:
                queue.append((neighbor_id, current_depth + 1))

    selected_links = [
        link
        for link in visible_links
        if str(link.get("source")) in visited and str(link.get("target")) in visited
    ]
    result_nodes = []
    sources: list[dict[str, str]] = []
    seen_sources: set[tuple[str, str]] = set()
    for node_id in sorted(visited, key=lambda item: (visited[item], -_node_score(visible[item], question, terms))):
        node = visible[node_id]
        item = {
            "id": node_id,
            "label": node.get("label"),
            "kind": node.get("node_kind"),
            "layer": node.get("layer"),
            "status": node.get("status"),
            "domain": node.get("domain"),
            "distance": visited[node_id],
            "source_file": node.get("source_file"),
            "source_location": node.get("source_location"),
        }
        result_nodes.append(item)
        source_file = str(node.get("source_file") or "")
        location = str(node.get("source_location") or "")
        key = (source_file, location)
        if source_file and not source_file.endswith("/") and key not in seen_sources:
            sources.append({"path": source_file, "location": location})
            seen_sources.add(key)

    relations = [
        {
            "source": visible[str(link.get("source"))].get("label"),
            "target": visible[str(link.get("target"))].get("label"),
            "relation": link.get("relation"),
            "relation_source": link.get("relation_source"),
            "confidence": link.get("confidence"),
        }
        for link in selected_links[: max_nodes * 3]
    ]
    return {
        "ok": True,
        "question": question,
        "view": view,
        "seed_count": len(seeds),
        "node_count": len(result_nodes),
        "relation_count": len(relations),
        "nodes": result_nodes,
        "relations": relations,
        "sources": sources[: max_nodes],
        "source_recheck_required": True,
    }
