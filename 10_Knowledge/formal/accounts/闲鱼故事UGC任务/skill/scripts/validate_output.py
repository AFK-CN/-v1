from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


METHOD_IDS = {f"xugc-m0{index}" for index in range(1, 8)}
VISUAL_MODES = {
    "platform_evidence_chain",
    "object_truth_sequence",
    "hook_card_then_proof",
    "single_visual",
}
VISUAL_ROLES = {
    "hook_card",
    "listing_context",
    "object_context",
    "object_detail",
    "service_process",
    "chat_evidence",
    "feedback_evidence",
    "result_proof",
}
SCREENSHOT_ROLES = {"listing_context", "chat_evidence", "feedback_evidence"}
PHOTO_ROLES = {"object_context", "object_detail", "service_process", "result_proof"}
PRIVACY_FIELDS = {"faces", "names_and_avatars", "contact_and_order_info"}
PRIVACY_STATES = {"not_present", "redacted", "authorized"}
ABSTRACT_OPENINGS = (
    "闲鱼不只是",
    "在这个快节奏",
    "在这个万物",
    "有些东西的价值",
    "真正的告别",
)
CLICHE_TERMS = ("原来", "真正的", "治愈", "温柔", "沉甸甸", "独一无二", "闪闪发光")


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    hashtags = payload.get("hashtags")
    facts = payload.get("input_facts")
    evidence_notes = payload.get("evidence_notes")
    fabricated = payload.get("fabricated_claims")
    visual_claims = payload.get("visual_claims")
    visual_reviewed = payload.get("visual_evidence_reviewed") is True
    visual_package = payload.get("visual_package")
    trace = payload.get("method_trace")

    if not 8 <= len(title) <= 42:
        errors.append("title_length_must_be_8_to_42")
    if not 40 <= len(body) <= 900:
        errors.append("body_length_must_be_40_to_900")
    if not isinstance(hashtags, list) or not 2 <= len(hashtags) <= 8 or not all(str(item).strip() for item in hashtags):
        errors.append("hashtags_must_be_2_to_8_nonempty_items")
    if not isinstance(facts, list) or len(facts) < 2:
        errors.append("input_facts_requires_at_least_2")
    if not isinstance(evidence_notes, list) or not evidence_notes:
        errors.append("evidence_notes_required")
    if not isinstance(fabricated, list) or fabricated:
        errors.append("fabricated_claims_must_be_empty_list")
    if not isinstance(visual_claims, list):
        errors.append("visual_claims_must_be_list")
    elif visual_claims and not visual_reviewed:
        errors.append("visual_claims_require_reviewed_evidence")
    elif visual_claims and not isinstance(visual_package, dict):
        errors.append("visual_claims_require_visual_package")

    visual_mode = ""
    visual_frame_count = 0
    if visual_package is not None:
        if not isinstance(visual_package, dict):
            errors.append("visual_package_must_be_object")
        else:
            if not visual_reviewed:
                errors.append("visual_package_requires_reviewed_evidence")
            visual_mode = str(visual_package.get("mode") or "")
            if visual_mode not in VISUAL_MODES:
                errors.append("visual_mode_invalid")

            frames = visual_package.get("frames")
            frame_roles: list[str] = []
            if not isinstance(frames, list) or not 1 <= len(frames) <= 5:
                errors.append("visual_frames_must_be_1_to_5")
                frames = []
            visual_frame_count = len(frames)
            for index, frame in enumerate(frames):
                if not isinstance(frame, dict):
                    errors.append(f"visual_frame_{index + 1}_must_be_object")
                    continue
                role = str(frame.get("role") or "")
                frame_roles.append(role)
                if role not in VISUAL_ROLES:
                    errors.append(f"visual_frame_{index + 1}_role_invalid")
                if not str(frame.get("content") or "").strip():
                    errors.append(f"visual_frame_{index + 1}_content_required")
                if not str(frame.get("source_basis") or "").strip():
                    errors.append(f"visual_frame_{index + 1}_source_basis_required")
                evidence_type = str(frame.get("evidence_type") or "")
                if role in SCREENSHOT_ROLES and evidence_type not in {"supplied_screenshot", "verified_source_frame"}:
                    errors.append(f"visual_frame_{index + 1}_screenshot_must_be_real")
                if role == "hook_card" and frame.get("line_count") not in {1, 2}:
                    errors.append(f"visual_frame_{index + 1}_hook_card_must_be_1_or_2_lines")

            if visual_mode == "platform_evidence_chain" and not (
                any(role in SCREENSHOT_ROLES for role in frame_roles)
                and any(role in PHOTO_ROLES for role in frame_roles)
            ):
                errors.append("platform_evidence_chain_requires_real_screenshot_and_photo")
            if visual_mode == "object_truth_sequence" and not any(
                role in {"object_context", "object_detail", "service_process", "result_proof"}
                for role in frame_roles
            ):
                errors.append("object_truth_sequence_requires_object_or_process_frame")
            if visual_mode == "hook_card_then_proof" and not (
                len(frame_roles) >= 2 and frame_roles[0] == "hook_card" and any(role != "hook_card" for role in frame_roles[1:])
            ):
                errors.append("hook_card_requires_following_evidence_frame")
            if visual_mode == "single_visual" and len(frame_roles) != 1:
                errors.append("single_visual_requires_exactly_1_frame")

            privacy = visual_package.get("privacy_check")
            if not isinstance(privacy, dict) or set(privacy) != PRIVACY_FIELDS:
                errors.append("privacy_check_requires_all_fields")
            elif any(value not in PRIVACY_STATES for value in privacy.values()):
                errors.append("privacy_check_state_invalid")

            performance_claims = visual_package.get("performance_claims")
            if not isinstance(performance_claims, list) or performance_claims:
                errors.append("visual_performance_claims_must_be_empty_list")
            fabricated_visuals = visual_package.get("fabricated_visual_assets")
            if not isinstance(fabricated_visuals, list) or fabricated_visuals:
                errors.append("fabricated_visual_assets_must_be_empty_list")

            sequence_basis = str(visual_package.get("sequence_basis") or "")
            if sequence_basis not in {"recommended_structure", "user_verified_publish_order"}:
                errors.append("visual_sequence_basis_invalid")
            claims_actual_order = visual_package.get("claims_actual_publish_order") is True
            if claims_actual_order and (
                sequence_basis != "user_verified_publish_order"
                or not str(visual_package.get("publish_order_evidence") or "").strip()
            ):
                errors.append("actual_publish_order_claim_requires_evidence")
    if not isinstance(trace, dict):
        errors.append("method_trace_required")
        trace = {}
    primary = str(trace.get("primary_method") or "")
    support = trace.get("support_methods")
    completion = trace.get("completion_evidence")
    if primary not in METHOD_IDS:
        errors.append("primary_method_invalid")
    if not isinstance(support, list) or len(support) > 1 or any(item != "xugc-m07" for item in support):
        errors.append("support_methods_only_optional_m07")
    if not isinstance(completion, list) or len(completion) < 2:
        errors.append("completion_evidence_requires_at_least_2")
    if body.startswith(ABSTRACT_OPENINGS):
        errors.append("abstract_or_platform_opening_forbidden")
    if "爆款" in title or "爆款" in body:
        errors.append("performance_promise_forbidden")
    if len(re.findall(r"不是.{0,18}而是", body)) > 1:
        errors.append("contrast_template_overused")
    if sum(body.count(term) for term in CLICHE_TERMS) > 3:
        errors.append("cliche_density_too_high")
    if primary == "xugc-m06" and len(body) > 240:
        errors.append("short_transaction_story_too_long")
    if primary != "xugc-m06" and len(body) < 90:
        errors.append("full_story_too_short_for_selected_method")

    return {
        "ok": not errors,
        "errors": errors,
        "metrics": {
            "title_length": len(title),
            "body_length": len(body),
            "hashtag_count": len(hashtags) if isinstance(hashtags, list) else 0,
            "primary_method": primary,
            "support_method_count": len(support) if isinstance(support, list) else 0,
            "cliche_term_count": sum(body.count(term) for term in CLICHE_TERMS),
            "visual_mode": visual_mode or None,
            "visual_frame_count": visual_frame_count,
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_output.py <package.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"invalid_input:{exc}"]}, ensure_ascii=False, indent=2))
        return 2
    if not isinstance(payload, dict):
        result = {"ok": False, "errors": ["input_must_be_json_object"]}
    else:
        result = validate(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
