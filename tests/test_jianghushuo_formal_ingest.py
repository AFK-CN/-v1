from __future__ import annotations

import unittest

from tools.jianghushuo_formal_ingest import formalize_card
from tools.jianghushuo_formal_ingest import formalize_method_md
from tools.jianghushuo_formal_ingest import REQUIRED_TOP_LEVEL
from tools.jianghushuo_formal_ingest import top_level_files


class JianghushuoFormalIngestTest(unittest.TestCase):
    def test_formalize_card_keeps_candidate_method_boundary(self) -> None:
        source = """# 姜胡说 2.2 升级学习卡：测试

学习卡契约：unified_three_layer_v2
source_id：1
主方向：个人成长
状态：candidate_learned

## 1. 证据边界

证据。

## 10. 方法候选与可复用方法论

候选。

## 12. 证据缺口与候选判断

边界。
"""
        result = formalize_card(source, "2026-07-14T23:00:00+08:00")
        self.assertIn("状态：formal_evidence_card", result)
        self.assertIn("方法调用：false", result)
        self.assertIn("## 10. 方法候选与可复用方法论", result)
        self.assertIn("单卡方法候选不直接调用", result)
        self.assertNotIn("状态：candidate_learned", result)

    def test_formalize_method_uses_approved_callable(self) -> None:
        source = """# 方法

状态：`verified_candidate`；调用：`false`；账号范围：`姜胡说`。

## R - 原始证据
"""
        result = formalize_method_md(source, "2026-07-14T23:00:00+08:00")
        self.assertIn("状态：`approved_callable`", result)
        self.assertIn("调用：`true`", result)
        self.assertIn("用户明确批准正式入库", result)

    def test_top_level_package_contains_every_required_file(self) -> None:
        method_index = {
            "methods": [{"id": "m1", "title": "方法一"}],
            "relations": [],
        }
        package = top_level_files(method_index, {"个人成长": 1}, 1, "2026-07-14T23:00:00+08:00")
        self.assertTrue(REQUIRED_TOP_LEVEL - {"METHOD_INDEX.json", "FORMAL_CARD_INDEX.jsonl", "FORMAL_INGEST_RECEIPT.json", "deep_learning_plan.json"} <= set(package))
        self.assertIn("正式入库总验收报告.md", package)

if __name__ == "__main__":
    unittest.main()
