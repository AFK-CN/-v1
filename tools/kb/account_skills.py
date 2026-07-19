from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .schemas import now_iso


ACCOUNT_INDEX_PATH = Path("10_Knowledge/evidence/index/account_knowledge_index.json")
ACCOUNT_INDEX_MARKDOWN_PATH = Path("10_Knowledge/evidence/index/account_knowledge_index.md")
FORMAL_ACCOUNTS_ROOT = Path("10_Knowledge/formal/accounts")
FORMAL_ACCOUNT_MANIFEST = "ACCOUNT_SKILL_MANIFEST.json"
UPGRADE_COMPATIBILITY_FILE = "UPGRADE_COMPATIBILITY.json"
REGISTRY_PATH = Path("20_User/config/account_skill_registry.json")
REQUIRED_PACKAGE_FILES = (
    "SKILL.md",
    "references/production.md",
    "references/style.md",
    "references/boundaries.md",
    "references/acceptance.md",
)
REQUIRED_ACCOUNT_VIEW_FILES = (
    "账号整体方法论.md",
    "内容生产使用说明.md",
    "减少AI味输出规则.md",
    "内容输出标准模板.md",
)
ACCOUNT_VIEW_SOURCE_MARKER = "<!-- account-view: source=skill; sync=required -->"
REQUIRED_PRODUCTION_MEMORY_MARKERS = (
    "topic-memory-check",
    "topic-memory-record",
    "production-memory-record",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_repo_path(value: Any) -> bool:
    text = str(value or "").strip()
    path = Path(text)
    return bool(text and not path.is_absolute() and ".." not in path.parts and not text.startswith("/Volumes/"))


def _under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _validate_visual_regression_package(
    package_path: Path,
    *,
    skill_root: Path,
    account_skill_id: str,
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    payload = read_json(package_path, {})
    label = package_path.name
    if not payload:
        return [f"regression_package_invalid_json:{label}"]
    multi = contract.get("multi_image_continuity", {})
    if payload.get("schema_version") != multi.get("schema_id"):
        errors.append(f"regression_package_schema_invalid:{label}")
    if payload.get("account_skill_id") != account_skill_id:
        errors.append(f"regression_package_account_mismatch:{label}")
    for field in ("source_kind", "origin_kind", "reference_policy"):
        if payload.get(field) != multi.get(field):
            errors.append(f"regression_package_{field}_invalid:{label}")
    if set(map(str, payload.get("allowed_uses", []))) != set(map(str, multi.get("allowed_uses", []))):
        errors.append(f"regression_package_allowed_uses_invalid:{label}")
    for field in multi.get("required_false_fields", []):
        if payload.get(str(field)) is not False:
            errors.append(f"regression_package_authority_must_be_false:{label}:{field}")
    if payload.get("continuity_required") is not True:
        errors.append(f"regression_package_continuity_required:{label}")
    if payload.get("independent_regeneration_allowed") is not False:
        errors.append(f"regression_package_independent_regeneration_forbidden:{label}")
    if payload.get("derivation_policy") != "local_edit_or_controlled_derivation":
        errors.append(f"regression_package_derivation_policy_invalid:{label}")

    pages = payload.get("pages")
    minimum = int(multi.get("minimum_page_count", 2) or 2)
    if not isinstance(pages, list) or len(pages) < minimum:
        return [*errors, f"regression_package_page_count_below_{minimum}:{label}"]
    page_ids = [str(item.get("asset_id") or "") for item in pages if isinstance(item, dict)]
    if len(page_ids) != len(pages) or any(not item for item in page_ids) or len(page_ids) != len(set(page_ids)):
        errors.append(f"regression_package_page_ids_invalid:{label}")
    orders = [item.get("order") for item in pages if isinstance(item, dict)]
    if orders != list(range(1, len(pages) + 1)):
        errors.append(f"regression_package_page_order_invalid:{label}")
    mother = str(payload.get("continuity_mother_asset_id") or "")
    if not mother or mother not in page_ids:
        errors.append(f"regression_package_mother_invalid:{label}")
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("asset_id") or "")
        parent_id = page.get("parent_asset_id")
        if page_id == mother:
            if parent_id not in (None, ""):
                errors.append(f"regression_package_mother_parent_forbidden:{label}:{page_id}")
        elif parent_id != mother:
            errors.append(f"regression_package_direct_parent_required:{label}:{page_id}")
        asset_value = str(page.get("asset_path") or "").strip()
        if not asset_value or Path(asset_value).is_absolute() or asset_value.startswith("/Volumes/"):
            errors.append(f"regression_package_asset_path_invalid:{label}:{page_id}")
            continue
        asset_path = (package_path.parent / asset_value).resolve()
        if not _under(asset_path, skill_root):
            errors.append(f"regression_package_asset_outside_skill:{label}:{page_id}")
        elif not asset_path.is_file():
            errors.append(f"regression_package_asset_missing:{label}:{page_id}")
        else:
            expected = str(page.get("sha256") or "").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                errors.append(f"regression_package_asset_hash_invalid:{label}:{page_id}")
            elif _sha256_file(asset_path) != expected:
                errors.append(f"regression_package_asset_hash_mismatch:{label}:{page_id}")
    return errors


def validate_account_skill_upgrade_compatibility(
    root: Path,
    account_root: Path,
    *,
    formal_manifest: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one formal account upgrade without loading account evidence or other accounts."""

    root = root.resolve()
    account_root = account_root.resolve()
    formal_manifest = formal_manifest or read_json(account_root / FORMAL_ACCOUNT_MANIFEST, {})
    account_skill_id = str(formal_manifest.get("account_skill_id") or "")
    contract = contract or read_json(root / "00_System/shareable/config/account_skill_contract.json", {})
    upgrade_contract = contract.get("upgrade_compatibility", {}) if isinstance(contract, dict) else {}
    errors: list[str] = []
    relative_value = str(
        formal_manifest.get("upgrade_compatibility_manifest")
        or f"{account_root.relative_to(root).as_posix()}/skill/{UPGRADE_COMPATIBILITY_FILE}"
    )
    if not _portable_repo_path(relative_value):
        return {"ok": False, "errors": [f"upgrade_manifest_path_not_portable:{account_skill_id}"]}
    compatibility_path = (root / relative_value).resolve()
    if not _under(compatibility_path, account_root / "skill"):
        return {"ok": False, "errors": [f"upgrade_manifest_outside_account_skill:{account_skill_id}"]}
    payload = read_json(compatibility_path, {})
    if not payload:
        return {"ok": False, "errors": [f"upgrade_manifest_missing_or_invalid:{account_skill_id}"]}

    required = set(map(str, upgrade_contract.get("required_top_level_fields", [])))
    missing = sorted(required - set(payload))
    errors.extend(f"upgrade_manifest_field_missing:{account_skill_id}:{field}" for field in missing)
    if payload.get("schema_version") != upgrade_contract.get("schema_id"):
        errors.append(f"upgrade_manifest_schema_invalid:{account_skill_id}")
    if payload.get("account_skill_id") != account_skill_id:
        errors.append(f"upgrade_manifest_account_mismatch:{account_skill_id}")
    if str(payload.get("target_version") or "") != str(formal_manifest.get("version") or ""):
        errors.append(f"upgrade_manifest_target_version_mismatch:{account_skill_id}")
    if payload.get("upgrade_scope") not in {"single_account", "system_account_batch_member", "initial_registration"}:
        errors.append(f"upgrade_manifest_scope_invalid:{account_skill_id}")

    previous = [str(item) for item in payload.get("previous_capability_ids", [])]
    new_ids = [str(item) for item in payload.get("new_capability_ids", [])]
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list):
        capabilities = []
        errors.append(f"upgrade_capabilities_not_list:{account_skill_id}")
    capability_ids: list[str] = []
    changed_by_id = {
        str(item.get("capability_id") or ""): item
        for item in payload.get("changed_capabilities", [])
        if isinstance(item, dict) and item.get("capability_id")
    }
    allowed_statuses = set(map(str, upgrade_contract.get("capability_statuses", [])))
    required_capability_fields = set(map(str, upgrade_contract.get("required_capability_fields", [])))
    account_relative = account_root.relative_to(root).as_posix() + "/"
    skill_name = str(formal_manifest.get("skill_name") or "")
    for item in capabilities:
        if not isinstance(item, dict):
            errors.append(f"upgrade_capability_invalid:{account_skill_id}")
            continue
        cap_id = str(item.get("id") or "")
        capability_ids.append(cap_id)
        for field in sorted(required_capability_fields - set(item)):
            errors.append(f"upgrade_capability_field_missing:{account_skill_id}:{cap_id}:{field}")
        status = str(item.get("status") or "")
        if status not in allowed_statuses:
            errors.append(f"upgrade_capability_status_invalid:{account_skill_id}:{cap_id}")
        source_paths = item.get("source_paths")
        if not isinstance(source_paths, list) or not source_paths:
            errors.append(f"upgrade_capability_sources_missing:{account_skill_id}:{cap_id}")
            source_paths = []
        for value in source_paths:
            relative = str(value or "")
            if not _portable_repo_path(relative) or not relative.startswith(account_relative):
                errors.append(f"upgrade_capability_cross_account_or_nonportable_source:{account_skill_id}:{cap_id}")
            elif not (root / relative).is_file():
                errors.append(f"upgrade_capability_source_missing:{account_skill_id}:{cap_id}:{relative}")
        if status in {"replaced", "deprecated"}:
            change = changed_by_id.get(cap_id)
            if not isinstance(change, dict):
                errors.append(f"upgrade_capability_change_record_missing:{account_skill_id}:{cap_id}")
                continue
            confirmation = change.get("user_confirmation")
            if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
                errors.append(f"upgrade_capability_user_confirmation_missing:{account_skill_id}:{cap_id}")
            proposal_value = str(confirmation.get("proposal_path") or "") if isinstance(confirmation, dict) else ""
            if not _portable_repo_path(proposal_value) or not proposal_value.startswith(account_relative):
                errors.append(f"upgrade_capability_proposal_path_invalid:{account_skill_id}:{cap_id}")
            else:
                proposal_path = root / proposal_value
                if not _under(proposal_path, account_root):
                    errors.append(f"upgrade_capability_proposal_cross_account:{account_skill_id}:{cap_id}")
                elif not proposal_path.is_file():
                    errors.append(f"upgrade_capability_proposal_missing:{account_skill_id}:{cap_id}")
                elif skill_name and parse_frontmatter(proposal_path).get("skill_name") != skill_name:
                    errors.append(f"upgrade_capability_proposal_account_mismatch:{account_skill_id}:{cap_id}")
            if status == "replaced" and not change.get("replacement_ids"):
                errors.append(f"upgrade_capability_replacement_missing:{account_skill_id}:{cap_id}")
            if not str(change.get("rollback") or "").strip():
                errors.append(f"upgrade_capability_rollback_missing:{account_skill_id}:{cap_id}")

    current_set = set(capability_ids)
    previous_set = set(previous)
    if not previous_set.issubset(current_set):
        for cap_id in sorted(previous_set - current_set):
            errors.append(f"upgrade_capability_silent_loss:{account_skill_id}:{cap_id}")
    if set(new_ids) != current_set - previous_set:
        errors.append(f"upgrade_new_capability_delta_mismatch:{account_skill_id}")
    if len(capability_ids) != len(current_set) or len(previous) != len(previous_set) or len(new_ids) != len(set(new_ids)):
        errors.append(f"upgrade_capability_ids_duplicate_or_empty:{account_skill_id}")

    isolation = payload.get("isolation")
    expected_isolation = {
        "same_account_only": True,
        "cross_account_merge": False,
        "system_rule_contamination": False,
        "absolute_or_nas_paths": False,
    }
    if not isinstance(isolation, dict) or any(isolation.get(key) is not value for key, value in expected_isolation.items()):
        errors.append(f"upgrade_isolation_invalid:{account_skill_id}")
    if not isinstance(payload.get("rollback"), dict) or not payload.get("rollback"):
        errors.append(f"upgrade_rollback_missing:{account_skill_id}")

    snapshots = payload.get("source_snapshot")
    if not isinstance(snapshots, list) or not snapshots:
        errors.append(f"upgrade_source_snapshot_missing:{account_skill_id}")
        snapshots = []
    for item in snapshots:
        if not isinstance(item, dict):
            errors.append(f"upgrade_source_snapshot_invalid:{account_skill_id}")
            continue
        relative = str(item.get("path") or "")
        expected = str(item.get("sha256") or "").lower()
        if not _portable_repo_path(relative) or not relative.startswith(account_relative):
            errors.append(f"upgrade_source_snapshot_cross_account_or_nonportable:{account_skill_id}")
        elif not re.fullmatch(r"[0-9a-f]{64}", expected):
            errors.append(f"upgrade_source_snapshot_hash_invalid:{account_skill_id}:{relative}")
        elif not (root / relative).is_file():
            errors.append(f"upgrade_source_snapshot_file_missing:{account_skill_id}:{relative}")
        elif _sha256_file(root / relative) != expected:
            errors.append(f"upgrade_source_snapshot_hash_mismatch:{account_skill_id}:{relative}")

    regression_manifests = payload.get("regression_package_manifests")
    if not isinstance(regression_manifests, list):
        errors.append(f"upgrade_regression_package_manifests_not_list:{account_skill_id}")
        regression_manifests = []
    for value in regression_manifests:
        relative = str(value or "")
        if not _portable_repo_path(relative) or not relative.startswith(account_relative):
            errors.append(f"upgrade_regression_package_cross_account_or_nonportable:{account_skill_id}")
            continue
        package_path = root / relative
        if not package_path.is_file():
            errors.append(f"upgrade_regression_package_missing:{account_skill_id}:{relative}")
            continue
        errors.extend(
            _validate_visual_regression_package(
                package_path,
                skill_root=account_root / "skill",
                account_skill_id=account_skill_id,
                contract=upgrade_contract,
            )
        )
    return {
        "ok": not errors,
        "errors": errors,
        "account_skill_id": account_skill_id,
        "base_version": payload.get("base_version", ""),
        "target_version": payload.get("target_version", ""),
        "capability_count": len(current_set),
        "new_capability_count": len(set(new_ids)),
        "regression_package_count": len(regression_manifests),
        "manifest": relative_value,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stable_capability_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "unnamed"


def _next_patch_version(value: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", value.strip())
    if not match:
        raise ValueError(f"account_skill_version_not_semver:{value}")
    major, minor, patch = match.groups()
    if patch is None:
        return f"{major}.{int(minor) + 1}"
    return f"{major}.{minor}.{int(patch) + 1}"


def _replace_account_skill_version(path: Path, base_version: str, target_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = (
        (f"账号 Skill 版本：{base_version}", f"账号 Skill 版本：{target_version}"),
        (f"正式版本：`{base_version}`", f"正式版本：`{target_version}`"),
        (f"Skill 版本 `{base_version}`", f"Skill 版本 `{target_version}`"),
    )
    updated = text
    for source, target in replacements:
        updated = updated.replace(source, target)
    if updated == text:
        raise ValueError(f"account_skill_version_marker_missing:{path.name}:{base_version}")
    path.write_text(updated, encoding="utf-8")


def _formal_account_capabilities(
    root: Path,
    account_root: Path,
    *,
    introduced_in: str,
    target_version: str,
) -> list[dict[str, Any]]:
    """Build stable capability IDs only from the current account's formal package."""

    root = root.resolve()
    skill_root = account_root / "skill"
    capabilities: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(capability_id: str, paths: list[Path], *, version: str = introduced_in) -> None:
        source_paths = [path.relative_to(root).as_posix() for path in paths if path.is_file()]
        if not source_paths or capability_id in seen:
            return
        seen.add(capability_id)
        capabilities.append(
            {
                "id": capability_id,
                "introduced_in": version,
                "status": "active",
                "source_paths": source_paths,
            }
        )

    skill_path = skill_root / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8")
    for marker, capability_id in (
        ("topic-memory-check", "topic_memory_deduplication"),
        ("topic-memory-record", "topic_memory_recording"),
        ("production-memory-record", "production_memory_recording"),
    ):
        if marker in skill_text:
            add(capability_id, [skill_path])

    core_references = {
        "production": "production_mechanism",
        "style": "style_fingerprint",
        "boundaries": "evidence_boundaries",
        "acceptance": "acceptance_gates",
        "publishing-copy": "publishing_copy_specialization",
        "publishing-copy-golden": "publishing_copy_golden_regression",
        "visual": "visual_rules",
        "visual-evidence": "visual_evidence_rules",
        "visual-production": "visual_production_rules",
        "visual-golden": "visual_golden_regression",
        "visual-lineage": "visual_lineage_rules",
        "package-cycle": "package_cycle_rules",
    }
    references_root = skill_root / "references"
    if references_root.is_dir():
        for reference in sorted(references_root.glob("*.md")):
            if reference.stem == "upgrade-compatibility":
                continue
            capability_id = core_references.get(reference.stem)
            if not capability_id:
                capability_id = f"reference_{_stable_capability_slug(reference.stem)}"
            add(capability_id, [reference])

    method_index = account_root / "METHOD_INDEX.json"
    method_payload = read_json(method_index, {})
    for method in method_payload.get("methods", []) if isinstance(method_payload, dict) else []:
        if not isinstance(method, dict) or not method.get("id"):
            continue
        add(f"formal_method_{_stable_capability_slug(str(method['id']))}", [method_index])

    scripts_root = skill_root / "scripts"
    if scripts_root.is_dir():
        for script in sorted(path for path in scripts_root.rglob("*") if path.is_file()):
            add(f"validator_{_stable_capability_slug(script.stem)}", [script])

    views = [account_root / filename for filename in REQUIRED_ACCOUNT_VIEW_FILES]
    add("account_view_sync", views)
    add(
        "capability_preserving_upgrade_guard",
        [skill_root / UPGRADE_COMPATIBILITY_FILE, references_root / "upgrade-compatibility.md"],
        version=target_version,
    )
    return capabilities


def _render_upgrade_reference(
    *,
    account_name: str,
    base_version: str,
    target_version: str,
    previous_ids: list[str],
) -> str:
    lines = [
        "# 升级兼容与能力保留",
        "",
        f"- 账号：{account_name}",
        f"- 基线版本：{base_version}",
        f"- 当前版本：{target_version}",
        f"- 基线能力数：{len(previous_ids)}",
        "- 升级范围：系统账号批次中的单账号成员",
        "",
        "## 强制规则",
        "",
        "1. 每次升级先读取 `UPGRADE_COMPATIBILITY.json`，对比旧能力 ID 和当前能力 ID。",
        "2. 旧能力不得静默丢失；替换或弃用必须有用户确认、替代能力和回滚路径。",
        "3. 单账号只能引用本账号正式 Skill、方法、规则、校验器和视图。",
        "4. 整体账号升级必须一账号一清单、逐账号验收，禁止跨账号合并规则、素材或正例。",
        "5. 本次只新增升级防回退能力，没有替换或弃用任何基线能力。",
        "",
        "## 基线能力 ID",
        "",
        *[f"- `{capability_id}`" for capability_id in previous_ids],
        "",
    ]
    return "\n".join(lines)


def audit_account_skill_v29_compatibility(root: Path) -> dict[str, Any]:
    """Audit every registered account without reading candidates, raw data, or another account's sources."""

    root = root.resolve()
    registry = read_json(registry_path(root), default_registry())
    results: list[dict[str, Any]] = []
    for item in registry.get("accounts", []):
        if not isinstance(item, dict):
            continue
        account_name = str(item.get("account_name") or "")
        account_root = root / FORMAL_ACCOUNTS_ROOT / account_name
        manifest = read_json(account_root / FORMAL_ACCOUNT_MANIFEST, {})
        if manifest.get("upgrade_guard_required") is not True:
            results.append(
                {
                    "ok": False,
                    "account_skill_id": item.get("account_skill_id", ""),
                    "account_name": account_name,
                    "version": manifest.get("version", ""),
                    "error": "v29_upgrade_guard_missing",
                }
            )
            continue
        validation = validate_account_skill_upgrade_compatibility(
            root,
            account_root,
            formal_manifest=manifest,
        )
        results.append({"account_name": account_name, "version": manifest.get("version", ""), **validation})
    return {
        "ok": bool(results) and all(item.get("ok") for item in results),
        "account_count": len(results),
        "passed_count": sum(1 for item in results if item.get("ok")),
        "failed": [str(item.get("account_skill_id") or "") for item in results if not item.get("ok")],
        "results": results,
    }


def upgrade_formal_account_skill_v29(
    root: Path,
    account_skill_id: str,
    *,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Add the v2.9 no-loss guard to one formal account Skill without changing account methods."""

    if not user_confirmed:
        return {"ok": False, "account_skill_id": account_skill_id, "error": "user_confirmation_required"}
    root = root.resolve()
    registry = read_json(registry_path(root), default_registry())
    registered = next(
        (
            item
            for item in registry.get("accounts", [])
            if isinstance(item, dict) and str(item.get("account_skill_id") or "") == account_skill_id
        ),
        None,
    )
    if not registered:
        return {"ok": False, "account_skill_id": account_skill_id, "error": "registered_account_not_found"}
    account_name = str(registered.get("account_name") or "")
    account_root = root / FORMAL_ACCOUNTS_ROOT / account_name
    manifest_path = account_root / FORMAL_ACCOUNT_MANIFEST
    manifest = read_json(manifest_path, {})
    if not manifest:
        return {"ok": False, "account_skill_id": account_skill_id, "error": "formal_manifest_missing"}

    if manifest.get("upgrade_guard_required") is True:
        current_validation = validate_account_skill_upgrade_compatibility(
            root,
            account_root,
            formal_manifest=manifest,
        )
        if current_validation.get("ok"):
            return {
                "ok": True,
                "status": "already_v29_compatible",
                "account_name": account_name,
                **current_validation,
            }
        return {
            "ok": False,
            "account_skill_id": account_skill_id,
            "account_name": account_name,
            "error": "existing_upgrade_guard_invalid",
            "validation": current_validation,
        }

    base_version = str(manifest.get("version") or "")
    target_version = _next_patch_version(base_version)
    skill_root = account_root / "skill"
    skill_path = skill_root / "SKILL.md"
    for path in [skill_path, *[account_root / filename for filename in REQUIRED_ACCOUNT_VIEW_FILES]]:
        _replace_account_skill_version(path, base_version, target_version)

    preliminary = _formal_account_capabilities(
        root,
        account_root,
        introduced_in=base_version,
        target_version=target_version,
    )
    previous_ids = [item["id"] for item in preliminary if item["id"] != "capability_preserving_upgrade_guard"]
    upgrade_reference = skill_root / "references" / "upgrade-compatibility.md"
    upgrade_reference.write_text(
        _render_upgrade_reference(
            account_name=account_name,
            base_version=base_version,
            target_version=target_version,
            previous_ids=previous_ids,
        ),
        encoding="utf-8",
    )
    skill_text = skill_path.read_text(encoding="utf-8")
    if "references/upgrade-compatibility.md" not in skill_text:
        skill_path.write_text(
            skill_text.rstrip()
            + "\n\n## 升级兼容\n\n"
            + "升级本账号 Skill 前必须读取 `UPGRADE_COMPATIBILITY.json` 和 "
            + "`references/upgrade-compatibility.md`。旧能力 ID 不得静默丢失；替换或弃用必须经用户确认并保留回滚。"
            + "整体账号升级仍只能使用本账号证据，禁止跨账号合并能力、规则、素材和正例。\n",
            encoding="utf-8",
        )

    proposal_relative = (
        f"{account_root.relative_to(root).as_posix()}/skill/proposals/"
        f"capability-preservation-v{target_version}.md"
    )
    proposal_path = root / proposal_relative
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        "---\n"
        f"skill_name: {manifest.get('skill_name', '')}\n"
        f"version: '{target_version}'\n"
        "status: applied\n"
        "---\n\n"
        f"# {account_name} 账号 Skill 能力保留升级\n\n"
        f"- 基线版本：{base_version}\n"
        f"- 目标版本：{target_version}\n"
        "- 用户确认：已确认全部账号按 account-learning v2.9 补齐。\n"
        "- 变更：只新增能力保留清单、同账号来源快照和回滚；不替换、不弃用已批准能力。\n"
        "- 污染边界：本账号清单只引用本账号正式 Skill 和方法。\n",
        encoding="utf-8",
    )

    manifest["version"] = target_version
    manifest["updated_at"] = now_iso()[:10]
    manifest["upgrade_guard_required"] = True
    manifest["upgrade_compatibility_manifest"] = (
        f"{account_root.relative_to(root).as_posix()}/skill/{UPGRADE_COMPATIBILITY_FILE}"
    )
    manifest["upgrade_proposal"] = proposal_relative
    approval = str(manifest.get("approval_basis") or "").strip()
    v29_approval = "2026-07-19 用户确认全部账号按 account-learning v2.9 补齐且保留旧能力。"
    manifest["approval_basis"] = f"{approval} {v29_approval}".strip()
    _write_json(manifest_path, manifest)

    capabilities = _formal_account_capabilities(
        root,
        account_root,
        introduced_in=base_version,
        target_version=target_version,
    )
    current_ids = [item["id"] for item in capabilities]
    previous_ids = [item for item in current_ids if item != "capability_preserving_upgrade_guard"]
    snapshot_paths = sorted(
        {
            source
            for capability in capabilities
            for source in capability.get("source_paths", [])
            if not source.endswith(f"/skill/{UPGRADE_COMPATIBILITY_FILE}")
        }
    )
    regression_manifests = sorted(
        path.relative_to(root).as_posix()
        for path in (skill_root / "assets" / "visual" / "regression-packages").glob("*/manifest.json")
    ) if (skill_root / "assets" / "visual" / "regression-packages").is_dir() else []
    compatibility = {
        "schema_version": "account_skill_upgrade_compatibility_v1",
        "account_skill_id": account_skill_id,
        "base_version": base_version,
        "target_version": target_version,
        "upgrade_scope": "system_account_batch_member",
        "previous_capability_ids": previous_ids,
        "new_capability_ids": ["capability_preserving_upgrade_guard"],
        "capabilities": capabilities,
        "changed_capabilities": [],
        "source_snapshot": [
            {"path": relative, "sha256": _sha256_file(root / relative)} for relative in snapshot_paths
        ],
        "regression_package_manifests": regression_manifests,
        "isolation": {
            "same_account_only": True,
            "cross_account_merge": False,
            "system_rule_contamination": False,
            "absolute_or_nas_paths": False,
        },
        "rollback": {
            "restore_version": base_version,
            "restore_proposal": proposal_relative,
            "preserve_new_audit_artifacts": True,
            "delete_original_or_formal_evidence": False,
        },
    }
    _write_json(skill_root / UPGRADE_COMPATIBILITY_FILE, compatibility)
    validation = validate_account_skill_upgrade_compatibility(
        root,
        account_root,
        formal_manifest=manifest,
    )
    return {
        "ok": bool(validation.get("ok")),
        "status": "upgraded" if validation.get("ok") else "validation_failed",
        "account_name": account_name,
        "account_skill_id": account_skill_id,
        "base_version": base_version,
        "target_version": target_version,
        "proposal": proposal_relative,
        "validation": validation,
    }


def upgrade_all_formal_account_skills_v29(
    root: Path,
    *,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    registry = read_json(registry_path(root), default_registry())
    results = [
        upgrade_formal_account_skill_v29(
            root,
            str(item.get("account_skill_id") or ""),
            user_confirmed=user_confirmed,
        )
        for item in registry.get("accounts", [])
        if isinstance(item, dict) and item.get("status") == "active"
    ]
    if all(item.get("ok") for item in results):
        write_account_indexes(root)
        registry_result = sync_registry(root)
    else:
        registry_result = {"ok": False, "error": "upgrade_failed_before_registry_sync"}
    return {
        "ok": bool(results) and all(item.get("ok") for item in results) and registry_result.get("ok", False),
        "account_count": len(results),
        "upgraded_count": sum(1 for item in results if item.get("status") == "upgraded"),
        "already_compatible_count": sum(
            1 for item in results if item.get("status") == "already_v29_compatible"
        ),
        "failed": [str(item.get("account_skill_id") or "") for item in results if not item.get("ok")],
        "registry": registry_result,
        "results": results,
    }


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def registry_path(root: Path) -> Path:
    return root.resolve() / REGISTRY_PATH


def default_registry() -> dict[str, Any]:
    return {"version": 1, "updated_at": now_iso(), "accounts": []}


def parse_frontmatter(skill_path: Path) -> dict[str, str]:
    if not skill_path.exists():
        return {}
    text = skill_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _existing_layer(
    root: Path,
    layers: list[dict[str, Any]],
    path: Path,
    layer: str,
    description: str,
    *,
    direction: str = "",
) -> None:
    if not path.exists():
        return
    item: dict[str, Any] = {
        "layer": layer,
        "path": _relative(root, path),
        "description": description,
    }
    if direction:
        item["direction"] = direction
    layers.append(item)


def build_account_knowledge_index(root: Path) -> dict[str, Any]:
    """Build the account index from direct formal account manifests.

    The formal account directory is authoritative. This prevents a stale hand-written
    index from recreating retired theme wrappers or pointing at deleted account docs.
    """

    root = root.resolve()
    accounts_root = root / FORMAL_ACCOUNTS_ROOT
    accounts: list[dict[str, Any]] = []
    discovery_errors: list[str] = []
    if not accounts_root.exists():
        return {"generated_at": now_iso(), "accounts": [], "discovery_errors": []}

    for account_dir in sorted(path for path in accounts_root.iterdir() if path.is_dir()):
        manifest_path = account_dir / FORMAL_ACCOUNT_MANIFEST
        manifest = read_json(manifest_path, {})
        if not manifest:
            discovery_errors.append(f"formal_account_manifest_missing_or_invalid:{_relative(root, account_dir)}")
            continue
        account_id = str(manifest.get("account_skill_id") or "").strip()
        account_name = str(manifest.get("account_name") or account_dir.name).strip()
        platform = str(manifest.get("platform") or "").strip()
        skill_path = account_dir / "skill" / "SKILL.md"
        if not account_id or not account_name:
            discovery_errors.append(f"formal_account_manifest_identity_invalid:{_relative(root, manifest_path)}")
            continue
        if account_name != account_dir.name:
            discovery_errors.append(f"formal_account_directory_name_mismatch:{account_id}:{account_dir.name}:{account_name}")
        if not skill_path.exists():
            discovery_errors.append(f"formal_account_skill_missing:{account_id}:{_relative(root, skill_path)}")

        receipt = read_json(account_dir / "FORMAL_INGEST_RECEIPT.json", {})
        directions: list[dict[str, Any]] = []
        layers: list[dict[str, Any]] = []
        directions_root = account_dir / "directions"
        if directions_root.exists():
            for direction_dir in sorted(path for path in directions_root.iterdir() if path.is_dir()):
                cards_dir = direction_dir / "cards"
                card_count = len(list(cards_dir.rglob("*.md"))) if cards_dir.exists() else 0
                directions.append(
                    {
                        "direction": direction_dir.name,
                        "status": str(receipt.get("status") or "formal_ingested"),
                        "card_count": card_count,
                        "transcript_file_count": 0,
                        "formal_direction_dir": _relative(root, direction_dir),
                    }
                )
                summary_path = next(
                    (
                        direction_dir / name
                        for name in ("方向正式证据说明.md", "方向方法论总结.md")
                        if (direction_dir / name).exists()
                    ),
                    None,
                )
                if summary_path is not None:
                    _existing_layer(
                        root,
                        layers,
                        summary_path,
                        "direction_method",
                        "方向证据路由、方法与边界。",
                        direction=direction_dir.name,
                    )
                _existing_layer(
                    root,
                    layers,
                    cards_dir,
                    "single_cards",
                    "经审核的正式证据卡。",
                    direction=direction_dir.name,
                )

        for filename, layer, description in (
            (FORMAL_ACCOUNT_MANIFEST, "account_manifest", "账号身份、平台、版本和正式 Skill 路径。"),
            ("账号概述.md", "account_status_overview", "账号范围、证据状态与边界。"),
            ("账号索引.md", "account_index", "账号内部方向和方法入口。"),
            ("METHOD_INDEX.json", "method_index", "正式方法机器索引。"),
            ("FORMAL_CARD_INDEX.jsonl", "formal_card_index", "正式证据卡机器索引。"),
            ("FORMAL_INGEST_RECEIPT.json", "formal_ingest_receipt", "正式入库验收凭证。"),
            ("skill/SKILL.md", "account_skill", "正式可调用账号 Skill。"),
            ("账号整体方法论.md", "account_methodology_view", "正式方法、编排、表达与边界的中文聚合视图。"),
            ("内容生产使用说明.md", "account_production_guide_view", "账号内容生产顺序与交付说明。"),
            ("减少AI味输出规则.md", "account_anti_ai_view", "账号专属表达指纹与防模板规则。"),
            ("内容输出标准模板.md", "account_output_template_view", "由正式生产机制生成的可填写模板。"),
        ):
            _existing_layer(root, layers, account_dir / filename, layer, description)

        methods_root = account_dir / "methods"
        method_count = len(list(methods_root.glob("*/METHOD.md"))) if methods_root.exists() else 0
        accounts.append(
            {
                "account_id": account_id,
                "account_name": account_name,
                "platform": platform,
                "formal_account_dir": _relative(root, account_dir),
                "formal_status": str(receipt.get("status") or manifest.get("status") or "active"),
                "formal_card_count": sum(item["card_count"] for item in directions),
                "formal_method_count": method_count,
                "directions": directions,
                "knowledge_layers": layers,
            }
        )

    return {
        "generated_at": now_iso(),
        "accounts": sorted(accounts, key=lambda item: item["account_id"]),
        "discovery_errors": discovery_errors,
    }


def render_account_knowledge_index(payload: dict[str, Any]) -> str:
    lines = [
        "# 账号知识总索引",
        "",
        "本文件由代码从正式账号目录直属清单生成，不手工维护。",
        "",
        "| 账号 | 平台 | 正式目录 | 已入库方向 |",
        "| --- | --- | --- | --- |",
    ]
    for account in payload.get("accounts", []):
        directions = "、".join(item["direction"] for item in account.get("directions", [])) or "-"
        lines.append(
            f"| {account['account_name']} | {account.get('platform', '')} | "
            f"{account['formal_account_dir']} | {directions} |"
        )
    if payload.get("discovery_errors"):
        lines.extend(["", "## 发现错误", ""])
        lines.extend(f"- {item}" for item in payload["discovery_errors"])
    return "\n".join(lines) + "\n"


def write_account_indexes(root: Path) -> dict[str, Any]:
    root = root.resolve()
    payload = build_account_knowledge_index(root)
    json_target = root / ACCOUNT_INDEX_PATH
    markdown_target = root / ACCOUNT_INDEX_MARKDOWN_PATH
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_target.write_text(render_account_knowledge_index(payload), encoding="utf-8")
    return {
        "ok": not payload.get("discovery_errors"),
        "account_count": len(payload.get("accounts", [])),
        "errors": payload.get("discovery_errors", []),
    }


def sync_registry(root: Path) -> dict[str, Any]:
    root = root.resolve()
    current = read_json(registry_path(root), default_registry())
    existing_by_id = {
        str(item.get("account_skill_id") or ""): item
        for item in current.get("accounts", [])
        if isinstance(item, dict)
    }
    account_index = read_json(root / ACCOUNT_INDEX_PATH, {"accounts": []})
    accounts = []
    missing_skills = []
    for account in account_index.get("accounts", []):
        if not isinstance(account, dict):
            continue
        account_id = str(account.get("account_id") or "").strip()
        account_name = str(account.get("account_name") or "").strip()
        formal_dir = str(account.get("formal_account_dir") or "").strip()
        if not account_id or not account_name or not formal_dir:
            continue
        skill_relative = f"{formal_dir}/skill/SKILL.md"
        skill_path = root / skill_relative
        if not skill_path.exists():
            missing_skills.append(account_id)
            continue
        frontmatter = parse_frontmatter(skill_path)
        prior = existing_by_id.get(account_id, {})
        manifest = read_json(root / formal_dir / FORMAL_ACCOUNT_MANIFEST, {})
        manifest_aliases = manifest.get("aliases") if isinstance(manifest.get("aliases"), list) else []
        prior_aliases = prior.get("aliases") if isinstance(prior.get("aliases"), list) else []
        aliases = [account_name, *manifest_aliases, *prior_aliases]
        aliases = sorted({account_name, *(str(item) for item in aliases if str(item).strip())})
        accounts.append(
            {
                "account_skill_id": account_id,
                "account_name": account_name,
                "platform": str(account.get("platform") or ""),
                "skill_path": skill_relative,
                "skill_name": frontmatter.get("name", str(manifest.get("skill_name") or f"account-{account_id}")),
                "version": str(manifest.get("version") or prior.get("version") or "1.0"),
                "status": str(manifest.get("status") or prior.get("status") or "active"),
                "aliases": aliases,
                "updated_at": now_iso(),
            }
        )
    payload = {"version": 1, "updated_at": now_iso(), "accounts": sorted(accounts, key=lambda item: item["account_skill_id"])}
    target = registry_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": not missing_skills,
        "registered": len(accounts),
        "missing_account_skills": missing_skills,
        "registry": str(REGISTRY_PATH),
    }


def validate_registry(root: Path) -> dict[str, Any]:
    root = root.resolve()
    payload = read_json(registry_path(root), {})
    errors: list[str] = []
    if payload.get("version") != 1:
        errors.append("account_skill_registry_version_invalid")
    accounts = payload.get("accounts")
    if not isinstance(accounts, list):
        return {"ok": False, "errors": [*errors, "account_skill_registry_accounts_invalid"]}
    seen_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for item in accounts:
        if not isinstance(item, dict):
            errors.append("account_skill_registry_item_invalid")
            continue
        account_id = str(item.get("account_skill_id") or "")
        if not account_id:
            errors.append("account_skill_registry_id_missing")
            continue
        if account_id in seen_ids:
            errors.append(f"account_skill_registry_duplicate_id:{account_id}")
        seen_ids.add(account_id)
        skill_relative = str(item.get("skill_path") or "")
        account_name = str(item.get("account_name") or "")
        expected_skill_relative = f"10_Knowledge/formal/accounts/{account_name}/skill/SKILL.md"
        if skill_relative != expected_skill_relative:
            errors.append(f"account_skill_registry_path_noncanonical:{account_id}:{skill_relative}")
            continue
        if not skill_relative.startswith("10_Knowledge/formal/accounts/"):
            errors.append(f"account_skill_registry_path_outside_account_layer:{account_id}")
            continue
        skill_path = root / skill_relative
        manifest = read_json(skill_path.parent.parent / FORMAL_ACCOUNT_MANIFEST, {})
        if not manifest:
            errors.append(f"account_skill_manifest_missing_or_invalid:{account_id}")
        elif manifest.get("account_skill_id") != account_id:
            errors.append(f"account_skill_manifest_id_mismatch:{account_id}")
        elif manifest.get("upgrade_guard_required") is True:
            compatibility = validate_account_skill_upgrade_compatibility(
                root,
                skill_path.parent.parent,
                formal_manifest=manifest,
            )
            errors.extend(compatibility.get("errors", []))
        frontmatter = parse_frontmatter(skill_path)
        if not skill_path.exists():
            errors.append(f"account_skill_missing:{account_id}")
        elif not frontmatter.get("name") or not frontmatter.get("description"):
            errors.append(f"account_skill_frontmatter_invalid:{account_id}")
        if skill_path.exists():
            skill_root = skill_path.parent
            account_root = skill_root.parent
            for relative in REQUIRED_PACKAGE_FILES:
                if not (skill_root / relative).exists():
                    errors.append(f"account_skill_package_file_missing:{account_id}:{relative}")
            manifest_version = str(manifest.get("version") or "").strip()
            for filename in REQUIRED_ACCOUNT_VIEW_FILES:
                view_path = account_root / filename
                if not view_path.exists():
                    errors.append(f"account_skill_view_file_missing:{account_id}:{filename}")
                    continue
                view_text = view_path.read_text(encoding="utf-8")
                if ACCOUNT_VIEW_SOURCE_MARKER not in view_text:
                    errors.append(f"account_skill_view_source_marker_missing:{account_id}:{filename}")
                if manifest_version and f"账号 Skill 版本：{manifest_version}" not in view_text:
                    errors.append(f"account_skill_view_version_mismatch:{account_id}:{filename}:{manifest_version}")
            skill_text = skill_path.read_text(encoding="utf-8")
            for marker in REQUIRED_PRODUCTION_MEMORY_MARKERS:
                if marker not in skill_text:
                    errors.append(f"account_skill_production_memory_rule_missing:{account_id}:{marker}")
        for alias in item.get("aliases", []) if isinstance(item.get("aliases"), list) else []:
            normalized = str(alias).strip().lower()
            if not normalized:
                continue
            owner = seen_aliases.get(normalized)
            if owner and owner != account_id:
                errors.append(f"account_skill_alias_collision:{alias}:{owner}:{account_id}")
            seen_aliases[normalized] = account_id
    return {"ok": not errors, "errors": errors, "registered": len(seen_ids)}


def resolve_account_skill(root: Path, query: str) -> dict[str, Any]:
    payload = read_json(registry_path(root), default_registry())
    text = str(query).strip().lower()
    matches = []
    for item in payload.get("accounts", []):
        if not isinstance(item, dict) or item.get("status") != "active":
            continue
        names = [str(item.get("account_name") or ""), *(str(alias) for alias in item.get("aliases", []))]
        matched = [name for name in names if name and name.lower() in text]
        if matched:
            matches.append((max(len(name) for name in matched), item))
    if not matches:
        return {"ok": False, "status": "not_found", "query": query}
    matches.sort(key=lambda pair: pair[0], reverse=True)
    best_length = matches[0][0]
    best = [item for length, item in matches if length == best_length]
    if len(best) != 1:
        return {
            "ok": False,
            "status": "ambiguous",
            "query": query,
            "account_skill_ids": [item["account_skill_id"] for item in best],
        }
    item = dict(best[0])
    return {"ok": True, "status": "resolved", **item}
