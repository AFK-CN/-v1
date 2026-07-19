import json
import unittest
from pathlib import Path

from tools.kb.validator import validate_system_version


class SystemUpgradeV31Tests(unittest.TestCase):
    def test_system_version_records_p0_p1_p2_and_full_acceptance_matrix(self) -> None:
        payload = json.loads(
            Path("00_System/shareable/config/system_version.json").read_text(encoding="utf-8")
        )
        failures: list[str] = []

        validate_system_version(Path.cwd(), payload, failures)

        self.assertEqual(failures, [])
        self.assertEqual(payload["system_version"], "3.1")
        self.assertEqual(payload["predecessor"]["system_version"], "3.0")
        self.assertIn(payload["status"], {"validating", "active"})
        self.assertEqual({item["id"] for item in payload["components"]}, {"P0", "P1", "P2", "P3"})
        self.assertFalse(payload["boundaries"]["account_learning_executed"])
        self.assertTrue(payload["boundaries"]["active_account_learning_modified"])
        self.assertTrue(payload["boundaries"]["account_skill_upgrade_executed"])
        self.assertTrue(payload["boundaries"]["historical_workflow_migration_executed"])
        self.assertFalse(payload["boundaries"]["account_specific_content_allowed_in_system"])
        self.assertIn("full_unit_test_suite", payload["validation"]["required"])
        self.assertIn("account_pollution_audit", payload["validation"]["required"])
        self.assertIn("all_account_v29_learning_audit", payload["validation"]["required"])
        p3 = next(item for item in payload["components"] if item["id"] == "P3")
        self.assertTrue(p3["all_registered_accounts_v29_complete"])
        self.assertEqual(p3["registered_account_count"], 5)

    def test_v31_keeps_visual_provenance_and_activates_expression_learning(self) -> None:
        formal = json.loads(
            Path("00_System/shareable/config/formal_retrieval.json").read_text(encoding="utf-8")
        )
        expression = json.loads(
            Path("00_System/shareable/config/expression_asset_contract.json").read_text(encoding="utf-8")
        )
        routes = json.loads(
            Path("00_System/shareable/index/controller_routes.json").read_text(encoding="utf-8")
        )
        output = json.loads(
            Path("00_System/shareable/config/output_contracts.json").read_text(encoding="utf-8")
        )
        pipeline = json.loads(
            Path("00_System/shareable/config/account_learning_pipeline.json").read_text(encoding="utf-8")
        )

        self.assertEqual(formal["version"], "3.0")
        self.assertEqual(expression["version"], "3.1")
        self.assertEqual(routes["version"], "3.0")
        self.assertEqual(output["version"], "3.0")
        self.assertIn("formal_retrieval", {item["id"] for item in routes["routes"]})
        self.assertTrue(expression["activation_boundary"]["active_account_learning_integration"])
        self.assertEqual(pipeline["version"], "3.0")
        self.assertEqual(
            pipeline["stage6_upgrade_compatibility"]["schema_id"],
            "account_skill_upgrade_compatibility_v1",
        )
        self.assertTrue(
            pipeline["historical_workflow_v29_migration"]["required_for_all_registered_accounts"]
        )
        self.assertEqual(
            pipeline["historical_workflow_v29_migration"]["acceptance_command"],
            "tools.kb.cli account-learning-v29-audit",
        )
        self.assertEqual(
            pipeline["stage6_visual_reference_package"]["source_kinds"]["user_accepted_ai_output"],
            "page_continuity_and_composition_regression_only",
        )
        self.assertIn("expression_asset_learning", pipeline)
        self.assertEqual(len(pipeline["stages"]), 7)

    def test_upgrade_record_explicitly_forbids_account_learning_and_pollution(self) -> None:
        record = Path("00_System/shareable/docs/project_use/系统升级3.1记录.md").read_text(encoding="utf-8")

        self.assertIn("系统升级 3.1", record)
        self.assertIn("不执行真实账号学习", record)
        self.assertIn("不把账号内容写入系统层", record)
        self.assertIn("只有一套 active 账号学习工作流", record)
        self.assertIn("旧能力 ID", record)
        self.assertIn("来源原文只可展示与溯源", record)
        self.assertTrue(Path("00_System/shareable/docs/project_use/系统升级3.0记录.md").is_file())

    def test_v31_system_artifacts_contain_no_registered_account_tokens(self) -> None:
        registry = json.loads(Path("20_User/config/account_skill_registry.json").read_text(encoding="utf-8"))
        tokens = set()
        for account in registry.get("accounts", []):
            tokens.add(str(account.get("account_name", "")))
            tokens.add(str(account.get("account_skill_id", "")))
            tokens.update(map(str, account.get("aliases", [])))
        tokens = {item for item in tokens if len(item) >= 3}
        artifacts = [
            "00_System/shareable/config/formal_retrieval.json",
            "00_System/shareable/config/expression_asset_contract.json",
            "00_System/shareable/config/system_version.json",
            "00_System/shareable/docs/project_use/系统升级3.0记录.md",
            "00_System/shareable/docs/project_use/系统升级3.1记录.md",
            "00_System/shareable/skills/proposals/account-learning-expression-assets-v3.0.md",
            "00_System/shareable/skills/proposals/account-learning-ai-output-provenance-v2.8.md",
            "00_System/shareable/skills/proposals/account-learning-capability-preservation-v2.9.md",
            "00_System/shareable/index/controller_routes.json",
            "00_System/shareable/config/output_contracts.json",
            "tools/kb/formal_search.py",
            "tools/kb/expression_assets.py",
            "tools/account_expression_assets.py",
            "00_System/shareable/skills/active/account-learning/references/capability-preserving-upgrades.md",
            "00_System/shareable/skills/active/account-learning/references/expression-asset-learning.md",
        ]
        leaks = []
        for relative in artifacts:
            text = Path(relative).read_text(encoding="utf-8")
            leaks.extend(f"{relative}:{token}" for token in tokens if token in text)

        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
