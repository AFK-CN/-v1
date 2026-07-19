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

    def test_unified_card_uses_unified_wording_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root)
            workflow = root / "10_Knowledge/candidates/account_learning_workflows/sample"
            workflow.mkdir(parents=True)
            (workflow / "PIPELINE_STATE.json").write_text(
                json.dumps({"current_stage": "stage1_parallel_extraction", "account_name": "测试账号"}),
                encoding="utf-8",
            )
            inventory = root / "inventory.jsonl"
            inventory.write_text(json.dumps({"source_id": "n1"}) + "\n", encoding="utf-8")
            card = root / "cards/directions/自然一人食/cards/n1.md"
            card.parent.mkdir(parents=True)
            card.write_text(
                "# 图文深度学习卡：n1\n\n"
                "学习卡契约：unified_three_layer_v2\nsource_id: n1\n主方向：自然一人食\n"
                "## 1. 证据边界\n\n- 主证据：原图。\n"
                "## 2. 为什么值得学习\n\n- 结果前置。\n"
                "## 3. 多维分类与商业隔离\n\n- 内容形态：图文。\n- 商业属性：正常内容。\n- 隔离判断：不进入商业轨。\n"
                "## 4. 核心观点\n\n- 先给结果。\n"
                "## 5. 内容结构\n\n- 封面承诺：完整餐。\n- 分图顺序：材料、动作、状态、结果。\n"
                "## 6. 发布内容层学习\n\n- 标题：一人食。\n- 标题机制：处境加结果承诺。\n- 正文结构：处境、动作、结果。\n- 细节密度：数量、时长和状态。\n- 真人感：下班晚和个人偏好。\n- 结尾方式：自然停住。\n- 话题策略：场景检索词。\n- 发布视觉协同：正文补组图细节。\n"
                "## 7. 视频/图文表现层学习\n\n- 表现学习：俯拍。\n- 封面钩子：成品结果。\n- 逐图角色：材料、动作、结果。\n- 分图顺序：信息逐页增加。\n- 构图与视角：俯拍和近景。\n- 动作与状态：动作连接完成状态。\n- 视觉层级：主体先于注释。\n- 文字注释设计：贴纸指向动作。\n- 字形字号层级：标题与步骤分级。\n- 色彩光线质感：自然光。\n- 真人与生活感：自然手势和使用痕迹。\n- 跨模态协同：文图同一承诺。\n- 收藏理由：步骤可回看。\n"
                "## 8. 金句与表达素材\n\n- 原文金句：今天吃。\n"
                "## 9. 可复用选题与案例\n\n- 可复用选题：完整餐。\n"
                "## 10. 方法候选与可复用方法论\n\n- 单卡待验证。\n"
                "## 11. 可复用模板\n\n- 结果到步骤。\n"
                "## 12. 证据缺口与候选判断\n\n- 证据缺口：单卡。\n",
                encoding="utf-8",
            )

            result = extract_stage1_candidates(
                root,
                workflow_id="sample",
                card_root=Path("cards"),
                inventory_path=Path("inventory.jsonl"),
                apply=True,
            )

            self.assertEqual(result["unified_card_count"], 1)
            self.assertEqual(result["downgraded_legacy_card_count"], 0)
            positioning = read_jsonl(workflow / "candidates/positioning.jsonl")[0]
            self.assertIn("统一学习卡", positioning["summary"])
            self.assertNotIn("降级后的兼容旧卡", positioning["summary"])
            expression = read_jsonl(workflow / "candidates/expression.jsonl")[0]
            self.assertEqual(expression["publish_copy_observation"]["schema"], "publish_copy_observation_v1")
            self.assertIn("operational_or_argument_detail_density", [item["signal"] for item in expression["publish_copy_observation"]["observed_signals"]])
            structures = read_jsonl(workflow / "candidates/structures.jsonl")[0]
            self.assertEqual(structures["image_text_visual_observation"]["schema"], "image_text_visual_observation_v1")
            self.assertIn("text_annotation_design", [item["signal"] for item in structures["image_text_visual_observation"]["observed_signals"]])
            report = (workflow / "STAGE1_EXTRACTION_REPORT.md").read_text(encoding="utf-8")
            self.assertIn("统一卡 1；降级旧卡 0", report)

    def test_unified_video_card_also_gets_publish_copy_special_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root)
            workflow = root / "10_Knowledge/candidates/account_learning_workflows/sample"
            workflow.mkdir(parents=True)
            (workflow / "PIPELINE_STATE.json").write_text(
                json.dumps({"current_stage": "stage1_parallel_extraction", "account_name": "测试视频账号"}),
                encoding="utf-8",
            )
            inventory = root / "inventory.jsonl"
            inventory.write_text(json.dumps({"source_id": "v1"}) + "\n", encoding="utf-8")
            card = root / "cards/directions/剧情/cards/v1.md"
            card.parent.mkdir(parents=True)
            card.write_text(
                "# 视频深度学习卡：v1\n\n"
                "学习卡契约：unified_three_layer_v2\nsource_id：v1\n主方向：剧情\n标题：看似答应，结果反转\n"
                "## 1. 多维分类与商业隔离\n\n- 内容形态：剧情段子\n"
                "## 2. 发布内容层学习\n\n- 标题：看似答应，结果反转\n- 标题机制：先给矛盾承诺。\n"
                "- 正文或文案：先交代约定，再延迟揭示反转。\n- 话题或标签：剧情、反转。\n"
                "- 协同判断：标题承诺冲突，正文兑现过程，话题限定内容类型。\n",
                encoding="utf-8",
            )

            result = extract_stage1_candidates(
                root,
                workflow_id="sample",
                card_root=Path("cards"),
                inventory_path=Path("inventory.jsonl"),
                apply=True,
            )

            self.assertEqual(result["publish_copy_completed_count"], 1)
            expression = read_jsonl(workflow / "candidates/expression.jsonl")[0]
            self.assertEqual(expression["publish_copy_observation"]["publish_layer_status"], "observed")
            self.assertEqual(expression["publish_copy_observation"]["source_facets"]["body"]["status"], "observed_raw")
            structures = read_jsonl(workflow / "candidates/structures.jsonl")[0]
            self.assertNotIn("image_text_visual_observation", structures)
            study = json.loads((workflow / "PUBLISH_COPY_SPECIAL_STUDY.json").read_text(encoding="utf-8"))
            self.assertEqual(study["completed_source_count"], 1)
            self.assertEqual(study["deferred_source_count"], 0)


if __name__ == "__main__":
    unittest.main()
