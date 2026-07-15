from __future__ import annotations

import hashlib
import importlib.metadata
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
from networkx.readwrite import json_graph

from ..runtime import write_json
from ..schemas import now_iso
from .config import is_blocked, load_source_config, load_view_config, output_root, safe_repo_path


GRAPH_SCHEMA_VERSION = "1.0"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def _stable_id(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]
    return f"{kind}:{digest}"


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _account_name(path: str) -> str:
    parts = Path(path).parts
    if "账号中心" in parts:
        index = parts.index("账号中心")
        if index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _formal_domain(path: str) -> str:
    parts = Path(path).parts
    try:
        index = parts.index("formal")
    except ValueError:
        return "formal"
    if index + 1 >= len(parts):
        return "formal"
    category = parts[index + 1]
    if "." in category:
        return "general"
    account = _account_name(path)
    return f"accounts/{account}" if account else category


def _system_domain(path: str) -> str:
    if path.startswith("tools/"):
        return "code"
    for name in ("config", "index", "rules", "docs"):
        if f"/shareable/{name}/" in path:
            return name
    return "entry"


def _views_for(path: str, layer: str, account: str = "") -> list[str]:
    views: set[str] = {"cross_layer"}
    if layer == "system":
        views.add("system")
    if layer in {"formal_knowledge", "account"}:
        views.add("knowledge")
    if account or layer == "account":
        views.add("accounts")
    lowered = path.lower()
    if any(token in lowered for token in ("workflow", "pipeline", "learning", "学习", "流程")):
        views.add("workflows")
    return sorted(views)


def _source_record(path: str, layer: str, status: str, purpose: str = "") -> dict[str, Any]:
    account = _account_name(path)
    effective_layer = "account" if account else layer
    domain = _formal_domain(path) if layer == "formal_knowledge" else _system_domain(path)
    return {
        "path": path,
        "layer": effective_layer,
        "status": status,
        "domain": domain,
        "account": account,
        "purpose": purpose,
        "views": _views_for(path, effective_layer, account),
    }


def _iter_files(base: Path, allowed_extensions: set[str]) -> Iterable[Path]:
    if base.is_file():
        if base.suffix.lower() in allowed_extensions:
            yield base
        return
    if not base.exists():
        return
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in allowed_extensions and "__pycache__" not in path.parts:
            yield path


