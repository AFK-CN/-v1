from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.account_learning_stage1_extract import extract_stage1_candidates, read_jsonl


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_RELATIVE = Path("00_System/shareable/config/account_learning_pipeline.json")


class AccountLearningStage1ExtractTests(unittest.TestCase):
    def _write_config(self, root: Path) -> None:
        config = root / CONFIG_RELATIVE
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text((REPO_ROOT / CONFIG_RELATIVE).read_text(encoding="utf-8"), encoding="utf-8")

    def test_extracts_five_independent_candidates_per_compatibility_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root)
            workflow = root / "10_Knowledge/candidates/account_learning_workflows/sample"
            workflow.mkdir(parents=True)
            (workflow / "PIPELINE_STATE.json").write_text(
                json.dumps({"current_stage": "stage1_parallel_extraction"}), encoding="utf-8"
            )
            inventory = root / "inventory.jsonl"
            inventory.write_text(json.dumps({"source_id": "n1"}) + "\n" + json.dumps({"source_id": "n2"}) + "\n")
            card = root / "cards/directions/护肤功效/cards/01_n1.md"
            card.parent.mkdir(parents=True)
            card.write_text(
                "# 账号发布资产学习卡：测试标题\n\nsource_id: n1  \n主方向：护肤功效  \n"
                "## 1. 为什么值得学习\n\n- 真实肤质经验。\n"
                "## 2. 核心观点\n\n- 先说具体问题。\n"
                "## 3. 内容结构\n\n- 标题给结果。\n"
                "## 4. 表达素材与金句提炼\n\n- 用具体年限。\n"
                "## 5. 发布资产学习\n\n- 视频待抽帧。\n"
                "## 6. 可复用案例\n\n- 油痘肌案例。\n"
                "## 8. 可复用模板\n\n- 步骤模板。\n"
                "## 9. 证据缺口/后续问题\n\n- 未完成 OCR。\n"
                "## 10. 入库判断\n\n- 待跨卡验证。\n",
                encoding="utf-8",
            )

            result = extract_stage1_candidates(
                root,
                workflow_id="sample",
                card_root=Path("cards"),
                inventory_path=Path("inventory.jsonl"),
                apply=True,
            )

            self.assertEqual(result["candidate_count"], 5)
            self.assertEqual(result["pending_full_evidence_count"], 1)
            for lens in ("positioning", "topics", "structures", "expression", "counterexamples"):
                rows = read_jsonl(workflow / "candidates" / f"{lens}.jsonl")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["source_refs"], ["n1"])
                self.assertFalse(rows[0]["callable"])
            structures = read_jsonl(workflow / "candidates/structures.jsonl")[0]
            self.assertEqual(structures["observation_schema"], "deep_structure_expression_v1")
            self.assertEqual(structures["observation"]["status"], "single_card_observation")
            self.assertIn("initial_problem_or_context", structures["observation"]["missing_or_uncertain_units"])
            expression = read_jsonl(workflow / "candidates/expression.jsonl")[0]
            self.assertTrue(expression["observation"]["evidence_coordinates"])
            report = (workflow / "STAGE1_EXTRACTION_REPORT.md").read_text(encoding="utf-8")
            self.assertIn("sample阶段 1 五视角提取报告", report)
            self.assertNotIn("小森林", report)

    def test_refuses_to_run_outside_stage1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root)
            workflow = root / "10_Knowledge/candidates/account_learning_workflows/sample"
            workflow.mkdir(parents=True)
            (workflow / "PIPELINE_STATE.json").write_text(
                json.dumps({"current_stage": "stage0_account_overview"}), encoding="utf-8"
            )
            inventory = root / "inventory.jsonl"
            inventory.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stage1_parallel_extraction"):
                extract_stage1_candidates(
                    root,
                    workflow_id="sample",
                    card_root=Path("cards"),
                    inventory_path=Path("inventory.jsonl"),
                )


if __name__ == "__main__":
    unittest.main()
