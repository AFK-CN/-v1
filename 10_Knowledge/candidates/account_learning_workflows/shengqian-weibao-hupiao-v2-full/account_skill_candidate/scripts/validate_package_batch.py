#!/usr/bin/env python3
"""Validate package-level deduplication and dynamic meal-page allocation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


COMPLEX_LEVELS = {"simple": 0, "medium": 1, "complex": 2, "简单": 0, "中等": 1, "复杂": 2}
TUTORIAL_ROLES = {"tutorial", "steps", "step", "process", "教程", "步骤", "过程"}
GRID_LAYOUTS = {"grid_2x2", "2x2", "四宫格"}
VISUAL_RISK_LEVELS = {"low", "medium", "high"}


def normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value or "").strip().lower())


def complexity(value: Any) -> int:
    if isinstance(value, int):
        return max(0, min(2, value))
    return COMPLEX_LEVELS.get(str(value or "").strip().lower(), -1)


def dish_key(item: Any) -> str:
    if isinstance(item, str):
        return normalize(item)
    if not isinstance(item, dict):
        return ""
    ingredient = normalize(item.get("ingredient_key") or item.get("name"))
    technique = normalize(item.get("technique"))
    return f"{ingredient}|{technique}" if technique else ingredient


def subject_keys(item: Any) -> set[str]:
    if isinstance(item, str):
        return {normalize(item)}
    if not isinstance(item, dict):
        return set()
    values = {
        normalize(item.get("name")),
        normalize(item.get("ingredient_key")),
        dish_key(item),
    }
    return {value for value in values if value}


def staple_key(item: Any) -> str:
    if isinstance(item, str):
        return normalize(item)
    if not isinstance(item, dict):
        return ""
    return normalize(item.get("category") or item.get("name"))


def is_rice_category(value: Any) -> bool:
    key = normalize(value)
    return "rice" in key or "米饭" in key or key in {"杂粮饭", "紫米饭"}


def primary_key(package: dict[str, Any]) -> str:
    dishes = package.get("dishes") if isinstance(package.get("dishes"), list) else []
    for dish in dishes:
        if isinstance(dish, dict) and str(dish.get("role") or "").lower() in {"main", "primary", "主菜"}:
            return dish_key(dish)
    return dish_key(dishes[0]) if dishes else ""


def signature(package: dict[str, Any]) -> str:
    dishes = package.get("dishes") if isinstance(package.get("dishes"), list) else []
    dish_keys = sorted(key for key in (dish_key(item) for item in dishes) if key)
    return f"dishes={'+'.join(dish_keys)};staple={staple_key(package.get('staple'))}"


def tutorial_subjects(package: dict[str, Any]) -> set[str]:
    pages = package.get("pages") if isinstance(package.get("pages"), list) else []
    result: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            continue
        if str(page.get("role") or "").strip().lower() not in TUTORIAL_ROLES:
            continue
        result.add(normalize(page.get("subject_key") or page.get("subject")))
    return {value for value in result if value}


def tutorial_layouts(package: dict[str, Any]) -> list[str]:
    pages = package.get("pages") if isinstance(package.get("pages"), list) else []
    result: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        if str(page.get("role") or "").strip().lower() not in TUTORIAL_ROLES:
            continue
        result.append(str(page.get("layout_family") or "").strip().lower())
    return result


def overlap(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_set = {dish_key(item) for item in left.get("dishes", []) if dish_key(item)}
    right_set = {dish_key(item) for item in right.get("dishes", []) if dish_key(item)}
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    packages = payload.get("packages")
    history = payload.get("history_packages") or []
    errors: list[str] = []
    if not isinstance(packages, list) or not packages:
        return {"ok": False, "package_count": 0, "signatures": [], "errors": ["packages_missing"]}
    if not isinstance(history, list):
        errors.append("history_packages_not_list")
        history = []

    identifiers: list[str] = []
    signatures: list[str] = []
    staple_categories: list[str] = []
    step_counts: list[int] = []
    complex_counts: list[int] = []
    layout_policy_enabled = bool(str(payload.get("layout_policy_version") or "").strip())
    visual_policy_enabled = bool(str(payload.get("visual_policy_version") or "").strip())
    all_tutorial_layouts: list[str] = []

    if visual_policy_enabled:
        if str(payload.get("visual_policy_version") or "") != "2.0":
            errors.append("visual:visual_policy_version_must_be_2.0")
        if payload.get("golden_package_id") != "shengqian-visual-golden-v2":
            errors.append("visual:golden_package_id_invalid")
        if str(payload.get("golden_package_version") or "") != "2.0":
            errors.append("visual:golden_package_version_invalid")
        if payload.get("food_master_gate_required") is not True:
            errors.append("visual:food_master_gate_must_be_required")
        if payload.get("tableware_gate_required") is not True:
            errors.append("visual:tableware_gate_must_be_required")
        if payload.get("prompt_firewall_required") is not True:
            errors.append("visual:prompt_firewall_must_be_required")
        if payload.get("table_locked") is not True:
            errors.append("visual:table_must_be_locked")
        if payload.get("calibration_gate_required") is not True:
            errors.append("visual:calibration_gate_must_be_required")
        if payload.get("parallel_generation_locked") is not True:
            errors.append("visual:parallel_generation_must_start_locked")

    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            errors.append(f"package_{index}:not_object")
            continue
        package_id = str(package.get("package_id") or f"index_{index}")
        identifiers.append(package_id)
        dishes = package.get("dishes")
        if not isinstance(dishes, list) or not 2 <= len(dishes) <= 3:
            errors.append(f"{package_id}:dish_count_must_be_2_to_3")
            dishes = dishes if isinstance(dishes, list) else []
        if any(not dish_key(item) for item in dishes):
            errors.append(f"{package_id}:dish_key_missing")
        staple = package.get("staple")
        current_staple = staple_key(staple)
        if not current_staple:
            errors.append(f"{package_id}:staple_missing")
        staple_categories.append(current_staple)

        if visual_policy_enabled:
            if package.get("food_master_required") is not True:
                errors.append(f"{package_id}:food_master_must_be_required")
            if package.get("tableware_edit_policy") != "optional_after_food_approval":
                errors.append(f"{package_id}:tableware_edit_policy_invalid")
            if package.get("table_locked") is not True:
                errors.append(f"{package_id}:table_must_be_locked")
            if package.get("visual_lineage_manifest_required") is not True:
                errors.append(f"{package_id}:visual_lineage_manifest_must_be_required")
            texture_high_count = 0
            for item_index, item in enumerate([*dishes, staple]):
                item_label = dish_key(item) if item_index < len(dishes) else current_staple
                item_label = item_label or f"item_{item_index}"
                if not isinstance(item, dict):
                    errors.append(f"{package_id}:{item_label}:visual_plan_requires_object")
                    continue
                risk = str(item.get("visual_risk") or "").strip().lower()
                if risk not in VISUAL_RISK_LEVELS:
                    errors.append(f"{package_id}:{item_label}:visual_risk_missing_or_invalid")
                if risk == "high" and item.get("real_reference_planned") is not True:
                    errors.append(f"{package_id}:{item_label}:high_risk_real_reference_not_planned")
                texture_risk = str(item.get("texture_risk") or "").strip().lower()
                if texture_risk not in VISUAL_RISK_LEVELS:
                    errors.append(f"{package_id}:{item_label}:texture_risk_missing_or_invalid")
                elif texture_risk == "high":
                    texture_high_count += 1
            if texture_high_count > 2:
                errors.append(f"{package_id}:texture_risk_high_count_exceeds_2:{texture_high_count}")

        current_signature = signature(package)
        signatures.append(current_signature)
        tutorials = tutorial_subjects(package)
        layouts = tutorial_layouts(package)
        if layout_policy_enabled:
            for page_index, family in enumerate(layouts):
                if not family:
                    errors.append(f"{package_id}:tutorial_{page_index}:layout_family_missing")
        all_tutorial_layouts.extend(family for family in layouts if family)
        step_counts.append(len(tutorials))
        required: list[tuple[str, set[str]]] = []
        current_complex_count = 0
        for dish in dishes:
            level = complexity(dish.get("complexity") if isinstance(dish, dict) else None)
            if level < 0:
                errors.append(f"{package_id}:{dish_key(dish) or 'dish'}:complexity_missing")
            if level == 2:
                current_complex_count += 1
                required.append((dish_key(dish), subject_keys(dish)))
        if isinstance(staple, dict):
            staple_level = complexity(staple.get("complexity"))
            if staple_level == 2:
                current_complex_count += 1
                required.append((current_staple, subject_keys(staple)))
        complex_counts.append(current_complex_count)
        for label, aliases in required:
            if not aliases.intersection(tutorials):
                errors.append(f"{package_id}:complex_subject_missing_tutorial:{label}")

    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            continue
        package_id = str(package.get("package_id") or f"index_{index}")
        for prior_index in range(index):
            prior = packages[prior_index]
            if not isinstance(prior, dict):
                continue
            prior_id = str(prior.get("package_id") or f"index_{prior_index}")
            if signature(package) == signature(prior):
                errors.append(f"{package_id}:duplicate_package_in_batch:{prior_id}")
            elif (
                staple_key(package.get("staple")) == staple_key(prior.get("staple"))
                and overlap(package, prior) >= 0.67
                and (
                    primary_key(package) == primary_key(prior)
                    or normalize(package.get("core_angle")) == normalize(prior.get("core_angle"))
                )
            ):
                errors.append(f"{package_id}:near_duplicate_package_in_batch:{prior_id}")
        for history_index, prior in enumerate(history):
            if not isinstance(prior, dict):
                continue
            prior_id = str(prior.get("package_id") or f"history_{history_index}")
            if signature(package) == signature(prior):
                errors.append(f"{package_id}:duplicate_package_in_history:{prior_id}")
            elif (
                staple_key(package.get("staple")) == staple_key(prior.get("staple"))
                and overlap(package, prior) >= 0.67
                and primary_key(package) == primary_key(prior)
            ):
                errors.append(f"{package_id}:near_duplicate_package_in_history:{prior_id}")

    if len(packages) >= 2:
        if len(set(staple_categories)) < 2:
            errors.append("batch:staple_category_rotation_missing")
        if all(is_rice_category(category) for category in staple_categories):
            errors.append("batch:staples_cannot_all_be_rice")
        for index in range(1, len(staple_categories)):
            if staple_categories[index] == staple_categories[index - 1]:
                errors.append(f"batch:consecutive_staple_category_repeat:{index - 1}:{index}")
        if len(set(complex_counts)) > 1 and len(set(step_counts)) == 1:
            errors.append("batch:step_page_count_looks_fixed_despite_complexity_change")

    if layout_policy_enabled:
        layout_count = len(all_tutorial_layouts)
        unique_layouts = set(all_tutorial_layouts)
        if layout_count >= 2 and len(unique_layouts) < 2:
            errors.append("batch:tutorial_layout_rotation_missing")
        grid_count = sum(1 for family in all_tutorial_layouts if family in GRID_LAYOUTS)
        if layout_count >= 4 and grid_count / layout_count > 0.40:
            errors.append(f"batch:grid_2x2_share_exceeds_40_percent:{grid_count}/{layout_count}")
        if layout_count >= 6 and len(unique_layouts) < 3:
            errors.append(f"batch:tutorial_layout_family_count_below_3:{len(unique_layouts)}")

    return {
        "ok": not errors,
        "package_count": len(packages),
        "signatures": signatures,
        "tutorial_layouts": all_tutorial_layouts,
        "errors": errors,
    }


def self_test() -> dict[str, Any]:
    passing = {
        "layout_policy_version": "1.7",
        "visual_policy_version": "2.0",
        "golden_package_id": "shengqian-visual-golden-v2",
        "golden_package_version": "2.0",
        "food_master_gate_required": True,
        "tableware_gate_required": True,
        "prompt_firewall_required": True,
        "table_locked": True,
        "calibration_gate_required": True,
        "parallel_generation_locked": True,
        "packages": [
            {
                "package_id": "purple_rice_meal",
                "core_angle": "清爽蒸煮",
                "dishes": [
                    {"name": "白灼虾", "ingredient_key": "虾", "technique": "白灼", "role": "main", "complexity": "complex", "visual_risk": "high", "texture_risk": "high", "real_reference_planned": True},
                    {"name": "炒菠菜", "ingredient_key": "菠菜", "technique": "炒", "role": "side", "complexity": "simple", "visual_risk": "low", "texture_risk": "low"},
                ],
                "staple": {"name": "紫米饭", "category": "purple_rice", "complexity": "simple", "visual_risk": "medium", "texture_risk": "medium"},
                "food_master_required": True,
                "tableware_edit_policy": "optional_after_food_approval",
                "table_locked": True,
                "visual_lineage_manifest_required": True,
                "pages": [
                    {"role": "cover", "subject": "complete_meal"},
                    {"role": "tutorial", "subject": "白灼虾", "layout_family": "hero_plus_steps"},
                ],
            },
            {
                "package_id": "corn_meal",
                "core_angle": "双蛋白煎蒸",
                "dishes": [
                    {"name": "香煎牛肉", "ingredient_key": "牛肉", "technique": "煎", "role": "main", "complexity": "complex", "visual_risk": "high", "texture_risk": "high", "real_reference_planned": True},
                    {"name": "清蒸虾", "ingredient_key": "虾", "technique": "蒸", "role": "side", "complexity": "complex", "visual_risk": "high", "texture_risk": "high", "real_reference_planned": True},
                    {"name": "焯青菜", "ingredient_key": "青菜", "technique": "焯", "role": "side", "complexity": "simple", "visual_risk": "low", "texture_risk": "low"},
                ],
                "staple": {"name": "烤玉米", "category": "corn", "complexity": "simple", "visual_risk": "medium", "texture_risk": "medium"},
                "food_master_required": True,
                "tableware_edit_policy": "optional_after_food_approval",
                "table_locked": True,
                "visual_lineage_manifest_required": True,
                "pages": [
                    {"role": "cover", "subject": "complete_meal"},
                    {"role": "tutorial", "subject": "香煎牛肉", "layout_family": "vertical_story"},
                    {"role": "tutorial", "subject": "清蒸虾", "layout_family": "horizontal_story"},
                ],
            },
        ]
    }
    failing = {
        "packages": [passing["packages"][0], {**passing["packages"][0], "package_id": "duplicate"}]
    }
    all_rice = {
        "packages": [
            passing["packages"][0],
            {
                **passing["packages"][1],
                "package_id": "white_rice_meal",
                "staple": {"name": "白米饭", "category": "white_rice", "complexity": "simple"},
            },
        ]
    }
    passed = validate(passing)
    failed = validate(failing)
    rice_failed = validate(all_rice)
    layout_missing = {
        "layout_policy_version": "1.7",
        "packages": [
            {
                **passing["packages"][0],
                "pages": [
                    {"role": "cover", "subject": "complete_meal"},
                    {"role": "tutorial", "subject": "白灼虾"},
                ],
            },
            passing["packages"][1],
        ],
    }
    layout_failed = validate(layout_missing)
    visual_missing = copy_payload = json.loads(json.dumps(passing, ensure_ascii=False))
    copy_payload["packages"][0]["dishes"][0]["real_reference_planned"] = False
    visual_failed = validate(visual_missing)
    texture_overload = json.loads(json.dumps(passing, ensure_ascii=False))
    texture_overload["packages"][1]["dishes"][2]["texture_risk"] = "high"
    texture_failed = validate(texture_overload)
    return {
        "ok": passed["ok"] and not failed["ok"] and "batch:staples_cannot_all_be_rice" in rice_failed["errors"] and not layout_failed["ok"] and not visual_failed["ok"] and not texture_failed["ok"],
        "passing_case": passed,
        "failing_case": failed,
        "all_rice_case": rice_failed,
        "layout_missing_case": layout_failed,
        "visual_reference_missing_case": visual_failed,
        "texture_budget_case": texture_failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.input:
        result = validate(json.loads(args.input.read_text(encoding="utf-8")))
    else:
        parser.error("provide --input or --self-test")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
