#!/usr/bin/env python3
"""Validate the immutable visual golden package manifest and asset hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_SOURCE_KINDS = {"account_source", "user_accepted"}
REQUIRED_ACCOUNT_ROLES = {"annotated_cover", "clean_meal", "tutorial", "result", "process"}
REQUIRED_ACCEPTED_ROLES = {"annotated_cover", "clean_meal", "tutorial", "result", "side_staple"}
SHA256_LENGTH = 64
MASTER_ROLES = {"annotated_cover", "clean_meal"}
ACCEPTED_POLICIES = {"validation_only", "identity_only"}
FORBIDDEN_ACCEPTED_USES = {
    "package_master",
    "master_reference",
    "phone_realism",
    "camera_realism",
    "food_morphology",
    "ingredient_real",
    "texture_naturalness",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate(manifest_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"manifest_unreadable:{exc}"]}

    base = manifest_path.parent
    items = payload.get("items")
    if payload.get("schema_version") != 2:
        errors.append("schema_version_must_be_2")
    for field in ("golden_package_id", "account_skill_id", "version"):
        if not str(payload.get(field) or "").strip():
            errors.append(f"{field}_missing")
    if not isinstance(items, list) or not items:
        return {"ok": False, "errors": errors + ["items_missing"]}

    lineage = payload.get("source_lineage")
    if not isinstance(lineage, dict):
        errors.append("source_lineage_missing")
    else:
        offline_manifest = str(lineage.get("offline_source_manifest") or "").strip()
        if not offline_manifest or Path(offline_manifest).is_absolute():
            errors.append("source_lineage:offline_source_manifest_must_be_relative")
        elif not (base / offline_manifest).resolve().is_file():
            errors.append("source_lineage:offline_source_manifest_missing")
        if lineage.get("golden_sampling") != "role_and_ingredient_risk_specialized":
            errors.append("source_lineage:golden_sampling_invalid")
        if lineage.get("reference_role_firewall") != "account_realism_vs_generated_continuity":
            errors.append("source_lineage:reference_role_firewall_invalid")

    ids: set[str] = set()
    kinds: set[str] = set()
    account_roles: set[str] = set()
    accepted_roles: set[str] = set()
    source_ids: set[str] = set()
    master_account_ids: set[str] = set()

    for index, item in enumerate(items):
        label = f"item_{index}"
        if not isinstance(item, dict):
            errors.append(f"{label}:not_object")
            continue
        item_id = str(item.get("id") or "").strip()
        label = item_id or label
        if not item_id:
            errors.append(f"{label}:id_missing")
        elif item_id in ids:
            errors.append(f"{label}:id_duplicate")
        ids.add(item_id)

        kind = str(item.get("source_kind") or "").strip()
        role = str(item.get("role") or "").strip()
        if kind not in REQUIRED_SOURCE_KINDS:
            errors.append(f"{label}:source_kind_invalid")
        kinds.add(kind)
        if not role:
            errors.append(f"{label}:role_missing")
        if kind == "account_source":
            account_roles.add(role)
            source_id = str(item.get("source_id") or "").strip()
            if not source_id:
                errors.append(f"{label}:source_id_missing")
            else:
                source_ids.add(source_id)
            formal_card = str(item.get("formal_card") or "").strip()
            if not formal_card or Path(formal_card).is_absolute():
                errors.append(f"{label}:formal_card_must_be_relative")
            elif not (base / formal_card).resolve().is_file():
                errors.append(f"{label}:formal_card_missing")
            use_for = item.get("use_for") if isinstance(item.get("use_for"), list) else []
            if "master_reference" in use_for:
                if role not in MASTER_ROLES:
                    errors.append(f"{label}:master_reference_role_invalid")
                else:
                    master_account_ids.add(item_id)
        elif kind == "user_accepted":
            accepted_roles.add(role)
            if not str(item.get("content_id") or "").strip():
                errors.append(f"{label}:content_id_missing")
            policy = str(item.get("reference_policy") or "").strip()
            if policy not in ACCEPTED_POLICIES:
                errors.append(f"{label}:reference_policy_invalid")
            use_for = {str(value) for value in item.get("use_for") or []}
            for forbidden in sorted(use_for & FORBIDDEN_ACCEPTED_USES):
                errors.append(f"{label}:forbidden_user_accepted_use:{forbidden}")
            if policy == "identity_only" and "hand_identity" not in use_for:
                errors.append(f"{label}:identity_only_requires_hand_identity")
            if policy == "validation_only" and "hand_identity" in use_for:
                errors.append(f"{label}:hand_identity_requires_identity_only")

        relative = str(item.get("path") or "").strip()
        if not relative or Path(relative).is_absolute() or relative.startswith("/Volumes/"):
            errors.append(f"{label}:asset_path_must_be_relative")
            continue
        target = (base / relative).resolve()
        if not _inside(target, base):
            errors.append(f"{label}:asset_path_outside_golden_package")
            continue
        if not target.is_file():
            errors.append(f"{label}:asset_missing")
            continue
        expected = str(item.get("sha256") or "").lower()
        if len(expected) != SHA256_LENGTH or any(char not in "0123456789abcdef" for char in expected):
            errors.append(f"{label}:sha256_invalid")
        elif file_sha256(target) != expected:
            errors.append(f"{label}:sha256_mismatch")
        if not isinstance(item.get("ingredient_classes"), list) or not item.get("ingredient_classes"):
            errors.append(f"{label}:ingredient_classes_missing")
        if not isinstance(item.get("use_for"), list) or not item.get("use_for"):
            errors.append(f"{label}:use_for_missing")

    for kind in sorted(REQUIRED_SOURCE_KINDS - kinds):
        errors.append(f"source_kind_missing:{kind}")
    for role in sorted(REQUIRED_ACCOUNT_ROLES - account_roles):
        errors.append(f"account_source_role_missing:{role}")
    for role in sorted(REQUIRED_ACCEPTED_ROLES - accepted_roles):
        errors.append(f"user_accepted_role_missing:{role}")
    if len(source_ids) < 3:
        errors.append(f"account_source_id_count_below_3:{len(source_ids)}")
    if len(master_account_ids) < 3:
        errors.append(f"account_master_reference_count_below_3:{len(master_account_ids)}")
    if isinstance(lineage, dict) and set(str(value) for value in lineage.get("nas_source_ids") or []) != source_ids:
        errors.append("source_lineage:nas_source_ids_mismatch")

    counts = payload.get("source_counts") or {}
    actual_counts = {
        kind: sum(1 for item in items if isinstance(item, dict) and item.get("source_kind") == kind)
        for kind in REQUIRED_SOURCE_KINDS
    }
    for kind, actual in actual_counts.items():
        if counts.get(kind) != actual:
            errors.append(f"source_count_mismatch:{kind}:{counts.get(kind)}:{actual}")

    negative_count = 0
    negative_value = str(payload.get("negative_package_manifest") or "").strip()
    if not negative_value or Path(negative_value).is_absolute():
        errors.append("negative_package_manifest_must_be_relative")
    else:
        negative_manifest_path = (base / negative_value).resolve()
        if not negative_manifest_path.is_file():
            errors.append("negative_package_manifest_missing")
        else:
            try:
                negative = json.loads(negative_manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"negative_package_manifest_unreadable:{exc}")
                negative = {}
            if negative.get("source_kind") != "user_rejected_output":
                errors.append("negative_package_source_kind_invalid")
            if negative.get("reference_policy") != "validation_only":
                errors.append("negative_package_reference_policy_invalid")
            if negative.get("never_use_as_positive_reference") is not True:
                errors.append("negative_package_positive_reference_guard_missing")
            negative_items = negative.get("items")
            if not isinstance(negative_items, list) or not negative_items:
                errors.append("negative_package_items_missing")
                negative_items = []
            negative_count = len(negative_items)
            negative_base = negative_manifest_path.parent
            for index, item in enumerate(negative_items):
                label = str(item.get("id") or f"negative_{index}") if isinstance(item, dict) else f"negative_{index}"
                if not isinstance(item, dict):
                    errors.append(f"{label}:not_object")
                    continue
                if label in ids:
                    errors.append(f"{label}:negative_id_overlaps_positive")
                relative = str(item.get("path") or "").strip()
                if not relative or Path(relative).is_absolute():
                    errors.append(f"{label}:negative_asset_path_must_be_relative")
                    continue
                target = (negative_base / relative).resolve()
                if not _inside(target, negative_base):
                    errors.append(f"{label}:negative_asset_outside_package")
                elif not target.is_file():
                    errors.append(f"{label}:negative_asset_missing")
                elif file_sha256(target) != str(item.get("sha256") or "").lower():
                    errors.append(f"{label}:negative_sha256_mismatch")
                if not isinstance(item.get("failure_labels"), list) or not item.get("failure_labels"):
                    errors.append(f"{label}:failure_labels_missing")
                if not str(item.get("rejection_rule") or "").strip():
                    errors.append(f"{label}:rejection_rule_missing")

    return {
        "ok": not errors,
        "golden_package_id": payload.get("golden_package_id"),
        "version": payload.get("version"),
        "item_count": len(items),
        "source_counts": actual_counts,
        "source_ids": sorted(source_ids),
        "negative_item_count": negative_count,
        "errors": errors,
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        asset = root / "asset.jpg"
        asset.write_bytes(b"golden-test")
        digest = file_sha256(asset)
        common = {
            "path": "asset.jpg",
            "sha256": digest,
            "ingredient_classes": ["test"],
        }
        items = []
        for index, role in enumerate(sorted(REQUIRED_ACCOUNT_ROLES)):
            card = root / f"card-{index}.md"
            card.write_text("# test\n", encoding="utf-8")
            items.append({
                **common,
                "id": f"account-{index}",
                "source_kind": "account_source",
                "source_id": f"source-{index % 3}",
                "formal_card": card.name,
                "role": role,
                "use_for": ["master_reference"] if role in MASTER_ROLES else ["ingredient_real"],
            })
        extra_card = root / "card-extra.md"
        extra_card.write_text("# test\n", encoding="utf-8")
        items.append({
            **common,
            "id": "account-extra-master",
            "source_kind": "account_source",
            "source_id": "source-2",
            "formal_card": extra_card.name,
            "role": "annotated_cover",
            "use_for": ["master_reference"],
        })
        for index, role in enumerate(sorted(REQUIRED_ACCEPTED_ROLES)):
            items.append({
                **common,
                "id": f"accepted-{index}",
                "source_kind": "user_accepted",
                "content_id": "content-test",
                "role": role,
                "reference_policy": "identity_only" if role == "tutorial" else "validation_only",
                "use_for": ["hand_identity"] if role == "tutorial" else ["package_continuity"],
            })
        manifest = root / "manifest.json"
        negative_dir = root / "negative-package"
        negative_dir.mkdir()
        negative_asset = negative_dir / "negative.png"
        negative_asset.write_bytes(b"negative-test")
        (negative_dir / "manifest.json").write_text(json.dumps({
            "source_kind": "user_rejected_output",
            "reference_policy": "validation_only",
            "never_use_as_positive_reference": True,
            "items": [{
                "id": "negative-test",
                "path": "negative.png",
                "sha256": file_sha256(negative_asset),
                "failure_labels": ["synthetic_texture"],
                "rejection_rule": "reject",
            }],
        }), encoding="utf-8")
        payload = {
            "schema_version": 2,
            "golden_package_id": "test-golden",
            "account_skill_id": "test-account",
            "version": "1.0",
            "source_lineage": {
                "offline_source_manifest": "offline-manifest.json",
                "golden_sampling": "role_and_ingredient_risk_specialized",
                "reference_role_firewall": "account_realism_vs_generated_continuity",
                "nas_source_ids": ["source-0", "source-1", "source-2"],
            },
            "source_counts": {"account_source": 6, "user_accepted": 5},
            "negative_package_manifest": "negative-package/manifest.json",
            "items": items,
        }
        (root / "offline-manifest.json").write_text("{}", encoding="utf-8")
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        passing = validate(manifest)
        payload["items"][0]["sha256"] = "0" * 64
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        failing = validate(manifest)
        return {
            "ok": passing["ok"] and not failing["ok"] and any("sha256_mismatch" in error for error in failing["errors"]),
            "passing_case": passing,
            "tampered_hash_case": failing,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.manifest:
        result = validate(args.manifest)
    else:
        parser.error("provide --manifest or --self-test")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
