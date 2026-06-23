import json
import tempfile
import unittest
from pathlib import Path

from tools.video_learning_account_ingest import AccountIngestConfig, ingest_directions


class VideoLearningAccountIngestTests(unittest.TestCase):
    def test_ingest_directions_uses_profile_config_not_hardcoded_account_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AccountIngestConfig.for_profile(
                profile_id="demo_profile",
                account_id="demo_account",
                account_name="测试账号",
                formal_account_dir=Path("06_Sub_KB/测试账号中心/测试账号"),
            )
            audit_items = []
            for index, direction in enumerate(("赚钱", "表达"), start=1):
                source_id = str(9000 + index)
                learned = root / config.learned_base / direction
                cards = learned / "cards"
                cards.mkdir(parents=True)
                (learned / "方向方法论总结.md").write_text(
                    f"# {direction}方向方法论总结\n\n学习状态：complete_candidate（待审核）\n",
                    encoding="utf-8",
                )
                (learned / "粗扫内容和选题.md").write_text(f"# {direction}粗扫\n", encoding="utf-8")
                (cards / f"01_{source_id}_测试卡.md").write_text(
                    "\n".join(
                        [
                            f"# 视频深度学习卡：{direction}测试卡",
                            "",
                            f"source_id: {source_id}",
                            f"原视频链接：https://www.douyin.com/video/{source_id}",
                            "账号：测试账号",
                            "平台：抖音",
                            f"主方向：{direction}",
                            "辅方向：无",
                            "学习批次：test",
                            "状态：confirmed_learned",
                            "",
                            "## 10. 入库判断",
                            "",
                            "- 待验证：保留为候选学习卡；审核后再进入正式知识库。",
                        ]
                    ),
                    encoding="utf-8",
                )
                artifact = root / config.artifacts_dir / f"douyin_{source_id}"
                artifact.mkdir(parents=True)
                (artifact / "transcript.srt").write_text("测试", encoding="utf-8")
                (artifact / "transcript.json").write_text(json.dumps({"text": "测试"}, ensure_ascii=False), encoding="utf-8")
                audit_items.append({"source_id": source_id, "direction": direction, "decision": "pass"})
            register = root / "audit.json"
            register.write_text(json.dumps({"profile_id": "demo_profile", "items": audit_items}, ensure_ascii=False), encoding="utf-8")

            result = ingest_directions(root, config, ["赚钱", "表达"], audit_register=register)
            account_index = (root / config.formal_account_dir / "账号索引.md").read_text(encoding="utf-8")
            formal_card = (root / config.formal_account_dir / "directions/表达/cards/01_9002_测试卡.md").read_text(encoding="utf-8")
            global_index = json.loads((root / config.global_account_index_json).read_text(encoding="utf-8"))
            wrong_account_dir = root / "06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说"

        self.assertEqual(result["profile_id"], "demo_profile")
        self.assertEqual(result["direction_count"], 2)
        self.assertIn("# 测试账号账号索引", account_index)
        self.assertIn("| 表达 | formal_ingested |", account_index)
        self.assertIn("状态：formal_ingested", formal_card)
        self.assertNotIn("候选学习卡", formal_card)
        self.assertEqual(global_index["accounts"][0]["account_id"], "demo_account")
        self.assertFalse(wrong_account_dir.exists())


if __name__ == "__main__":
    unittest.main()
