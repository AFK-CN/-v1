import json
import tempfile
import unittest
from pathlib import Path

from tools.jianghushuo_learning_index import write_learning_index


class JianghushuoLearningIndexTests(unittest.TestCase):
    def test_write_learning_index_links_scope_cards_and_direction_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scope = root / "10_Knowledge/candidates/account_assets/content_rough_scan/jianghushuo/deep_learning_scope.json"
            scope.parent.mkdir(parents=True)
            scope.write_text(
                json.dumps(
                    {
                        "profile_id": "jianghushuo",
                        "items": [
                            {
                                "source_id": "1",
                                "primary_direction": "赚钱",
                                "source_url": "https://example.com/1",
                                "title": "普通人赚钱",
                                "learning_status": "confirmed_learned",
                            },
                            {
                                "source_id": "2",
                                "primary_direction": "创业",
                                "source_url": "https://example.com/2",
                                "title": "低成本创业",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            money_dir = root / "10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/赚钱"
            cards_dir = money_dir / "cards"
            cards_dir.mkdir(parents=True)
            (money_dir / "方向方法论总结.md").write_text("# 赚钱方向方法论总结\n", encoding="utf-8")
            (money_dir / "粗扫内容和选题.md").write_text("# stale rough scan\n", encoding="utf-8")
            (cards_dir / "01_1_普通人赚钱.md").write_text(
                "\n".join(
                    [
                        "# 视频深度学习卡：普通人赚钱",
                        "",
                        "source_id: 1",
                        "原视频链接：https://example.com/1",
                        "账号：姜胡说",
                        "平台：抖音",
                        "主方向：赚钱",
                        "状态：confirmed_learned",
                    ]
                ),
                encoding="utf-8",
            )
            insights = root / "10_Knowledge/candidates/account_assets/content_rough_scan/jianghushuo/directions/赚钱/rough_scan_insights.json"
            insights.parent.mkdir(parents=True)
            (insights.parent / "粗扫内容和选题.md").write_text("# canonical rough scan\n", encoding="utf-8")
            insights.write_text(
                json.dumps({"topic_clusters": [{"topic": "赚钱"}], "candidate_deep_learning": [], "needs_video_review": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = write_learning_index(root)
            index = json.loads((root / result["json"]).read_text(encoding="utf-8"))
            markdown = (root / result["markdown"]).read_text(encoding="utf-8")
            synced_rough_scan = (money_dir / "粗扫内容和选题.md").read_text(encoding="utf-8")
            synced_insights_path = money_dir / "rough_scan_insights.json"
            synced_insights = json.loads(synced_insights_path.read_text(encoding="utf-8")) if synced_insights_path.exists() else {}

        self.assertEqual(index["scope_count"], 2)
        self.assertEqual(index["unique_source_id_count"], 2)
        self.assertIn("10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/赚钱/cards/01_1_普通人赚钱.md", markdown)
        self.assertIn("## AI 读取顺序", markdown)
        self.assertEqual(synced_rough_scan, "# canonical rough scan\n")
        self.assertEqual(synced_insights["topic_clusters"], [{"topic": "赚钱"}])


if __name__ == "__main__":
    unittest.main()
