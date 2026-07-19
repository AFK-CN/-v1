from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


TRACE_FIELDS = ("opening_mode", "progression_mode", "ending_mode")
CLICHE_CLOSERS = ("原来", "真正的", "没想到", "那一刻", "最后才", "治愈")


def normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def text_units(value: Any) -> set[str]:
    text = normalize(value)
    if len(text) <= 2:
        return {text} if text else set()
    return {text[index : index + 2] for index in range(len(text) - 1)}


def similarity(left: Any, right: Any) -> float:
    left_units = text_units(left)
    right_units = text_units(right)
    union = left_units | right_units
    return len(left_units & right_units) / len(union) if union else 0.0


def length_band(body: str) -> str:
    length = len(body)
    if length <= 140:
        return "short"
    if length <= 220:
        return "medium"
    return "long"


def sentence_edge(body: str, *, ending: bool = False) -> str:
    sentences = [item.strip() for item in re.split(r"[。！？!?]", body) if item.strip()]
    if not sentences:
        return ""
    return sentences[-1][-40:] if ending else sentences[0][:24]


def validate(payload: Any) -> dict[str, Any]:
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    errors: list[str] = []
    if not isinstance(items, list) or len(items) < 2:
        return {
            "ok": False,
            "errors": ["batch_requires_at_least_2_items"],
            "metrics": {"item_count": len(items) if isinstance(items, list) else 0},
        }

    summaries: list[dict[str, Any]] = []
    openings: list[str] = []
    progressions: list[str] = []
    endings: list[str] = []
    methods: list[str] = []
    bands: list[str] = []
    signatures: list[str] = []
    title_prefixes: list[str] = []
    opening_edges: list[str] = []
    ending_edges: list[str] = []

    for index, raw_item in enumerate(items, 1):
        if not isinstance(raw_item, dict):
            errors.append(f"item_{index}_must_be_object")
            continue
        title = str(raw_item.get("title") or "").strip()
        body = str(raw_item.get("body") or "").strip()
        structure = raw_item.get("structure_trace")
        method_trace = raw_item.get("method_trace")
        if not title:
            errors.append(f"item_{index}_title_required")
        if not body:
            errors.append(f"item_{index}_body_required")
        if not isinstance(structure, dict):
            errors.append(f"item_{index}_structure_trace_required")
            structure = {}
        if not isinstance(method_trace, dict):
            errors.append(f"item_{index}_method_trace_required")
            method_trace = {}

        trace_values: dict[str, str] = {}
        for field in TRACE_FIELDS:
            value = str(structure.get(field) or "").strip()
            if not value:
                errors.append(f"item_{index}_{field}_required")
            trace_values[field] = value

        method = str(method_trace.get("primary_method") or "").strip()
        if not method:
            errors.append(f"item_{index}_primary_method_required")

        band = length_band(body)
        signature = "|".join(
            [trace_values["opening_mode"], trace_values["progression_mode"], trace_values["ending_mode"], band]
        )
        openings.append(trace_values["opening_mode"])
        progressions.append(trace_values["progression_mode"])
        endings.append(trace_values["ending_mode"])
        methods.append(method)
        bands.append(band)
        signatures.append(signature)
        title_prefixes.append(normalize(title)[:6])
        opening_edges.append(sentence_edge(body))
        ending_edges.append(sentence_edge(body, ending=True))
        summaries.append(
            {
                "index": index,
                "title": title,
                "primary_method": method,
                "opening_mode": trace_values["opening_mode"],
                "progression_mode": trace_values["progression_mode"],
                "ending_mode": trace_values["ending_mode"],
                "length_band": band,
                "structure_signature": signature,
            }
        )

    item_count = len(items)
    if item_count >= 4:
        if len(set(openings)) < 3:
            errors.append("batch_requires_at_least_3_opening_modes")
        if len(set(endings)) < 3:
            errors.append("batch_requires_at_least_3_ending_modes")
        if len(set(methods)) < 3:
            errors.append("batch_requires_at_least_3_primary_methods")
        if len(set(bands)) < 2:
            errors.append("batch_requires_at_least_2_length_bands")
        required_signatures = max(3, math.ceil(item_count * 0.8))
        if len(set(signatures)) < required_signatures:
            errors.append(f"batch_requires_at_least_{required_signatures}_structure_signatures")

    for label, values in (
        ("opening_mode", openings),
        ("ending_mode", endings),
        ("title_prefix", title_prefixes),
    ):
        repeated = [value for value, count in Counter(values).items() if value and count >= 3]
        if repeated:
            errors.append(f"batch_{label}_repeated_3_or_more:{','.join(sorted(repeated))}")

    for left_index in range(item_count):
        for right_index in range(left_index + 1, item_count):
            if similarity(opening_edges[left_index], opening_edges[right_index]) >= 0.78:
                errors.append(f"opening_too_similar:{left_index + 1}:{right_index + 1}")
            if similarity(ending_edges[left_index], ending_edges[right_index]) >= 0.72:
                errors.append(f"ending_too_similar:{left_index + 1}:{right_index + 1}")

    bodies = [str(item.get("body") or "") for item in items if isinstance(item, dict)]
    for phrase in CLICHE_CLOSERS:
        used_by = [index + 1 for index, body in enumerate(bodies) if phrase in sentence_edge(body, ending=True)]
        if len(used_by) >= 2:
            errors.append(f"closing_cliche_reused:{phrase}:{','.join(map(str, used_by))}")

    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "metrics": {
            "item_count": item_count,
            "opening_mode_count": len(set(openings)),
            "progression_mode_count": len(set(progressions)),
            "ending_mode_count": len(set(endings)),
            "primary_method_count": len(set(methods)),
            "length_band_count": len(set(bands)),
            "structure_signature_count": len(set(signatures)),
        },
        "items": summaries,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_batch.py <batch.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"invalid_input:{exc}"]}, ensure_ascii=False, indent=2))
        return 2
    result = validate(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
