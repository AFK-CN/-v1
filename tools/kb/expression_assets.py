from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .schemas import SYSTEM_CONFIG_DIR, as_posix


CONTRACT_PATH = f"{SYSTEM_CONFIG_DIR}/expression_asset_contract.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
COORDINATE = re.compile(r"^.+:L\d+(?:-L\d+)?$")


def canonical_sha256(value: dict[str, Any], *, excluded: set[str] | None = None) -> str:
    excluded = excluded or set()
    payload = {key: item for key, item in value.items() if key not in excluded}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def valid_coordinate(value: Any) -> bool:
    return bool(COORDINATE.fullmatch(str(value or "")))


def load_expression_asset_contract(root: Path) -> dict[str, Any]:
    path = root.resolve() / CONTRACT_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def validate_expression_asset_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    *,
    expected_account_id: str = "",
) -> list[str]:
    errors: list[str] = []
    required = set(map(str, contract.get("required_record_fields", [])))
    for field in sorted(required - set(record)):
        errors.append(f"missing_field:{field}")
    for field in sorted(set(record) - required):
        errors.append(f"unknown_field:{field}")
    asset_id = str(record.get("asset_id", ""))
    account_id = str(record.get("account_id", ""))
    if not SAFE_ID.fullmatch(asset_id):
        errors.append("asset_id_invalid")
    if not SAFE_ID.fullmatch(account_id):
        errors.append("account_id_invalid")
    if expected_account_id and account_id != expected_account_id:
        errors.append("account_id_mismatch")
    asset_types = set(map(str, contract.get("asset_types", {}).keys()))
    if str(record.get("asset_type", "")) not in asset_types:
        errors.append("asset_type_invalid")
    surface_contract = contract.get("surface_contract", {}) if isinstance(contract.get("surface_contract"), dict) else {}
    source_surface = str(record.get("source_surface", ""))
    content_position = str(record.get("content_position", ""))
    functional_role = str(record.get("functional_role", ""))
    if source_surface not in set(map(str, surface_contract.get("source_surfaces", []))):
        errors.append("source_surface_invalid")
    if content_position not in set(map(str, surface_contract.get("content_positions", []))):
        errors.append("content_position_invalid")
    if functional_role not in set(map(str, surface_contract.get("functional_roles", []))):
        errors.append("functional_role_invalid")
    if record.get("asset_type") == "hook":
        hook_role = str(record.get("pattern_variables", {}).get("hook_role", "")) if isinstance(record.get("pattern_variables"), dict) else ""
        if hook_role not in set(map(str, surface_contract.get("hook_roles", []))):
            errors.append("hook_role_invalid")
    if record.get("knowledge_layer") != "candidate":
        errors.append("knowledge_layer_must_be_candidate")
    if record.get("callable") is not False:
        errors.append("candidate_must_not_be_callable")
    if record.get("method_evidence_eligible") is not False:
        errors.append("candidate_must_not_be_method_evidence")
    if record.get("generation_eligible") is not False:
        errors.append("candidate_must_not_be_generation_eligible")
    lifecycle = contract.get("lifecycle", {}) if isinstance(contract.get("lifecycle"), dict) else {}
    state = str(record.get("lifecycle_state", ""))
    allowed_states = set(map(str, lifecycle.get("states", [])))
    if state not in allowed_states:
        errors.append("lifecycle_state_invalid")
    if state in set(map(str, lifecycle.get("callable_states", []))):
        errors.append("approved_state_not_allowed_in_candidate_record")
    transitions = record.get("transition_history", [])
    allowed_transitions = {
        (str(item[0]), str(item[1]))
        for item in lifecycle.get("transitions", [])
        if isinstance(item, list) and len(item) == 2
    }
    current_state = str(lifecycle.get("default_state", "observed"))
    if not isinstance(transitions, list):
        errors.append("transition_history_must_be_list")
        transitions = []
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            errors.append(f"transition_not_object:{index}")
            continue
        source_state = str(transition.get("from", ""))
        target_state = str(transition.get("to", ""))
        if source_state != current_state or (source_state, target_state) not in allowed_transitions:
            errors.append(f"transition_invalid:{index}")
        if not valid_coordinate(transition.get("evidence_coordinate")):
            errors.append(f"transition_evidence_invalid:{index}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(transition.get("evidence_sha256", ""))):
            errors.append(f"transition_evidence_sha256_invalid:{index}")
        current_state = target_state
    if state in allowed_states and current_state != state:
        errors.append("transition_history_does_not_reach_state")
    gate_evidence = record.get("gate_evidence", {})
    if not isinstance(gate_evidence, dict):
        errors.append("gate_evidence_must_be_object")
        gate_evidence = {}
    required_gates = contract.get("gates", {}).get("state_gate_evidence", {}).get(state, [])
    for gate in required_gates:
        evidence_items = gate_evidence.get(str(gate), [])
        if (
            not isinstance(evidence_items, list)
            or not evidence_items
            or any(
                not isinstance(item, dict)
                or not valid_coordinate(item.get("evidence_coordinate"))
                or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("evidence_sha256", "")))
                for item in evidence_items
            )
        ):
            errors.append(f"gate_evidence_missing_or_invalid:{gate}")

    source = record.get("source", {})
    source_contract = contract.get("source_contract", {}) if isinstance(contract.get("source_contract"), dict) else {}
    if not isinstance(source, dict):
        errors.append("source_must_be_object")
        source = {}
    for field in sorted(set(map(str, source_contract.get("required_fields", []))) - set(source)):
        errors.append(f"source_missing_field:{field}")
    source_type = str(source.get("source_type", ""))
    allowed_source_types = set(map(str, source_contract.get("source_types", {}).keys()))
    if source_type not in allowed_source_types:
        errors.append("source_type_invalid")
    source_account_id = str(source.get("source_account_id", ""))
    same_account_types = {"account_source_positive", "user_accepted_output", "user_rejected_output"}
    if source_type in same_account_types and source_account_id != account_id:
        errors.append("source_account_isolation_failed")
    if source_type == "external_explicit_reference" and source_account_id:
        errors.append("external_reference_must_not_claim_account_origin")
    for key in ("source_id", "source_registry_id"):
        if not SAFE_ID.fullmatch(str(source.get(key, ""))):
            errors.append(f"{key}_invalid")
    if not SAFE_ID.fullmatch(str(source.get("authority_record_id", ""))):
        errors.append("authority_record_id_invalid")
    authority_manifest = str(source.get("authority_manifest_path", ""))
    if not authority_manifest or authority_manifest.startswith("/") or ".." in Path(authority_manifest).parts:
        errors.append("authority_manifest_path_invalid")
    locator = str(source.get("source_path_or_url", "")).strip()
    if not locator or ".." in Path(locator).parts:
        errors.append("source_locator_invalid")
    coordinate = str(source.get("evidence_coordinate", ""))
    if not valid_coordinate(coordinate):
        errors.append("evidence_coordinate_invalid")
    elif locator and not coordinate.startswith(f"{locator}:L"):
        errors.append("evidence_coordinate_source_mismatch")
    sha_pattern = str(source_contract.get("sha256_pattern", r"^[0-9a-f]{64}$"))
    try:
        sha_valid = bool(re.fullmatch(sha_pattern, str(source.get("sha256", ""))))
    except re.error:
        sha_valid = False
    if not sha_valid:
        errors.append("source_sha256_invalid")
    if not re.fullmatch(sha_pattern, str(source.get("registry_record_sha256", ""))):
        errors.append("source_registry_sha256_invalid")
    if not re.fullmatch(sha_pattern, str(source.get("authority_record_sha256", ""))):
        errors.append("source_authority_sha256_invalid")

    source_excerpt = str(record.get("source_excerpt", "")).strip()
    abstracted_pattern = str(record.get("abstracted_pattern", "")).strip()
    if not source_excerpt:
        errors.append("source_excerpt_required")
    if not abstracted_pattern:
        errors.append("abstracted_pattern_required")
    if source_excerpt and abstracted_pattern and source_excerpt == abstracted_pattern:
        errors.append("source_and_abstraction_must_be_separate")
    pattern_variables = record.get("pattern_variables", {})
    if not isinstance(pattern_variables, dict) or not pattern_variables:
        errors.append("pattern_variables_required")
    adaptation_template = str(record.get("adaptation_template", "")).strip()
    if not adaptation_template:
        errors.append("adaptation_template_required")
    if source_excerpt and adaptation_template == source_excerpt:
        errors.append("adaptation_template_must_not_copy_source")

    usage_contract = contract.get("usage_contract", {}) if isinstance(contract.get("usage_contract"), dict) else {}
    source_usage = record.get("source_usage", {})
    if not isinstance(source_usage, dict):
        errors.append("source_usage_must_be_object")
        source_usage = {}
    required_source_usage = set(map(str, usage_contract.get("source_usage_required_fields", [])))
    for field in sorted(required_source_usage - set(source_usage)):
        errors.append(f"source_usage_missing_field:{field}")
    for field in sorted(set(source_usage) - required_source_usage):
        errors.append(f"source_usage_unknown_field:{field}")
    if source_usage.get("generation_eligible") is not False:
        errors.append("source_excerpt_must_not_be_generation_eligible")
    if source_usage.get("display_eligible") not in {True, False} or source_usage.get("retrieval_eligible") not in {True, False}:
        errors.append("source_usage_flags_must_be_boolean")
    pattern_usage = record.get("pattern_usage", {})
    if not isinstance(pattern_usage, dict):
        errors.append("pattern_usage_must_be_object")
        pattern_usage = {}
    required_pattern_usage = set(map(str, usage_contract.get("pattern_usage_required_fields", [])))
    for field in sorted(required_pattern_usage - set(pattern_usage)):
        errors.append(f"pattern_usage_missing_field:{field}")
    for field in sorted(set(pattern_usage) - required_pattern_usage):
        errors.append(f"pattern_usage_unknown_field:{field}")
    if pattern_usage.get("candidate_reference_eligible") not in {True, False}:
        errors.append("pattern_candidate_reference_flag_must_be_boolean")
    if pattern_usage.get("production_eligible") is not False:
        errors.append("candidate_pattern_must_not_be_production_eligible")
    if pattern_usage.get("requires_user_confirmation") is not True:
        errors.append("pattern_usage_must_require_user_confirmation")

    score_range = contract.get("score_contract", {}).get("structural_usefulness_range", [0, 100])
    try:
        score = float(record.get("structural_usefulness_score"))
        lower, upper = float(score_range[0]), float(score_range[1])
        if score < lower or score > upper:
            errors.append("structural_usefulness_score_out_of_range")
    except (TypeError, ValueError, IndexError):
        errors.append("structural_usefulness_score_invalid")
    performance = record.get("performance_evidence", {})
    if not isinstance(performance, dict):
        errors.append("performance_evidence_must_be_object")
        performance = {}
    score_contract = contract.get("score_contract", {}) if isinstance(contract.get("score_contract"), dict) else {}
    required_performance = set(map(str, score_contract.get("performance_required_fields", [])))
    allowed_performance = set(map(str, score_contract.get("performance_allowed_fields", [])))
    for field in sorted(required_performance - set(performance)):
        errors.append(f"performance_missing_field:{field}")
    for field in sorted(set(performance) - allowed_performance):
        errors.append(f"performance_unknown_field:{field}")
    performance_status = str(performance.get("status", ""))
    statuses = set(map(str, score_contract.get("performance_statuses", [])))
    if performance_status not in statuses:
        errors.append("performance_status_invalid")
    evidence_coordinates = performance.get("evidence_coordinates", [])
    source_hashes = performance.get("source_hashes", [])
    try:
        sample_size = int(performance.get("sample_size", 0) or 0)
    except (TypeError, ValueError):
        sample_size = -1
    if performance_status == "validated_with_evidence":
        if (
            not isinstance(evidence_coordinates, list)
            or not evidence_coordinates
            or any(not valid_coordinate(item) for item in evidence_coordinates)
        ):
            errors.append("validated_performance_requires_traceable_coordinates")
        if str(performance.get("evidence_kind", "")) not in set(
            map(str, score_contract.get("validated_evidence_kinds", []))
        ):
            errors.append("validated_performance_evidence_kind_invalid")
        if not str(performance.get("metric", "")).strip() or not str(performance.get("observation_window", "")).strip():
            errors.append("validated_performance_metric_or_window_missing")
        if sample_size < int(score_contract.get("validated_min_sample_size", 2) or 2):
            errors.append("validated_performance_sample_too_small")
        if (
            not isinstance(source_hashes, list)
            or not source_hashes
            or any(not re.fullmatch(r"[0-9a-f]{64}", str(item)) for item in source_hashes)
        ):
            errors.append("validated_performance_source_hashes_invalid")
    elif performance_status == "not_claimed":
        if any(
            (
                evidence_coordinates,
                performance.get("evidence_kind"),
                performance.get("metric"),
                sample_size,
                performance.get("observation_window"),
                source_hashes,
                performance.get("authority_manifest_path"),
                performance.get("authority_record_ids"),
            )
        ):
            errors.append("not_claimed_performance_must_be_empty")

    usages = record.get("intended_usage", [])
    if not isinstance(usages, list) or not usages or any(not str(item).strip() for item in usages):
        errors.append("intended_usage_invalid")
        usages = []
    if source_type == "user_rejected_output" and set(map(str, usages)) != {"validation_only"}:
        errors.append("rejected_output_must_be_validation_only")
    if source_type == "user_rejected_output":
        if state != "rejected" or record.get("asset_type") != "anti_pattern":
            errors.append("rejected_output_must_be_rejected_anti_pattern")
        if record.get("generation_eligible") is not False:
            errors.append("rejected_output_must_not_be_generation_eligible")
    if source_type == "external_explicit_reference" and record.get("method_evidence_eligible") is not False:
        errors.append("external_reference_must_not_be_method_evidence")

    risk_flags = record.get("risk_flags", [])
    allowed_risks = set(map(str, contract.get("risk_flags", [])))
    if not isinstance(risk_flags, list):
        errors.append("risk_flags_must_be_list")
    elif any(str(item) not in allowed_risks for item in risk_flags):
        errors.append("risk_flag_invalid")
    return list(dict.fromkeys(errors))


