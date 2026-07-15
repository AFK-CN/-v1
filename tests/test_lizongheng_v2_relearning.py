import json
import tempfile
import unittest
from pathlib import Path

from tools import lizongheng_v2_relearning as relearning


def card(source_id: str = "1", commercial_axis: str = "正常内容") -> dict:
    return {
        "source_id": source_id,
        "batch_id": "batch_01",
        "content_form": "剧情段子",
        "relationship_axis": "职场/商务",
        "scene_axis": "职场/面试/会议",
        "comedy_engine": "身份/地位反转",
        "commercial_axis": commercial_axis,
        "core_direction_eligible": True,
        "learning_value_axis": "高价值结构样本",
        "classification_reason": "老板员工关系明确，冲突发生在公司并形成权力反转。",
        "commercial_reason": "没有品牌卖点、购买行动或平台活动，剧情能够独立成立。",
        "synopsis": "员工进入公司后发现所有同事都比老板有钱，并逐步接管工资、融资和雇佣决定。",
        "conflict": "老板掌握公司的传统权力与员工拥有绝对财力发生直接冲突。",
        "turning_point": "公司亏损时员工出资并反过来决定老板是否可以继续留任。",
        "reusable_topic": "当组织中的弱势角色突然掌握关键资源，原有权力关系会怎样改变。",
        "copy_learning": "标题先抛出反常识设定，不提前泄露最终权力反转。",
        "topic_learning": "职场、老板员工和权力反转是内容语义；不存在显式商业话题。",
        "evidence_quotes": ["老板让我加班", "员工反过来收购了公司"],
        "source": {
            "title": "员工比老板有钱 #测试",
            "desc": "员工比老板有钱 #测试",
            "source_url": "https://example.com/1",
            "transcript_path": "/tmp/transcript.txt",
            "video_path": "/tmp/source.mp4",
            "frames_path": "/tmp/frames.json",
        },
    }


def assessment(source_id: str = "1") -> dict:
    lenses = {}
    for lens in relearning.LENSES:
        lenses[lens] = {
            "decision": "supports_candidate",
            "finding": f"这是{lens}视角下独立提取的具体判断，不能由旧分类直接替代。",
            "evidence_points": ["逐字稿和旧卡共同支持这个具体判断"],
            "candidate_ids": [f"b01-{lens}"],
        }
    return {
        "source_id": source_id,
        "schema_version": "2.0",
        "reviewer_mode": "independent_five_lens",
        "legacy_card_used_as_evidence": True,
        "professional_lenses": lenses,
    }


def candidates(source_id: str = "1") -> dict[str, list[dict]]:
    return {
        lens: [
            {
                "id": f"b01-{lens}",
                "title": f"{lens}视角的候选方法标题",
                "type": lens,
                "source_refs": [source_id],
                "summary": f"从{lens}视角提取一条可供后续三重验证的候选规律。",
                "tags": [lens],
                "callable": False,
            }
        ]
        for lens in relearning.LENSES
    }


def quote_review(source_id: str = "1") -> dict:
    return {
        "source_id": source_id,
        "review_mode": "asr_quality_screened",
        "retained_quotes": ["员工反过来收购了公司"],
        "rejected_quotes": [{"text": "老板让我加班", "reason": "疑似ASR或语义不完整，不作为金句保留。"}],
    }


