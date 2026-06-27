import json
import tempfile
import unittest
from pathlib import Path

from tools.jianghushuo_account_ingest import ingest_direction, ingest_directions


class JianghushuoAccountIngestTests(unittest.TestCase):
    def test_ingest_directions_preserves_all_directions_and_formalizes_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_items = []
            for index, direction in enumerate(("赚钱", "创业"), start=1):
                source_id = str(2000 + index)
                learned = root / f"10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/{direction}"
                cards = learned / "cards"
                cards.mkdir(parents=True)
                (learned / "方向方法论总结.md").write_text(
                    f"# {direction}方向方法论总结\n\n学习状态：complete_candidate（已完成1/1，待用户审核后入正式账号中心）\n",
                    encoding="utf-8",
                )
                (learned / "粗扫内容和选题.md").write_text(f"# {direction}粗扫内容和选题\n", encoding="utf-8")
                (cards / f"01_{source_id}_测试卡.md").write_text(
                    "\n".join(
                        [
                            f"# 视频深度学习卡：{direction}测试卡",
                            "",
                            f"source_id: {source_id}",
                            f"原视频链接：https://www.douyin.com/video/{source_id}",
                            "账号：姜胡说",
                            "平台：抖音",
                            f"主方向：{direction}",
                            "辅方向：无",
                            "学习批次：test",
                            "状态：confirmed_learned",
                            "",
                            "## 10. 入库判断",
                            "",
                            "- 待验证：保留为候选学习卡；方向完成后结合用户审核决定是否进入正式知识库。",
                        ]
                    ),
                    encoding="utf-8",
                )
                artifact = root / f"00_System/runtime/cache/video_learning/video_artifacts/douyin_{source_id}"
                artifact.mkdir(parents=True)
                (artifact / "transcript.srt").write_text("测试", encoding="utf-8")
                (artifact / "transcript.json").write_text(json.dumps({"text": "测试"}, ensure_ascii=False), encoding="utf-8")
                audit_items.append({"source_id": source_id, "direction": direction, "decision": "pass"})
            register = root / "audit.json"
            register.write_text(json.dumps({"items": audit_items}, ensure_ascii=False), encoding="utf-8")

            result = ingest_directions(root, ["赚钱", "创业"], audit_register=register)
            account_dir = root / "10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说"
            account_index = (account_dir / "账号索引.md").read_text(encoding="utf-8")
            formal_card = (account_dir / "directions/创业/cards/01_2002_测试卡.md").read_text(encoding="utf-8")
            formal_summary = (account_dir / "directions/创业/方向方法论总结.md").read_text(encoding="utf-8")
            global_index = json.loads((root / "10_Knowledge/evidence/index/account_knowledge_index.json").read_text(encoding="utf-8"))

        self.assertEqual(result["direction_count"], 2)
        self.assertIn("| 赚钱 | formal_ingested |", account_index)
        self.assertIn("| 创业 | formal_ingested |", account_index)
        self.assertIn("状态：formal_ingested", formal_card)
        self.assertNotIn("待验证", formal_card)
        self.assertNotIn("候选学习卡", formal_card)
        self.assertIn("学习状态：formal_ingested", formal_summary)
        self.assertEqual({row["direction"] for row in global_index["accounts"][0]["directions"]}, {"赚钱", "创业"})

    def test_ingest_directions_rejects_unapproved_card_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned = root / "10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/创业"
            cards = learned / "cards"
            cards.mkdir(parents=True)
            (learned / "方向方法论总结.md").write_text("# 创业方向方法论总结\n", encoding="utf-8")
            (learned / "粗扫内容和选题.md").write_text("# 创业粗扫\n", encoding="utf-8")
            (cards / "01_3001_测试.md").write_text("# 视频深度学习卡：测试\n\nsource_id: 3001\n", encoding="utf-8")
            register = root / "audit.json"
            register.write_text(json.dumps({"items": [{"source_id": "3001", "direction": "创业", "decision": "relearn"}]}, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not approved"):
                ingest_directions(root, ["创业"], audit_register=register)

            self.assertFalse((root / "10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说/directions/创业").exists())

    def test_ingest_direction_builds_formal_account_package_and_lightweight_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned = root / "10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/赚钱"
            cards = learned / "cards"
            cards.mkdir(parents=True)
            (learned / "方向方法论总结.md").write_text("# 赚钱方向方法论总结\n\n可回溯到单卡。\n", encoding="utf-8")
            (learned / "粗扫内容和选题.md").write_text("# 赚钱粗扫内容和选题\n\n选题线索。\n", encoding="utf-8")
            for number, source_id in enumerate(("1001", "1002"), start=1):
                (cards / f"{number:02d}_{source_id}_测试卡.md").write_text(
                    "\n".join(
                        [
                            f"# 视频深度学习卡：测试卡{number}",
                            "",
                            f"source_id: {source_id}",
                            f"原视频链接：https://example.com/{source_id}",
                            "账号：姜胡说",
                            "平台：抖音",
                            "主方向：赚钱",
                            "状态：confirmed_learned",
                            "",
                            "## 10 入库判断",
                            "",
                            "- 可入库：测试方法论可复用。",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                artifact = root / f"00_System/runtime/cache/video_learning/video_artifacts/douyin_{source_id}"
                artifact.mkdir(parents=True)
                (artifact / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n测试\n", encoding="utf-8")
                (artifact / "transcript.json").write_text(json.dumps({"text": "测试"}, ensure_ascii=False), encoding="utf-8")
                (artifact / "source.mp4").write_bytes(b"video")
                (artifact / "audio.wav").write_bytes(b"audio")
                (artifact / "source-Scene-001-01.jpg").write_bytes(b"jpg")

            result = ingest_direction(root, "赚钱")
            formal_dir = root / result["formal_direction_dir"]
            account_index = root / "10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说/账号索引.md"
            total_index = root / "10_Knowledge/evidence/index/account_knowledge_index.json"
            storage_manifest = json.loads((formal_dir / "存储分层清单.json").read_text(encoding="utf-8"))
            total_index_payload = json.loads(total_index.read_text(encoding="utf-8"))

            self.assertEqual(result["card_count"], 2)
            self.assertEqual(result["transcript_file_count"], 4)
            self.assertTrue((formal_dir / "方向方法论总结.md").exists())
            self.assertTrue((formal_dir / "粗扫内容和选题.md").exists())
            self.assertEqual(len(list((formal_dir / "cards").glob("*.md"))), 2)
            self.assertEqual(len(list((formal_dir / "transcripts").glob("*"))), 4)
            self.assertIn("赚钱", account_index.read_text(encoding="utf-8"))
            self.assertEqual(total_index_payload["accounts"][0]["directions"][0]["direction"], "赚钱")
        self.assertFalse(any("测试方法论可复用" in layer.get("description", "") for layer in total_index_payload["accounts"][0]["knowledge_layers"]))
        self.assertTrue(any(item["tier"] == "cloud_candidate" and item["path"].endswith("source.mp4") for item in storage_manifest["items"]))
        self.assertTrue(any(item["tier"] == "formal_hot" and item["path"].endswith("transcript.srt") for item in storage_manifest["items"]))

    def test_ingest_direction_writes_content_usage_templates_and_style_guardrail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned = root / "10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo/赚钱"
            cards = learned / "cards"
            cards.mkdir(parents=True)
            (learned / "方向方法论总结.md").write_text("# 赚钱方向方法论总结\n", encoding="utf-8")
            (learned / "粗扫内容和选题.md").write_text("# 赚钱粗扫内容和选题\n", encoding="utf-8")
            (cards / "01_1001_测试卡.md").write_text(
                "\n".join(
                    [
                        "# 视频深度学习卡：测试卡",
                        "",
                        "source_id: 1001",
                        "原视频链接：https://www.douyin.com/video/1001",
                        "账号：姜胡说",
                        "平台：抖音",
                        "主方向：赚钱",
                        "状态：confirmed_learned",
                    ]
                ),
                encoding="utf-8",
            )
            artifact = root / "00_System/runtime/cache/video_learning/video_artifacts/douyin_1001"
            artifact.mkdir(parents=True)
            (artifact / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n测试\n", encoding="utf-8")
            (artifact / "transcript.json").write_text(json.dumps({"text": "测试"}, ensure_ascii=False), encoding="utf-8")

            ingest_direction(root, "赚钱")
            account_dir = root / "10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说"
            direction_dir = account_dir / "directions/赚钱"
            usage = (account_dir / "内容生产使用说明.md").read_text(encoding="utf-8")
            style = (account_dir / "减少AI味输出规则.md").read_text(encoding="utf-8")
            template = (account_dir / "内容输出标准模板.md").read_text(encoding="utf-8")
            total_index = json.loads((root / "10_Knowledge/evidence/index/account_knowledge_index.json").read_text(encoding="utf-8"))

        self.assertIn("会话外调用", usage)
        self.assertIn("不要全扫候选区", usage)
        self.assertIn("持续更新", style)
        self.assertIn("禁止同一批选题使用同一种黄金3秒", style)
        self.assertIn("对标知识库内容", template)
        self.assertIn("原抖音链接", template)
        self.assertIn("选题标题", template)
        self.assertIn("对应方法论", template)
        self.assertIn("受众痛点", template)
        self.assertIn("钩子角度", template)
        self.assertIn("核心观点", template)
        self.assertIn("可引用案例", template)
        self.assertIn("黄金3s", template)
        self.assertIn("完整文案", template)
        self.assertIn("互动收尾", template)
        layers = {layer["layer"] for layer in total_index["accounts"][0]["knowledge_layers"]}
        self.assertIn("content_usage", layers)
        self.assertIn("anti_ai_style", layers)
        self.assertIn("account_content_template", layers)
        self.assertFalse((direction_dir / "出内容标准模板.md").exists())


if __name__ == "__main__":
    unittest.main()