def load_source_registry(path: Path, contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    registry: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if not path.exists():
        return registry, ["source_registry_missing"]
    required = set(map(str, contract.get("source_contract", {}).get("registry_required_fields", [])))
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return registry, ["source_registry_unreadable"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"source_registry_line:{line_number}:invalid_json")
            continue
        if not isinstance(item, dict):
            errors.append(f"source_registry_line:{line_number}:not_object")
            continue
        missing = required - set(item)
        for field in sorted(missing):
            errors.append(f"source_registry_line:{line_number}:missing_field:{field}")
        registry_id = str(item.get("source_registry_id", ""))
        if not SAFE_ID.fullmatch(registry_id):
            errors.append(f"source_registry_line:{line_number}:registry_id_invalid")
            continue
        if registry_id in registry:
            errors.append(f"source_registry_line:{line_number}:duplicate_registry_id")
        expected_hash = canonical_sha256(item, excluded={"registry_record_sha256"})
        if item.get("registry_record_sha256") != expected_hash:
            errors.append(f"source_registry_line:{line_number}:record_hash_mismatch")
        registry[registry_id] = item
    if not registry:
        errors.append("source_registry_empty")
    return registry, errors


def validate_source_registry_binding(
    record: dict[str, Any],
    registry: dict[str, dict[str, Any]],
) -> list[str]:
    source = record.get("source", {}) if isinstance(record.get("source"), dict) else {}
    registry_id = str(source.get("source_registry_id", ""))
    registered = registry.get(registry_id)
    if not registered:
        return ["source_registry_binding_missing"]
    mappings = {
        "source_id": "source_id",
        "source_type": "source_type",
        "source_account_id": "account_id",
        "source_path_or_url": "source_path_or_url",
        "sha256": "sha256",
        "registry_record_sha256": "registry_record_sha256",
    }
    errors = []
    for source_key, registry_key in mappings.items():
        if str(source.get(source_key, "")) != str(registered.get(registry_key, "")):
            errors.append(f"source_registry_binding_mismatch:{source_key}")
    account_id = str(record.get("account_id", ""))
    if source.get("source_type") == "external_explicit_reference":
        if registered.get("account_id"):
            errors.append("external_registry_must_not_claim_account_origin")
    elif str(registered.get("account_id", "")) != account_id:
        errors.append("source_registry_account_isolation_failed")
    return errors


def coordinate_path(coordinate: Any) -> str:
    value = str(coordinate or "")
    return value.rsplit(":L", 1)[0] if ":L" in value else ""


def verify_local_evidence(root: Path, coordinate: Any, declared_sha256: Any) -> list[str]:
    relative = coordinate_path(coordinate)
    if not relative or relative.startswith(("http://", "https://", "/")) or ".." in Path(relative).parts:
        return ["evidence_path_not_portable_local_file"]
    path = root / relative
    if not path.exists() or not path.is_file():
        return ["evidence_file_missing"]
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ["evidence_file_unreadable"]
    return [] if actual == str(declared_sha256 or "") else ["evidence_file_hash_mismatch"]


def load_authority_manifest(
    path: Path,
    *,
    required_fields: set[str],
    id_field: str,
    hash_field: str,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if not path.exists():
        return records, ["authority_manifest_missing"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return records, ["authority_manifest_unreadable"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"authority_line:{line_number}:invalid_json")
            continue
        if not isinstance(item, dict):
            errors.append(f"authority_line:{line_number}:not_object")
            continue
        for field in sorted(required_fields - set(item)):
            errors.append(f"authority_line:{line_number}:missing_field:{field}")
        record_id = str(item.get(id_field, ""))
        if not SAFE_ID.fullmatch(record_id):
            errors.append(f"authority_line:{line_number}:id_invalid")
            continue
        if item.get(hash_field) != canonical_sha256(item, excluded={hash_field}):
            errors.append(f"authority_line:{line_number}:record_hash_mismatch")
        if record_id in records:
            errors.append(f"authority_line:{line_number}:duplicate_id")
        records[record_id] = item
    if not records:
        errors.append("authority_manifest_empty")
    return records, errors


def validate_source_authority_binding(
    root: Path,
    record: dict[str, Any],
    contract: dict[str, Any],
    manifest_cache: dict[str, tuple[dict[str, dict[str, Any]], list[str]]],
) -> list[str]:
    source = record.get("source", {}) if isinstance(record.get("source"), dict) else {}
    account_id = str(record.get("account_id", ""))
    manifest_relative = str(source.get("authority_manifest_path", ""))
    template = str(contract.get("storage", {}).get("source_authority_root_template", ""))
    required_prefix = template.replace("{account_id}", account_id)
    if not manifest_relative.startswith(required_prefix) or manifest_relative.startswith("/") or ".." in Path(manifest_relative).parts:
        return ["source_authority_manifest_path_invalid"]
    if manifest_relative not in manifest_cache:
        required = set(map(str, contract.get("source_contract", {}).get("authority_required_fields", [])))
        manifest_cache[manifest_relative] = load_authority_manifest(
            root / manifest_relative,
            required_fields=required,
            id_field="authority_record_id",
            hash_field="authority_record_sha256",
        )
    authority, manifest_errors = manifest_cache[manifest_relative]
    errors = [f"source_authority:{item}" for item in manifest_errors]
    authority_id = str(source.get("authority_record_id", ""))
    item = authority.get(authority_id)
    if not item:
        errors.append("source_authority_record_missing")
        return errors
    mappings = {
        "source_id": "source_id",
        "source_type": "source_type",
        "source_account_id": "account_id",
        "source_path_or_url": "source_path_or_url",
        "sha256": "sha256",
        "authority_record_sha256": "authority_record_sha256",
    }
    for source_key, authority_key in mappings.items():
        if str(source.get(source_key, "")) != str(item.get(authority_key, "")):
            errors.append(f"source_authority_binding_mismatch:{source_key}")
    if source.get("source_type") != "external_explicit_reference" and item.get("account_id") != account_id:
        errors.append("source_authority_account_isolation_failed")
    coordinate = str(source.get("evidence_coordinate", ""))
    errors.extend(f"source_authority:{item}" for item in verify_local_evidence(root, coordinate, source.get("sha256")))
    return list(dict.fromkeys(errors))


def validate_performance_authority_binding(
    root: Path,
    record: dict[str, Any],
    contract: dict[str, Any],
    manifest_cache: dict[str, tuple[dict[str, dict[str, Any]], list[str]]],
) -> list[str]:
    performance = record.get("performance_evidence", {}) if isinstance(record.get("performance_evidence"), dict) else {}
    if performance.get("status") != "validated_with_evidence":
        return []
    account_id = str(record.get("account_id", ""))
    manifest_relative = str(performance.get("authority_manifest_path", ""))
    template = str(contract.get("storage", {}).get("performance_authority_root_template", ""))
    if not manifest_relative.startswith(template.replace("{account_id}", account_id)) or ".." in Path(manifest_relative).parts:
        return ["performance_authority_manifest_path_invalid"]
    if manifest_relative not in manifest_cache:
        required = set(map(str, contract.get("score_contract", {}).get("performance_authority_required_fields", [])))
        manifest_cache[manifest_relative] = load_authority_manifest(
            root / manifest_relative,
            required_fields=required,
            id_field="performance_record_id",
            hash_field="performance_record_sha256",
        )
    authority, manifest_errors = manifest_cache[manifest_relative]
    errors = [f"performance_authority:{item}" for item in manifest_errors]
    record_ids = performance.get("authority_record_ids", [])
    if not isinstance(record_ids, list) or not record_ids:
        return errors + ["performance_authority_record_ids_missing"]
    selected = [authority.get(str(item)) for item in record_ids]
    if any(item is None for item in selected):
        errors.append("performance_authority_record_missing")
        return errors
    selected_items = [item for item in selected if isinstance(item, dict)]
    unique_samples: set[str] = set()
    evidence_hashes: set[str] = set()
    evidence_paths: set[str] = set()
    for item in selected_items:
        if item.get("account_id") != account_id:
            errors.append("performance_authority_account_isolation_failed")
        for key in ("evidence_kind", "metric", "observation_window"):
            if str(item.get(key, "")) != str(performance.get(key, "")):
                errors.append(f"performance_authority_binding_mismatch:{key}")
        unique_samples.update(map(str, item.get("unique_sample_ids", [])))
        evidence_hashes.add(str(item.get("evidence_sha256", "")))
        evidence_paths.add(str(item.get("evidence_path", "")))
        errors.extend(
            f"performance_authority:{failure}"
            for failure in verify_local_evidence(
                root,
                f"{item.get('evidence_path', '')}:L1",
                item.get("evidence_sha256", ""),
            )
        )
    if int(performance.get("sample_size", 0) or 0) > len(unique_samples):
        errors.append("performance_sample_exceeds_registered_unique_samples")
    if set(map(str, performance.get("source_hashes", []))) != evidence_hashes:
        errors.append("performance_source_hashes_not_authorized")
    for coordinate in performance.get("evidence_coordinates", []):
        if coordinate_path(coordinate) not in evidence_paths:
            errors.append("performance_coordinate_not_authorized")
    return list(dict.fromkeys(errors))


def validate_expression_asset_file(
    root: Path,
    path: Path,
    *,
    expected_account_id: str = "",
    expected_workflow_id: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    target = path if path.is_absolute() else root / path
    contract = load_expression_asset_contract(root)
    if not contract:
        return {"ok": False, "status": "contract_missing", "errors": ["expression_asset_contract_missing"]}
    if not target.exists():
        return {"ok": False, "status": "file_missing", "errors": ["expression_asset_file_missing"]}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    storage = contract.get("storage", {}) if isinstance(contract.get("storage"), dict) else {}
    registry_path = target.parent / str(storage.get("source_registry_file", "source_registry.jsonl"))
    registry, registry_errors = load_source_registry(registry_path, contract)
    errors.extend(registry_errors)
    source_authority_cache: dict[str, tuple[dict[str, dict[str, Any]], list[str]]] = {}
    performance_authority_cache: dict[str, tuple[dict[str, dict[str, Any]], list[str]]] = {}
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {"ok": False, "status": "file_unreadable", "errors": ["expression_asset_file_unreadable"]}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line:{line_number}:invalid_json")
            continue
        if not isinstance(record, dict):
            errors.append(f"line:{line_number}:record_not_object")
            continue
        rows.append(record)
        for error in validate_expression_asset_record(
            record,
            contract,
            expected_account_id=expected_account_id,
        ):
            errors.append(f"line:{line_number}:{error}")
        for error in validate_source_registry_binding(record, registry):
            errors.append(f"line:{line_number}:{error}")
        for error in validate_source_authority_binding(root, record, contract, source_authority_cache):
            errors.append(f"line:{line_number}:{error}")
        for error in validate_performance_authority_binding(root, record, contract, performance_authority_cache):
            errors.append(f"line:{line_number}:{error}")
        validation_prefix = str(storage.get("validation_evidence_root_template", "")).replace(
            "{account_id}", str(record.get("account_id", ""))
        )
        for transition in record.get("transition_history", []) if isinstance(record.get("transition_history"), list) else []:
            if isinstance(transition, dict):
                if not coordinate_path(transition.get("evidence_coordinate")).startswith(validation_prefix):
                    errors.append(f"line:{line_number}:transition:account_validation_namespace_mismatch")
                for error in verify_local_evidence(
                    root,
                    transition.get("evidence_coordinate"),
                    transition.get("evidence_sha256"),
                ):
                    errors.append(f"line:{line_number}:transition:{error}")
        gate_evidence = record.get("gate_evidence", {}) if isinstance(record.get("gate_evidence"), dict) else {}
        for gate, evidence_items in gate_evidence.items():
            for evidence_item in evidence_items if isinstance(evidence_items, list) else []:
                if not isinstance(evidence_item, dict):
                    continue
                if not coordinate_path(evidence_item.get("evidence_coordinate")).startswith(validation_prefix):
                    errors.append(f"line:{line_number}:gate:{gate}:account_validation_namespace_mismatch")
                for error in verify_local_evidence(
                    root,
                    evidence_item.get("evidence_coordinate"),
                    evidence_item.get("evidence_sha256"),
                ):
                    errors.append(f"line:{line_number}:gate:{gate}:{error}")
    accounts = {str(item.get("account_id", "")) for item in rows if str(item.get("account_id", ""))}
    if len(accounts) > 1:
        errors.append("file_cross_account_mixing_forbidden")
    if not rows:
        errors.append("expression_asset_file_empty")
    sample_name = str(storage.get("sample_file", "expression_assets.sample.jsonl"))
    full_name = str(storage.get("full_file", "expression_assets.jsonl"))
    if target.name not in {sample_name, full_name}:
        errors.append("expression_asset_filename_invalid")
    if target.name == sample_name:
        sample_max = int(contract.get("gates", {}).get("sample_max_items", 20) or 20)
        if len(rows) > sample_max:
            errors.append("sample_item_limit_exceeded")
    if target.name == full_name:
        acceptance_path = target.parent / str(storage.get("sample_acceptance_file", "sample_acceptance.json"))
        retrieval_path = target.parent / str(storage.get("retrieval_validation_file", "retrieval_validation.json"))
        sample_path = target.parent / sample_name
        sample_validation: dict[str, Any] = {}
        sample_validation_sha256 = ""
        if sample_path.exists():
            expected_sample_account = next(iter(accounts)) if len(accounts) == 1 else expected_account_id
            sample_validation = validate_expression_asset_file(
                root,
                sample_path,
                expected_account_id=expected_sample_account,
                expected_workflow_id=expected_workflow_id,
            )
            validation_receipt = {
                key: sample_validation.get(key)
                for key in (
                    "ok",
                    "status",
                    "path",
                    "record_count",
                    "account_ids",
                    "errors",
                    "contract_version",
                    "activation_boundary",
                )
            }
            sample_validation_sha256 = hashlib.sha256(
                json.dumps(validation_receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if not sample_validation.get("ok"):
                errors.extend(f"sample_validation_failed:{item}" for item in sample_validation.get("errors", []))
        if not acceptance_path.exists():
            errors.append("full_extraction_requires_sample_acceptance_file")
        else:
            try:
                acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                acceptance = {}
                errors.append("sample_acceptance_invalid_json")
            required_checks = set(map(str, contract.get("gates", {}).get("sample_acceptance", [])))
            completed_checks = set(map(str, acceptance.get("completed_checks", []))) if isinstance(acceptance, dict) else set()
            try:
                accepted_sample_count = int(acceptance.get("sample_count", 0) or 0)
            except (TypeError, ValueError):
                accepted_sample_count = 0
            if not isinstance(acceptance, dict) or acceptance.get("status") != "accepted":
                errors.append("sample_acceptance_status_not_accepted")
            required_acceptance_fields = set(map(str, contract.get("gates", {}).get("sample_acceptance_required_fields", [])))
            if not required_acceptance_fields.issubset(set(acceptance)):
                errors.append("sample_acceptance_required_fields_missing")
            if not required_checks.issubset(completed_checks):
                errors.append("sample_acceptance_checks_incomplete")
            if not 1 <= accepted_sample_count <= int(contract.get("gates", {}).get("sample_max_items", 20) or 20):
                errors.append("sample_acceptance_count_invalid")
            coordinates = acceptance.get("evidence_coordinates", []) if isinstance(acceptance, dict) else []
            if not isinstance(coordinates, list) or not coordinates or any(not valid_coordinate(item) for item in coordinates):
                errors.append("sample_acceptance_evidence_invalid")
            registry_hash = hashlib.sha256(registry_path.read_bytes()).hexdigest() if registry_path.exists() else ""
            if acceptance.get("source_registry_sha256") != registry_hash:
                errors.append("sample_acceptance_registry_hash_mismatch")
            if acceptance.get("validator_version") != storage.get("validator_version"):
                errors.append("sample_acceptance_validator_version_mismatch")
            if acceptance.get("sample_validation_sha256") != sample_validation_sha256:
                errors.append("sample_acceptance_validation_receipt_mismatch")
            if not retrieval_path.exists():
                errors.append("sample_retrieval_validation_file_missing")
            else:
                try:
                    retrieval = json.loads(retrieval_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    retrieval = {}
                    errors.append("sample_retrieval_validation_invalid_json")
                if not isinstance(retrieval, dict) or retrieval.get("status") != "passed":
                    errors.append("sample_retrieval_validation_not_passed")
                if accounts and retrieval.get("account_id") not in accounts:
                    errors.append("sample_retrieval_validation_account_mismatch")
                if sample_path.exists() and retrieval.get("sample_file_sha256") != hashlib.sha256(sample_path.read_bytes()).hexdigest():
                    errors.append("sample_retrieval_validation_sample_hash_mismatch")
                required_retrieval_checks = set(map(str, contract.get("gates", {}).get("sample_acceptance", [])))
                retrieval_checks = retrieval.get("checks", {}) if isinstance(retrieval, dict) else {}
                if not isinstance(retrieval_checks, dict) or any(
                    retrieval_checks.get(check) is not True for check in required_retrieval_checks
                ):
                    errors.append("sample_retrieval_validation_checks_incomplete")
                if acceptance.get("retrieval_validation_sha256") != hashlib.sha256(retrieval_path.read_bytes()).hexdigest():
                    errors.append("sample_acceptance_retrieval_hash_mismatch")
            if accounts and acceptance.get("account_id") not in accounts:
                errors.append("sample_acceptance_account_mismatch")
            if not sample_path.exists():
                errors.append("accepted_sample_file_missing")
            else:
                sample_bytes = sample_path.read_bytes()
                if acceptance.get("sample_file_sha256") != hashlib.sha256(sample_bytes).hexdigest():
                    errors.append("sample_acceptance_file_hash_mismatch")
                sample_records = []
                for line in sample_bytes.decode("utf-8", errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        item = None
                    if isinstance(item, dict):
                        sample_records.append(item)
                expected_record_hashes = {canonical_sha256(item) for item in sample_records}
                if set(map(str, acceptance.get("sample_record_hashes", []))) != expected_record_hashes:
                    errors.append("sample_acceptance_record_hashes_mismatch")
                if accepted_sample_count != len(sample_records):
                    errors.append("sample_acceptance_count_does_not_match_file")
            audit_coordinate = acceptance.get("audit_report_coordinate")
            audit_sha = acceptance.get("audit_report_sha256")
            validation_prefix = str(storage.get("validation_evidence_root_template", "")).replace(
                "{account_id}", next(iter(accounts)) if len(accounts) == 1 else expected_account_id
            )
            if not coordinate_path(audit_coordinate).startswith(validation_prefix):
                errors.append("sample_acceptance_audit_account_namespace_mismatch")
            for error in verify_local_evidence(root, audit_coordinate, audit_sha):
                errors.append(f"sample_acceptance_audit:{error}")
            if any(coordinate_path(item) != coordinate_path(audit_coordinate) for item in coordinates):
                errors.append("sample_acceptance_coordinates_not_bound_to_audit")
    try:
        relative = as_posix(target.resolve().relative_to(root))
    except ValueError:
        relative = target.name
    template = str(storage.get("candidate_root_template", ""))
    candidate_prefix = template.split("{account_id}", 1)[0]
    workflow_template = str(storage.get("workflow_root_template", ""))
    workflow_prefix = workflow_template.split("{workflow_id}", 1)[0]
    in_account_root = bool(candidate_prefix and relative.startswith(candidate_prefix))
    in_workflow_root = bool(workflow_prefix and relative.startswith(workflow_prefix))
    if not in_account_root and not in_workflow_root:
        errors.append("file_outside_expression_asset_candidate_root")
    elif in_account_root and accounts:
        directory_account = relative[len(candidate_prefix) :].split("/", 1)[0]
        if accounts != {directory_account}:
            errors.append("file_account_directory_mismatch")
    elif in_workflow_root:
        directory_workflow = relative[len(workflow_prefix) :].split("/", 1)[0]
        if expected_workflow_id and directory_workflow != expected_workflow_id:
            errors.append("file_workflow_directory_mismatch")
    return {
        "ok": not errors,
        "status": "valid" if not errors else "invalid",
        "path": relative,
        "record_count": len(rows),
        "account_ids": sorted(accounts),
        "errors": errors,
        "contract_version": contract.get("version", ""),
        "activation_boundary": "active_pipeline_candidate_only",
    }
