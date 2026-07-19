from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.kb.account_skills import (
    audit_account_skill_v29_compatibility,
    upgrade_formal_account_skill_v29,
    validate_account_skill_upgrade_compatibility,
)
from tools.account_learning_pipeline import (
    audit_all_account_learning_v29,
    _candidate_compatibility_from_formal,
    _candidate_resource_allowed,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class AccountSkillUpgradeCompatibilityTests(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def fixture(self, tmp: str) -> tuple[Path, Path, dict]:
        root = Path(tmp)
        contract_target = root / "00_System/shareable/config/account_skill_contract.json"
        contract_target.parent.mkdir(parents=True, exist_ok=True)
        contract_target.write_text(
            (REPO_ROOT / "00_System/shareable/config/account_skill_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        account_root = root / "10_Knowledge/formal/accounts/测试账号"
        skill_root = account_root / "skill"
        skill = skill_root / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(
            "---\nname: account-test\ndescription: Test.\n---\n\n# Test\n",
            encoding="utf-8",
        )
        proposal = root / "00_System/shareable/skills/proposals/account-test-v2.md"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text(
            "---\nskill_name: account-test\nversion: '2.0'\nstatus: applied\n---\n\n# Proposal\n",
            encoding="utf-8",
        )
        mother = skill_root / "assets/regression/mother.png"
        child = skill_root / "assets/regression/child.png"
        mother.parent.mkdir(parents=True, exist_ok=True)
        mother.write_bytes(b"mother")
        child.write_bytes(b"child")
        package = skill_root / "assets/regression/manifest.json"
        self.write_json(
            package,
            {
                "schema_version": "account_visual_regression_package_v1",
                "package_id": "package-1",
                "account_skill_id": "test-account",
                "source_kind": "user_accepted_ai_output",
                "origin_kind": "ai_generated",
                "reference_policy": "page_continuity_and_composition_regression_only",
                "allowed_uses": ["page_continuity_regression", "composition_regression"],
                "authenticity_authority": False,
                "realism_authority": False,
                "master_reference_eligible": False,
                "golden_positive_eligible": False,
                "method_evidence_eligible": False,
                "generation_reference_eligible": False,
                "continuity_required": True,
                "continuity_mother_asset_id": "mother",
                "derivation_policy": "local_edit_or_controlled_derivation",
                "independent_regeneration_allowed": False,
                "pages": [
                    {
                        "order": 1,
                        "asset_id": "mother",
                        "role": "clean_meal",
                        "parent_asset_id": None,
                        "asset_path": "mother.png",
                        "sha256": hashlib.sha256(mother.read_bytes()).hexdigest(),
                    },
                    {
                        "order": 2,
                        "asset_id": "child",
                        "role": "result",
                        "parent_asset_id": "mother",
                        "asset_path": "child.png",
                        "sha256": hashlib.sha256(child.read_bytes()).hexdigest(),
                    },
                ],
            },
        )
        account_relative = "10_Knowledge/formal/accounts/测试账号"
        manifest = {
            "account_skill_id": "test-account",
            "account_name": "测试账号",
            "skill_name": "account-test",
            "version": "2.0",
            "upgrade_guard_required": True,
            "upgrade_compatibility_manifest": f"{account_relative}/skill/UPGRADE_COMPATIBILITY.json",
        }
        self.write_json(account_root / "ACCOUNT_SKILL_MANIFEST.json", manifest)
        payload = {
            "schema_version": "account_skill_upgrade_compatibility_v1",
            "account_skill_id": "test-account",
            "base_version": "1.0",
            "target_version": "2.0",
            "upgrade_scope": "single_account",
            "previous_capability_ids": ["old-capability"],
            "new_capability_ids": ["new-capability"],
            "capabilities": [
                {
                    "id": "old-capability",
                    "introduced_in": "1.0",
                    "status": "active",
                    "source_paths": [f"{account_relative}/skill/SKILL.md"],
                },
                {
                    "id": "new-capability",
                    "introduced_in": "2.0",
                    "status": "active",
                    "source_paths": [f"{account_relative}/skill/SKILL.md"],
                },
            ],
            "changed_capabilities": [],
            "source_snapshot": [
                {
                    "path": f"{account_relative}/skill/SKILL.md",
                    "sha256": hashlib.sha256(skill.read_bytes()).hexdigest(),
                }
            ],
            "regression_package_manifests": [f"{account_relative}/skill/assets/regression/manifest.json"],
            "isolation": {
                "same_account_only": True,
                "cross_account_merge": False,
                "system_rule_contamination": False,
                "absolute_or_nas_paths": False,
            },
            "rollback": {"restore_version": "1.0"},
        }
        self.write_json(skill_root / "UPGRADE_COMPATIBILITY.json", payload)
        return root, account_root, payload

    def formal_upgrade_fixture(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp)
        contract_target = root / "00_System/shareable/config/account_skill_contract.json"
        contract_target.parent.mkdir(parents=True, exist_ok=True)
        contract_target.write_text(
            (REPO_ROOT / "00_System/shareable/config/account_skill_contract.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        account_root = root / "10_Knowledge/formal/accounts/测试账号"
        skill_root = account_root / "skill"
        self.write_json(
            account_root / "ACCOUNT_SKILL_MANIFEST.json",
            {
                "schema_version": "formal_account_skill_v1",
                "account_skill_id": "test_account",
                "account_name": "测试账号",
                "platform": "test",
                "skill_name": "account-test",
                "version": "1.3",
                "status": "active",
                "canonical_skill_path": "10_Knowledge/formal/accounts/测试账号/skill/SKILL.md",
            },
        )
        skill_root.mkdir(parents=True, exist_ok=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: account-test\ndescription: Test account.\n---\n\n"
            "# Test\n\n账号 Skill 版本：1.3\n\n"
            "topic-memory-check topic-memory-record production-memory-record\n\n"
            "保留本账号旧能力原文。\n",
            encoding="utf-8",
        )
        for name in ("production", "style", "boundaries", "acceptance", "publishing-copy"):
            path = skill_root / "references" / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {name}\n\nSame-account rule.\n", encoding="utf-8")
        for filename in ("账号整体方法论.md", "内容生产使用说明.md", "减少AI味输出规则.md", "内容输出标准模板.md"):
            (account_root / filename).write_text(
                "<!-- account-view: source=skill; sync=required -->\n\n"
                "账号 Skill 版本：1.3\n",
                encoding="utf-8",
            )
        self.write_json(
            account_root / "METHOD_INDEX.json",
            {"methods": [{"id": "method-one", "status": "approved_callable", "callable": True}]},
        )
        self.write_json(
            root / "20_User/config/account_skill_registry.json",
            {
                "version": 1,
                "accounts": [
                    {
                        "account_skill_id": "test_account",
                        "account_name": "测试账号",
                        "status": "active",
                        "skill_path": "10_Knowledge/formal/accounts/测试账号/skill/SKILL.md",
                    }
                ],
            },
        )
        return root, account_root

    def validate(self, root: Path, account_root: Path) -> dict:
        return validate_account_skill_upgrade_compatibility(root, account_root)

    def test_valid_upgrade_preserves_old_capability_and_ordered_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root, _ = self.fixture(tmp)

            result = self.validate(root, account_root)

            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["capability_count"], 2)
            self.assertEqual(result["regression_package_count"], 1)

    def test_silent_capability_loss_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root, payload = self.fixture(tmp)
            payload["previous_capability_ids"].append("lost-capability")
            self.write_json(account_root / "skill/UPGRADE_COMPATIBILITY.json", payload)

            result = self.validate(root, account_root)

            self.assertFalse(result["ok"])
            self.assertIn("upgrade_capability_silent_loss:test-account:lost-capability", result["errors"])

    def test_deprecation_without_user_confirmation_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root, payload = self.fixture(tmp)
            payload["capabilities"][0]["status"] = "deprecated"
            payload["changed_capabilities"] = [
                {
                    "capability_id": "old-capability",
                    "change_type": "deprecated",
                    "replacement_ids": ["new-capability"],
                    "user_confirmation": {"confirmed": False, "proposal_path": ""},
                    "rollback": "restore",
                }
            ]
            self.write_json(account_root / "skill/UPGRADE_COMPATIBILITY.json", payload)

            result = self.validate(root, account_root)

            self.assertFalse(result["ok"])
            self.assertIn("upgrade_capability_user_confirmation_missing:test-account:old-capability", result["errors"])

    def test_cross_account_source_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root, payload = self.fixture(tmp)
            payload["capabilities"][0]["source_paths"] = [
                "10_Knowledge/formal/accounts/另一个账号/skill/SKILL.md"
            ]
            self.write_json(account_root / "skill/UPGRADE_COMPATIBILITY.json", payload)

            result = self.validate(root, account_root)

            self.assertFalse(result["ok"])
            self.assertIn(
                "upgrade_capability_cross_account_or_nonportable_source:test-account:old-capability",
                result["errors"],
            )

    def test_changed_capability_proposal_must_remain_in_same_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root, payload = self.fixture(tmp)
            payload["capabilities"][0]["status"] = "deprecated"
            payload["changed_capabilities"] = [
                {
                    "capability_id": "old-capability",
                    "change_type": "deprecated",
                    "replacement_ids": ["new-capability"],
                    "user_confirmation": {
                        "confirmed": True,
                        "proposal_path": "00_System/shareable/skills/proposals/account-test-v2.md",
                    },
                    "rollback": "restore",
                }
            ]
            self.write_json(account_root / "skill/UPGRADE_COMPATIBILITY.json", payload)

            blocked = self.validate(root, account_root)

            self.assertFalse(blocked["ok"])
            self.assertIn(
                "upgrade_capability_proposal_path_invalid:test-account:old-capability",
                blocked["errors"],
            )

            proposal = account_root / "skill/proposals/capability-change-v2.md"
            proposal.parent.mkdir(parents=True, exist_ok=True)
            proposal.write_text(
                "---\nskill_name: account-test\nversion: '2.0'\nstatus: applied\n---\n\n# Proposal\n",
                encoding="utf-8",
            )
            payload["changed_capabilities"][0]["user_confirmation"]["proposal_path"] = (
                "10_Knowledge/formal/accounts/测试账号/skill/proposals/capability-change-v2.md"
            )
            self.write_json(account_root / "skill/UPGRADE_COMPATIBILITY.json", payload)

            accepted = self.validate(root, account_root)

            self.assertTrue(accepted["ok"], accepted["errors"])

    def test_ai_regression_package_cannot_gain_realism_or_independent_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root, _ = self.fixture(tmp)
            package = account_root / "skill/assets/regression/manifest.json"
            payload = json.loads(package.read_text(encoding="utf-8"))
            payload["realism_authority"] = True
            payload["independent_regeneration_allowed"] = True
            self.write_json(package, payload)

            result = self.validate(root, account_root)

            self.assertFalse(result["ok"])
            self.assertIn("regression_package_authority_must_be_false:manifest.json:realism_authority", result["errors"])
            self.assertIn("regression_package_independent_regeneration_forbidden:manifest.json", result["errors"])

    def test_live_account_upgrade_manifest_passes(self) -> None:
        account_root = REPO_ROOT / "10_Knowledge/formal/accounts/省钱也要喂饱自己（沪漂版）"

        result = validate_account_skill_upgrade_compatibility(REPO_ROOT, account_root)

        self.assertTrue(result["ok"], result["errors"])
        self.assertGreaterEqual(result["capability_count"], 33)
        self.assertEqual(result["new_capability_count"], 2)
        self.assertEqual(result["regression_package_count"], 1)

    def test_formal_v29_upgrade_preserves_content_and_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root = self.formal_upgrade_fixture(tmp)

            result = upgrade_formal_account_skill_v29(
                root,
                "test_account",
                user_confirmed=True,
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["base_version"], "1.3")
            self.assertEqual(result["target_version"], "1.4")
            self.assertTrue(
                result["proposal"].startswith(
                    "10_Knowledge/formal/accounts/测试账号/skill/proposals/"
                )
            )
            skill_text = (account_root / "skill/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("保留本账号旧能力原文", skill_text)
            self.assertIn("账号 Skill 版本：1.4", skill_text)
            compatibility = json.loads(
                (account_root / "skill/UPGRADE_COMPATIBILITY.json").read_text(encoding="utf-8")
            )
            ids = {item["id"] for item in compatibility["capabilities"]}
            self.assertIn("formal_method_method_one", ids)
            self.assertIn("publishing_copy_specialization", ids)
            self.assertIn("capability_preserving_upgrade_guard", ids)
            self.assertEqual(
                set(compatibility["new_capability_ids"]),
                {"capability_preserving_upgrade_guard"},
            )
            self.assertTrue(set(compatibility["previous_capability_ids"]).issubset(ids))
            for capability in compatibility["capabilities"]:
                for source in capability["source_paths"]:
                    self.assertTrue(source.startswith("10_Knowledge/formal/accounts/测试账号/"))

            audit = audit_account_skill_v29_compatibility(root)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(audit["passed_count"], 1)

    def test_formal_v29_upgrade_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root = self.formal_upgrade_fixture(tmp)

            result = upgrade_formal_account_skill_v29(root, "test_account")

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "user_confirmation_required")
            manifest = json.loads((account_root / "ACCOUNT_SKILL_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "1.3")

    def test_candidate_conversion_never_hashes_compatibility_manifest_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, account_root = self.formal_upgrade_fixture(tmp)
            result = upgrade_formal_account_skill_v29(root, "test_account", user_confirmed=True)
            self.assertTrue(result["ok"], result)
            pipeline_config = root / "00_System/shareable/config/account_learning_pipeline.json"
            pipeline_config.parent.mkdir(parents=True, exist_ok=True)
            pipeline_config.write_text(
                (REPO_ROOT / "00_System/shareable/config/account_learning_pipeline.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            workflow_root = root / "10_Knowledge/candidates/account_learning_workflows/test-workflow"
            target_root = workflow_root / "account_skill_candidate"
            shutil.copytree(account_root / "skill", target_root)
            method_snapshot = target_root / "references/formal-method-index.json"
            shutil.copy2(account_root / "METHOD_INDEX.json", method_snapshot)
            for filename in ("账号整体方法论.md", "内容生产使用说明.md", "减少AI味输出规则.md", "内容输出标准模板.md"):
                view = target_root / "account_views" / filename
                view.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(account_root / filename, view)

            payload = _candidate_compatibility_from_formal(
                root,
                workflow_id="test-workflow",
                source_root=account_root / "skill",
                source_account_root=account_root,
                target_root=target_root,
            )

            snapshot_paths = {item["path"] for item in payload["source_snapshot"]}
            self.assertFalse(any(path.endswith("/UPGRADE_COMPATIBILITY.json") for path in snapshot_paths))
            for capability in payload["capabilities"]:
                self.assertFalse(
                    any(path.endswith("/UPGRADE_COMPATIBILITY.json") for path in capability["source_paths"])
                )

    def test_candidate_resource_filter_blocks_generated_garbage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "scripts/validate.py"
            cache = root / "scripts/__pycache__/validate.cpython-312.pyc"
            ds_store = root / "scripts/.DS_Store"
            for path in (valid, cache, ds_store):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test")

            self.assertTrue(_candidate_resource_allowed(valid))
            self.assertFalse(_candidate_resource_allowed(cache))
            self.assertFalse(_candidate_resource_allowed(ds_store))

    def test_all_registered_accounts_have_complete_isolated_v29_learning_snapshots(self) -> None:
        result = audit_all_account_learning_v29(REPO_ROOT)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["pipeline_version"], "2.9")
        self.assertEqual(result["registered_account_count"], 5)
        self.assertEqual(result["workflow_count"], 5)
        self.assertEqual(result["passed_count"], 5)
        self.assertEqual(result["formal_compatibility_passed_count"], 5)
        self.assertEqual(result["missing_workflows"], [])
        self.assertEqual(result["extra_workflows"], [])
        self.assertEqual(result["duplicate_account_skill_ids"], [])
        self.assertEqual(result["cross_account_token_leaks"], [])
        self.assertEqual(result["cross_account_template_collisions"], [])
        deferred = [
            item for item in result["results"] if item.get("deferred_evidence_count", 0) > 0
        ]
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0]["deferred_evidence_count"], 49)
        self.assertTrue(deferred[0]["deferred_evidence_isolated"])


if __name__ == "__main__":
    unittest.main()
