from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .runtime import runtime_path
from .schemas import SYSTEM_CONFIG_DIR, as_posix, now_iso


CONFIG_PATH = f"{SYSTEM_CONFIG_DIR}/formal_retrieval.json"
CACHE_DIR_NAME = "formal_retrieval"
INDEX_FILE_NAME = "chunks.jsonl"
META_FILE_NAME = "meta.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "scope": "formal_only",
    "allowed_roots": ["10_Knowledge/formal/"],
    "forbidden_prefixes": [
        "10_Knowledge/candidates/",
        "00_Inbox/",
        "数据/",
        "00_System/",
        "20_User/",
        "90_Temp/",
        "99_Archive/",
    ],
    "allowed_extensions": [".md", ".json", ".jsonl", ".txt"],
    "excluded_path_fragments": ["/轻量数据源/", "/skill/proposals/"],
    "max_file_bytes": 1048576,
    "chunk": {"max_chars": 900, "overlap_lines": 2},
    "vector": {"backend": "hashed_char_ngram_v1", "dimensions": 512, "ngram_sizes": [2, 3], "max_features": 96},
    "weights": {"keyword": 0.55, "vector": 0.30, "metadata": 0.10, "rerank": 0.05},
    "result": {"default_limit": 8, "max_limit": 30, "snippet_chars": 320},
}


def load_config(root: Path) -> dict[str, Any]:
    path = root.resolve() / CONFIG_PATH
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    return payload if isinstance(payload, dict) else json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))


def cache_dir(root: Path) -> Path:
    return runtime_path(root.resolve(), "cache") / CACHE_DIR_NAME


def cache_paths(root: Path) -> tuple[Path, Path]:
    base = cache_dir(root)
    return base / INDEX_FILE_NAME, base / META_FILE_NAME


def normalized_prefix(value: str) -> str:
    cleaned = value.strip().replace("\\", "/").lstrip("/")
    return f"{cleaned.rstrip('/')}/" if cleaned else ""


def is_within_allowed_root(relative: str, config: dict[str, Any]) -> bool:
    allowed = tuple(normalized_prefix(str(item)) for item in config.get("allowed_roots", []) if str(item).strip())
    forbidden = tuple(
        normalized_prefix(str(item)) for item in config.get("forbidden_prefixes", []) if str(item).strip()
    )
    return bool(allowed) and relative.startswith(allowed) and not relative.startswith(forbidden)


def eligible_source_paths(root: Path, config: dict[str, Any] | None = None) -> list[Path]:
    root = root.resolve()
    config = config or load_config(root)
    extensions = {str(item).lower() for item in config.get("allowed_extensions", [])}
    excluded = tuple(str(item) for item in config.get("excluded_path_fragments", []) if str(item))
    max_bytes = max(int(config.get("max_file_bytes", 1048576) or 1048576), 1)
    paths: list[Path] = []
    for allowed_root in config.get("allowed_roots", []):
        prefix = normalized_prefix(str(allowed_root))
        if not prefix or not is_within_allowed_root(prefix, config):
            continue
        base = root / prefix.rstrip("/")
        if not base.exists() or not base.is_dir():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            try:
                relative = as_posix(path.resolve().relative_to(root))
                size = path.stat().st_size
            except (OSError, ValueError):
                continue
            wrapped = f"/{relative}"
            if not is_within_allowed_root(relative, config):
                continue
            if path.suffix.lower() not in extensions or size > max_bytes:
                continue
            if any(fragment in wrapped for fragment in excluded):
                continue
            paths.append(path)
    return sorted(set(paths))


def config_sha256(config: dict[str, Any]) -> str:
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_fingerprint(root: Path, paths: Iterable[Path], config: dict[str, Any]) -> str:
    root = root.resolve()
    digest = hashlib.sha256(config_sha256(config).encode("utf-8"))
    for path in sorted(paths):
        try:
            relative = as_posix(path.resolve().relative_to(root))
            stat = path.stat()
        except (OSError, ValueError):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(f":{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8"))
    return digest.hexdigest()


