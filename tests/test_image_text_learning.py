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

    def test_structure_accepts_paddleocr_visual_features_and_image2_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "90_Temp" / "scratch" / "image_text_learning" / "input" / "sample"
            input_dir.mkdir(parents=True)
            self._write_image(input_dir / "01.png")
            image2_script = root / "fake_image2.py"
            image2_script.write_text(
                "import json, sys\n"
                "print(json.dumps({'visual_description':'clean cover with centered title','layout_type':'cover_title','image_role_guess':'cover'}, ensure_ascii=False))\n",
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
