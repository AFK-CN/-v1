import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class KBRuntimeTests(unittest.TestCase):
    def test_health_gate_never_computes_full_knowledge_fingerprint(self):
        from tools.kb.runtime import health_gate, initialize_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=True)

            with patch("tools.kb.runtime.full_knowledge_fingerprint", side_effect=AssertionError("must not run")):
                result = health_gate(root)

            self.assertEqual(result["status"], "healthy")
            self.assertFalse(result["full_scan_performed"])

    def test_health_credential_is_shared_by_every_caller_of_same_root(self):
        from tools.kb.runtime import credential_path, health_gate, initialize_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=True)
            first = health_gate(root)
            first_mtime = credential_path(root).stat().st_mtime_ns
            second = health_gate(root)

            self.assertEqual(first["root_id"], second["root_id"])
            self.assertEqual(first["credential_path"], second["credential_path"])
            self.assertEqual(credential_path(root).stat().st_mtime_ns, first_mtime)

    def test_health_gate_requires_init_for_missing_runtime_or_schema_mismatch(self):
        from tools.kb.runtime import (
            RUNTIME_SCHEMA_VERSION,
            credential_path,
            health_gate,
            initialize_runtime,
            manifest_path,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(health_gate(root)["status"], "requires_init")

            initialize_runtime(root, rebuild=False, migrate=True)
            manifest = json.loads(manifest_path(root).read_text(encoding="utf-8"))
            manifest["schema_version"] = RUNTIME_SCHEMA_VERSION + 1
            write_json(manifest_path(root), manifest)

            self.assertEqual(health_gate(root)["status"], "requires_init")

            manifest["schema_version"] = RUNTIME_SCHEMA_VERSION
            write_json(manifest_path(root), manifest)
            credential = json.loads(credential_path(root).read_text(encoding="utf-8"))
            credential["schema_version"] = RUNTIME_SCHEMA_VERSION + 1
            write_json(credential_path(root), credential)

            self.assertEqual(health_gate(root)["status"], "requires_init")

    def test_health_gate_requires_init_for_incomplete_layout_or_unapplied_migration(self):
        from tools.kb.runtime import MIGRATION_VERSION, health_gate, initialize_runtime, manifest_path, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=True)

            manifest = json.loads(manifest_path(root).read_text(encoding="utf-8"))
            manifest["applied_migrations"] = []
            write_json(manifest_path(root), manifest)
            result = health_gate(root)
            self.assertEqual(result["status"], "requires_init")
            self.assertIn("migration_required", result["reasons"])

            manifest["applied_migrations"] = [MIGRATION_VERSION]
            write_json(manifest_path(root), manifest)
            runtime_path(root, "logs").rmdir()
            result = health_gate(root)
            self.assertEqual(result["status"], "requires_init")
            self.assertIn("runtime_layout_incomplete", result["reasons"])

    def test_mark_dirty_invalidates_same_day_credential_without_scanning(self):
        from tools.kb.runtime import health_gate, initialize_runtime, mark_dirty

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=True)
            mark_dirty(root, "formal_ingest", ["06_Sub_KB/account.md"])

            with patch("tools.kb.runtime.full_knowledge_fingerprint", side_effect=AssertionError("must not run")):
                result = health_gate(root)

            self.assertEqual(result["status"], "requires_doctor")
            self.assertIn("dirty_generation_changed", result["reasons"])

    def test_maintenance_lock_prevents_concurrent_maintenance(self):
        from tools.kb.runtime import MaintenanceLock, initialize_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)

            with MaintenanceLock(root, "doctor"):
                with self.assertRaises(RuntimeError):
                    with MaintenanceLock(root, "repair"):
                        pass

    def test_concurrent_doctor_returns_structured_maintenance_status(self):
        from tools.kb.runtime import MaintenanceLock, initialize_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=True)

            with MaintenanceLock(root, "repair"):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "tools.kb.cli",
                        "--root",
                        str(root),
                        "doctor",
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    check=False,
                    capture_output=True,
                    text=True,
                )

            self.assertEqual(completed.returncode, 4)
            self.assertEqual(json.loads(completed.stdout)["status"], "maintenance_in_progress")

    def test_stale_lock_is_reclaimed_only_for_dead_local_process(self):
        from tools.kb.runtime import MaintenanceLock, initialize_runtime, maintenance_lock_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            lock = maintenance_lock_path(root)
            lock.mkdir()
            old = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
            write_json(
                lock / "owner.json",
                {
                    "operation": "doctor",
                    "pid": 99999999,
                    "hostname": socket.gethostname(),
                    "started_at": old,
                    "heartbeat_at": old,
                    "owner_token": "dead",
                },
            )

            with MaintenanceLock(root, "repair", stale_after_seconds=1800):
                self.assertTrue(lock.exists())

            self.assertFalse(lock.exists())

    def test_init_is_idempotent_and_respects_knowledge_and_task_boundaries(self):
        from tools.kb.runtime import initialize_runtime, manifest_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "数据" / "secret.json"
            raw.parent.mkdir(parents=True)
            raw.write_text("must not be parsed or hashed", encoding="utf-8")
            formal = root / "02_Viral_Methods" / "method.md"
            formal.parent.mkdir(parents=True)
            formal.write_text("# formal\n", encoding="utf-8")
            active = root / "13_Evolving_Skills" / "active" / "skill.md"
            active.parent.mkdir(parents=True)
            active.write_text("# active\n", encoding="utf-8")
            running = root / "14_KB_System" / "tasks" / "running" / "task_a"
            write_json(
                running / "status.json",
                {
                    "task_id": "task_a",
                    "task_status": "running",
                    "command": "touch SHOULD_NOT_EXIST",
                    "updated_at": "2020-01-01T00:00:00",
                },
            )
            before = {path: path.read_bytes() for path in (raw, formal, active)}
            from tools.kb.scanner import file_sha1 as real_file_sha1

            def guarded_file_sha1(path: Path) -> str:
                if "数据" in path.parts or "00_Inbox" in path.parts:
                    raise AssertionError("raw inputs must not be hashed")
                return real_file_sha1(path)

            with (
                patch("tools.kb.scanner.file_sha1", side_effect=guarded_file_sha1),
                patch("tools.kb.validator.validate_system", return_value={"ok": True, "failed": []}),
            ):
                first = initialize_runtime(root, rebuild=True, migrate=True)
                manifest_first = json.loads(manifest_path(root).read_text(encoding="utf-8"))
                second = initialize_runtime(root, rebuild=True, migrate=True)
                manifest_second = json.loads(manifest_path(root).read_text(encoding="utf-8"))

            self.assertEqual(first["root_id"], second["root_id"])
            self.assertEqual(manifest_first["initialized_at"], manifest_second["initialized_at"])
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertFalse((root / "SHOULD_NOT_EXIST").exists())

    def test_init_quarantines_corrupt_runtime_state_before_replacing_it(self):
        from tools.kb.runtime import credential_path, initialize_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            credential_path(root).write_text("{broken", encoding="utf-8")

            initialize_runtime(root, rebuild=False, migrate=False)

            quarantined = list(runtime_path(root, "quarantine").glob("health_credential*.json"))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0].read_text(encoding="utf-8"), "{broken")

    def test_init_migrates_runtime_outputs_and_separates_long_lived_plan(self):
        from tools.kb.runtime import initialize_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "14_KB_System" / "state" / "kb_registry.json", {"legacy": True})
            running = root / "14_KB_System" / "tasks" / "running" / "task_a"
            write_json(
                running / "status.json",
                {
                    "task_id": "task_a",
                    "task_status": "running",
                    "updated_at": "2020-01-01T00:00:00",
                },
            )
            plan = root / "14_KB_System" / "tasks" / "pending" / "long_plan"
            plan.mkdir(parents=True)
            (plan / "task.md").write_text("# Long-lived plan\n", encoding="utf-8")

            result = initialize_runtime(root, rebuild=False, migrate=True)

            self.assertTrue((runtime_path(root, "state") / "kb_registry.json").exists())
            self.assertTrue((runtime_path(root, "tasks") / "running" / "task_a" / "status.json").exists())
            self.assertTrue((root / "14_KB_System" / "plans" / "long_plan" / "task.md").exists())
            self.assertIn("legacy_runtime_v1", result["applied_migrations"])

    def test_init_dry_run_does_not_create_or_move_files(self):
        from tools.kb.runtime import initialize_runtime, runtime_root

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "14_KB_System" / "state" / "kb_registry.json"
            write_json(legacy, {"legacy": True})

            result = initialize_runtime(root, rebuild=False, migrate=True, dry_run=True)

            self.assertTrue(result["dry_run"])
            self.assertTrue(legacy.exists())
            self.assertFalse(runtime_root(root).exists())

    def test_repair_only_rebuilds_whitelisted_outputs_and_marks_stale(self):
        from tools.kb.runtime import initialize_runtime, repair_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            running = runtime_path(root, "tasks") / "running" / "task_a"
            stale_at = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
            write_json(
                running / "status.json",
                {
                    "task_id": "task_a",
                    "task_name": "dangerous_download",
                    "task_status": "running",
                    "command": "touch SHOULD_NOT_EXIST",
                    "updated_at": stale_at,
                    "heartbeat_at": stale_at,
                },
            )

            result = repair_runtime(root, rebuild=False, stale_after_seconds=600)

            self.assertFalse((root / "SHOULD_NOT_EXIST").exists())
            self.assertTrue((runtime_path(root, "tasks") / "stale" / "task_a").exists())
            status = json.loads(
                (runtime_path(root, "tasks") / "stale" / "task_a" / "status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(status["task_status"], "stale")
            self.assertEqual(result["rerun_task_count"], 0)

    def test_repair_dry_run_does_not_move_stale_task_or_rebuild(self):
        from tools.kb.runtime import initialize_runtime, repair_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            old = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
            write_json(
                runtime_path(root, "tasks") / "running" / "task_a" / "status.json",
                {
                    "task_id": "task_a",
                    "task_status": "running",
                    "heartbeat_at": old,
                    "updated_at": old,
                },
            )

            result = repair_runtime(root, rebuild=True, stale_after_seconds=600, dry_run=True)

            self.assertTrue(result["dry_run"])
            self.assertIn("task_a", result["would_mark_stale"])
            self.assertTrue((runtime_path(root, "tasks") / "running" / "task_a").exists())
            self.assertFalse((root / "14_KB_System/index/knowledge_index.json").exists())

    def test_repair_does_not_expand_raw_input_directories(self):
        from tools.kb.runtime import initialize_runtime, repair_runtime
        from tools.kb.scanner import os as scanner_os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            raw_directories = [root / "00_Inbox", root / "数据"]
            for directory in raw_directories:
                directory.mkdir()
                (directory / "must_not_read.json").write_text(
                    "not valid json and must not be read",
                    encoding="utf-8",
                )
            visited: list[Path] = []
            real_walk = scanner_os.walk

            def tracking_walk(path: Path):
                for current, dirnames, filenames in real_walk(path):
                    visited.append(Path(current))
                    yield current, dirnames, filenames

            with (
                patch("tools.kb.scanner.os.walk", side_effect=tracking_walk),
                patch("tools.kb.scanner.file_sha1", side_effect=AssertionError("raw files must not be hashed")),
                patch("tools.kb.validator.validate_system", return_value={"ok": True, "failed": []}),
            ):
                result = repair_runtime(root, rebuild=True)

            self.assertTrue(result["ok"])
            self.assertTrue(all(directory not in visited for directory in raw_directories))

    def test_active_worker_prevents_running_task_from_being_marked_stale(self):
        from tools.kb.runtime import initialize_runtime, repair_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            old = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
            write_json(
                runtime_path(root, "tasks") / "running" / "task_a" / "status.json",
                {
                    "task_id": "task_a",
                    "task_status": "running",
                    "updated_at": old,
                    "heartbeat_at": old,
                },
            )
            write_json(
                runtime_path(root, "state") / "web_console_state.json",
                {
                    "worker_status": "running",
                    "worker_heartbeat_at": datetime.now().isoformat(timespec="seconds"),
                },
            )

            result = repair_runtime(root, rebuild=False, stale_after_seconds=600)

            self.assertEqual(result["stale_tasks"], [])
            self.assertTrue((runtime_path(root, "tasks") / "running" / "task_a").exists())

    def test_healthy_doctor_renews_expired_shared_credential(self):
        from tools.kb.runtime import credential_path, doctor_runtime, initialize_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_runtime(root, rebuild=False, migrate=False)
            credential = json.loads(credential_path(root).read_text(encoding="utf-8"))
            credential["day"] = "2020-01-01"
            write_json(credential_path(root), credential)

            with patch("tools.kb.validator.validate_system", return_value={"ok": True, "failed": []}):
                result = doctor_runtime(root)

            self.assertEqual(result["status"], "healthy")
            self.assertTrue(credential_path(root).exists())

    def test_scanner_excludes_runtime_tree(self):
        from tools.kb.runtime import initialize_runtime
        from tools.kb.scanner import scan_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# KB\n", encoding="utf-8")
            initialize_runtime(root, rebuild=False, migrate=False)

            result = scan_files(root)

            self.assertFalse(any(item["path"].startswith("14_KB_System/runtime/") for item in result["files"]))

    def test_validate_system_is_read_only_by_default(self):
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = validate_system(root)

            self.assertFalse(result["ok"])
            self.assertFalse((root / "14_KB_System" / "runtime" / "reports").exists())


if __name__ == "__main__":
    unittest.main()