def collect_sources(root: Path, config: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = root.resolve()
    config = config or load_source_config(root)
    allowed_extensions = {str(item).lower() for item in config.get("allowed_extensions") or []}
    records: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []

    def accept(path: Path, layer: str, status: str, purpose: str = "") -> None:
        try:
            relative = _relative(root, path)
        except ValueError:
            rejected.append({"path": str(path), "reason": "outside_root"})
            return
        if is_blocked(relative, config):
            rejected.append({"path": relative, "reason": "blocked_prefix"})
            return
        if path.suffix.lower() not in allowed_extensions:
            return
        if not path.exists() or not path.is_file():
            return
        records[relative] = _source_record(relative, layer, status, purpose)

    for relative in config.get("system_files") or []:
        path = safe_repo_path(root, str(relative), config)
        if path is not None:
            accept(path, "system", "system")
    for relative in config.get("system_roots") or []:
        base = safe_repo_path(root, str(relative), config)
        if base is None:
            rejected.append({"path": str(relative), "reason": "blocked_system_root"})
            continue
        for path in _iter_files(base, allowed_extensions):
            accept(path, "system", "system")

    formal_index_path = root / str(config.get("formal_index") or "")
    formal_index = _read_json(formal_index_path, {})
    formal_items = formal_index.get("items") if isinstance(formal_index, dict) else []
    if isinstance(formal_items, list):
        for item in formal_items:
            if not isinstance(item, dict):
                continue
            relative = str(item.get("path") or "")
            path = safe_repo_path(root, relative, config)
            if path is not None:
                accept(
                    path,
                    "formal_knowledge",
                    str(item.get("content_status") or "approved"),
                    str(item.get("purpose") or "formal_knowledge"),
                )

    candidate_index_path = root / str(config.get("candidate_index") or "")
    candidate_index = _read_json(candidate_index_path, {})
    candidate_summary = {
        "path": str(config.get("candidate_index") or ""),
        "item_count": int(candidate_index.get("item_count") or 0) if isinstance(candidate_index, dict) else 0,
        "generated_at": str(candidate_index.get("generated_at") or "") if isinstance(candidate_index, dict) else "",
        "policy": "summary_only",
    }
    return sorted(records.values(), key=lambda item: item["path"]), {
        "rejected": rejected,
        "formal_index_item_count": len(formal_items) if isinstance(formal_items, list) else 0,
        "candidate_summary": candidate_summary,
    }


def _extract_with_graphify(root: Path, records: list[dict[str, Any]], config: dict[str, Any]) -> nx.DiGraph:
    try:
        from graphify.build import build as graphify_build
        from graphify.extract import extract_python
        from graphify.extractors.markdown import extract_markdown
    except ImportError as exc:
        raise RuntimeError("graphify_dependency_missing: install graphifyy==0.9.15") from exc

    extract_extensions = {str(item).lower() for item in config.get("graphify_extract_extensions") or []}
    max_bytes = int(config.get("max_extract_bytes") or 1_048_576)
    extractions: list[dict[str, Any]] = []
    for record in records:
        path = root / record["path"]
        if path.suffix.lower() not in extract_extensions or path.stat().st_size > max_bytes:
            continue
        if path.suffix.lower() == ".md":
            extractions.append(extract_markdown(path))
        elif path.suffix.lower() == ".py":
            extractions.append(extract_python(path))
    if not extractions:
        return nx.DiGraph()
    return graphify_build(extractions, directed=True, dedup=False, root=root)


def _normalize_graphify_nodes(graph: nx.DiGraph) -> nx.MultiDiGraph:
    mapping: dict[str, str] = {}
    for node_id, attrs in graph.nodes(data=True):
        source = str(attrs.get("source_file") or "")
        location = str(attrs.get("source_location") or "")
        if source and location == "L1" and str(attrs.get("label") or "") == Path(source).name:
            mapping[str(node_id)] = f"file:{source}"
        attrs["engine_node_id"] = str(node_id)
    if mapping:
        graph = nx.relabel_nodes(graph, mapping, copy=True)
    result = nx.MultiDiGraph()
    result.add_nodes_from(graph.nodes(data=True))
    for source, target, attrs in graph.edges(data=True):
        result.add_edge(source, target, **dict(attrs))
    return result


def _attach_source_metadata(graph: nx.MultiDiGraph, records: list[dict[str, Any]]) -> None:
    by_path = {item["path"]: item for item in records}
    for record in records:
        node_id = f"file:{record['path']}"
        attrs = {
            "label": Path(record["path"]).name,
            "file_type": "document" if Path(record["path"]).suffix.lower() != ".py" else "code",
            "source_file": record["path"],
            "source_location": "L1",
            "node_kind": "file",
            **{key: record[key] for key in ("layer", "status", "domain", "account", "purpose", "views")},
        }
        if node_id in graph:
            graph.nodes[node_id].update(attrs)
        else:
            graph.add_node(node_id, **attrs)

    for node_id, attrs in graph.nodes(data=True):
        source = str(attrs.get("source_file") or "")
        record = by_path.get(source)
        if record:
            for key in ("layer", "status", "domain", "account", "purpose", "views"):
                attrs[key] = record[key]
            attrs.setdefault("node_kind", "section" if attrs.get("file_type") == "document" else "symbol")
        else:
            attrs.setdefault("layer", "system")
            attrs.setdefault("status", "system")
            attrs.setdefault("domain", "external")
            attrs.setdefault("account", "")
            attrs.setdefault("purpose", "")
            attrs.setdefault("views", ["system", "cross_layer"])
            attrs.setdefault("node_kind", "concept")


def _annotate_engine_edges(graph: nx.MultiDiGraph) -> None:
    for _, _, _, attrs in graph.edges(keys=True, data=True):
        relation = str(attrs.get("relation") or "related_to")
        raw_confidence = str(attrs.get("confidence") or "EXTRACTED").upper()
        if relation == "contains":
            relation_source, confidence = "deterministic", "high"
        elif relation == "references":
            relation_source, confidence = "explicit", "high"
        elif raw_confidence == "INFERRED":
            relation_source, confidence = "inferred", "low"
        else:
            relation_source, confidence = "inferred", "medium"
        attrs.update(
            relation=relation,
            relation_source=relation_source,
            confidence=confidence,
            engine="graphify",
        )


def _add_edge(graph: nx.MultiDiGraph, source: str, target: str, relation: str, relation_source: str = "deterministic", confidence: str = "high") -> None:
    if source in graph and target in graph:
        graph.add_edge(
            source,
            target,
            relation=relation,
            relation_source=relation_source,
            confidence=confidence,
            engine="kb_adapter",
        )


def _add_directory_hierarchy(graph: nx.MultiDiGraph, records: list[dict[str, Any]]) -> None:
    for record in records:
        parts = Path(record["path"]).parts[:-1]
        parent_id = ""
        for index in range(len(parts)):
            relative = Path(*parts[: index + 1]).as_posix()
            node_id = f"dir:{relative}"
            if node_id not in graph:
                graph.add_node(
                    node_id,
                    label=parts[index],
                    source_file=relative + "/",
                    source_location="",
                    file_type="concept",
                    node_kind="directory",
                    layer=record["layer"],
                    status=record["status"],
                    domain=record["domain"],
                    account=record["account"],
                    purpose="hierarchy",
                    views=record["views"],
                )
            else:
                graph.nodes[node_id]["views"] = sorted(set(graph.nodes[node_id].get("views") or []) | set(record["views"]))
            if parent_id:
                _add_edge(graph, parent_id, node_id, "contains")
            parent_id = node_id
        if parent_id:
            _add_edge(graph, parent_id, f"file:{record['path']}", "contains")


def _add_route_graph(root: Path, graph: nx.MultiDiGraph) -> None:
    path = root / "00_System/shareable/index/controller_routes.json"
    data = _read_json(path, {})
    routes = data.get("routes") if isinstance(data, dict) else []
    if not isinstance(routes, list):
        return
    route_file_id = "file:00_System/shareable/index/controller_routes.json"
    for route in routes:
        if not isinstance(route, dict) or not route.get("id"):
            continue
        route_id = f"route:{route['id']}"
        graph.add_node(
            route_id,
            label=str(route.get("name") or route["id"]),
            node_kind="route",
            file_type="concept",
            source_file="00_System/shareable/index/controller_routes.json",
            source_location="",
            layer="system",
            status="system",
            domain="routes",
            account="",
            purpose="controller_route",
            views=["cross_layer", "system", "workflows"],
        )
        _add_edge(graph, route_file_id, route_id, "declares", "explicit", "high")
        for source_path in route.get("read_first") or []:
            _add_edge(graph, route_id, f"file:{source_path}", "reads_first", "explicit", "high")
        for tool in route.get("tools") or []:
            command = str(tool)
            command_id = f"command:{command}"
            if command_id not in graph:
                graph.add_node(
                    command_id,
                    label=command,
                    node_kind="command",
                    file_type="code",
                    source_file="00_System/shareable/index/controller_routes.json",
                    source_location="",
                    layer="system",
                    status="system",
                    domain="commands",
                    account="",
                    purpose="route_tool",
                    views=["cross_layer", "system", "workflows"],
                )
            _add_edge(graph, route_id, command_id, "dispatches", "explicit", "high")


def _add_workflow_graph(root: Path, graph: nx.MultiDiGraph) -> None:
    relative = "00_System/shareable/config/account_learning_pipeline.json"
    data = _read_json(root / relative, {})
    stages = data.get("stages") if isinstance(data, dict) else []
    if not isinstance(stages, list):
        return
    previous = ""
    source_id = f"file:{relative}"
    gates = set(data.get("confirmation_gates") or [])
    for stage in stages:
        if not isinstance(stage, dict) or not stage.get("id"):
            continue
        stage_key = str(stage["id"])
        stage_id = f"stage:{stage_key}"
        graph.add_node(
            stage_id,
            label=str(stage.get("name") or stage_key),
            node_kind="workflow_stage",
            file_type="concept",
            source_file=relative,
            source_location="",
            layer="workflow",
            status="confirmation_gate" if stage_key in gates else "defined",
            domain="account_learning",
            account="",
            purpose=str(stage.get("principle") or ""),
            artifacts=list(stage.get("required_artifacts") or []),
            views=["cross_layer", "system", "workflows"],
        )
        _add_edge(graph, source_id, stage_id, "declares", "explicit", "high")
        if previous:
            _add_edge(graph, previous, stage_id, "next_stage", "deterministic", "high")
        previous = stage_id


def _add_account_graph(graph: nx.MultiDiGraph, records: list[dict[str, Any]]) -> None:
    accounts = sorted({record["account"] for record in records if record.get("account")})
    for account in accounts:
        node_id = f"account:{account}"
        graph.add_node(
            node_id,
            label=account,
            node_kind="account",
            file_type="concept",
            source_file="",
            source_location="",
            layer="account",
            status="approved",
            domain=f"accounts/{account}",
            account=account,
            purpose="formal_account_center",
            views=["accounts", "cross_layer", "knowledge"],
        )
        for record in records:
            if record.get("account") == account:
                _add_edge(graph, node_id, f"file:{record['path']}", "contains", "deterministic", "high")


def _add_candidate_summary(graph: nx.MultiDiGraph, summary: dict[str, Any]) -> None:
    node_id = "summary:candidate_assets"
    graph.add_node(
        node_id,
        label=f"候选资产汇总（{int(summary.get('item_count') or 0)}）",
        node_kind="summary",
        file_type="concept",
        source_file=str(summary.get("path") or ""),
        source_location="",
        layer="candidate_summary",
        status="summary_only",
        domain="candidates",
        account="",
        purpose="候选层仅统计，不展开正文或逐条路径",
        item_count=int(summary.get("item_count") or 0),
        generated_at=str(summary.get("generated_at") or ""),
        views=["cross_layer", "knowledge"],
    )


def _apply_communities(graph: nx.MultiDiGraph) -> dict[int, str]:
    from graphify.cluster import cluster, label_communities_by_hub

    simple = nx.Graph()
    simple.add_nodes_from(graph.nodes(data=True))
    simple.add_edges_from((source, target) for source, target in graph.edges())
    communities = cluster(simple, resolution=1.15, exclude_hubs_percentile=99.5)
    labels = label_communities_by_hub(simple, communities)
    for community_id, members in communities.items():
        for node_id in members:
            if node_id in graph:
                graph.nodes[node_id]["community"] = community_id
                graph.nodes[node_id]["community_name"] = labels.get(community_id, f"Community {community_id}")
    return labels


def _graph_data(graph: nx.MultiDiGraph, root: Path, views: dict[str, Any], labels: dict[int, str]) -> dict[str, Any]:
    data = json_graph.node_link_data(graph, edges="links")
    data.update(
        schema_version=GRAPH_SCHEMA_VERSION,
        generated_at=now_iso(),
        root=str(root.resolve()),
        engine={"name": "Graphify", "package": "graphifyy", "version": importlib.metadata.version("graphifyy")},
        view_config=views,
        community_labels={str(key): value for key, value in labels.items()},
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
    )
    return data


def build_graph(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = load_source_config(root)
    views = load_view_config(root)
    records, collection = collect_sources(root, config)
    graph = _normalize_graphify_nodes(_extract_with_graphify(root, records, config))
    _attach_source_metadata(graph, records)
    _annotate_engine_edges(graph)
    _add_directory_hierarchy(graph, records)
    _add_route_graph(root, graph)
    _add_workflow_graph(root, graph)
    _add_account_graph(graph, records)
    _add_candidate_summary(graph, collection["candidate_summary"])
    labels = _apply_communities(graph)

    out = output_root(root, config)
    out.mkdir(parents=True, exist_ok=True)
    data = _graph_data(graph, root, views, labels)
    graph_path = out / "graph.json"
    manifest_path = out / "manifest.json"
    html_path = out / "index.html"
    write_json(graph_path, data)
    manifest = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "generated_at": data["generated_at"],
        "engine": data["engine"],
        "source_policy": {
            "formal": config.get("formal_policy"),
            "candidate": config.get("candidate_policy"),
            "blocked_prefixes": config.get("blocked_prefixes") or [],
        },
        "allowed_sources": [record["path"] for record in records],
        "allowed_source_count": len(records),
        "rejected_sources": collection["rejected"],
        "candidate_summary": collection["candidate_summary"],
        "counts": {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "layers": dict(Counter(str(attrs.get("layer") or "unknown") for _, attrs in graph.nodes(data=True))),
            "relation_sources": dict(Counter(str(attrs.get("relation_source") or "unknown") for *_, attrs in graph.edges(data=True))),
        },
        "outputs": [str(graph_path.relative_to(root)), str(manifest_path.relative_to(root)), str(html_path.relative_to(root))],
    }
    write_json(manifest_path, manifest)
    from .viewer import render_graph_html

    html_path.write_text(render_graph_html(data), encoding="utf-8")
    status = graph_status(root)
    status.update(outputs=manifest["outputs"], source_count=len(records))
    return status


def graph_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = load_source_config(root)
    out = output_root(root, config)
    graph_data = _read_json(out / "graph.json", {})
    manifest = _read_json(out / "manifest.json", {})
    allowed_sources = manifest.get("allowed_sources") if isinstance(manifest, dict) else []
    allowed_sources = allowed_sources if isinstance(allowed_sources, list) else []
    blocked = [path for path in allowed_sources if is_blocked(str(path), config)]
    candidate_policy = (manifest.get("source_policy") or {}).get("candidate") if isinstance(manifest, dict) else ""
    expected_views = {"system", "knowledge", "accounts", "workflows", "cross_layer"}
    configured_views = {
        str(item.get("id"))
        for item in ((graph_data.get("view_config") or {}).get("views") or [])
        if isinstance(item, dict)
    } if isinstance(graph_data, dict) else set()
    try:
        engine_version = importlib.metadata.version("graphifyy")
    except importlib.metadata.PackageNotFoundError:
        engine_version = ""
    checks = {
        "engine_pinned": engine_version == str((config.get("engine") or {}).get("pinned_version") or ""),
        "graph_exists": (out / "graph.json").exists(),
        "manifest_exists": (out / "manifest.json").exists(),
        "web_exists": (out / "index.html").exists(),
        "no_blocked_sources": not blocked,
        "candidate_summary_only": candidate_policy == "summary_only",
        "five_views_present": expected_views.issubset(configured_views),
    }
    return {
        "ok": all(checks.values()),
        "status": "ready" if all(checks.values()) else "requires_build",
        "engine_version": engine_version,
        "output_root": str(out.relative_to(root)),
        "node_count": int(graph_data.get("node_count") or 0) if isinstance(graph_data, dict) else 0,
        "edge_count": int(graph_data.get("edge_count") or 0) if isinstance(graph_data, dict) else 0,
        "checks": checks,
        "blocked_sources": blocked,
    }
