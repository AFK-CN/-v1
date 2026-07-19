from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.kb.release_gate import run_release_gate


class ReleaseGateTests(unittest.TestCase):
    def _root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "VERSION").write_text("3.0.0\n", encoding="utf-8")
        config = root / "00_System/shareable/config"
        config.mkdir(parents=True)
        (config / "system_version.json").write_text(
            json.dumps({"system_version": "3.0", "release_version": "3.0.0"}),
            encoding="utf-8",
        )
        return temp, root

    @patch("tools.kb.release_gate.search_formal")
    @patch("tools.kb.release_gate.index_status")
    @patch("tools.kb.release_gate.audit_distribution")
    @patch("tools.kb.release_gate.audit_system_boundaries")
    @patch("tools.kb.release_gate.validate_user_layer")
    @patch("tools.kb.release_gate.doctor_runtime")
    @patch("tools.kb.release_gate.validate_system")
    def test_release_gate_passes_all_engineering_checks(
        self,
        validate_system_mock,
        doctor_mock,
        user_mock,
        boundary_mock,
        distribution_mock,
        index_mock,
        search_mock,
    ):
        temp, root = self._root()
        self.addCleanup(temp.cleanup)
        validate_system_mock.return_value = {"ok": True, "failed": []}
        doctor_mock.return_value = {"status": "healthy", "repair_actions": []}
        user_mock.return_value = {"ok": True, "errors": []}
        boundary_mock.return_value = {"ok": True, "violations": [], "legacy_path_references": []}
        distribution_mock.return_value = {
            "ok": True,
            "portable": True,
            "license_files": ["LICENSE"],
            "legal_release_blocker": "",
            "errors": [],
        }
        index_mock.return_value = {
            "ok": True,
            "status": "ready",
            "meta": {"source_count": 1, "chunk_count": 1, "forbidden_layers_indexed": False},
        }
        positive = {
            "ok": True,
            "items": [
                {
                    "path": "10_Knowledge/formal/example.md",
                    "line_start": 1,
                    "evidence_coordinate": "10_Knowledge/formal/example.md:L1-L2",
                    "chunk_sha256": "a" * 64,
                }
            ],
        }
        search_mock.side_effect = [positive, {"ok": True, "items": []}]

        result = run_release_gate(root, max_search_ms=5000)

        self.assertTrue(result["ok"])
        self.assertEqual(result["failed"], [])
        self.assertTrue(result["checks"]["strict_account_filter"]["ok"])

    @patch("tools.kb.release_gate.search_formal")
    @patch("tools.kb.release_gate.index_status")
    @patch("tools.kb.release_gate.audit_distribution")
    @patch("tools.kb.release_gate.audit_system_boundaries")
    @patch("tools.kb.release_gate.validate_user_layer")
    @patch("tools.kb.release_gate.doctor_runtime")
    @patch("tools.kb.release_gate.validate_system")
    def test_release_gate_fails_untraceable_or_cross_account_results(
        self,
        validate_system_mock,
        doctor_mock,
        user_mock,
        boundary_mock,
        distribution_mock,
        index_mock,
        search_mock,
    ):
        temp, root = self._root()
        self.addCleanup(temp.cleanup)
        validate_system_mock.return_value = {"ok": True, "failed": []}
        doctor_mock.return_value = {"status": "healthy", "repair_actions": []}
        user_mock.return_value = {"ok": True, "errors": []}
        boundary_mock.return_value = {"ok": True, "violations": [], "legacy_path_references": []}
        distribution_mock.return_value = {
            "ok": True,
            "portable": True,
            "license_files": ["LICENSE"],
            "legal_release_blocker": "",
            "errors": [],
        }
        index_mock.return_value = {
            "ok": True,
            "status": "ready",
            "meta": {"source_count": 1, "chunk_count": 1, "forbidden_layers_indexed": False},
        }
        search_mock.side_effect = [
            {"ok": True, "items": [{"path": "10_Knowledge/candidates/leak.md"}]},
            {"ok": True, "items": [{"path": "10_Knowledge/formal/cross-account.md"}]},
        ]

        result = run_release_gate(root, max_search_ms=5000)

        self.assertFalse(result["ok"])
        self.assertIn("formal_search_smoke", result["failed"])
        self.assertIn("strict_account_filter", result["failed"])


if __name__ == "__main__":
    unittest.main()
