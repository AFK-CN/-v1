from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.xiaosenlin_batch_learning import INVENTORY_REL, build_batch_plan, evidence_for_item, run_batch, topic_family


class XiaosenlinBatchLearningTests(unittest.TestCase):
    def test_winter_health_content_is_not_lifestyle_vlog(self) -> None:
        self.assertEqual(topic_family("真的有用！冬季养好保持一年好状态！", "养生经验与状态反馈"), "饮食与状态")

    def test_dark_circle_content_routes_to_eye_care(self) -> None:
        self.assertEqual(topic_family("淡化黑眼圈的干货来了", "睡眠和生活方式只是正文背景"), "眼周护理")

    def test_account_engagement_title_wins_over_body(self) -> None:
        self.assertEqual(topic_family("30w粉福，是谁会收到一个礼物", "正文提到油痘肌和护肤"), "账号互动与社群")

    def test_makeup_and_active_titles_win_over_body(self) -> None:
        self.assertEqual(topic_family("干净、清透的底妆分享", "正文提到长痘"), "彩妆与底妆")
        self.assertEqual(topic_family("一张常年刷A醇的脸", "正文提到痘肌"), "抗老与紧致")
        self.assertEqual(topic_family("12年油痘肌，用酸干货+爱用酸分享！", "正文同时出现产品"), "刷酸与焕肤")

    def test_skincare_vlog_is_not_lifestyle_topic(self) -> None:
        self.assertFalse(topic_family("日常晚间护肤Vlog", "晚间护肤流程") == "生活方式与信任")

    def test_title_main_proposition_beats_incidental_body_terms(self) -> None:
        self.assertEqual(topic_family("油痘肌养成通透感好皮肤", "正文提到A醇"), "提亮与肤色")
        self.assertEqual(topic_family("给混油皮安利一款伪素颜神器防晒", "正文强调妆感"), "防晒")
        self.assertEqual(topic_family("油敏K老思路，换季不垮脸", "正文提到生活习惯"), "抗老与紧致")
        self.assertEqual(topic_family("油痘肌1-2月爱用，面膜、粉霜、防晒、爽肤水", "多品类月度清单"), "空瓶与产品复盘")

    def test_plan_freezes_40_item_batches(self) -> None:
        inventory = [{"source_id": str(i), "publish_time": i} for i in range(85)]
        plan = build_batch_plan(inventory, 40)
        self.assertEqual(plan["total_batches"], 3)
        self.assertEqual([row["count"] for row in plan["batches"]], [40, 40, 5])
        self.assertTrue(plan["frozen"])

    def test_run_batch_requires_complete_media_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_path = root / INVENTORY_REL
            inventory_path.parent.mkdir(parents=True)
            rows = []
            nas = root / "nas"
            for i in range(2):
                source_id = f"id{i}"
                rows.append({"source_id": source_id, "title": f"毛孔方法{i}", "content_type": "normal", "publish_time": i, "metrics": {}})
                item = nas / f"xhs_{source_id}"
                (item / "images").mkdir(parents=True)
                (item / "source.json").write_text(
                    json.dumps({"title": f"毛孔方法{i}", "desc": "第一步先判断毛孔堵塞状态，再做温和清洁；第二天观察皮肤触感与泛红变化，根据反馈决定是否继续，最后补充保湿和防晒。"}),
                    encoding="utf-8",
                )
                (item / "status.json").write_text(json.dumps({"steps": {}}), encoding="utf-8")
                (item / "images" / "000_cover.jpg").write_bytes(b"image")
                (item / "images" / "ocr.json").write_text(json.dumps({"images": [{"text": "毛孔清洁"}]}), encoding="utf-8")
                (item / "images" / "visual_summary.json").write_text(json.dumps({"ocr_text": "毛孔清洁"}), encoding="utf-8")
            inventory_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            result = run_batch(root, nas, 1, 2)
            self.assertEqual(result["technical_gate"], "pass")
            self.assertEqual(result["quality_gate"], "pass")
            self.assertEqual(result["batch_gate"], "pass")
            self.assertEqual(result["user_acceptance"], "not_required")
            self.assertEqual(result["candidate_count"], 10)
            self.assertFalse(result["formal_write_allowed"])

    def test_incomplete_nas_media_is_registered_gap_with_sqlite_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            nas = Path(tmp)
            source_id = "missing-video-assets"
            item_root = nas / f"xhs_{source_id}"
            (item_root / "images").mkdir(parents=True)
            (item_root / "source.json").write_text(
                json.dumps({"title": "黑头护理", "desc": "目录仍然存在，但原视频、转写和关键帧都缺失；这里只允许登记主题覆盖，不能据此推断步骤、表达方式或效果机制。"}),
                encoding="utf-8",
            )
            (item_root / "images" / "000_cover.jpg").write_bytes(b"image")
            item = {"source_id": source_id, "title": "黑头护理", "content_type": "video", "publish_time": 1, "metrics": {}}
            sqlite_row = {"desc": "目录仍然存在，但原视频、转写和关键帧都缺失；这里只允许登记主题覆盖，不能据此推断步骤、表达方式或效果机制。"}

            evidence, _ = evidence_for_item(nas, item, sqlite_row=sqlite_row)

            self.assertEqual(evidence["evidence_status"], "registered_external_gap")
            self.assertTrue(evidence["registered_external_gap"])
            self.assertEqual(evidence["external_gap"]["reason"], "nas_media_bundle_incomplete_sqlite_metadata_only")
            self.assertIn("missing_video", evidence["gaps"])
            self.assertIn("missing_frames", evidence["gaps"])


if __name__ == "__main__":
    unittest.main()
