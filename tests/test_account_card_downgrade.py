from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.account_card_downgrade import downgrade_cards


class AccountCardDowngradeTests(unittest.TestCase):
    def test_apply_creates_verified_candidate_snapshot_and_removes_formal_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "10_Knowledge/formal/accounts/example"
            card = account_dir / "directions/topic/cards/01_source.md"
            card.parent.mkdir(parents=True)
            card.write_text("# card\n", encoding="utf-8")

            result = downgrade_cards(root, "example", account_dir, apply=True)

            self.assertTrue(result["backup_verified"])
            self.assertEqual(result["source_remaining"], 0)
            self.assertFalse(card.exists())
            manifest_path = root / str(result["manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["card_count"], 1)
            self.assertEqual(manifest["knowledge_layer"], "candidate_knowledge")
            self.assertFalse(manifest["formal_callable"])
            backup = root / manifest["entries"][0]["backup"]
            self.assertEqual(backup.read_text(encoding="utf-8"), "# card\n")

    def test_dry_run_leaves_formal_card_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "10_Knowledge/formal/accounts/example"
            card = account_dir / "directions/topic/cards/01_source.md"
            card.parent.mkdir(parents=True)
            card.write_text("# card\n", encoding="utf-8")

            result = downgrade_cards(root, "example", account_dir, apply=False)

            self.assertEqual(result["card_count"], 1)
            self.assertTrue(card.exists())
            self.assertFalse((root / str(result["backup_root"])).exists())


if __name__ == "__main__":
    unittest.main()