def lexical_terms(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9][a-z0-9_-]*", lowered)
    chinese_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    chinese: list[str] = []
    for run in chinese_runs:
        chinese.extend(run)
        chinese.extend(run[index : index + 2] for index in range(max(len(run) - 1, 0)))
    return latin + chinese


def hashed_vector(text: str, vector_config: dict[str, Any]) -> dict[str, float]:
    dimensions = max(int(vector_config.get("dimensions", 512) or 512), 8)
    sizes = [max(int(item), 1) for item in vector_config.get("ngram_sizes", [2, 3])]
    compact = "".join(re.findall(r"[a-z0-9\u3400-\u9fff]+", text.lower()))
    features: Counter[int] = Counter()
    for size in sizes:
        for index in range(max(len(compact) - size + 1, 0)):
            gram = compact[index : index + size]
            bucket = int.from_bytes(hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest(), "big") % dimensions
            features[bucket] += 1
    for term in set(lexical_terms(text)):
        bucket = int.from_bytes(hashlib.blake2b(f"t:{term}".encode("utf-8"), digest_size=8).digest(), "big") % dimensions
        features[bucket] += 1
    max_features = max(int(vector_config.get("max_features", 96) or 96), 8)
    selected = dict(sorted(features.items(), key=lambda item: (-item[1], item[0]))[:max_features])
    norm = math.sqrt(sum(value * value for value in selected.values()))
    if not norm:
        return {}
    return {str(key): round(value / norm, 6) for key, value in sorted(selected.items())}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(float(value) * float(right.get(key, 0.0)) for key, value in left.items())


def metadata_for_path(relative: str) -> dict[str, str]:
    parts = relative.split("/")
    account = ""
    direction = ""
    if len(parts) >= 5 and parts[:3] == ["10_Knowledge", "formal", "accounts"]:
        account = parts[3]
    if "directions" in parts:
        index = parts.index("directions")
        if index + 1 < len(parts):
            direction = parts[index + 1]
    if "/skill/SKILL.md" in relative:
        role = "account_skill"
    elif "/skill/references/" in relative:
        role = "skill_reference"
    elif "/methods/" in relative:
        role = "method"
    elif "/directions/" in relative and "/cards/" in relative:
        role = "formal_card"
    elif "/directions/" in relative and "方向方法论总结" in relative:
        role = "direction_summary"
    elif "/evidence/" in relative:
        role = "evidence"
    elif relative.endswith("账号整体方法论.md"):
        role = "account_methodology"
    elif relative.endswith("账号索引.md"):
        role = "account_index"
    else:
        role = "formal_document"
    return {"account": account, "direction": direction, "document_role": role}


def chunk_text(text: str, max_chars: int, overlap_lines: int) -> list[dict[str, Any]]:
    lines = text.splitlines() or [text]
    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(lines):
        end = start
        size = 0
        while end < len(lines):
            extra = len(lines[end]) + (1 if end > start else 0)
            if end > start and size + extra > max_chars:
                break
            size += extra
            end += 1
            if size >= max_chars:
                break
        if end == start:
            end += 1
        chunk_lines = lines[start:end]
        heading = ""
        for line in reversed(lines[:end]):
            if re.match(r"^#{1,6}\s+", line.strip()):
                heading = re.sub(r"^#{1,6}\s+", "", line.strip())
                break
        chunks.append(
            {
                "line_start": start + 1,
                "line_end": end,
                "heading": heading,
                "text": "\n".join(chunk_lines).strip(),
            }
        )
        if end >= len(lines):
            break
        start = max(end - max(overlap_lines, 0), start + 1)
    return [item for item in chunks if item["text"]]


