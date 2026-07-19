from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.account_offline_source import build_offline_sources, verify_offline_sources


class AccountOfflineSourceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        account_center = root / "10_Knowledge/formal/accounts/测试账号"
        (account_center / "skill").mkdir(parents=True)
        (account_center / "skill/SKILL.md").write_text("# test\n", encoding="utf-8")
        registry = root / "20_User/config/account_skill_registry.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(
            json.dumps(
                {
                    "accounts": [
                        {
                            "account_name": "测试账号",
                            "platform": "小红书",
                            "skill_path": "10_Knowledge/formal/accounts/测试账号/skill/SKILL.md",
                            "status": "active",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        nas_root = root / "nas"
        creator_root = nas_root / "xhs/accounts/xhs_creator"
        for direction_index, direction in enumerate(("方向甲", "方向乙", "方向丙"), start=1):
            cards = account_center / "directions" / direction / "cards"
            cards.mkdir(parents=True)
            for item_index in range(1, 4):
                source_id = f"source{direction_index}{item_index:02d}abcdefgh"
                (cards / f"xhs_{source_id}.md").write_text(
                    f"# {direction}-{item_index}\n\nsource_id：{source_id}\n",
                    encoding="utf-8",
                )
                source_dir = creator_root / f"xhs_{source_id}"
                (source_dir / "images").mkdir(parents=True)
                for name in ("source.json", "status.json", "manifest_item.json"):
                    (source_dir / name).write_text("{}\n", encoding="utf-8")
                (source_dir / "images/000_cover.jpg").write_bytes(
                    (f"image-{direction_index}-{item_index}" * item_index).encode("utf-8")
                )
                (source_dir / "images/ocr.json").write_text("{}\n", encoding="utf-8")
        return nas_root

    def test_dry_run_distributes_across_every_direction_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nas_root = self._fixture(root)
            result = build_offline_sources(
                root,
                nas_root=nas_root,
                min_total=5,
                max_total=6,
                per_direction_max=2,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "dry_run")
            account = result["accounts"][0]
            self.assertEqual(account["selected_count"], 5)
            self.assertEqual(sorted(account["direction_counts"].values()), [1, 2, 2])
            self.assertFalse(
                (root / "10_Knowledge/formal/accounts/测试账号/轻量数据源").exists()
            )

    def test_apply_copies_complete_outputs_and_verify_checks_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nas_root = self._fixture(root)
            result = build_offline_sources(
                root,
                nas_root=nas_root,
                min_total=4,
                max_total=6,
                per_direction_max=2,
                apply=True,
            )
            self.assertTrue(result["ok"])
            output = root / "10_Knowledge/formal/accounts/测试账号/轻量数据源"
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["selected_count"], 4)
            self.assertEqual(manifest["direction_count"], 3)
            first_bundle = output / manifest["items"][0]["bundle_path"]
            self.assertTrue((first_bundle / "学习卡.md").is_file())
            self.assertTrue((first_bundle / "完整产出物/images/000_cover.jpg").is_file())
            self.assertTrue((first_bundle / "bundle_manifest.json").is_file())
            verified = verify_offline_sources(root)
            self.assertTrue(verified["ok"], verified)
            self.assertEqual(verified["selected_count"], 4)

    def test_missing_direction_source_blocks_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nas_root = self._fixture(root)
            missing = next((nas_root / "xhs/accounts/xhs_creator").glob("xhs_source301*"))
            for path in sorted(missing.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            missing.rmdir()
            for sibling in list((nas_root / "xhs/accounts/xhs_creator").glob("xhs_source30*")):
                if sibling == missing:
                    continue
                for path in sorted(sibling.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                sibling.rmdir()
            result = build_offline_sources(
                root,
                nas_root=nas_root,
                min_total=3,
                max_total=6,
                per_direction_max=2,
                apply=True,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "partial_failure")
            self.assertTrue(any("source_root_unmatched:方向丙" in error for error in result["accounts"][0]["errors"]))

    def test_existing_bundle_dry_run_reports_selection_diff_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nas_root = self._fixture(root)
            first = build_offline_sources(
                root,
                nas_root=nas_root,
                min_total=4,
                max_total=6,
                per_direction_max=2,
                apply=True,
            )
            self.assertTrue(first["ok"])
            manifest_path = root / "10_Knowledge/formal/accounts/测试账号/轻量数据源/manifest.json"
            before = manifest_path.read_bytes()

            preview = build_offline_sources(
                root,
                nas_root=nas_root,
                min_total=5,
                max_total=6,
                per_direction_max=2,
                apply=True,
            )

            self.assertTrue(preview["ok"])
            self.assertEqual(preview["status"], "refresh_review_required")
            account = preview["accounts"][0]
            self.assertEqual(account["offline_source_status"], "refresh_review_required")
            self.assertEqual(len(account["selection_diff"]["added"]), 1)
            self.assertEqual(account["write_skipped"], "existing_bundle_requires_explicit_force_after_diff_review")
            self.assertEqual(manifest_path.read_bytes(), before)

    def test_nas_unavailable_preserves_existing_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nas_root = self._fixture(root)
            built = build_offline_sources(
                root,
                nas_root=nas_root,
                min_total=4,
                max_total=6,
                per_direction_max=2,
                apply=True,
            )
            self.assertTrue(built["ok"])
            offline_root = root / "nas-offline"
            nas_root.rename(offline_root)

            result = build_offline_sources(root, nas_root=nas_root, apply=True)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "nas_unavailable")
            self.assertEqual(
                result["accounts"][0]["offline_source_status"],
                "nas_unavailable_existing_bundle_preserved",
            )
            verified = verify_offline_sources(root)
            self.assertEqual(verified["status"], "verified")

    def test_new_account_without_nas_writes_pending_sync_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            missing_nas = root / "missing-nas"

            result = build_offline_sources(root, nas_root=missing_nas, apply=True)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "nas_unavailable")
            account = result["accounts"][0]
            self.assertEqual(account["offline_source_status"], "pending_nas_sync")
            manifest = json.loads(
                (root / "10_Knowledge/formal/accounts/测试账号/轻量数据源/manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "pending_nas_sync")
            verified = verify_offline_sources(root)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["status"], "pending")

    def test_account_learning_active_contract_registers_offline_source_delivery(self) -> None:
        skill = Path("00_System/shareable/skills/active/account-learning/SKILL.md").read_text(encoding="utf-8")
        reference = Path(
            "00_System/shareable/skills/active/account-learning/references/offline-lightweight-source.md"
        )
        pipeline = json.loads(
            Path("00_System/shareable/config/account_learning_pipeline.json").read_text(encoding="utf-8")
        )
        routes = json.loads(
            Path("00_System/shareable/index/controller_routes.json").read_text(encoding="utf-8")
        )
        route = next(item for item in routes["routes"] if item["id"] == "account_learning")
        contracts = json.loads(
            Path("00_System/shareable/config/output_contracts.json").read_text(encoding="utf-8")
        )
        contract = next(item for item in contracts["contracts"] if item["route_id"] == "account_learning")
        task_index = Path("00_System/shareable/index/task_entry_index.md").read_text(encoding="utf-8")

        self.assertIn("offline-lightweight-source.md", skill)
        self.assertTrue(reference.is_file())
        self.assertIn("七阶段完成", reference.read_text(encoding="utf-8"))
        post_approval = pipeline["post_approval_offline_source"]
        self.assertFalse(post_approval["part_of_seven_stages"])
        self.assertEqual(post_approval["selection"]["min_total_per_account"], 10)
        self.assertEqual(post_approval["selection"]["max_per_formal_direction"], 5)
        self.assertIn("tools.account_offline_source", route["tools"])
        self.assertIn("组建轻量数据源", route["triggers"])
        self.assertIn("轻量数据源状态", contract["required_fields"])
        self.assertIn("轻量数据源", task_index)


if __name__ == "__main__":
    unittest.main()
