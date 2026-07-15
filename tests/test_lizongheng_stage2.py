import json
import unittest
from pathlib import Path

from tools.lizongheng_stage2 import classify


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class LizonghengStage2Test(unittest.TestCase):
    def test_boundary_priority_prevents_method_promotion(self) -> None:
        commercial = {"type": "structures", "title": "广告里的系统迁移", "summary": "品牌卖点", "tags": []}
        evidence = {"type": "structures", "title": "系统迁移", "summary": "ASR和画面证据不足", "tags": []}
        self.assertEqual(classify(commercial), "lz-g1-commercial-contamination")
        self.assertEqual(classify(evidence), "lz-g2-evidence-account-boundary")

    def test_primary_methods_and_expression_support_are_distinct(self) -> None:
        cases = {
            "lz-m1-system-transfer": "整套系统迁移并完成完整流程",
            "lz-m2-control-right-reversal": "求职者夺回评价权",
            "lz-m3-semantic-reinterpretation": "字面歧义形成双语境",
            "lz-m4-fixed-rule-escalation": "固定口令在多场景重复升级",
        }
        for expected, title in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(classify({"type": "structures", "title": title, "summary": "", "tags": []}), expected)
        self.assertEqual(
            classify({"type": "expression", "title": "短标题保留悬念", "summary": "", "tags": []}),
            "lz-r3-packaging-support",
        )

    def test_current_stage2_assigns_every_candidate_exactly_once(self) -> None:
        candidates = [item for path in sorted((WORKFLOW / "candidates").glob("*.jsonl")) for item in read_jsonl(path)]
        clusters = read_jsonl(WORKFLOW / "candidate_clusters.jsonl")
        assigned = [candidate_id for cluster in clusters for candidate_id in cluster["candidate_ids"]]
        self.assertEqual(len(candidates), 1330)
        self.assertEqual(len(assigned), 1330)
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual({item["id"] for item in candidates}, set(assigned))
        self.assertEqual(len(read_jsonl(WORKFLOW / "verified.jsonl")), 4)
        self.assertEqual(len(read_jsonl(WORKFLOW / "rejected.jsonl")), 6)

    def test_v1_evidence_excludes_commercial_and_platform_content(self) -> None:
        cards = {
            str(card["source_id"]): card
            for path in sorted((ROOT / "10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/batches").glob("batch_*/structured_cards.jsonl"))
            for card in read_jsonl(path)
        }
        for method in read_jsonl(WORKFLOW / "verified.jsonl"):
            for source_id in method["triple_verification"]["v1_cross_context"]["evidence_refs"]:
                with self.subTest(method=method["id"], source_id=source_id):
                    self.assertEqual(cards[source_id]["commercial_axis"], "正常内容")
                    self.assertIs(cards[source_id]["core_direction_eligible"], True)


if __name__ == "__main__":
    unittest.main()
