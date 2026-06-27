import tempfile
import unittest
from pathlib import Path

from tools.jianghushuo_card_validator import validate_cards


VALID_CARD = """# 视频深度学习卡：样例

source_id: 1
原视频链接:https://example.com/1
账号：姜胡说
平台：抖音
主方向：赚钱
状态：confirmed_learned

## 1. 为什么值得学习
内容

## 2. 核心观点
内容

## 3. 内容结构
- 收尾/互动引导：未明确

## 4. 表达素材与金句提炼
内容

## 5. 视频层学习
内容

## 6. 可复用案例
内容

## 7. 可复用方法论
内容

## 8. 可复用模板
内容

## 9. 证据缺口/后续问题
内容

## 10. 入库判断
内容
"""


class JianghushuoCardValidatorTests(unittest.TestCase):
    def test_validate_cards_accepts_current_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/赚钱/cards/01_1.md"
            card.parent.mkdir(parents=True)
            card.write_text(VALID_CARD, encoding="utf-8")

            result = validate_cards(root)

        self.assertTrue(result["valid"])
        self.assertEqual(result["card_count"], 1)

    def test_validate_cards_rejects_old_ending_and_extension_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/赚钱/cards/01_1.md"
            card.parent.mkdir(parents=True)
            card.write_text(VALID_CARD.replace("收尾/互动引导", "结尾金句/互动引导") + "\n可延展选题\n", encoding="utf-8")

            result = validate_cards(root)

        self.assertFalse(result["valid"])
        self.assertTrue(any("old ending field" in error for error in result["errors"]))
        self.assertTrue(any("可延展选题" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
