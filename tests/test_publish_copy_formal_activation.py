from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = ROOT / "10_Knowledge/formal/accounts"
CANDIDATE_ROOT = ROOT / "10_Knowledge/candidates/account_learning_workflows"

TARGETS = {
    "姜胡说": ("1.4", "jianghushuo-v2-full", 548),
    "李宗恒": ("1.4", "lizongheng-v2-full", 430),
    "闲鱼故事UGC任务": ("1.3", "xianyu-story-ugc-xiaohao-20260713-0717", 100),
    "小森林的小世界": ("1.4", "xiaosenlin-xiaoshijie-v2-full", 379),
}

VIEWS = (
    "账号整体方法论.md",
    "内容生产使用说明.md",
    "减少AI味输出规则.md",
    "内容输出标准模板.md",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublishCopyFormalActivationTest(unittest.TestCase):
    def test_four_approved_skills_resolve_to_account_specific_publish_rules(self) -> None:
        account_names = set(TARGETS) | {"省钱也要喂饱自己（沪漂版）"}
        for account_name, (version, workflow_id, expected_count) in TARGETS.items():
            with self.subTest(account=account_name):
                account_root = FORMAL_ROOT / account_name
                manifest = read_json(account_root / "ACCOUNT_SKILL_MANIFEST.json")
                self.assertEqual(manifest["version"], version)
                self.assertEqual(manifest["status"], "active")

                skill = (account_root / "skill/SKILL.md").read_text(encoding="utf-8")
                self.assertIn("publishing-copy.md", skill)
                self.assertIn(version, skill)

                rules_path = account_root / "skill/references/publishing-copy.md"
                rules = rules_path.read_text(encoding="utf-8")
                self.assertIn("标题", rules)
                self.assertIn("正文", rules)
                self.assertIn("话题", rules)
                self.assertIn("协同", rules)
                for other_account in account_names - {account_name}:
                    self.assertNotIn(other_account, rules)

                evidence_path = account_root / "evidence/PUBLISH_COPY_EVIDENCE_VALIDATION.json"
                evidence = read_json(evidence_path)
                compatibility = read_json(account_root / "skill/UPGRADE_COMPATIBILITY.json")
                self.assertEqual(evidence["status"], "approved_callable")
                self.assertEqual(evidence["account_skill_version"], compatibility["base_version"])
                self.assertEqual(compatibility["target_version"], version)
                self.assertEqual(evidence["counts"]["eligible"], expected_count)
                self.assertEqual(evidence["counts"]["completed"], expected_count)
                self.assertEqual(evidence["counts"]["deferred"], 0)
                self.assertEqual(set(evidence["triple_verification"].keys()), {
                    "cross_context",
                    "predictive_usefulness",
                    "account_exclusivity",
                })

                workflow_root = CANDIDATE_ROOT / workflow_id
                self.assertEqual(
                    evidence["source_report_sha256"],
                    sha256(workflow_root / "PUBLISH_COPY_SPECIAL_STUDY.json"),
                )
                self.assertEqual(
                    evidence["observation_sha256"],
                    sha256(workflow_root / "candidates/publish_copy_observations.jsonl"),
                )

                for view in VIEWS:
                    self.assertIn(
                        f"账号 Skill 版本：{version}",
                        (account_root / view).read_text(encoding="utf-8"),
                    )

    def test_food_skill_remains_on_latest_approved_specialized_version(self) -> None:
        account_root = FORMAL_ROOT / "省钱也要喂饱自己（沪漂版）"
        manifest = read_json(account_root / "ACCOUNT_SKILL_MANIFEST.json")
        self.assertEqual(manifest["version"], "2.1")
        self.assertTrue((account_root / "skill/references/publishing-copy.md").is_file())
        self.assertTrue((account_root / "skill/references/publishing-copy-golden.md").is_file())
        self.assertTrue((account_root / "skill/scripts/validate_publishing_copy.py").is_file())

    def test_registry_versions_match_formal_manifests(self) -> None:
        registry = read_json(ROOT / "20_User/config/account_skill_registry.json")
        versions = {item["account_name"]: item["version"] for item in registry["accounts"]}
        for account_name, (version, _, _) in TARGETS.items():
            self.assertEqual(versions[account_name], version)
        self.assertEqual(versions["省钱也要喂饱自己（沪漂版）"], "2.1")


if __name__ == "__main__":
    unittest.main()
