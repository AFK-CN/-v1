import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full"
METHOD_IDS = {
    "lz-m1-system-transfer",
    "lz-m2-control-right-reversal",
    "lz-m3-semantic-reinterpretation",
    "lz-m4-fixed-rule-escalation",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def contains_key(value: object, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, target) for item in value)
    return False


class LizonghengStageThreeToSixTest(unittest.TestCase):
    def test_method_units_are_distinct_and_candidate_only(self) -> None:
        bodies = []
        required_sections = ["## R - 原始证据", "## I - 方法论解释", "## A1 - 已发生案例", "## A2 - 未来触发场景", "## E - 可执行步骤", "## B - 边界与反例"]
        for method_id in METHOD_IDS:
            method_dir = BASE / "methods" / method_id
            payload = read_json(method_dir / "method.json")
            body = (method_dir / "METHOD.md").read_text(encoding="utf-8")
            self.assertEqual(payload["status"], "verified_candidate")
            self.assertIs(payload["callable"], False)
            self.assertGreaterEqual(len(payload["source_refs"]), 4)
            for section in required_sections:
                self.assertIn(section, body)
            bodies.append(body)
        self.assertEqual(len(bodies), len(set(bodies)))

    def test_method_links_have_valid_endpoints_and_real_relation_types(self) -> None:
        index = read_json(BASE / "METHOD_INDEX.json")
        self.assertEqual({item["id"] for item in index["methods"]}, METHOD_IDS)
        self.assertGreaterEqual(len(index["relations"]), 6)
        for relation in index["relations"]:
            self.assertIn(relation["source"], METHOD_IDS)
            self.assertIn(relation["target"], METHOD_IDS)
            self.assertNotEqual(relation["source"], relation["target"])
            self.assertIn(relation["type"], {"depends_on", "contrasts_with", "composes_with"})
            self.assertTrue(relation["reason"])

    def test_pressure_tests_cover_all_nontrivial_boundaries(self) -> None:
        required_types = {"should_trigger", "should_not_trigger", "edge_case", "cross_scene_transfer", "ablation", "composition", "commercial_contamination"}
        all_prompts = []
        for method_id in METHOD_IDS:
            prompts_path = BASE / "methods" / method_id / "test-prompts.json"
            prompts = read_json(prompts_path)
            results = read_json(BASE / "methods" / method_id / "test-results.json")
            self.assertTrue(prompts["executor_input_excludes_expected_answer"])
            self.assertFalse(contains_key(prompts, "_expected"))
            self.assertEqual(len(prompts["test_cases"]), 8)
            self.assertTrue(required_types.issubset({case["type"] for case in prompts["test_cases"]}))
            self.assertEqual(results["prompt_set_sha256"], hashlib.sha256(prompts_path.read_bytes()).hexdigest())
            self.assertEqual(results["passed"], 8)
            self.assertEqual(results["failed"], 0)
            commercial_id = next(case["id"] for case in prompts["test_cases"] if case["type"] == "commercial_contamination")
            commercial_result = next(item for item in results["case_results"] if item["id"] == commercial_id)
            self.assertEqual(commercial_result["actual_decision"], "boundary_only")
            all_prompts.extend(case["prompt"] for case in prompts["test_cases"])
        self.assertEqual(len(all_prompts), len(set(all_prompts)))

    def test_delivery_remains_non_callable_and_non_formal(self) -> None:
        manifest = read_json(BASE / "promotion_manifest.json")
        audit = read_json(BASE / "STAGE3_6_AUDIT.json")
        state = read_json(BASE / "PIPELINE_STATE.json")
        self.assertEqual(set(manifest["method_ids"]), METHOD_IDS)
        self.assertIs(manifest["formal_write"], False)
        self.assertIs(manifest["callable"], False)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["v1_evidence_ref_count"], 16)
        self.assertIs(audit["v1_all_normal_core"], True)
        self.assertIs(audit["ad_integration_ok"], True)
        self.assertEqual(audit["product_ad_learning_card_count"], 140)
        self.assertIs(audit["formal_write_allowed"], False)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["current_stage"], "completed")
        self.assertTrue(all(stage["status"] == "completed" for stage in state["stages"]))


if __name__ == "__main__":
    unittest.main()
