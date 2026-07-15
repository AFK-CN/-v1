import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full"
AD_BASE = BASE / "ad_integration"
BRIDGE_IDS = {
    "ad-b1-same-engine",
    "ad-b2-reveal-payoff",
    "ad-b3-role-need-prop",
    "ad-b4-world-feature",
    "ad-b5-payload-takeover",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class LizonghengAdIntegrationTest(unittest.TestCase):
    def test_all_commercial_sources_have_separate_learning_outputs(self) -> None:
        records = read_jsonl(AD_BASE / "AD_INTEGRATION_INDEX.jsonl")
        platforms = read_jsonl(AD_BASE / "PLATFORM_PROJECT_INDEX.jsonl")
        self.assertEqual(len(records), 140)
        self.assertEqual(len(platforms), 18)
        self.assertEqual(len({row["source_id"] for row in records}), 140)
        self.assertEqual(len(list((AD_BASE / "cards").glob("*.md"))), 140)
        self.assertEqual({row["ad_entry"]["primary_bridge_id"] for row in records}, BRIDGE_IDS)

    def test_every_ad_card_preserves_plot_bridge_product_and_closure(self) -> None:
        for row in read_jsonl(AD_BASE / "AD_INTEGRATION_INDEX.jsonl"):
            with self.subTest(source_id=row["source_id"]):
                self.assertTrue(row["pre_ad_content"]["normal_conflict"])
                self.assertTrue(row["pre_ad_content"]["plot_summary"])
                self.assertTrue(row["ad_entry"]["bridge_evidence"])
                self.assertTrue(row["ad_integration"]["product_role"])
                self.assertTrue(row["ad_integration"]["commercial_payload_evidence"])
                self.assertIsInstance(row["ad_integration"]["returns_to_story"], bool)
                self.assertTrue(row["post_ad_closure"]["closure_evidence"])
                self.assertEqual(row["source_evidence"]["audit_status"], "passed")
                self.assertTrue(row["source_evidence"]["all_quotes_matched"])
                card = (AD_BASE / "cards" / f"{row['source_id']}.md").read_text(encoding="utf-8")
                for section in ("## 1. 广告前的正常剧情如何成立", "## 2. 广告怎么引入", "## 3. 产品怎样进入剧情", "## 4. 广告后如何处理", "## 5. 学习边界"):
                    self.assertIn(section, card)

    def test_complete_plot_integrations_are_manually_reviewed_and_not_hard_cut(self) -> None:
        integrated = [row for row in read_jsonl(AD_BASE / "AD_INTEGRATION_INDEX.jsonl") if row["commercial_axis"] == "广告植入但剧情完整"]
        self.assertEqual(len(integrated), 12)
        for row in integrated:
            with self.subTest(source_id=row["source_id"]):
                self.assertEqual(row["ad_entry"]["classification_basis"], "manual_plot_causality_review")
                self.assertNotEqual(row["ad_entry"]["primary_bridge_id"], "ad-b5-payload-takeover")
                self.assertEqual(row["ad_integration"]["integration_grade"], "A")

    def test_commercial_learning_does_not_pollute_natural_v1(self) -> None:
        summary = read_json(AD_BASE / "AD_INTEGRATION_SUMMARY.json")
        audit = read_json(BASE / "STAGE3_6_AUDIT.json")
        manifest = read_json(BASE / "promotion_manifest.json")
        self.assertTrue(summary["ok"])
        self.assertGreaterEqual(summary["manual_plot_causality_review_count"], 20)
        self.assertEqual(summary["source_transcript_audit_count"], 140)
        self.assertEqual(summary["platform_source_audit_count"], 18)
        self.assertTrue((AD_BASE / "MANUAL_AD_BRIDGE_AUDIT.md").exists())
        self.assertEqual(summary["natural_v1_commercial_pollution"], [])
        self.assertIs(summary["formal_write_allowed"], False)
        self.assertTrue(audit["ad_integration_ok"])
        self.assertEqual(audit["product_ad_learning_card_count"], 140)
        self.assertIn("ad_integration/cards/", manifest["ad_integration_artifacts"])

    def test_v22_source_platform_and_performance_artifacts_are_complete(self) -> None:
        ad_audits = read_jsonl(AD_BASE / "AD_SOURCE_AUDIT_INDEX.jsonl")
        platform_audits = read_jsonl(AD_BASE / "PLATFORM_SOURCE_AUDIT_INDEX.jsonl")
        platforms = read_jsonl(AD_BASE / "PLATFORM_PROJECT_INDEX.jsonl")
        performance = read_json(AD_BASE / "PERFORMANCE_METHOD_ANALYSIS.json")
        acceptance = read_json(BASE / "REAL_ACCEPTANCE_SUMMARY.json")

        self.assertEqual(len(ad_audits), 140)
        self.assertTrue(all(row["audit_status"] == "passed" for row in ad_audits))
        self.assertTrue(all(row["all_quotes_matched"] for row in ad_audits))
        self.assertTrue(all(row["account_id"] == "63700340656" for row in ad_audits))
        visual_rows = [row for row in ad_audits if row["visual_claim"]]
        self.assertEqual(len(visual_rows), 88)
        self.assertTrue(all(row["visual_review_coordinates"] for row in visual_rows))
        self.assertEqual(len(platform_audits), 18)
        self.assertTrue(all(row["audit_status"] == "passed" for row in platform_audits))
        self.assertEqual(sum(row["audit_basis"] == "low_asr_visual_frame_fallback" for row in platform_audits), 2)
        self.assertEqual(len(platforms), 18)
        self.assertTrue(all(row["transferable_rule"] for row in platforms))
        self.assertEqual(len(list((AD_BASE / "platform_cards").glob("*.md"))), 18)
        self.assertEqual(performance["matched_learning_cards"], 430)
        self.assertEqual(acceptance["schema_version"], "2.2")
        self.assertEqual(acceptance["status"], "passed")
        self.assertEqual(acceptance["commercial_learning"]["product_ads"]["audited"], 140)
        self.assertEqual(acceptance["commercial_learning"]["platform_projects"]["audited"], 18)
        self.assertTrue((AD_BASE / "MANUAL_VISUAL_COORDINATE_AUDIT.md").exists())


if __name__ == "__main__":
    unittest.main()
