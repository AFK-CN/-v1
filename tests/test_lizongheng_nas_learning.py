import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.account_learning_card import CONTRACT_ID, validate_unified_text
from tools.lizongheng_nas_learning import (
    ACCOUNT_ID,
    ACCOUNT_NAME,
    CURRENT_NAS_ROOT,
    audit_card,
    card_markdown,
    resolve_evidence_path,
    update_cumulative_status,
)


def evidence(**overrides):
    value = {
        "source_id": "1",
        "account_id": ACCOUNT_ID,
        "account_name": ACCOUNT_NAME,
        "transcript": "老板让我加班，我说没问题。后来员工反过来收购了公司，这是完整的剧情证据。",
        "transcript_chars": 100,
        "video_available": True,
        "frames_available": True,
        "title": "员工比老板有钱",
        "desc": "",
    }
    value.update(overrides)
    return value


def card(**overrides):
    value = {
        "source_id": "1",
        "content_form": "剧情段子",
        "relationship_axis": "职场/商务",
        "scene_axis": "职场/面试/会议",
        "comedy_engine": "身份/地位反转",
        "commercial_axis": "正常内容",
        "learning_value_axis": "高价值结构样本",
        "core_direction_eligible": True,
        "synopsis": "员工以有钱人的身份上班，最终反过来决定老板能否留任。",
        "conflict": "员工身份与传统雇佣关系发生冲突，形成持续反差。",
        "turning_point": "公司亏损时员工直接出资，权力关系彻底反转。",
        "reusable_topic": "当员工比老板更有钱，公司权力关系会怎样变化。",
        "copy_learning": "标题直接抛出反常识设定，用问句制造点击动机。",
        "topic_learning": "账号标签之外补充职场、老板员工和身份反转话题。",
        "commercial_reason": "逐字稿没有品牌、商品卖点或购买行动，剧情独立闭环。",
        "classification_reason": "人物是老板与员工，冲突和反转都发生在公司场景。",
        "evidence_quotes": ["老板让我加班", "员工反过来收购了公司"],
    }
    value.update(overrides)
    return value


class AuditCardTest(unittest.TestCase):
    def test_completed_batches_do_not_auto_authorize_formal_ingest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_dir = root / "output" / "batch_01"
            batch_dir.mkdir(parents=True)
            (batch_dir / "audit.json").write_text(
                json.dumps({"batch_id": "batch_01", "batch_gate": "pass"}),
                encoding="utf-8",
            )
            (batch_dir / "structured_cards.jsonl").write_text(
                json.dumps(card()) + "\n",
                encoding="utf-8",
            )

            status = update_cumulative_status(root, Path("output"), total_items=1, batch_size=10)

            self.assertEqual(status["completed_items"], 1)
            self.assertFalse(status["formal_ingest_allowed"])

    def test_legacy_nas_path_remaps_to_current_mount(self):
        legacy = Path("/Volumes/AFK/zhishikushuju/dy/accounts/example/source.json")
        expected = CURRENT_NAS_ROOT / "accounts/example/source.json"

        with patch.object(Path, "exists", lambda path: path == expected):
            self.assertEqual(resolve_evidence_path(legacy), expected)

    def test_clean_card_passes(self):
        self.assertEqual(audit_card(card(), evidence()), [])

    def test_ad_heavy_cannot_enter_core_direction(self):
        errors = audit_card(
            card(commercial_axis="广告强绑定/广告主导", learning_value_axis="广告隔离样本"),
            evidence(title="亚朵深睡被"),
        )
        self.assertIn("ad_heavy_entered_core_direction", errors)

    def test_integrated_ad_cannot_enter_core_direction(self):
        errors = audit_card(
            card(commercial_axis="广告植入但剧情完整", learning_value_axis="广告隔离样本"),
            evidence(),
        )
        self.assertIn("commercial_entered_core_direction", errors)

    def test_commercial_reason_cannot_claim_core_direction(self):
        errors = audit_card(
            card(
                commercial_axis="广告植入但剧情完整",
                learning_value_axis="广告隔离样本",
                core_direction_eligible=False,
                classification_reason="剧情完整，因此保留核心方向并标记商业。",
            ),
            evidence(),
        )
        self.assertIn("commercial_core_language_conflict", errors)

    def test_brand_signal_cannot_be_marked_normal(self):
        self.assertIn("brand_signal_marked_normal", audit_card(card(), evidence(title="宁德时代麒麟电池")))

    def test_quote_must_be_supported_by_transcript(self):
        self.assertIn(
            "unsupported_evidence_quote",
            audit_card(card(evidence_quotes=["并不存在", "老板让我加班"]), evidence()),
        )

    def test_platform_event_can_keep_persona_learning_value(self):
        event_card = card(
            commercial_axis="平台活动/挑战赛",
            learning_value_axis="高价值人设/表演样本",
            core_direction_eligible=False,
        )
        self.assertEqual(audit_card(event_card, evidence()), [])

    def test_short_transcript_requires_visual_review(self):
        errors = audit_card(card(), evidence(transcript_chars=20))
        self.assertIn("short_transcript_without_visual_review", errors)

    def test_short_transcript_passes_with_visual_review(self):
        reviewed = card(
            visual_review={
                "performed": True,
                "frames_inspected": 3,
                "finding": "三帧确认人物关系、场景和最终动作反转均一致。",
            }
        )
        self.assertEqual(audit_card(reviewed, evidence(transcript_chars=20)), [])

    def test_visual_only_requires_five_frames_and_three_evidence_points(self):
        reviewed = card(
            evidence_quotes=[],
            visual_review={
                "performed": True,
                "frames_inspected": 5,
                "finding": "五帧确认人物、场景、动作推进和结尾状态。",
                "visual_evidence": ["首帧人物关系", "中段动作变化", "末帧结局字幕"],
            },
        )
        self.assertEqual(audit_card(reviewed, evidence(transcript="", transcript_chars=0)), [])

    def test_generated_card_uses_unified_three_layer_contract(self):
        structured = {**card(), "batch_id": "batch_01"}
        source = evidence(
            source_url="https://example.com/video/1",
            transcript_sha256="abc123",
            frames_available=True,
        )

        text = card_markdown(structured, source)
        validation = validate_unified_text(text)

        self.assertTrue(validation.valid, validation.errors)
        self.assertIn(f"学习卡契约：{CONTRACT_ID}", text)
        self.assertIn("状态：candidate_learned", text)
        self.assertIn("可调用：false", text)
        for section in (
            "核心观点",
            "内容结构",
            "金句与表达素材",
            "可复用模板",
            "证据边界",
            "多维分类与商业隔离",
            "方法候选与可复用方法论",
        ):
            self.assertIn(section, text)

    def test_commentary_card_uses_commentary_structure(self):
        structured = {**card(content_form="口播/独白"), "batch_id": "batch_01"}
        source = evidence(
            source_url="https://example.com/video/1",
            transcript_sha256="abc123",
            frames_available=True,
        )
        text = card_markdown(structured, source)
        validation = validate_unified_text(text)
        self.assertTrue(validation.valid, validation.errors)
        self.assertIn("- 黄金3秒：", text)
        self.assertIn("- 观点提出：", text)


if __name__ == "__main__":
    unittest.main()
