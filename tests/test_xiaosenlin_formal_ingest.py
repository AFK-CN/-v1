from __future__ import annotations

import unittest

from tools.xiaosenlin_formal_ingest import formalize_card, formalize_method_md


class XiaosenlinFormalIngestTests(unittest.TestCase):
    def test_formal_card_is_evidence_but_single_card_method_stays_noncallable(self) -> None:
        source = """# card

状态：candidate_learned

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。关联机制：`m1` / 方法。
> 可调用：false。单卡通过不代表方法可调用。

当前不可调用。三重验证全部通过后再另建方法卡。

- 卡片判断：证据完整，保留为统一十二段深学候选卡；不直接写入正式账号中心。
- 跨卡状态：支持候选，方法仍不可调用。
"""
        result = formalize_card(source, "2026-07-14T00:00:00+08:00")
        self.assertIn("状态：formal_ingested", result)
        self.assertIn("单卡方法调用：false", result)
        self.assertIn("正式证据卡进入账号中心", result)
        self.assertNotIn("状态：candidate_learned", result)

    def test_formal_method_becomes_approved_callable(self) -> None:
        source = "状态：verified_candidate；可调用：false；Skill：v2.2。\n更换场景后才进入候选调用。\n"
        result = formalize_method_md(source, "2026-07-14T00:00:00+08:00")
        self.assertIn("状态：approved_callable", result)
        self.assertIn("可调用：true", result)
        self.assertIn("进入正式调用", result)


if __name__ == "__main__":
    unittest.main()
