from __future__ import annotations

import unittest

from tools.lizongheng_formal_ingest import formalize_ad_card
from tools.lizongheng_formal_ingest import formalize_method_md
from tools.lizongheng_formal_ingest import formalize_natural_card
from tools.lizongheng_formal_ingest import formalize_platform_card


class LiZonghengFormalIngestTests(unittest.TestCase):
    def test_natural_card_removes_candidate_method_tail(self) -> None:
        source = "# card\n\n状态：batch_review_passed\n\n## 9. 可复用选题\nkeep\n\n## 10. 方法候选与可复用方法论\ndrop\n"
        result = formalize_natural_card(source)
        self.assertIn("状态：formal_ingested", result)
        self.assertIn("keep", result)
        self.assertNotIn("方法候选", result)
        self.assertIn("正式入库状态", result)

    def test_commercial_cards_replace_candidate_boundary(self) -> None:
        source = "# card\n\n- 本卡保持 `callable=false`、`formal_write=false`。\n"
        for transform in (formalize_ad_card, formalize_platform_card):
            result = transform(source)
            self.assertNotIn("callable=false", result)
            self.assertIn("正式账号中心", result)

    def test_method_becomes_formal_and_callable(self) -> None:
        source = "状态：`verified_candidate`；调用：`false`；账号范围：`李宗恒`；角色：`primary_conflict`。\n"
        result = formalize_method_md(source)
        self.assertIn("状态：`formal_verified`", result)
        self.assertIn("调用：`true`", result)
        self.assertNotIn("verified_candidate", result)


if __name__ == "__main__":
    unittest.main()
