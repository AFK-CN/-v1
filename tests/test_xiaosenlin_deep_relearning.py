from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.account_learning_card import CONTRACT_ID, validate_card_text
from tools.xiaosenlin_deep_relearning import (
    METHOD_REVISION,
    merge_units,
    primary_mechanism,
    prune_stale_cards,
    quality_quote_candidates,
)
from tools.xiaosenlin_v22_learning import blind_decision, classify_track, commercial_entry


class XiaosenlinDeepRelearningTests(unittest.TestCase):
    def test_merge_units_preserves_content_order(self) -> None:
        values = ["先判断自己的状态", "再选择对应步骤", "最后根据反馈决定是否继续"]
        units = merge_units(values, minimum=12, maximum=30)
        self.assertTrue(units)
        self.assertIn("先判断", units[0])
        self.assertIn("最后", units[-1])

    def test_quote_candidates_are_exact_source_units(self) -> None:
        units = [
            "我先记录自己的皮肤状态再决定今天是否继续使用",
            "如果出现泛红就不要再叠加其他刺激性步骤",
            "这里是一句没有判断的普通内容摘要",
        ]
        quotes = quality_quote_candidates(units)
        self.assertEqual(len(quotes), 2)
        self.assertTrue(all(quote in units for quote in quotes))

    def test_contract_and_method_revision_are_account_independent(self) -> None:
        self.assertEqual(CONTRACT_ID, "unified_three_layer_v2")
        self.assertIn("deep_relearn", METHOD_REVISION)
        self.assertTrue(callable(validate_card_text))

    def test_primary_mechanism_uses_content_causality_not_first_key(self) -> None:
        card = {"mechanism_keys": ["problem_result", "step_sequence", "time_feedback", "list_decision"]}
        key, _ = primary_mechanism(
            card,
            "第一先判断状态，第二再调整步骤，然后观察，如果泛红就停止，最后保湿。",
        )
        self.assertEqual(key, "step_sequence")

    def test_product_packing_list_is_not_mistaken_for_time_feedback(self) -> None:
        card = {
            "title": "护肤博主出行洗漱包大公开",
            "topic_family": "空瓶与产品复盘",
            "mechanism_keys": ["list_decision", "time_feedback"],
        }
        key, _ = primary_mechanism(
            card,
            "出差七天，先公开洗漱包，再就是洁面，还有这个防晒，然后是收纳袋。",
        )
        self.assertEqual(key, "list_decision")

    def test_lifestyle_evidence_gate_does_not_default_to_skincare_method(self) -> None:
        card = {
            "title": "新加坡工作vlog",
            "topic_family": "生活方式与信任",
            "mechanism_keys": ["evidence_gate"],
        }
        key, _ = primary_mechanism(card, "帧000001建立地点，帧000020进入活动，帧000040城市夜景收尾。")
        self.assertEqual(key, "evidence_gate")

    def test_v22_no_ad_product_review_is_natural_but_self_reported(self) -> None:
        track = classify_track(
            {"title": "年度爱用", "commercial_axis": "产品/商业决策内容"},
            "这些都是我用完的，没有广告，按肤质说清楚适用边界。",
        )
        self.assertEqual(track["track"], "natural_product_review")
        self.assertTrue(track["natural_v1_eligible"])
        self.assertEqual(track["ad_disclosure_status"], "explicit_no_ad_self_report")

    def test_v22_discussing_refused_collaboration_is_not_fake_ad(self) -> None:
        track = classify_track(
            {"title": "我长过的痘不会让你再长", "commercial_axis": "产品/商业决策内容"},
            "很多合作我都拒绝了，如果只想恰饭会更容易，但不想让大家花冤枉钱。",
        )
        self.assertEqual(track["track"], "commercial_unknown")
        self.assertFalse(track["natural_v1_eligible"])

    def test_v22_blind_evaluator_understands_negated_mechanism_terms(self) -> None:
        decision, _ = blind_decision(
            {
                "prompt": "只出现护肤和产品词，没有具体问题、目标状态或判断标准。",
            }
        )
        self.assertEqual(decision, "not_trigger")

    def test_v22_visual_only_platform_project_keeps_frame_coordinate(self) -> None:
        record = {"source_id": "visual-only", "title": "工作vlog"}
        evidence = (
            "帧000020为酒店庭院生活段落。\n"
            "帧000030出现品牌活动周年庆典礼物，只记录视觉事实。\n"
            "帧000040回到公共场馆人物挥手。"
        )
        track = classify_track(record, evidence)
        entry = commercial_entry(record, evidence, [], track)
        self.assertEqual(track["track"], "platform_project")
        self.assertEqual(entry["ad_entry"]["coordinate"], "frame_000030")
        self.assertEqual(entry["natural_method_v1_weight"], 0)
        self.assertFalse(entry["callable"])

    def test_relearn_prunes_cards_no_longer_backed_by_complete_evidence(self) -> None:
        with TemporaryDirectory() as temp:
            cards_dir = Path(temp)
            kept = cards_dir / "xhs_kept.md"
            stale = cards_dir / "xhs_stale.md"
            kept.write_text("kept", encoding="utf-8")
            stale.write_text("stale", encoding="utf-8")
            removed = prune_stale_cards(cards_dir, [{"source_id": "kept"}])
            self.assertEqual(removed, ["xhs_stale.md"])
            self.assertTrue(kept.exists())
            self.assertFalse(stale.exists())



if __name__ == "__main__":
    unittest.main()