def build_formal_search_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    paths = eligible_source_paths(root, config)
    index_path, meta_path = cache_paths(root)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    max_chars = max(int(config.get("chunk", {}).get("max_chars", 900) or 900), 100)
    overlap = max(int(config.get("chunk", {}).get("overlap_lines", 2) or 0), 0)
    vector_config = config.get("vector", {}) if isinstance(config.get("vector"), dict) else {}
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for path in paths:
        relative = as_posix(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            skipped.append({"path": relative, "reason": "not_utf8_text"})
            continue
        metadata = metadata_for_path(relative)
        for ordinal, chunk in enumerate(chunk_text(text, max_chars, overlap), start=1):
            terms = lexical_terms(chunk["text"])
            chunk_id = hashlib.sha256(
                f"{relative}:{chunk['line_start']}:{chunk['line_end']}:{chunk['text']}".encode("utf-8")
            ).hexdigest()[:24]
            records.append(
                {
                    "chunk_id": chunk_id,
                    "path": relative,
                    "chunk_ordinal": ordinal,
                    "heading": chunk["heading"],
                    "line_start": chunk["line_start"],
                    "line_end": chunk["line_end"],
                    "text": chunk["text"],
                    "term_count": len(terms),
                    "vector": hashed_vector(chunk["text"], vector_config),
                    **metadata,
                }
            )
    temporary = index_path.with_suffix(".jsonl.tmp")
    temporary.write_text(
        "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in records),
        encoding="utf-8",
    )
    temporary.replace(index_path)
    meta = {
        "version": "1.0",
        "generated_at": now_iso(),
        "scope": "formal_only",
        "source_fingerprint": source_fingerprint(root, paths, config),
        "config_sha256": config_sha256(config),
        "source_count": len(paths),
        "chunk_count": len(records),
        "skipped": skipped,
        "vector_backend": vector_config.get("backend", "hashed_char_ngram_v1"),
        "index_path": as_posix(index_path.relative_to(root)),
        "forbidden_layers_indexed": False,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "status": "rebuilt", **meta}


def read_index_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return records
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            return []
        if isinstance(item, dict):
            records.append(item)
    return records


def index_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    index_path, meta_path = cache_paths(root)
    if not index_path.exists() or not meta_path.exists():
        return {"ok": False, "status": "requires_rebuild", "reason": "index_missing"}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"ok": False, "status": "requires_rebuild", "reason": "meta_invalid"}
    if not isinstance(meta, dict):
        return {"ok": False, "status": "requires_rebuild", "reason": "meta_invalid"}
    config = load_config(root)
    current = source_fingerprint(root, eligible_source_paths(root, config), config)
    if meta.get("source_fingerprint") != current or meta.get("config_sha256") != config_sha256(config):
        return {"ok": False, "status": "requires_rebuild", "reason": "index_stale", "meta": meta}
    return {"ok": True, "status": "ready", "meta": meta}


def _metadata_matches(record: dict[str, Any], account: str, direction: str, document_role: str) -> bool:
    return (
        (not account or str(record.get("account", "")) == account)
        and (not direction or str(record.get("direction", "")) == direction)
        and (not document_role or str(record.get("document_role", "")) == document_role)
    )


