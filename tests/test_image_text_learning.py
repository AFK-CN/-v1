from __future__ import annotations

import json
import tempfile
import subprocess
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tools import image_text_learning


class ImageTextLearningTest(unittest.TestCase):
    def _write_image(self, path: Path, color: tuple[int, int, int] = (240, 230, 210)) -> None:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (360, 480), color=color)
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 40, 330, 130), outline=(20, 20, 20), width=3)
        draw.text((45, 75), "TEST COVER", fill=(20, 20, 20))
        image.save(path)

    def test_environment_accepts_tesseract_without_paddleocr(self) -> None:
        def available(module: str) -> bool:
            return module in {"PIL", "pytesseract"}

        with patch("tools.image_text_learning.import_available", side_effect=available), patch(
            "tools.image_text_learning.shutil.which",
            side_effect=lambda command: "/usr/local/bin/tesseract" if command == "tesseract" else None,
        ):
            report = image_text_learning.image_text_env_report()

        self.assertTrue(report["ok"])
        self.assertTrue(report["degraded"])
        self.assertFalse(report["packages"]["paddleocr"])

    def test_image_text_workflow_creates_candidate_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "90_Temp" / "scratch" / "image_text_learning" / "input" / "sample"
            input_dir.mkdir(parents=True)
            self._write_image(input_dir / "01.png")
            self._write_image(input_dir / "02.jpg", color=(210, 230, 245))

            ingest = image_text_learning.command_ingest(
                Namespace(
                    root=str(root),
                    account_name="测试图文账号",
                    profile_id="test_image_account",
                    platform="xhs",
                    input_dir=str(input_dir),
                    workflow_id="image_text_test",
                    ocr_engine="none",
                    visual_feature_engine="opencv",
                    image2_mode="codex",
                    image2_command="",
                )
            )
            self.assertEqual(ingest["workflow_id"], "image_text_test")
            self.assertEqual(len(ingest["images"]), 2)
            self.assertEqual(ingest["ocr_status"], "pending")

            image_text_learning.command_structure(Namespace(root=str(root), workflow_id="image_text_test"))
            image_text_learning.command_scan(Namespace(root=str(root), workflow_id="image_text_test"))
            image_text_learning.command_select(Namespace(root=str(root), workflow_id="image_text_test", top_n=1))
            learned = image_text_learning.command_learn(Namespace(root=str(root), workflow_id="image_text_test"))
            status = image_text_learning.command_status(Namespace(root=str(root), workflow_id="image_text_test"))

            self.assertEqual(learned["learned_cards"], 1)
            self.assertEqual(status["media_branch"], "image_text")
            self.assertEqual(status["candidate_card_count"], 1)

            account_assets = root / "10_Knowledge" / "candidates" / "account_assets" / "image_text_learning" / "test_image_account" / "image_text_test"
            self.assertTrue((account_assets / "账号概述.md").exists())
            self.assertTrue((account_assets / "粗学与选题池.md").exists())
            self.assertTrue((account_assets / "deep_learning_plan.json").exists())
            self.assertFalse((root / "10_Knowledge" / "formal" / "accounts").exists())

            structured = image_text_learning.read_jsonl(root / "00_System" / "runtime" / "cache" / "image_text_learning" / "image_text_test" / "structured_posts.jsonl")
            image = structured[0]["images"][0]
            self.assertIn(image["visual_features"]["status"], {"completed", "completed_degraded"})
            self.assertEqual(image["image2_evidence"]["status"], "pending_codex_review")
            self.assertEqual(image["image2_evidence"]["provider"], "codex_image2")
            self.assertEqual(structured[0]["publish_layer"]["status"], "missing")
            self.assertEqual(structured[0]["visual_sequence"]["status"], "post_grouping_unknown")

    def test_post_manifest_preserves_full_publish_copy_and_ordered_multi_image_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "90_Temp" / "scratch" / "image_text_learning" / "input" / "sample"
            input_dir.mkdir(parents=True)
            for index in range(1, 4):
                self._write_image(input_dir / f"{index:02d}.png", color=(230 - index * 5, 225, 210 + index * 5))
            body = "下班有点晚，先把材料切好。\n加热 3 分钟后看状态，再继续 2 分钟。\n刚好够一个人吃，我就不另外装盘了。"
            (input_dir / "posts.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "xhs_post_001",
                        "title": "下班晚也能吃上的一人食",
                        "caption": body,
                        "tags": ["一人食", "下班做饭"],
                        "url": "https://example.com/xhs_post_001",
                        "images": ["01.png", "02.png", "03.png"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            ingest = image_text_learning.command_ingest(
                Namespace(
                    root=str(root),
                    account_name="测试图文账号",
                    profile_id="test_image_account",
                    platform="xhs",
                    input_dir=str(input_dir),
                    posts_file="",
                    workflow_id="image_text_grouped",
                    ocr_engine="none",
                    visual_feature_engine="pillow",
                    image2_mode="none",
                    image2_command="",
                )
            )
            self.assertEqual(ingest["source_mode"], "post_manifest_v2")
            self.assertEqual(ingest["post_count"], 1)
            self.assertEqual(ingest["image_count"], 3)

            image_text_learning.command_structure(Namespace(root=str(root), workflow_id="image_text_grouped"))
            image_text_learning.command_scan(Namespace(root=str(root), workflow_id="image_text_grouped"))
            image_text_learning.command_select(Namespace(root=str(root), workflow_id="image_text_grouped", top_n=0))
            image_text_learning.command_learn(Namespace(root=str(root), workflow_id="image_text_grouped"))

            rows = image_text_learning.read_jsonl(
                root / "00_System/runtime/cache/image_text_learning/image_text_grouped/structured_posts.jsonl"
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_id"], "xhs_post_001")
            self.assertEqual(rows[0]["caption"], body)
            self.assertEqual(rows[0]["tags"], ["一人食", "下班做饭"])
            self.assertEqual(rows[0]["publish_layer"]["status"], "complete")
            self.assertEqual(rows[0]["visual_sequence"]["status"], "ordered_post_sequence")
            self.assertEqual([image["image_role"] for image in rows[0]["images"]], ["cover", "body", "summary_or_cta"])
            self.assertIn("text_annotation_design", rows[0]["images"][0]["deep_visual_observation"]["missing_or_uncertain_dimensions"])

            card = (
                root
                / "10_Knowledge/candidates/learning_cards/image_text_cards/test_image_account/image_text_grouped/xhs_post_001.md"
            ).read_text(encoding="utf-8")
            self.assertIn("下班晚也能吃上的一人食", card)
            self.assertIn("加热 3 分钟后看状态，再继续 2 分钟", card)
            self.assertIn("## 2. 发布文案深学任务", card)
            self.assertIn("文字注释设计", card)
            self.assertIn("组图叙事", card)

    def test_structure_accepts_paddleocr_visual_features_and_image2_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "90_Temp" / "scratch" / "image_text_learning" / "input" / "sample"
            input_dir.mkdir(parents=True)
            self._write_image(input_dir / "01.png")
            image2_script = root / "fake_image2.py"
            image2_script.write_text(
                "import json, sys\n"
                "print(json.dumps({'visual_description':'clean cover with centered title','layout_type':'cover_title','image_role_guess':'cover','visual_analysis':{"
                "'subject_and_action':'a hand places the subject',"
                "'composition_and_viewpoint':'top-down close view',"
                "'visual_hierarchy':'subject before annotation',"
                "'text_annotation_design':'paper label points to the action',"
                "'typography_hierarchy':'large title and smaller step note',"
                "'color_light_texture':'soft daylight and visible texture',"
                "'state_or_result':'finished state is visible',"
                "'authenticity_cues':'natural hand and used surface',"
                "'narrative_function':'cover promise'}}, ensure_ascii=False))\n",
                encoding="utf-8",
            )

            image_text_learning.command_ingest(
                Namespace(
                    root=str(root),
                    account_name="测试图文账号",
                    profile_id="test_image_account",
                    platform="xhs",
                    input_dir=str(input_dir),
                    workflow_id="image_text_test",
                    ocr_engine="paddleocr",
                    ocr_lang="ch",
                    ocr_psm=6,
                    visual_feature_engine="pillow",
                    image2_mode="external",
                    image2_command=f"{sys.executable} {image2_script}",
                    image2_timeout=10,
                )
            )
            with patch("tools.image_text_learning.ocr_image_paddleocr") as ocr:
                ocr.return_value = {
                    "ocr_text": "普通女生变美的3个细节",
                    "ocr_status": "completed",
                    "ocr_engine": "paddleocr",
                    "ocr_lang": "ch",
                    "text_blocks": [{"text": "普通女生变美的3个细节", "confidence": 0.98, "bbox": [[1, 1], [2, 1], [2, 2], [1, 2]]}],
                }
                result = image_text_learning.command_structure(Namespace(root=str(root), workflow_id="image_text_test"))

            self.assertEqual(result["ocr_counts"]["completed"], 1)
            self.assertEqual(result["image2_counts"]["completed"], 1)
            structured = image_text_learning.read_jsonl(root / "00_System" / "runtime" / "cache" / "image_text_learning" / "image_text_test" / "structured_posts.jsonl")
            image = structured[0]["images"][0]
            self.assertEqual(image["ocr_engine"], "paddleocr")
            self.assertEqual(image["ocr_text"], "普通女生变美的3个细节")
            self.assertEqual(image["text_blocks"][0]["confidence"], 0.98)
            self.assertEqual(image["visual_features"]["engine"], "pillow")
            self.assertEqual(image["image2_evidence"]["layout_type"], "cover_title")
            self.assertEqual(image["deep_visual_observation"]["status"], "complete_visual_analysis")
            self.assertEqual(image["deep_visual_observation"]["observed"]["text_annotation_design"], "paper label points to the action")

    def test_explicit_no_topics_is_preserved_without_becoming_missing_publish_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            input_dir.mkdir(parents=True)
            self._write_image(input_dir / "01.png")
            (input_dir / "posts.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "no_topics",
                        "title": "有标题",
                        "caption": "有完整正文",
                        "tags": [],
                        "images": ["01.png"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            image_text_learning.command_ingest(
                Namespace(
                    root=str(root),
                    account_name="测试图文账号",
                    profile_id="test_image_account",
                    platform="xhs",
                    input_dir=str(input_dir),
                    posts_file="",
                    workflow_id="image_text_no_topics",
                    ocr_engine="none",
                    visual_feature_engine="none",
                    image2_mode="none",
                    image2_command="",
                )
            )
            image_text_learning.command_structure(Namespace(root=str(root), workflow_id="image_text_no_topics"))
            row = image_text_learning.read_jsonl(
                root / "00_System/runtime/cache/image_text_learning/image_text_no_topics/structured_posts.jsonl"
            )[0]

            self.assertEqual(row["publish_layer"]["status"], "complete")
            self.assertEqual(row["publish_layer"]["topics_status"], "explicit_absence")
            self.assertEqual(row["tags"], [])

    def test_structure_accepts_external_paddleocr_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "90_Temp" / "scratch" / "image_text_learning" / "input" / "sample"
            input_dir.mkdir(parents=True)
            self._write_image(input_dir / "01.png")
            paddle_script = root / "fake_paddleocr.py"
            paddle_script.write_text(
                "import json, sys\n"
                "print(json.dumps({'ocr_text':'封面标题','text_blocks':[{'text':'封面标题','confidence':0.91}]}, ensure_ascii=False))\n",
                encoding="utf-8",
            )

            image_text_learning.command_ingest(
                Namespace(
                    root=str(root),
                    account_name="测试图文账号",
                    profile_id="test_image_account",
                    platform="xhs",
                    input_dir=str(input_dir),
                    workflow_id="image_text_external_paddle",
                    ocr_engine="paddleocr",
                    ocr_lang="ch",
                    ocr_psm=6,
                    visual_feature_engine="pillow",
                    paddleocr_command=f"{sys.executable} {paddle_script}",
                    image2_mode="none",
                    image2_command="",
                    image2_timeout=10,
                )
            )
            result = image_text_learning.command_structure(Namespace(root=str(root), workflow_id="image_text_external_paddle"))

            self.assertEqual(result["ocr_counts"]["completed"], 1)
            structured = image_text_learning.read_jsonl(
                root / "00_System" / "runtime" / "cache" / "image_text_learning" / "image_text_external_paddle" / "structured_posts.jsonl"
            )
            image = structured[0]["images"][0]
            self.assertEqual(image["ocr_engine"], "paddleocr_command")
            self.assertEqual(image["ocr_text"], "封面标题")
            self.assertEqual(image["text_blocks"][0]["confidence"], 0.91)

    def test_kb_cli_runs_image_text_branch_as_candidate_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "90_Temp" / "scratch" / "image_text_learning" / "input" / "sample"
            input_dir.mkdir(parents=True)
            self._write_image(input_dir / "01.png")

            base_command = [sys.executable, "-m", "tools.kb.cli", "--root", str(root)]
            ingest = subprocess.run(
                base_command
                + [
                    "image-text-ingest",
                    "--account-name",
                    "测试图文账号",
                    "--profile-id",
                    "test_image_account",
                    "--input-dir",
                    str(input_dir),
                    "--workflow-id",
                    "image_text_cli_test",
                    "--ocr-engine",
                    "none",
                    "--image2-mode",
                    "codex",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            payload = json.loads(ingest.stdout)
            self.assertEqual(payload["media_branch"], "image_text")

            for command in ("structure", "scan", "select", "learn", "status"):
                step = ["image-text-" + command, "--workflow-id", "image_text_cli_test"]
                if command == "select":
                    step.extend(["--top-n", "1"])
                subprocess.run(
                    base_command + step,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

            card_dir = root / "10_Knowledge" / "candidates" / "learning_cards" / "image_text_cards" / "test_image_account" / "image_text_cli_test"
            self.assertEqual(len(list(card_dir.glob("*.md"))), 1)
            self.assertFalse((root / "10_Knowledge" / "formal" / "accounts").exists())


if __name__ == "__main__":
    unittest.main()