class LizonghengV2RelearningTest(unittest.TestCase):
    def test_complete_five_lens_assessment_passes(self):
        self.assertEqual(relearning.audit_assessment(assessment(), card()), [])

    def test_missing_lens_is_rejected(self):
        value = assessment()
        del value["professional_lenses"]["expression"]
        errors = relearning.audit_assessment(value, card())
        self.assertIn("five_lens_scope_mismatch", errors)
        self.assertIn("expression:missing_assessment", errors)

    def test_commercial_content_requires_counterexample_isolation(self):
        value = assessment()
        errors = relearning.audit_assessment(value, card(commercial_axis="广告强绑定/广告主导"))
        self.assertIn("commercial_content_not_isolated_in_counterexamples", errors)
        value["professional_lenses"]["counterexamples"]["decision"] = "boundary_evidence"
        self.assertEqual(relearning.audit_assessment(value, card(commercial_axis="广告强绑定/广告主导")), [])

    def test_candidate_links_must_be_bidirectional(self):
        values = candidates()
        errors, _ = relearning.audit_candidates([card()], [assessment()], values)
        self.assertEqual(errors, [])
        values["topics"][0]["source_refs"] = []
        errors, _ = relearning.audit_candidates([card()], [assessment()], values)
        self.assertIn("b01-topics:missing_source_refs", errors)
        self.assertIn("1:topics:candidate_missing_backref:b01-topics", errors)

    def test_candidate_must_explicitly_declare_noncallable(self):
        values = candidates()
        del values["structures"][0]["callable"]
        errors, _ = relearning.audit_candidates([card()], [assessment()], values)
        self.assertIn("b01-structures:candidate_must_not_be_callable", errors)

    def test_every_asr_quote_must_be_retained_or_rejected(self):
        self.assertEqual(relearning.audit_quote_review(quote_review(), card()), [])
        value = quote_review()
        value["rejected_quotes"] = []
        self.assertIn("quote_review_scope_mismatch", relearning.audit_quote_review(value, card()))

    def test_rendered_unified_card_passes_new_contract_and_depth_gate(self):
        values = candidates()
        _, index = relearning.audit_candidates([card()], [assessment()], values)
        text = relearning.render_unified_card(card(), assessment(), index, quote_review())
        self.assertEqual(relearning.audit_unified_card_text(text, "1"), [])
        self.assertIn("学习卡契约：unified_three_layer_v2", text)
        self.assertIn(f"学习方法版本：{relearning.METHOD_REVISION}", text)
        self.assertIn("可调用：false", text)
        self.assertIn("当前不可调用", text)
        self.assertNotIn("可调用本候选", text)
        self.assertNotIn("可以跨场景调用", text)
        self.assertIn("### E - 初步执行步骤", text)
        self.assertIn("本小节执行的是候选验证，不是内容生成", text)
        self.assertIn("状态：candidate_learned", text)
        self.assertNotIn("状态：review_passed", text)
        self.assertIn("### R - 原始证据", text)
        self.assertIn("原文金句", text)
        self.assertIn("- 触发机制：", text)
        self.assertIn("- 适用关系：", text)
        self.assertIn("- 可迁移场景：", text)
        self.assertIn("- 不触发条件：", text)
        self.assertNotIn(f"当新任务需要处理“{card()['reusable_topic']}”", text)

    def test_noncallable_card_rejects_contradictory_call_language(self):
        values = candidates()
        _, index = relearning.audit_candidates([card()], [assessment()], values)
        text = relearning.render_unified_card(card(), assessment(), index, quote_review())
        text += "\n可调用本候选。\n"
        errors = relearning.audit_unified_card_text(text, "1")
        self.assertIn("single_card_callability_contradiction:可调用本候选", errors)

    def test_normal_non_core_card_is_not_described_as_core_evidence(self):
        value = card()
        value["core_direction_eligible"] = False
        values = candidates()
        _, index = relearning.audit_candidates([value], [assessment()], values)
        text = relearning.render_unified_card(value, assessment(), index, quote_review())
        self.assertEqual(relearning.audit_unified_card_text(text, "1"), [])
        self.assertIn("不进入自然选题与核心方向频次", text)
        self.assertIn("边界证据（可支持定位）", text)
        self.assertNotIn("允许作为核心方向候选证据", text)

    def test_empty_quote_review_does_not_claim_asr_is_clean(self):
        value = card()
        value["evidence_quotes"] = []
        review = {
            "source_id": "1",
            "review_mode": "asr_quality_screened",
            "retained_quotes": [],
            "rejected_quotes": [],
        }
        values = candidates()
        _, index = relearning.audit_candidates([value], [assessment()], values)
        text = relearning.render_unified_card(value, assessment(), index, review)
        self.assertEqual(relearning.audit_unified_card_text(text, "1"), [])
        self.assertIn("短音轨、歌词或低信息ASR不作为事实证据", text)
        self.assertNotIn("未发现需要退回的明显ASR错字", text)
        self.assertNotIn("保留句仍须", text)

    def test_commentary_card_uses_commentary_structure_profile(self):
        value = card()
        value["content_form"] = "口播/独白"
        values = candidates()
        _, index = relearning.audit_candidates([value], [assessment()], values)
        text = relearning.render_unified_card(value, assessment(), index, quote_review())
        self.assertEqual(relearning.audit_unified_card_text(text, "1"), [])
        self.assertIn("- 黄金3秒：", text)
        self.assertIn("- 观点提出：", text)
        self.assertIn("- 证据或案例：", text)

    def test_musical_card_uses_story_structure_profile(self):
        value = card()
        value["content_form"] = "唱演/音乐化表达"
        values = candidates()
        _, index = relearning.audit_candidates([value], [assessment()], values)
        text = relearning.render_unified_card(value, assessment(), index, quote_review())
        self.assertEqual(relearning.audit_unified_card_text(text, "1"), [])
        self.assertIn("- 开头设定：", text)
        self.assertIn("- 转折或笑点：", text)

    def test_same_contract_without_latest_method_revision_requires_relearning(self):
        audit = {
            "batch_gate": "pass",
            "unified_card_contract": "unified_three_layer_v2",
            "unified_card_passed_count": 10,
            "card_contract_version": relearning.CARD_CONTRACT_VERSION,
        }
        self.assertFalse(relearning.is_current_audit(audit))
        audit["learning_method_revision"] = relearning.METHOD_REVISION
        self.assertTrue(relearning.is_current_audit(audit))

    def test_legacy_batch_without_v2_audit_requires_relearning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / relearning.LEGACY_ROOT / "batch_01" / "audit.json"
            audit_path.parent.mkdir(parents=True)
            audit_path.write_text(
                json.dumps({"batch_id": "batch_01", "batch_gate": "pass", "expected_count": 10}),
                encoding="utf-8",
            )
            report = relearning.audit_legacy(root)
            self.assertEqual(report["relearn_required_batches"], ["batch_01"])
            self.assertFalse(report["formal_ingest_allowed"])

    def test_old_v2_audit_without_unified_cards_is_not_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / relearning.LEGACY_ROOT / "batch_01" / "audit.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps({"batch_id": "batch_01", "batch_gate": "pass", "expected_count": 10}),
                encoding="utf-8",
            )
            old_v2 = root / relearning.OUTPUT_ROOT / "batch_01" / "audit.json"
            old_v2.parent.mkdir(parents=True)
            old_v2.write_text(json.dumps({"batch_id": "batch_01", "batch_gate": "pass"}), encoding="utf-8")
            report = relearning.audit_legacy(root)
            self.assertEqual(report["relearn_required_batches"], ["batch_01"])

    def test_review_packet_exposes_all_five_lenses_and_source_ids(self):
        value = assessment()
        audit = {
            "batch_gate": "pass",
            "passed_card_count": 1,
            "batch_errors": [],
            "learning_method_revision": relearning.METHOD_REVISION,
        }
        text = relearning.render_review_packet(
            "batch_01",
            [{**card(), "source": {"title": "测试视频"}, "content_form": "剧情段子", "relationship_axis": "职场/商务"}],
            [value],
            candidates(),
            audit,
        )
        self.assertIn("source_id：`1`", text)
        self.assertIn("用户审核：`pending`", text)
        for lens in relearning.LENSES:
            self.assertIn(f"#### {lens}", text)
            self.assertIn(f"### {lens}", text)


if __name__ == "__main__":
    unittest.main()
