import json
import tempfile
import unittest
from pathlib import Path

from tools.video_learning_account_ingest import AccountIngestConfig, _approved_directions_from_register, ingest_directions


class VideoLearningAccountIngestTests(unittest.TestCase):
    def test_ingest_directions_uses_profile_config_not_hardcoded_account_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AccountIngestConfig.for_profile(
                profile_id="demo_profile",
                account_id="demo_account",
                account_name="测试账号",
                formal_account_dir=Path("10_Knowledge/formal/accounts/测试账号中心/测试账号"),
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
                (learned / "粗扫内容和选题.md").write_text(
                    "\n".join(
                        [
                            f"# {direction}方向粗学与选题池",
                            "",
                            "状态：candidate_learning_pool",
                            "",
                            "## 1. 方向素材总览",
                            "",
                            "- 内容总数：1条。",
                            "- 已确认深学卡：0条。",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
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
            account_summary = (root / config.formal_account_dir / "账号整体方法论.md").read_text(encoding="utf-8")
            formal_card = (root / config.formal_account_dir / "directions/表达/cards/01_9002_测试卡.md").read_text(encoding="utf-8")
            formal_rough = (root / config.formal_account_dir / "directions/表达/粗扫内容和选题.md").read_text(encoding="utf-8")
            global_index = json.loads((root / config.global_account_index_json).read_text(encoding="utf-8"))
            dirty_state = json.loads(
                (root / "00_System/runtime/state/dirty_generation.json").read_text(encoding="utf-8")
            )
            wrong_account_dir = root / "10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/姜胡说"

        self.assertEqual(result["profile_id"], "demo_profile")
        self.assertEqual(result["direction_count"], 2)
        self.assertIn("# 测试账号账号索引", account_index)
        self.assertIn("账号整体方法论.md", account_index)
        self.assertIn("# 测试账号账号整体方法论", account_summary)
        self.assertIn("| 表达 | formal_ingested |", account_index)
        self.assertIn("状态：formal_ingested", formal_card)
        self.assertNotIn("候选学习卡", formal_card)
        self.assertIn("状态：formal_learning_pool", formal_rough)
        self.assertIn("- 已确认深学卡：1条。", formal_rough)
        self.assertIn("不学习评论正文", formal_rough)
        self.assertEqual(global_index["accounts"][0]["account_id"], "demo_account")
        self.assertIn("account_summary", {layer["layer"] for layer in global_index["accounts"][0]["knowledge_layers"]})
        self.assertEqual(dirty_state["dirty_generation"], 1)
        self.assertEqual(dirty_state["events"][-1]["reason"], "formal_account_ingest")
        self.assertFalse(wrong_account_dir.exists())

    def test_xhs_platform_uses_xhs_artifact_prefix_for_transcripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AccountIngestConfig.for_profile(
                profile_id="xhs_profile",
                account_id="xhs_account",
                account_name="小红书测试账号",
                platform="小红书",
                formal_account_dir=Path("10_Knowledge/formal/accounts/测试账号中心/小红书测试账号"),
            )
            source_id = "xhs_note_1"
            learned = root / config.learned_base / "护肤"
            cards = learned / "cards"
            cards.mkdir(parents=True)
            (learned / "方向方法论总结.md").write_text("# 护肤方向方法论总结\n\n学习状态：complete_candidate\n", encoding="utf-8")
            (learned / "粗扫内容和选题.md").write_text("# 护肤粗扫\n", encoding="utf-8")
            (cards / f"01_{source_id}_测试卡.md").write_text(
                "\n".join(
                    [
                        "# 视频深度学习卡：小红书测试卡",
                        "",
                        f"source_id: {source_id}",
                        f"原视频链接：https://www.xiaohongshu.com/explore/{source_id}",
                        "账号：小红书测试账号",
                        "平台：xhs",
                        "主方向：护肤",
                        "状态：confirmed_learned",
                        "",
                        "## 10. 入库判断",
                        "",
                        "- 待验证：保留为候选学习卡；审核后再进入正式知识库。",
                    ]
                ),
                encoding="utf-8",
            )
            artifact = root / config.artifacts_dir / f"xhs_{source_id}"
            artifact.mkdir(parents=True)
            (artifact / "transcript.srt").write_text("小红书逐字稿", encoding="utf-8")
            (artifact / "transcript.json").write_text(json.dumps({"text": "小红书逐字稿"}, ensure_ascii=False), encoding="utf-8")

            dry_run = ingest_directions(root, config, ["护肤"], dry_run=True)
            result = ingest_directions(root, config, ["护肤"])
            transcript_dir = root / config.formal_account_dir / "directions/护肤/transcripts"
            srt_exists = (transcript_dir / f"{source_id}_transcript.srt").exists()
            json_exists = (transcript_dir / f"{source_id}_transcript.json").exists()
            anti_ai = (root / config.formal_account_dir / "减少AI味输出规则.md").read_text(encoding="utf-8")

        self.assertEqual(dry_run["transcript_file_count"], 2)
        self.assertEqual(result["transcript_file_count"], 2)
        self.assertTrue(srt_exists)
        self.assertTrue(json_exists)
        self.assertIn("小红书账号", anti_ai)
        self.assertIn("本账号正式单卡", anti_ai)
        self.assertIn("标题、正文和话题", anti_ai)
        self.assertNotIn("姜胡说", anti_ai)
        self.assertNotIn("普通人破局", anti_ai)

    def test_all_approved_directions_accepts_machine_audit_cards_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            register = root / "machine_audit.json"
            register.write_text(
                json.dumps(
                    {
                        "cards": [
                            {"source_id": "1", "direction": "护肤", "machine_decision": "pass"},
                            {"source_id": "2", "direction": "护肤", "machine_decision": "pass"},
                            {"source_id": "3", "direction": "彩妆", "machine_decision": "review"},
                            {"source_id": "4", "direction": "生活", "machine_decision": "pass"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            directions = _approved_directions_from_register(root, register)

        self.assertEqual(directions, ["护肤", "生活"])


if __name__ == "__main__":
    unittest.main()