def search_formal(
    root: Path,
    *,
    query: str,
    account: str = "",
    direction: str = "",
    document_role: str = "",
    limit: int | None = None,
    rebuild: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    if rebuild:
        build_formal_search_index(root)
    status = index_status(root)
    if not status.get("ok"):
        return {
            "ok": False,
            "status": "requires_rebuild",
            "reason": status.get("reason", "index_unavailable"),
            "next_action": "tools.kb.cli formal-search-index",
            "query": query.strip(),
            "filters": {"account": account, "direction": direction, "document_role": document_role},
            "count": 0,
            "items": [],
        }
    cleaned_query = query.strip()
    if not cleaned_query:
        return {
            "ok": False,
            "status": "query_required",
            "query": "",
            "filters": {"account": account, "direction": direction, "document_role": document_role},
            "count": 0,
            "items": [],
        }
    index_path, _ = cache_paths(root)
    records = [
        item
        for item in read_index_records(index_path)
        if _metadata_matches(item, account.strip(), direction.strip(), document_role.strip())
        and is_within_allowed_root(str(item.get("path", "")), config)
    ]
    query_terms = list(dict.fromkeys(lexical_terms(cleaned_query)))
    query_vector = hashed_vector(cleaned_query, config.get("vector", {}))
    total = len(records)
    average_length = sum(max(int(item.get("term_count", 0) or 0), 1) for item in records) / max(total, 1)
    record_frequencies = [Counter(lexical_terms(str(item.get("text", "")))) for item in records]
    document_frequency = {term: sum(term in frequencies for frequencies in record_frequencies) for term in query_terms}
    keyword_raw: list[float] = []
    for item, frequencies in zip(records, record_frequencies):
        length = max(int(item.get("term_count", 0) or 0), 1)
        score = 0.0
        for term in query_terms:
            frequency = int(frequencies.get(term, 0) or 0)
            if not frequency:
                continue
            frequency_docs = document_frequency.get(term, 0)
            inverse = math.log(1 + ((total - frequency_docs + 0.5) / (frequency_docs + 0.5)))
            score += inverse * ((frequency * 2.2) / (frequency + 1.2 * (0.25 + 0.75 * length / average_length)))
        keyword_raw.append(score)
    keyword_max = max(keyword_raw, default=0.0)
    weights = config.get("weights", {}) if isinstance(config.get("weights"), dict) else {}
    results: list[dict[str, Any]] = []
    normalized_query = re.sub(r"\s+", "", cleaned_query.lower())
    for item, raw_keyword, frequencies in zip(records, keyword_raw, record_frequencies):
        text = str(item.get("text", ""))
        heading = str(item.get("heading", ""))
        path = str(item.get("path", ""))
        keyword_score = raw_keyword / keyword_max if keyword_max else 0.0
        vector_score = max(cosine(query_vector, item.get("vector", {})), 0.0)
        metadata_text = f"{heading} {path}".lower()
        metadata_hits = sum(term in metadata_text for term in query_terms)
        metadata_score = metadata_hits / max(len(query_terms), 1)
        exact = 1.0 if normalized_query and normalized_query in re.sub(r"\s+", "", text.lower()) else 0.0
        rerank_score = min(1.0, (0.7 * exact) + (0.3 * metadata_score))
        final_score = (
            float(weights.get("keyword", 0.55)) * keyword_score
            + float(weights.get("vector", 0.30)) * vector_score
            + float(weights.get("metadata", 0.10)) * metadata_score
            + float(weights.get("rerank", 0.05)) * rerank_score
        )
        if final_score <= 0:
            continue
        matched_terms = [term for term in query_terms if term in frequencies]
        snippet_limit = max(int(config.get("result", {}).get("snippet_chars", 320) or 320), 80)
        snippet = re.sub(r"\s+", " ", text).strip()
        if len(snippet) > snippet_limit:
            snippet = snippet[: snippet_limit - 1].rstrip() + "…"
        line_start = int(item.get("line_start", 1) or 1)
        line_end = int(item.get("line_end", line_start) or line_start)
        results.append(
            {
                "path": path,
                "heading": heading,
                "line_start": line_start,
                "line_end": line_end,
                "evidence_coordinate": f"{path}:L{line_start}-L{line_end}",
                "snippet": snippet,
                "account": item.get("account", ""),
                "direction": item.get("direction", ""),
                "document_role": item.get("document_role", ""),
                "score": round(final_score, 6),
                "score_details": {
                    "bm25": round(keyword_score, 6),
                    "vector": round(vector_score, 6),
                    "metadata": round(metadata_score, 6),
                    "rerank": round(rerank_score, 6),
                },
                "matched_terms": matched_terms[:20],
                "chunk_sha256": str(item.get("chunk_id", "")),
            }
        )
    results.sort(key=lambda item: (-float(item["score"]), item["path"], int(item["line_start"])))
    result_config = config.get("result", {}) if isinstance(config.get("result"), dict) else {}
    default_limit = max(int(result_config.get("default_limit", 8) or 8), 1)
    max_limit = max(int(result_config.get("max_limit", 30) or 30), default_limit)
    selected_limit = min(max(int(limit or default_limit), 1), max_limit)
    selected = results[:selected_limit]
    return {
        "ok": True,
        "status": "ready",
        "scope": "formal_only",
        "query": cleaned_query,
        "filters": {"account": account, "direction": direction, "document_role": document_role},
        "retrieval": {
            "keyword": "bm25",
            "vector": config.get("vector", {}).get("backend", "hashed_char_ngram_v1"),
            "metadata_filter": "strict",
            "rerank": "exact_phrase_and_heading_v1",
        },
        "count": len(selected),
        "items": selected,
        "token_boundary": "compact_formal_snippets_only",
    }
