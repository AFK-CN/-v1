from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.account_learning_v26_upgrade import (
    _authoritative_accounting,
    _is_image_text,
    _upgrade_clusters,
    _upgrade_publish_copy_study,
)


class AccountLearningV26UpgradeTest(unittest.TestCase):
    def test_video_card_is_not_misclassified_by_generic_image_text_heading(self) -> None:
        text = """## 3. 多维分类与商业隔离

- 内容形态：知识/经验口播

## 7. 视频/图文表现层学习

- 媒体类型：视频。
"""

        self.assertEqual(_is_image_text(text), (False, "知识/经验口播"))

    def test_image_text_card_is_detected_from_content_form(self) -> None:
        text = """## 3. 多维分类与商业隔离

- 内容形态：故事型图文（生活叙事）

## 7. 视频/图文表现层学习

- 媒体类型：图文发布文案。
"""

        self.assertEqual(_is_image_text(text), (True, "故事型图文（生活叙事）"))

    def test_cluster_backfill_uses_existing_candidate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cluster = {
                "id": "m1",
                "title": "方法一",
                "cluster_type": "method_candidate",
                "core_mechanism": "先建立限制，再用动作和结果完成反转",
                "candidate_ids": ["s1", "e1", "c1"],
                "source_refs": ["a", "b", "c"],
                "lens_roles": {
                    "method_core": ["s1"],
                    "support": ["e1"],
                    "boundary": ["c1"],
                    "evidence_gate": [],
                },
            }
            (base / "candidate_clusters.jsonl").write_text(
                json.dumps(cluster, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            candidates = {
                "s1": {"id": "s1", "type": "structures", "summary": "限制、动作、结果依次推进。"},
                "e1": {"id": "e1", "type": "expression", "summary": "口语表达承接动作。"},
                "c1": {"id": "c1", "type": "counterexamples", "summary": "只有场景词时不得触发。"},
            }

            result = _upgrade_clusters(base, candidates, apply=True)
            updated = json.loads((base / "candidate_clusters.jsonl").read_text(encoding="utf-8"))

            self.assertTrue(result["stage2_schema_enabled"])
            self.assertEqual(updated["mechanism_kind"], "composite")
            self.assertEqual(updated["production_analysis"]["boundaries"], ["只有场景词时不得触发。"])

    def test_authoritative_accounting_preserves_blocked_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "FINAL_COMPLETION_AUDIT.json").write_text(
                json.dumps({"source_scope": {"planned": 12, "evidence_ready": 10, "blocked": 2}}),
                encoding="utf-8",
            )

            result = _authoritative_accounting(
                base,
                {"status": "completed"},
                {},
                {"source_total": 10, "unified_source_count": 10},
                3,
            )

            self.assertEqual(result["source_total"], 12)
            self.assertEqual(result["deep_card_count"], 10)
            self.assertEqual(result["deferred_evidence_count"], 2)

    def test_completed_legacy_workflow_is_compatible_not_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _authoritative_accounting(
                Path(tmp),
                {"status": "completed"},
                {},
                {"source_total": 20, "unified_source_count": 0},
                2,
            )

            self.assertEqual(result["deep_card_count"], 20)
            self.assertEqual(result["deferred_evidence_count"], 0)

    def test_publish_copy_study_discovers_profile_cards_and_links_grouped_expression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "10_Knowledge/candidates/account_learning_workflows/sample"
            (base / "candidates").mkdir(parents=True)
            expression = {
                "id": "legacy-expression-group",
                "type": "expression",
                "source_refs": ["s1", "s2"],
                "title": "分组表达观察",
                "summary": "历史分组候选",
                "tags": ["expression"],
            }
            (base / "candidates/expression.jsonl").write_text(
                json.dumps(expression, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            card_root = root / "10_Knowledge/candidates/account_assets/nas_video_learning/profile-a/batches/batch_01/cards"
            card_root.mkdir(parents=True)
            for source_id, schema in (("s1", "学习卡契约：unified_three_layer_v2\n"), ("s2", "")):
                (card_root / f"{source_id}.md").write_text(
                    f"# 学习卡：{source_id}\n\n{schema}source_id：{source_id}\n标题：标题 {source_id}\n"
                    "## 发布内容层学习\n\n"
                    f"- 标题：标题 {source_id}\n- 文案学习：正文机制 {source_id}\n"
                    "- 话题学习：无显式话题。\n- 协同判断：标题负责承诺，正文负责兑现。\n",
                    encoding="utf-8",
                )
            config = {
                "stage1_deep_observation": {
                    "publish_copy_schema_id": "publish_copy_observation_v1",
                    "publish_copy_study_schema_id": "publish_copy_special_study_v1",
                    "candidate_status": "single_card_observation",
                    "publish_copy_dimensions": ["title_promise_and_information_gap", "body_information_sequence"],
                }
            }
            state = {
                "workflow_id": "sample",
                "account_name": "测试账号",
                "profile_id": "profile-a",
            }

            result = _upgrade_publish_copy_study(root, base, config, state, apply=True)
            updated = json.loads((base / "candidates/expression.jsonl").read_text(encoding="utf-8"))

            self.assertEqual(result["completed_source_count"], 2)
            self.assertEqual(result["unified_card_count"], 1)
            self.assertEqual(result["legacy_publish_evidence_count"], 1)
            self.assertEqual(
                updated["publish_copy_observation_refs"],
                ["publish-copy-s1", "publish-copy-s2"],
            )
            self.assertNotIn("publish_copy_observation", updated)


if __name__ == "__main__":
    unittest.main()
