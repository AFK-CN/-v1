#!/usr/bin/env python3
"""Validate account-real visual references, two-stage master lineage, gates and QA."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_MODES = {
    "single_generation",
    "tableware_local_edit",
    "annotation_overlay",
    "crop",
    "local_edit",
    "tutorial_generation",
}
ANNOTATED_ROLES = {"annotated_cover", "cover"}
TUTORIAL_ROLES = {"tutorial", "steps", "process"}
RESULT_ROLES = {"result", "closeup", "side_staple"}
MASTER_REFERENCE_ROLES = {"annotated_cover", "clean_meal"}
HIGH_RISK_CLASSES = {
    "whole_fish",
    "fish",
    "shrimp",
    "beef",
    "pork",
    "chicken",
    "mushroom",
    "shellfish",
}
REVIEW_FIELDS = {
    "identity_continuity",
    "ingredient_morphology",
    "texture_naturalness",
    "lighting_continuity",
    "cookware_realism",
    "hand_identity",
}
REVIEW_VALUES = {"passed", "not_applicable"}
PROMPT_FIREWALL_FIELDS = {
    "qa_language_separated",
    "no_microtexture_enumeration",
    "single_role_per_reference",
    "no_uniform_sharpness_request",
}
MATERIAL_PRESERVATION_FIELDS = {
    "table_locked",
    "food_preservation",
    "composition_preservation",
    "lighting_preservation",
}
HEX = set("0123456789abcdef")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(char in HEX for char in text)


def _resolve_reference(
    path_value: str, package_root: Path, golden_manifest: Path
) -> Path | None:
    if path_value.startswith("golden:"):
        return (golden_manifest.parent / path_value.removeprefix("golden:")).resolve()
    if path_value.startswith("skill:"):
        try:
            skill_root = golden_manifest.parents[3]
        except IndexError:
            return None
        return (skill_root / path_value.removeprefix("skill:")).resolve()
    if path_value.startswith("package:"):
        return (package_root / path_value.removeprefix("package:")).resolve()
    return None


def _passed_gate(
    gate: Any, name: str, asset_id: str, errors: list[str]
) -> dict[str, Any]:
    if not isinstance(gate, dict):
        errors.append(f"{name}_missing")
        return {}
    if gate.get("status") != "passed":
        errors.append(f"{name}_not_passed")
    if str(gate.get("asset_id") or "") != asset_id:
        errors.append(f"{name}_asset_id_mismatch")
    if not str(gate.get("approved_at") or "").strip():
        errors.append(f"{name}_approved_at_missing")
    return gate


def validate(
    payload: dict[str, Any], package_root: Path, golden_manifest_path: Path
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        golden = json.loads(golden_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"golden_manifest_unreadable:{exc}"]}

    golden_items = {
        str(item.get("id")): item
        for item in golden.get("items", [])
        if isinstance(item, dict) and item.get("id")
    }
    negative_ids: set[str] = set()
    negative_manifest_value = str(golden.get("negative_package_manifest") or "").strip()
    if negative_manifest_value:
        negative_manifest_path = (
            golden_manifest_path.parent / negative_manifest_value
        ).resolve()
        try:
            negative_payload = json.loads(
                negative_manifest_path.read_text(encoding="utf-8")
            )
            negative_ids = {
                str(item.get("id"))
                for item in negative_payload.get("items", [])
                if isinstance(item, dict) and item.get("id")
            }
        except (OSError, json.JSONDecodeError):
            errors.append("negative_package_manifest_unreadable")

    if payload.get("schema_version") != 2:
        errors.append("schema_version_must_be_2")
    if payload.get("account_skill_id") != golden.get("account_skill_id"):
        errors.append("account_skill_id_mismatch")
    if payload.get("golden_package_id") != golden.get("golden_package_id"):
        errors.append("golden_package_id_mismatch")
    if str(payload.get("golden_package_version") or "") != str(
        golden.get("version") or ""
    ):
        errors.append("golden_package_version_mismatch")
    for field in (
        "skill_version",
        "content_id",
        "package_id",
        "food_master_asset_id",
        "master_asset_id",
    ):
        if not str(payload.get(field) or "").strip():
            errors.append(f"{field}_missing")
    generator = payload.get("generator")
    if (
        not isinstance(generator, dict)
        or not str(generator.get("name") or "").strip()
        or not str(generator.get("model_version") or "").strip()
    ):
        errors.append("generator_name_and_model_version_required")

    prompt_firewall = payload.get("prompt_firewall")
    if not isinstance(prompt_firewall, dict):
        errors.append("prompt_firewall_missing")
    else:
        for field in sorted(PROMPT_FIREWALL_FIELDS):
            if prompt_firewall.get(field) is not True:
                errors.append(f"prompt_firewall_must_pass:{field}")

    references = payload.get("references")
    reference_map: dict[str, dict[str, Any]] = {}
    if not isinstance(references, list) or not references:
        errors.append("references_missing")
        references = []
    for index, reference in enumerate(references):
        label = f"reference_{index}"
        if not isinstance(reference, dict):
            errors.append(f"{label}:not_object")
            continue
        ref_id = str(reference.get("id") or "").strip()
        label = ref_id or label
        if not ref_id:
            errors.append(f"{label}:id_missing")
            continue
        if ref_id in reference_map:
            errors.append(f"{label}:duplicate")
        reference_map[ref_id] = reference
        path_value = str(reference.get("path") or "")
        if ref_id in negative_ids or "negative-regression" in path_value:
            errors.append(f"{label}:negative_reference_forbidden")
        expected = str(reference.get("sha256") or "").lower()
        if not is_sha256(expected):
            errors.append(f"{label}:sha256_invalid")
        resolved = _resolve_reference(path_value, package_root, golden_manifest_path)
        if resolved is None:
            errors.append(f"{label}:reference_path_prefix_invalid")
        elif not resolved.is_file():
            errors.append(f"{label}:reference_file_missing")
        elif is_sha256(expected) and file_sha256(resolved) != expected:
            errors.append(f"{label}:reference_sha256_mismatch")
        if str(reference.get("kind") or "") == "golden":
            golden_item = golden_items.get(ref_id)
            if not golden_item:
                errors.append(f"{label}:golden_id_unknown")
            else:
                if path_value != f"golden:{golden_item.get('path')}":
                    errors.append(f"{label}:golden_path_mismatch")
                if expected != str(golden_item.get("sha256") or "").lower():
                    errors.append(f"{label}:golden_sha256_mismatch")

    validation_reference_ids = {
        str(value) for value in payload.get("validation_reference_asset_ids") or []
    }
    for ref_id in validation_reference_ids:
        if ref_id not in reference_map:
            errors.append(f"validation_reference_not_declared:{ref_id}")

    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        return {"ok": False, "errors": errors + ["pages_missing"]}
    page_map: dict[str, dict[str, Any]] = {}
    food_master_id = str(payload.get("food_master_asset_id") or "")
    master_id = str(payload.get("master_asset_id") or "")
    tutorial_ids: list[str] = []
    result_ids: list[str] = []
    prompt_hashes: list[str] = []

    for index, page in enumerate(pages):
        label = f"page_{index}"
        if not isinstance(page, dict):
            errors.append(f"{label}:not_object")
            continue
        page_id = str(page.get("id") or "").strip()
        label = page_id or label
        if not page_id:
            errors.append(f"{label}:id_missing")
            continue
        if page_id in page_map:
            errors.append(f"{label}:duplicate")
        page_map[page_id] = page
        role = str(page.get("role") or "").strip().lower()
        mode = str(page.get("generation_mode") or "").strip()
        if mode not in ALLOWED_MODES:
            errors.append(f"{label}:generation_mode_invalid")
        if mode == "text_only_generation":
            errors.append(f"{label}:text_only_generation_forbidden")
        if str(page.get("status") or "") != "approved":
            errors.append(f"{label}:status_must_be_approved")

        file_value = str(page.get("file") or "").strip()
        target = (package_root / file_value).resolve()
        try:
            target.relative_to(package_root.resolve())
        except ValueError:
            errors.append(f"{label}:file_outside_package")
        else:
            if not target.is_file():
                errors.append(f"{label}:file_missing")
            elif not is_sha256(page.get("sha256")):
                errors.append(f"{label}:sha256_invalid")
            elif file_sha256(target) != str(page.get("sha256")).lower():
                errors.append(f"{label}:sha256_mismatch")
        prompt_hash = str(page.get("prompt_sha256") or "").lower()
        if not is_sha256(prompt_hash):
            errors.append(f"{label}:prompt_sha256_invalid")
        else:
            prompt_hashes.append(prompt_hash)

        parent_ids = page.get("parent_ids")
        if not isinstance(parent_ids, list):
            errors.append(f"{label}:parent_ids_not_list")
            parent_ids = []
        page_refs = page.get("reference_asset_ids")
        if not isinstance(page_refs, list) or not page_refs:
            errors.append(f"{label}:reference_asset_ids_missing")
            page_refs = []
        for ref_id_value in page_refs:
            ref_id = str(ref_id_value)
            if ref_id not in reference_map:
                errors.append(f"{label}:reference_not_declared:{ref_id}")
            if golden_items.get(ref_id, {}).get("source_kind") == "user_accepted":
                errors.append(f"{label}:user_accepted_generation_reference_forbidden:{ref_id}")

        if page_id == food_master_id:
            expected_role = "master_meal" if food_master_id == master_id else "food_master"
            if role != expected_role:
                errors.append(f"{label}:food_master_role_invalid")
            if mode != "single_generation":
                errors.append(f"{label}:food_master_mode_must_be_single_generation")
            if parent_ids:
                errors.append(f"{label}:food_master_must_not_have_page_parent")
            valid_master_refs = []
            for ref_id_value in page_refs:
                item = golden_items.get(str(ref_id_value), {})
                valid = (
                    item.get("source_kind") == "account_source"
                    and item.get("role") in MASTER_REFERENCE_ROLES
                    and "master_reference" in item.get("use_for", [])
                )
                if valid:
                    valid_master_refs.append(str(ref_id_value))
                else:
                    errors.append(
                        f"{label}:food_master_reference_role_invalid:{ref_id_value}"
                    )
            if len(set(valid_master_refs)) < 2:
                errors.append(f"{label}:food_master_requires_2_account_master_refs")
        elif page_id == master_id and master_id != food_master_id:
            if role != "master_meal":
                errors.append(f"{label}:master_role_invalid")
            if mode != "tableware_local_edit":
                errors.append(f"{label}:master_mode_must_be_tableware_local_edit")
            if parent_ids != [food_master_id]:
                errors.append(f"{label}:tableware_edit_must_parent_food_master")
            material_refs = [
                str(ref_id)
                for ref_id in page_refs
                if reference_map.get(str(ref_id), {}).get("reference_role")
                == "tableware_material_only"
            ]
            if not material_refs:
                errors.append(f"{label}:tableware_material_reference_missing")
        else:
            if parent_ids != [master_id]:
                errors.append(f"{label}:derived_page_must_directly_parent_final_master")
            if role in ANNOTATED_ROLES and mode not in {"annotation_overlay", "local_edit"}:
                errors.append(f"{label}:annotated_cover_must_edit_master")
            if role in RESULT_ROLES and mode not in {"crop", "local_edit"}:
                errors.append(f"{label}:result_must_crop_or_edit_master")
            if role in TUTORIAL_ROLES:
                tutorial_ids.append(page_id)
                if mode != "tutorial_generation":
                    errors.append(f"{label}:tutorial_mode_invalid")
                has_tutorial_ref = any(
                    golden_items.get(str(ref_id), {}).get("source_kind")
                    == "account_source"
                    and golden_items.get(str(ref_id), {}).get("role")
                    in {"tutorial", "process"}
                    for ref_id in page_refs
                )
                if not has_tutorial_ref:
                    errors.append(f"{label}:account_tutorial_reference_missing")
            if role in RESULT_ROLES:
                result_ids.append(page_id)

        hand_present = page.get("hand_present")
        if not isinstance(hand_present, bool):
            errors.append(f"{label}:hand_present_boolean_required")
        elif hand_present:
            valid_hand_anchor = any(
                reference_map.get(str(ref_id), {}).get("reference_role")
                == "hand_identity"
                for ref_id in page_refs
            )
            if not valid_hand_anchor:
                errors.append(f"{label}:hand_anchor_missing")
        review = page.get("visual_review")
        if not isinstance(review, dict):
            errors.append(f"{label}:visual_review_missing")
        else:
            for field in sorted(REVIEW_FIELDS):
                value = str(review.get(field) or "")
                if value not in REVIEW_VALUES:
                    errors.append(f"{label}:visual_review_invalid:{field}")
            for field in (
                "identity_continuity",
                "ingredient_morphology",
                "texture_naturalness",
                "lighting_continuity",
            ):
                if review.get(field) != "passed":
                    errors.append(f"{label}:visual_review_must_pass:{field}")
            if role in TUTORIAL_ROLES and review.get("cookware_realism") != "passed":
                errors.append(f"{label}:cookware_realism_must_pass")
            if hand_present is True and review.get("hand_identity") != "passed":
                errors.append(f"{label}:hand_identity_must_pass")

    if food_master_id not in page_map:
        errors.append("food_master_asset_id_unknown")
    if master_id not in page_map:
        errors.append("master_asset_id_unknown")
    for page_id, page in page_map.items():
        for parent_id in page.get("parent_ids") or []:
            if parent_id not in page_map:
                errors.append(f"{page_id}:parent_unknown:{parent_id}")

    _passed_gate(payload.get("food_master_gate"), "food_master_gate", food_master_id, errors)
    material_gate = payload.get("material_gate")
    if not isinstance(material_gate, dict):
        errors.append("material_gate_missing")
    elif master_id == food_master_id:
        if material_gate.get("status") != "skipped":
            errors.append("material_gate_must_be_skipped_without_tableware_edit")
        if str(material_gate.get("asset_id") or "") != master_id:
            errors.append("material_gate_asset_id_mismatch")
    else:
        if material_gate.get("status") != "passed":
            errors.append("material_gate_not_passed")
        if str(material_gate.get("asset_id") or "") != master_id:
            errors.append("material_gate_asset_id_mismatch")
        if not str(material_gate.get("approved_at") or "").strip():
            errors.append("material_gate_approved_at_missing")
        for field in sorted(MATERIAL_PRESERVATION_FIELDS):
            if material_gate.get(field) is not True:
                errors.append(f"material_gate_preservation_must_pass:{field}")

    ingredients = payload.get("ingredients")
    if not isinstance(ingredients, list) or not ingredients:
        errors.append("ingredients_missing")
        ingredients = []
    for index, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            errors.append(f"ingredient_{index}:not_object")
            continue
        name = str(ingredient.get("name") or f"ingredient_{index}")
        ingredient_class = str(ingredient.get("class") or "").strip()
        risk = str(ingredient.get("risk") or "").lower()
        refs = ingredient.get("reference_asset_ids") or []
        if risk not in {"low", "medium", "high"}:
            errors.append(f"ingredient:{name}:risk_invalid")
        if not ingredient_class:
            errors.append(f"ingredient:{name}:class_missing")
        if risk == "high" or ingredient_class in HIGH_RISK_CLASSES:
            valid_real_ref = any(
                golden_items.get(str(ref_id), {}).get("source_kind")
                == "account_source"
                and "ingredient_real"
                in golden_items.get(str(ref_id), {}).get("use_for", [])
                and ingredient_class
                in golden_items.get(str(ref_id), {}).get("ingredient_classes", [])
                for ref_id in refs
            )
            if not valid_real_ref:
                errors.append(f"ingredient:{name}:high_risk_real_reference_missing")
        for ref_id in refs:
            if str(ref_id) not in reference_map:
                errors.append(f"ingredient:{name}:reference_not_declared:{ref_id}")

    calibration = payload.get("calibration_gate")
    if not isinstance(calibration, dict) or calibration.get("status") != "passed":
        errors.append("calibration_gate_not_passed")
        calibration_ids: set[str] = set()
    else:
        calibration_ids = {str(value) for value in calibration.get("page_ids") or []}
        if not str(calibration.get("approved_at") or "").strip():
            errors.append("calibration_gate_approved_at_missing")
    if master_id not in calibration_ids:
        errors.append("calibration_gate_final_master_missing")
    if not calibration_ids.intersection(tutorial_ids):
        errors.append("calibration_gate_tutorial_missing")
    if not calibration_ids.intersection(result_ids):
        errors.append("calibration_gate_result_missing")
    parallelism = payload.get("batch_parallelism")
    if (
        not isinstance(parallelism, dict)
        or parallelism.get("unlocked_after_calibration") is not True
    ):
        errors.append("batch_parallelism_not_unlocked_after_calibration")

    prompt_set_sha256 = hashlib.sha256(
        "\n".join(sorted(prompt_hashes)).encode("utf-8")
    ).hexdigest()
    return {
        "ok": not errors,
        "validator": "visual-package-v2.0",
        "account_skill_id": payload.get("account_skill_id"),
        "content_id": payload.get("content_id"),
        "package_id": payload.get("package_id"),
        "page_count": len(pages),
        "reference_count": len(references),
        "prompt_set_sha256": prompt_set_sha256,
        "errors": errors,
    }


def validate_file(
    input_path: Path,
    package_root: Path,
    golden_manifest_path: Path,
    *,
    write_validation: bool = False,
) -> dict[str, Any]:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"input_unreadable:{exc}"]}
    result = validate(payload, package_root, golden_manifest_path)
    if write_validation and result["ok"]:
        payload["validation"] = {
            "status": "passed",
            "validator": result["validator"],
            "validated_at": datetime.now(timezone.utc)
            .astimezone()
            .isoformat(timespec="seconds"),
            "prompt_set_sha256": result["prompt_set_sha256"],
        }
        input_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["validation_written"] = True
        result["visual_manifest_sha256"] = file_sha256(input_path)
    return result


def _review(*, tutorial: bool = False) -> dict[str, str]:
    return {
        "identity_continuity": "passed",
        "ingredient_morphology": "passed",
        "texture_naturalness": "passed",
        "lighting_continuity": "passed",
        "cookware_realism": "passed" if tutorial else "not_applicable",
        "hand_identity": "not_applicable",
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        golden_dir = root / "skill/assets/visual/golden-package-v2"
        golden_dir.mkdir(parents=True)
        skill_visual = root / "skill/assets/visual"
        package = root / "package"
        package.mkdir()
        for name in (
            "account-cover-a.jpg",
            "account-cover-b.jpg",
            "account-tutorial.jpg",
            "account-result.jpg",
            "accepted-clean.png",
        ):
            (golden_dir / name).write_bytes(name.encode("utf-8"))
        material = skill_visual / "optional-tableware.png"
        material.write_bytes(b"material")
        golden_items = [
            {
                "id": "account-cover-a",
                "path": "account-cover-a.jpg",
                "sha256": file_sha256(golden_dir / "account-cover-a.jpg"),
                "source_kind": "account_source",
                "role": "clean_meal",
                "ingredient_classes": ["shrimp"],
                "use_for": ["master_reference"],
            },
            {
                "id": "account-cover-b",
                "path": "account-cover-b.jpg",
                "sha256": file_sha256(golden_dir / "account-cover-b.jpg"),
                "source_kind": "account_source",
                "role": "annotated_cover",
                "ingredient_classes": ["shrimp"],
                "use_for": ["master_reference"],
            },
            {
                "id": "account-tutorial",
                "path": "account-tutorial.jpg",
                "sha256": file_sha256(golden_dir / "account-tutorial.jpg"),
                "source_kind": "account_source",
                "role": "tutorial",
                "ingredient_classes": ["shrimp"],
                "use_for": ["kitchen_process"],
            },
            {
                "id": "account-result",
                "path": "account-result.jpg",
                "sha256": file_sha256(golden_dir / "account-result.jpg"),
                "source_kind": "account_source",
                "role": "result",
                "ingredient_classes": ["shrimp"],
                "use_for": ["ingredient_real"],
            },
            {
                "id": "accepted-clean",
                "path": "accepted-clean.png",
                "sha256": file_sha256(golden_dir / "accepted-clean.png"),
                "source_kind": "user_accepted",
                "role": "clean_meal",
                "reference_policy": "validation_only",
                "ingredient_classes": ["tofu"],
                "use_for": ["package_continuity"],
            },
        ]
        negative_dir = golden_dir.parent / "negative-regression-v1"
        negative_dir.mkdir()
        (negative_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "source_kind": "user_rejected_output",
                    "reference_policy": "validation_only",
                    "never_use_as_positive_reference": True,
                    "items": [{"id": "negative-rejected"}],
                }
            ),
            encoding="utf-8",
        )
        golden = {
            "schema_version": 2,
            "golden_package_id": "golden-test-v2",
            "account_skill_id": "account-test",
            "version": "2.0",
            "negative_package_manifest": "../negative-regression-v1/manifest.json",
            "items": golden_items,
        }
        golden_manifest = golden_dir / "manifest.json"
        golden_manifest.write_text(json.dumps(golden), encoding="utf-8")
        for name in ("food.png", "master.png", "cover.png", "tutorial.png", "result.png"):
            (package / name).write_bytes(name.encode("utf-8"))
        refs = [
            {
                "id": item["id"],
                "kind": "golden",
                "path": f"golden:{item['path']}",
                "sha256": item["sha256"],
            }
            for item in golden_items
        ]
        refs.append(
            {
                "id": "optional-tableware",
                "kind": "skill_asset",
                "reference_role": "tableware_material_only",
                "path": "skill:assets/visual/optional-tableware.png",
                "sha256": file_sha256(material),
            }
        )
        prompt = hashlib.sha256(b"prompt").hexdigest()
        payload = {
            "schema_version": 2,
            "account_skill_id": "account-test",
            "skill_version": "2.0",
            "golden_package_id": "golden-test-v2",
            "golden_package_version": "2.0",
            "content_id": "content-test",
            "package_id": "package-test",
            "generator": {"name": "test-generator", "model_version": "test-model"},
            "food_master_asset_id": "food-master",
            "master_asset_id": "master",
            "prompt_firewall": {
                "qa_language_separated": True,
                "no_microtexture_enumeration": True,
                "single_role_per_reference": True,
                "no_uniform_sharpness_request": True,
            },
            "validation_reference_asset_ids": ["accepted-clean"],
            "ingredients": [
                {
                    "name": "虾",
                    "class": "shrimp",
                    "risk": "high",
                    "reference_asset_ids": ["account-result"],
                }
            ],
            "references": refs,
            "pages": [
                {
                    "id": "food-master",
                    "role": "food_master",
                    "file": "food.png",
                    "sha256": file_sha256(package / "food.png"),
                    "status": "approved",
                    "generation_mode": "single_generation",
                    "parent_ids": [],
                    "reference_asset_ids": ["account-cover-a", "account-cover-b"],
                    "prompt_sha256": prompt,
                    "hand_present": False,
                    "visual_review": _review(),
                },
                {
                    "id": "master",
                    "role": "master_meal",
                    "file": "master.png",
                    "sha256": file_sha256(package / "master.png"),
                    "status": "approved",
                    "generation_mode": "tableware_local_edit",
                    "parent_ids": ["food-master"],
                    "reference_asset_ids": ["optional-tableware"],
                    "prompt_sha256": prompt,
                    "hand_present": False,
                    "visual_review": _review(),
                },
                {
                    "id": "cover",
                    "role": "annotated_cover",
                    "file": "cover.png",
                    "sha256": file_sha256(package / "cover.png"),
                    "status": "approved",
                    "generation_mode": "annotation_overlay",
                    "parent_ids": ["master"],
                    "reference_asset_ids": ["account-cover-b"],
                    "prompt_sha256": prompt,
                    "hand_present": False,
                    "visual_review": _review(),
                },
                {
                    "id": "tutorial",
                    "role": "tutorial",
                    "file": "tutorial.png",
                    "sha256": file_sha256(package / "tutorial.png"),
                    "status": "approved",
                    "generation_mode": "tutorial_generation",
                    "parent_ids": ["master"],
                    "reference_asset_ids": ["account-tutorial", "account-result"],
                    "prompt_sha256": prompt,
                    "hand_present": False,
                    "visual_review": _review(tutorial=True),
                },
                {
                    "id": "result",
                    "role": "result",
                    "file": "result.png",
                    "sha256": file_sha256(package / "result.png"),
                    "status": "approved",
                    "generation_mode": "crop",
                    "parent_ids": ["master"],
                    "reference_asset_ids": ["account-result"],
                    "prompt_sha256": prompt,
                    "hand_present": False,
                    "visual_review": _review(),
                },
            ],
            "food_master_gate": {
                "status": "passed",
                "asset_id": "food-master",
                "approved_at": "2026-07-19T12:00:00+08:00",
            },
            "material_gate": {
                "status": "passed",
                "asset_id": "master",
                "approved_at": "2026-07-19T12:05:00+08:00",
                "table_locked": True,
                "food_preservation": True,
                "composition_preservation": True,
                "lighting_preservation": True,
            },
            "calibration_gate": {
                "status": "passed",
                "page_ids": ["master", "tutorial", "result"],
                "approved_at": "2026-07-19T12:10:00+08:00",
            },
            "batch_parallelism": {"unlocked_after_calibration": True},
        }
        passing = validate(payload, package, golden_manifest)
        lineage_path = package / "visual-lineage.json"
        lineage_path.write_text(json.dumps(payload), encoding="utf-8")
        write_case = validate_file(
            lineage_path, package, golden_manifest, write_validation=True
        )
        written_payload = json.loads(lineage_path.read_text(encoding="utf-8"))

        accepted_direct_payload = copy.deepcopy(payload)
        accepted_direct_payload["pages"][0]["reference_asset_ids"].append(
            "accepted-clean"
        )
        accepted_direct = validate(accepted_direct_payload, package, golden_manifest)
        closeup_master_payload = copy.deepcopy(payload)
        closeup_master_payload["pages"][0]["reference_asset_ids"].append(
            "account-result"
        )
        closeup_master = validate(closeup_master_payload, package, golden_manifest)
        prompt_fail_payload = copy.deepcopy(payload)
        prompt_fail_payload["prompt_firewall"]["no_microtexture_enumeration"] = False
        prompt_fail = validate(prompt_fail_payload, package, golden_manifest)
        preservation_fail_payload = copy.deepcopy(payload)
        preservation_fail_payload["material_gate"]["food_preservation"] = False
        preservation_fail = validate(
            preservation_fail_payload, package, golden_manifest
        )
        derived_chain_payload = copy.deepcopy(payload)
        derived_chain_payload["pages"][4]["parent_ids"] = ["cover"]
        derived_chain = validate(derived_chain_payload, package, golden_manifest)
        qa_fail_payload = copy.deepcopy(payload)
        qa_fail_payload["pages"][3]["visual_review"]["texture_naturalness"] = "failed"
        qa_fail = validate(qa_fail_payload, package, golden_manifest)
        hash_fail_payload = copy.deepcopy(payload)
        hash_fail_payload["pages"][0]["sha256"] = "0" * 64
        hash_fail = validate(hash_fail_payload, package, golden_manifest)
        negative_reference_payload = copy.deepcopy(payload)
        negative_reference_payload["references"].append(
            {
                "id": "negative-rejected",
                "kind": "package",
                "path": "package:master.png",
                "sha256": file_sha256(package / "master.png"),
            }
        )
        negative_reference_payload["pages"][0]["reference_asset_ids"].append(
            "negative-rejected"
        )
        negative_reference = validate(
            negative_reference_payload, package, golden_manifest
        )
        ok = (
            passing["ok"]
            and write_case["ok"]
            and write_case.get("validation_written") is True
            and written_payload.get("validation", {}).get("status") == "passed"
            and not accepted_direct["ok"]
            and not closeup_master["ok"]
            and not prompt_fail["ok"]
            and not preservation_fail["ok"]
            and not derived_chain["ok"]
            and not qa_fail["ok"]
            and not hash_fail["ok"]
            and not negative_reference["ok"]
            and "negative-rejected:negative_reference_forbidden"
            in negative_reference["errors"]
        )
        return {
            "ok": ok,
            "passing_case": passing,
            "write_validation_case": write_case,
            "negative_cases": {
                "accepted_ai_generation_reference": accepted_direct["errors"],
                "ingredient_closeup_in_food_master": closeup_master["errors"],
                "prompt_firewall_failed": prompt_fail["errors"],
                "tableware_preservation_failed": preservation_fail["errors"],
                "derived_from_derived": derived_chain["errors"],
                "visual_qa_failed": qa_fail["errors"],
                "file_hash_mismatch": hash_fail["errors"],
                "negative_reference_forbidden": negative_reference["errors"],
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--golden-manifest", type=Path)
    parser.add_argument("--write-validation", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.input and args.package_root and args.golden_manifest:
        result = validate_file(
            args.input,
            args.package_root,
            args.golden_manifest,
            write_validation=args.write_validation,
        )
    else:
        parser.error(
            "provide --self-test or --input, --package-root and --golden-manifest"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
