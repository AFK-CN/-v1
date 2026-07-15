from __future__ import annotations

import unittest

from tools.jianghushuo_stage2 import classify_source
from tools.jianghushuo_v2_audit import jaccard


class JianghushuoStage2AndAuditTests(unittest.TestCase):
    def test_stage2_uses_mechanism_evidence_not_generic_direction_words(self) -> None:
        candidates = [
            {"type": "structures", "title": "结构观察", "summary": "项目驱动学习，先做最小行动，再在实践中试错。"},
            {"type": "topics", "title": "选题观察", "summary": "用真实任务验证学习结果。"},
        ]
        self.assertEqual(classify_source(candidates), "project-driven-validation")

    def test_stage2_sends_ambiguous_observation_to_evidence_gate(self) -> None:
        candidates = [
            {"type": "structures", "title": "结构观察", "summary": "这是一个一般性的内容主题。"},
            {"type": "topics", "title": "选题观察", "summary": "目前没有稳定因果机制。"},
        ]
        self.assertEqual(classify_source(candidates), "unresolved-evidence-gate")

    def test_similarity_audit_separates_distinct_content(self) -> None:
        self.assertEqual(jaccard("完全不同的学习项目机制", "毫无关系的财富规则分析"), 0.0)
        self.assertGreater(jaccard("项目驱动学习验证", "项目驱动学习验证"), 0.99)


if __name__ == "__main__":
    unittest.main()
