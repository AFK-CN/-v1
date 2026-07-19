import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


class KBSystemTests(unittest.TestCase):
    def test_status_schemas_are_separate(self):
        from tools.kb.schemas import CONTENT_STATUSES, TASK_STATUSES, validate_content_status, validate_task_status

        self.assertIn("review_needed", CONTENT_STATUSES)
        self.assertIn("paused", TASK_STATUSES)
        self.assertNotIn("paused", CONTENT_STATUSES)
        self.assertNotIn("review_needed", TASK_STATUSES)
        self.assertEqual(validate_content_status("candidate"), "candidate")
        self.assertEqual(validate_task_status("running"), "running")
        with self.assertRaises(ValueError):
            validate_content_status("paused")
        with self.assertRaises(ValueError):
            validate_task_status("approved")

    def test_scanner_indexes_files_and_marks_cleanup_candidates_without_deleting(self):
        from tools.kb.scanner import scan_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "00_Inbox").mkdir()
            (root / "02_Viral_Methods").mkdir()
            (root / ".DS_Store").write_text("mac", encoding="utf-8")
            (root / "feishu-auth-qrcode.png").write_bytes(b"png")
            (root / "02_Viral_Methods" / "method.md").write_text("# Method\n", encoding="utf-8")
            (root / "00_Inbox" / "raw.json").write_text("[]", encoding="utf-8")

            result = scan_files(root)

            paths = {item["path"] for item in result["files"]}
            cleanup = {item["path"] for item in result["cleanup_candidates"]}
            raw = {item["path"] for item in result["files"] if item["is_raw_input"]}
            self.assertIn("02_Viral_Methods/method.md", paths)
            self.assertIn(".DS_Store", cleanup)
            self.assertIn("feishu-auth-qrcode.png", cleanup)
            self.assertIn("00_Inbox/raw.json", raw)
            self.assertTrue((root / ".DS_Store").exists())

    def test_asset_builder_uses_existing_topic_schema_with_account_and_source_url(self):
        from tools.kb.asset_builder import build_candidate_assets

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "知识账号甲"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#创业 普通人先行动",
                    "desc": "不要想太多，先做一个小实验",
                    "nickname": "知识账号甲",
                    "liked_count": "100",
                    "collected_count": "80",
                    "comment_count": "20",
                    "share_count": "40",
                    "aweme_url": "https://www.douyin.com/video/a1",
                    "video_download_url": "https://download.example/a1.mp4",
                }
            ]
            (data_dir / "creator_contents.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            result = build_candidate_assets(root, top_n=10)

            self.assertGreaterEqual(result["candidate_topics_count"], 1)
            candidate_path = root / "10_Knowledge" / "candidates" / "generated_assets" / "candidate_topics.jsonl"
            top10_path = root / "10_Knowledge" / "candidates" / "generated_assets" / "candidate_top10_by_category.md"
            candidates = [json.loads(line) for line in candidate_path.read_text(encoding="utf-8").splitlines()]
            candidate = next(item for item in candidates if item["source_id"] == "a1")
            top10 = top10_path.read_text(encoding="utf-8")
            self.assertEqual(candidate["account_name"], "知识账号甲")
            self.assertEqual(candidate["source_url"], "https://www.douyin.com/video/a1")
            self.assertEqual(candidate["状态"], "candidate")
            self.assertIn("account_name", candidate)
            self.assertIn("source_id", candidate)
            self.assertNotIn("video_download_url", candidate)
            self.assertIn("https://www.douyin.com/video/a1", top10)
            self.assertNotIn("https://download.example/a1.mp4", top10)

    def test_task_runner_writes_required_manual_wakeup_logs(self):
        from tools.kb.task_runner import create_task, finish_task

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = create_task(root, "scan_kb", command="python -m tools.kb.cli scan")
            finish_task(root, task["task_id"], "done", summary="scan completed", outputs=["10_Knowledge/evidence/index/knowledge_index.json"])

            task_dir = root / "00_System" / "runtime" / "tasks" / "done" / task["task_id"]
            self.assertTrue((task_dir / "status.json").exists())
            self.assertTrue((task_dir / "action_log.md").exists())
            self.assertTrue((task_dir / "summary_report.md").exists())
            self.assertTrue((task_dir / "errors.log").exists())
            self.assertTrue((task_dir / "outputs_manifest.json").exists())
            status = json.loads((task_dir / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["task_status"], "done")

    def test_runtime_cli_exposes_init_health_gate_doctor_repair_and_mark_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            init = subprocess.run(
                [sys.executable, "-m", "tools.kb.cli", "--root", str(root), "init", "--no-rebuild", "--no-migrate"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )
            gate = subprocess.run(
                [sys.executable, "-m", "tools.kb.cli", "--root", str(root), "health-gate"],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )
            dirty = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(root),
                    "mark-dirty",
                    "--reason",
                    "test",
                ],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(init.returncode, 0)
            self.assertEqual(json.loads(gate.stdout)["status"], "healthy")
            self.assertEqual(json.loads(dirty.stdout)["dirty_generation"], 1)

    def test_controller_account_learning_uses_generic_profile_tools(self):
        controller = json.loads(Path("00_System/shareable/index/controller_routes.json").read_text(encoding="utf-8"))
        routes = {route["id"]: route for route in controller["routes"]}
        account_learning_tools = routes["account_learning"]["tools"]

        self.assertIn("tools.kb.cli account-learning-init", account_learning_tools)
        self.assertIn("tools.kb.cli account-learning-validate-card", account_learning_tools)
        self.assertIn("tools.kb.cli account-skills-sync", account_learning_tools)
        self.assertNotIn("tools.knowledge_account_a_account_ingest", account_learning_tools)

    def test_indexer_writes_machine_and_human_indexes(self):
        from tools.kb.indexer import write_indexes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "知识库入口.md").write_text("# 入口\n", encoding="utf-8")
            formal_account = root / "10_Knowledge" / "formal" / "accounts" / "sample" / "skill"
            formal_account.mkdir(parents=True)
            (formal_account / "SKILL.md").write_text("# 账号 Skill\n", encoding="utf-8")
            (root / "05_Sub_KB_Candidates").mkdir()
            (root / "05_Sub_KB_Candidates" / "candidate.md").write_text("# 候选\n", encoding="utf-8")
            runtime_assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            runtime_assets.mkdir(parents=True)
            (runtime_assets / "candidate_topics.jsonl").write_text('{"topic_id":"t1"}\n', encoding="utf-8")
            (runtime_assets / "candidate_method_cards.md").write_text("# candidate\n", encoding="utf-8")
            (root / "00_Inbox").mkdir()
            (root / "00_Inbox" / "raw.json").write_text("[]", encoding="utf-8")

            result = write_indexes(root)

            self.assertEqual(result["index_files"], 10)
            index_dir = root / "10_Knowledge" / "evidence" / "index"
            knowledge_index = index_dir / "knowledge_index.json"
            summary_index = index_dir / "knowledge_index_summary.md"
            formal_index = index_dir / "formal_knowledge_index.json"
            candidate_index = index_dir / "candidate_asset_index.json"
            raw_blocked_index = index_dir / "raw_blocked_index.json"
            task_index = root / "00_System" / "shareable" / "index" / "task_entry_index.md"
            data = json.loads(knowledge_index.read_text(encoding="utf-8"))
            self.assertTrue(any(item["path"] == "知识库入口.md" for item in data["files"]))
            self.assertIn("默认不要读取全量索引", summary_index.read_text(encoding="utf-8"))
            formal = json.loads(formal_index.read_text(encoding="utf-8"))
            self.assertTrue(
                any(item["path"] == "10_Knowledge/formal/accounts/sample/skill/SKILL.md" for item in formal["items"])
            )
            candidate = json.loads(candidate_index.read_text(encoding="utf-8"))
            candidate_paths = {item["path"] for item in candidate["items"]}
            self.assertIn("05_Sub_KB_Candidates/candidate.md", candidate_paths)
            self.assertIn("10_Knowledge/candidates/generated_assets/candidate_topics.jsonl", candidate_paths)
            self.assertIn("10_Knowledge/candidates/generated_assets/candidate_method_cards.md", candidate_paths)
            self.assertFalse(any(item["path"].startswith("00_System/runtime/") for item in data["files"]))
            raw_blocked = json.loads(raw_blocked_index.read_text(encoding="utf-8"))
            self.assertTrue(any(item["path"] == "00_Inbox/" for item in raw_blocked["items"]))
            self.assertIn("其他项目调用", task_index.read_text(encoding="utf-8"))

    def test_layer_map_separates_system_skills_candidates_and_private_boundaries(self):
        from tools.kb.indexer import write_indexes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "00_System" / "shareable" / "config"
            config_dir.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            layer_map = {
                "version": 1,
                "default_blocked_dirs": ["数据/", "00_Inbox/", "99_Archive/", "80_Local/", "20_User/private/"],
                "formal_knowledge_roots": ["10_Knowledge/formal/", "02_Viral_Methods/"],
                "candidate_asset_roots": ["10_Knowledge/candidates/", "05_Sub_KB_Candidates/"],
                "system_skill_roots": ["00_System/shareable/skills/active/"],
            }
            (config_dir / "layer_map.json").write_text(json.dumps(layer_map, ensure_ascii=False), encoding="utf-8")
            (root / "10_Knowledge" / "formal" / "accounts" / "sample").mkdir(parents=True)
            (root / "10_Knowledge" / "formal" / "accounts" / "sample" / "account.md").write_text(
                "# account\n", encoding="utf-8"
            )
            (root / "10_Knowledge" / "candidates" / "topics").mkdir(parents=True)
            (root / "10_Knowledge" / "candidates" / "topics" / "candidate.md").write_text("# candidate\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "skills" / "active").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skills" / "active" / "JSON入库Skill_v1.md").write_text("# skill\n", encoding="utf-8")
            (root / "80_Local").mkdir()
            (root / "80_Local" / "paths.md").write_text("# local\n", encoding="utf-8")

            write_indexes(root)

            index_dir = root / "10_Knowledge" / "evidence" / "index"
            formal = json.loads((index_dir / "formal_knowledge_index.json").read_text(encoding="utf-8"))
            candidate = json.loads((index_dir / "candidate_asset_index.json").read_text(encoding="utf-8"))
            full_index = json.loads((index_dir / "knowledge_index.json").read_text(encoding="utf-8"))
            raw_blocked = json.loads((index_dir / "raw_blocked_index.json").read_text(encoding="utf-8"))
            formal_paths = {item["path"] for item in formal["items"]}
            candidate_paths = {item["path"] for item in candidate["items"]}
            scopes = {item["path"]: item["calling_scope"] for item in full_index["files"]}
            blocked_paths = {item["path"] for item in raw_blocked["items"]}

            self.assertIn("10_Knowledge/formal/accounts/sample/account.md", formal_paths)
            self.assertNotIn("00_System/shareable/skills/active/JSON入库Skill_v1.md", formal_paths)
            self.assertIn("10_Knowledge/candidates/topics/candidate.md", candidate_paths)
            self.assertEqual(scopes["00_System/shareable/skills/active/JSON入库Skill_v1.md"], "system_internal")
            self.assertNotIn("80_Local/paths.md", scopes)
            self.assertIn("80_Local/", blocked_paths)

    def test_candidate_index_marks_account_assets_as_candidate_knowledge(self):
        from tools.kb.indexer import write_indexes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "00_System" / "shareable" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "layer_map.json").write_text(
                json.dumps(
                    {
                        "candidate_asset_roots": ["10_Knowledge/candidates/"],
                        "formal_knowledge_roots": ["10_Knowledge/formal/"],
                        "default_blocked_dirs": ["数据/"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            card_dir = root / "10_Knowledge" / "candidates" / "learning_cards" / "learned_cards" / "sample_account" / "方向" / "cards"
            card_dir.mkdir(parents=True)
            (card_dir / "01_card.md").write_text("# card\n", encoding="utf-8")

            write_indexes(root)

            candidate = json.loads((root / "10_Knowledge" / "evidence" / "index" / "candidate_asset_index.json").read_text(encoding="utf-8"))
            item = next(row for row in candidate["items"] if row["path"].endswith("01_card.md"))
            self.assertEqual(item["knowledge_layer"], "candidate_knowledge")
            self.assertEqual(item["account_id"], "sample_account")

    def test_system_cleaner_rewrites_legacy_paths_with_layer_map(self):
        from tools.kb.system_cleaner import audit_system_boundaries, rewrite_legacy_path_references

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "00_System" / "shareable" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "layer_map.json").write_text(
                json.dumps(
                    {
                        "legacy_mapping": {
                            "01_Case_Cleaning/video_learning/learned_cards": "10_Knowledge/candidates/learning_cards/learned_cards",
                            "01_Case_Cleaning/video_learning/video_artifacts": "00_System/runtime/cache/video_learning/video_artifacts",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            scope_path = root / "10_Knowledge" / "candidates" / "account_assets" / "content_rough_scan" / "sample_account" / "deep_learning_scope.json"
            scope_path.parent.mkdir(parents=True)
            scope_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "card_path": "01_Case_Cleaning/video_learning/learned_cards/sample_account/方向/cards/01.md",
                                "video": "01_Case_Cleaning/video_learning/video_artifacts/douyin_1/source.mp4",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = rewrite_legacy_path_references(root)
            audit = audit_system_boundaries(root)

            text = scope_path.read_text(encoding="utf-8")
            self.assertEqual(result["changed_file_count"], 1)
            self.assertIn("10_Knowledge/candidates/learning_cards/learned_cards/sample_account/方向/cards/01.md", text)
            self.assertIn("00_System/runtime/cache/video_learning/video_artifacts/douyin_1/source.mp4", text)
            self.assertEqual(audit["legacy_path_references"], [])

    def test_system_boundary_audit_rejects_account_knowledge_in_rules(self):
        from tools.kb.system_cleaner import audit_system_boundaries

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "20_User" / "config"
            rules_dir = root / "00_System" / "shareable" / "rules"
            config_dir.mkdir(parents=True)
            rules_dir.mkdir(parents=True)
            (config_dir / "content_rough_scan_profiles.json").write_text(
                json.dumps({"profiles": {"sample_account": {"account_name": "样例账号"}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (rules_dir / "账号学习标准工作流.md").write_text(
                "通用规则不应读取 10_Knowledge/candidates/learning_cards/learned_cards/sample_account/card.md，也不应写样例账号模板。\n",
                encoding="utf-8",
            )

            result = audit_system_boundaries(root)

            self.assertFalse(result["ok"])
            violation_types = {item["type"] for item in result["violations"]}
            self.assertIn("account_token_in_system_rule", violation_types)
            self.assertIn("candidate_knowledge_link_in_system_rule", violation_types)

    def test_scanner_protects_data_directory_without_expanding_contents(self):
        from tools.kb.scanner import scan_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json"
            data_dir.mkdir(parents=True)
            (data_dir / "large.json").write_text("[{}]", encoding="utf-8")
            (root / "README.md").write_text("# KB\n", encoding="utf-8")

            result = scan_files(root)

            paths = {item["path"] for item in result["files"]}
            protected = {item["path"] for item in result["protected_directories"]}
            self.assertIn("README.md", paths)
            self.assertNotIn("数据/douyin/json/large.json", paths)
            self.assertIn("数据", protected)

    def test_reorganizer_plans_root_cleanup_without_touching_submission_dirs(self):
        from tools.kb.reorganizer import plan_reorganization

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "00_System" / "shareable" / "config").mkdir(parents=True)
            (root / "00_System" / "shareable" / "config" / "layer_map.json").write_text(
                json.dumps({"legacy_mapping": {"13_Evolving_Skills": "00_System/shareable/skills"}}),
                encoding="utf-8",
            )
            (root / "00_Inbox").mkdir()
            (root / "数据").mkdir()
            (root / "13_Evolving_Skills").mkdir()
            (root / "10_Knowledge").mkdir()
            (root / "20_User").mkdir()
            (root / "80_Local").mkdir()
            (root / "90_Temp").mkdir()
            (root / "JSON入库清洗规则.md").write_text("# rule\n", encoding="utf-8")
            (root / "验收报告_2026-06-14.md").write_text("# report\n", encoding="utf-8")
            (root / "feishu_doc_read").mkdir()
            (root / "feishu_doc_read" / "doc.md").write_text("# imported\n", encoding="utf-8")
            (root / ".DS_Store").write_text("mac", encoding="utf-8")

            plan = plan_reorganization(root)

            actions = {item["path"]: item for item in plan["actions"]}
            self.assertEqual(actions["JSON入库清洗规则.md"]["action"], "move")
            self.assertEqual(
                actions["JSON入库清洗规则.md"]["target"],
                "00_System/shareable/skills/active/content-processing/references/json-cleaning.md",
            )
            self.assertEqual(actions["验收报告_2026-06-14.md"]["target"], "00_System/runtime/reports/history/验收报告_2026-06-14.md")
            self.assertEqual(actions["feishu_doc_read"]["action"], "delete_candidate")
            self.assertEqual(actions[".DS_Store"]["action"], "delete_candidate")
            self.assertNotIn("00_Inbox", actions)
            self.assertNotIn("00_System", actions)
            self.assertNotIn("10_Knowledge", actions)
            self.assertNotIn("20_User", actions)
            self.assertEqual(actions["80_Local"]["target"], "20_User/local/legacy_80_local")
            self.assertNotIn("90_Temp", actions)
            self.assertNotIn("数据", actions)
            preview = {item["source"]: item for item in plan["migration_preview"]}
            self.assertEqual(preview["13_Evolving_Skills"]["target"], "00_System/shareable/skills")

    def test_reorganizer_keeps_github_as_engineering_control_directory(self):
        from tools.kb.reorganizer import plan_reorganization

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)

            plan = plan_reorganization(root)

        actions = {item["path"]: item["action"] for item in plan["actions"]}
        self.assertNotIn(".github", actions)

    def test_layer_structure_initializer_creates_target_skeleton(self):
        from tools.kb.reorganizer import initialize_layer_structure

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = initialize_layer_structure(root)

            self.assertGreater(result["created"], 0)
            for relative in (
                "00_System/shareable",
                "00_System/runtime/state",
                "10_Knowledge/formal",
                "10_Knowledge/candidates",
                "10_Knowledge/evidence",
                "20_User/config",
                "20_User/data",
                "20_User/feedback",
                "20_User/private",
                "20_User/local",
                "90_Temp/inbox",
            ):
                self.assertTrue((root / relative).is_dir(), relative)
            self.assertTrue((root / result["report"]).exists())

    def test_validate_system_checks_call_rules_and_core_outputs(self):
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)
            result = validate_system(root)
            self.assertTrue(result["ok"], result["failed"])
            self.assertEqual(result["health"]["route_count"], 10)
            self.assertEqual(result["health"]["agent_count"], 8)
            self.assertEqual(result["health"]["contract_count"], 10)
            self.assertTrue(result["health"]["production_memory_ok"])
        return


    def test_knowledge_base_skill_package_is_a_single_index_first_entry(self):
        skill = Path("00_System/shareable/skill_packages/knowledge-base/SKILL.md")
        ui = Path("00_System/shareable/skill_packages/knowledge-base/agents/openai.yaml")
        rules = Path("00_System/shareable/skill_packages/knowledge-base/references/calling-rules.md")
        zh_skill = Path("00_System/shareable/skill_packages/knowledge-base-zh/SKILL.md")
        zh_ui = Path("00_System/shareable/skill_packages/knowledge-base-zh/agents/openai.yaml")

        self.assertTrue(skill.exists())
        self.assertTrue(ui.exists())
        self.assertTrue(rules.exists())
        self.assertTrue(zh_skill.exists())
        self.assertTrue(zh_ui.exists())
        skill_text = skill.read_text(encoding="utf-8")
        ui_text = ui.read_text(encoding="utf-8")
        zh_skill_text = zh_skill.read_text(encoding="utf-8")
        zh_ui_text = zh_ui.read_text(encoding="utf-8")
        self.assertIn("name: knowledge-base", skill_text)
        self.assertIn("<KB_ROOT>/00_System/shareable/index/controller_routes.json", skill_text)
        self.assertIn("<KB_ROOT>/00_System/shareable/index/task_entry_index.md", skill_text)
        self.assertIn("Do not scan the whole knowledge base", skill_text)
        self.assertIn("logical AI roles", skill_text)
        self.assertIn("display_name: \"知识库\"", ui_text)
        self.assertIn("总控", ui_text)
        self.assertIn("name: knowledge-base-zh", zh_skill_text)
        self.assertIn("@知识库", zh_skill_text)
        self.assertIn("controller_routes.json", zh_skill_text)
        self.assertIn("display_name: \"知识库\"", zh_ui_text)
        self.assertIn("总控", zh_ui_text)
        self.assertIn("search-candidates", zh_skill_text)

    def test_skill_packages_are_deterministically_generated_from_shared_contract(self):
        from tools.kb.skill_package import load_skill_contract, skill_package_drift, write_skill_packages

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = root / "00_System" / "shareable" / "config" / "skill_contract.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "kb_root": "/tmp/kb",
                        "startup_read_order": ["知识库入口.md", "00_System/shareable/index/task_entry_index.md"],
                        "blocked_dirs": ["数据/", "00_Inbox/"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = write_skill_packages(root)

            self.assertEqual(result["written_count"], 6)
            self.assertEqual(load_skill_contract(root)["startup_read_order"][0], "知识库入口.md")
            self.assertEqual(skill_package_drift(root), [])
            en = root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "SKILL.md"
            zh = root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "SKILL.md"
            self.assertIn("Do not scan the whole knowledge base", en.read_text(encoding="utf-8"))
            self.assertIn("logical AI roles", en.read_text(encoding="utf-8"))
            self.assertIn("@知识库", zh.read_text(encoding="utf-8"))
            self.assertIn("search-candidates", zh.read_text(encoding="utf-8"))

    def test_skill_install_syncs_both_packages_and_machine_root_locator(self):
        from tools.kb.skill_package import installed_skill_package_status, sync_installed_skill_packages

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills"
            result = sync_installed_skill_packages(Path.cwd(), target)
            status = installed_skill_package_status(Path.cwd(), target)

            self.assertTrue(result["ok"])
            self.assertTrue(status["ok"])
            self.assertTrue(status["bound_to_root"])
            self.assertEqual(status["status"], "synced")
            for package in ("knowledge-base", "knowledge-base-zh"):
                locator = json.loads((target / package / "references" / "kb-root.json").read_text(encoding="utf-8"))
                self.assertEqual(Path(locator["kb_root"]), Path.cwd())

    def test_validate_system_detects_generated_skill_package_drift(self):
        from tools.kb.skill_package import write_skill_packages
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)
            write_skill_packages(root)
            skill = root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nmanual drift\n", encoding="utf-8")

            result = validate_system(root)

            self.assertIn("skill_package_drift:00_System/shareable/skill_packages/knowledge-base-zh/SKILL.md", result["failed"])

    def test_shareable_portability_detects_legacy_and_machine_paths(self):
        from tools.kb.validator import validate_shareable_portability

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "00_System/shareable/skills/rollback.md"
            target.parent.mkdir(parents=True)
            target.write_text(
                "从 13_Evolving_Skills/history 回滚，本机路径 /Volumes/AFK/knowledge。\n",
                encoding="utf-8",
            )

            result = validate_shareable_portability(root)

            self.assertEqual(result["legacy_references"][0]["token"], "13_Evolving_Skills")
            self.assertTrue(result["absolute_paths"][0]["token"].startswith("/Volumes/"))

    def test_validate_system_requires_account_learning_skill_reference(self):
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)
            (root / "00_System/shareable/skills/active/account-learning/references/seven-stage-gates.md").unlink()

            result = validate_system(root)

        self.assertIn(
            "account_gates_missing_account_overview",
            result["failed"],
        )

    def test_account_learning_skill_uses_seven_stage_skill_delivery(self):
        skill = Path("00_System/shareable/skills/active/account-learning/SKILL.md").read_text(encoding="utf-8")
        gates = Path(
            "00_System/shareable/skills/active/account-learning/references/seven-stage-gates.md"
        ).read_text(encoding="utf-8")
        packaging = Path(
            "00_System/shareable/skills/active/account-learning/references/account-skill-packaging.md"
        ).read_text(encoding="utf-8")
        processing = Path(
            "00_System/shareable/skills/active/content-processing/references/pipeline.md"
        ).read_text(encoding="utf-8")

        self.assertIn("seven-stage-gates.md", skill)
        self.assertIn("候选交付", gates)
        self.assertIn("三重验证", gates)
        self.assertIn("压力测试", gates)
        self.assertIn("ACCOUNT_SKILL_MANIFEST.json", packaging)
        self.assertIn("callable=false", packaging)
        self.assertIn("完整粗学与选题池", processing)
        self.assertIn("deep_learning_plan.json", processing)

    def test_task_entry_index_describes_three_core_skills_and_user_layer(self):
        text = Path("00_System/shareable/index/task_entry_index.md").read_text(encoding="utf-8")

        self.assertIn("content-processing/SKILL.md", text)
        self.assertIn("account-learning/SKILL.md", text)
        self.assertIn("content-review/SKILL.md", text)
        self.assertIn("account_skill_registry.json", text)
        self.assertIn("topic-memory-check", text)
        self.assertIn("模型不读取完整数据库", text)

    def test_controller_declares_agents_as_logical_roles_not_process_boundaries(self):
        routes_path = Path("00_System/shareable/index/controller_routes.json")
        payload = json.loads(routes_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["agent_model"], "logical_roles")
        self.assertIn("真实边界", payload["agent_model_notice"])
        self.assertTrue(all(agent.get("kind") == "logical_role" for agent in payload["agents"]))

    def test_rule_authority_document_assigns_each_rule_family_to_one_source(self):
        authority = Path("00_System/shareable/rules/规则权威源.md")
        self.assertTrue(authority.exists())
        text = authority.read_text(encoding="utf-8")

        self.assertIn("controller_routes.json", text)
        self.assertIn("skill_contract.json", text)
        self.assertIn("production_memory_schema.json", text)
        self.assertIn("同一规则只维护一份权威源", text)

    def test_end_to_end_user_call_chain_acceptance(self):
        from tools.kb.account_skills import sync_registry
        from tools.kb.call_resolver import resolve_call
        from tools.kb.runtime import health_gate, initialize_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)
            account_center = root / "10_Knowledge" / "formal" / "accounts" / "知识账号甲"
            account_center.mkdir(parents=True)
            skill = account_center / "skill" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: account-test\ndescription: Use for account test production.\n---\n\n"
                "topic-memory-check topic-memory-record production-memory-record\n",
                encoding="utf-8",
            )
            for name in ("production.md", "style.md", "boundaries.md", "acceptance.md"):
                target = skill.parent / "references" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# {name}\n", encoding="utf-8")
            account_center.joinpath("ACCOUNT_SKILL_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "account_skill_id": "test-account",
                        "account_name": "知识账号甲",
                        "platform": "抖音",
                        "skill_name": "account-test",
                        "version": "1.0",
                        "status": "active",
                        "aliases": ["知识账号甲"],
                        "canonical_skill_path": "10_Knowledge/formal/accounts/知识账号甲/skill/SKILL.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index = root / "10_Knowledge" / "evidence" / "index"
            system_index = root / "00_System" / "shareable" / "index"
            account_index = {
                "accounts": [
                    {
                        "account_id": "test-account",
                        "account_name": "知识账号甲",
                        "formal_account_dir": "10_Knowledge/formal/accounts/知识账号甲",
                        "directions": [{"direction": "赚钱"}],
                    }
                ]
            }
            index.joinpath("account_knowledge_index.json").write_text(json.dumps(account_index, ensure_ascii=False), encoding="utf-8")
            sync_registry(root)
            routes_path = root / "00_System" / "shareable" / "index" / "controller_routes.json"
            routes = json.loads(routes_path.read_text(encoding="utf-8"))
            topic_route = next(route for route in routes["routes"] if route["id"] == "topic_generation")
            topic_route["triggers"] = ["我要出选题", "出选题"]
            topic_route["read_first"] = ["知识库入口.md", "00_System/shareable/index/task_entry_index.md"]
            routes_path.write_text(json.dumps(routes, ensure_ascii=False), encoding="utf-8")
            runtime_assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            runtime_assets.mkdir(parents=True)
            runtime_assets.joinpath("candidate_topics.jsonl").write_text(
                json.dumps(
                    {
                        "platform": "douyin",
                        "account_name": "知识账号甲",
                        "领域": "赚钱",
                        "source_id": "a1",
                        "source_url": "https://example.com/a1",
                        "可生成标题": ["普通人赚钱选题"],
                        "score": 100,
                        "rank": 1,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            initialize_runtime(root, rebuild=False, migrate=True)
            gate = health_gate(root)
            result = resolve_call(root, "@知识库 知识账号甲 赚钱 我要出选题 1个")

            self.assertEqual(gate["status"], "healthy")
            self.assertTrue(result["ok"])
            self.assertEqual(result["route_id"], "topic_generation")
            self.assertEqual(result["search"]["status"], "not_requested")
            self.assertEqual(result["search"]["count"], 0)
            self.assertIn("10_Knowledge/formal/accounts/知识账号甲/skill/SKILL.md", result["read_paths"])
            self.assertTrue(result["account_skill"]["ok"])
            self.assertEqual(result["missing_read_paths"], [])
            self.assertEqual(result["output_contract"]["route_id"], "topic_generation")
            self.assertEqual(result["knowledge_boundary"]["raw_data"], "blocked_by_default")

    def _write_minimum_valid_system_fixture(self, root: Path) -> None:
        from tools.kb.user_layer import initialize_user_layer

        repo = Path.cwd()
        shutil.copytree(repo / "00_System" / "shareable", root / "00_System" / "shareable")
        shutil.copytree(repo / "tools", root / "tools", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(repo / "tests", root / "tests", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in (
            "知识库入口.md",
            "README.md",
            "VERSION",
            "CHANGELOG.md",
            "LICENSE",
            "LICENSE_SCOPE.md",
            "NOTICE",
        ):
            shutil.copy2(repo / name, root / name)
        for name in (".gitignore", "requirements.txt", "requirements-video-learning.txt", "requirements-ocr.txt"):
            shutil.copy2(repo / name, root / name)
        workflow = root / ".github/workflows/kb-system.yml"
        workflow.parent.mkdir(parents=True)
        shutil.copy2(repo / ".github/workflows/kb-system.yml", workflow)
        evidence = root / "10_Knowledge" / "evidence" / "index"
        evidence.mkdir(parents=True, exist_ok=True)
        for name in (
            "knowledge_index.json",
            "knowledge_index_summary.md",
            "formal_knowledge_index.json",
            "candidate_asset_index.json",
            "raw_blocked_index.json",
            "account_knowledge_index.json",
            "account_knowledge_index.md",
        ):
            shutil.copy2(repo / "10_Knowledge" / "evidence" / "index" / name, evidence / name)
        evidence.joinpath("account_knowledge_index.json").write_text(
            json.dumps({"generated_at": "fixture", "accounts": [], "discovery_errors": []}),
            encoding="utf-8",
        )
        evidence.joinpath("account_knowledge_index.md").write_text("# 账号知识总索引\n", encoding="utf-8")
        initialize_user_layer(root)
        return


    def test_controller_routes_define_required_agents_and_routes(self):
        routes_path = Path("00_System/shareable/index/controller_routes.json")
        self.assertTrue(routes_path.exists())
        payload = json.loads(routes_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["default_entry"], "@知识库")
        self.assertTrue(payload["global_priority"])
        agent_ids = {agent["id"] for agent in payload["agents"]}
        route_ids = {route["id"] for route in payload["routes"]}
        self.assertEqual(
            agent_ids,
            {
                "controller",
                "content_processor",
                "account_learner",
                "account_skill_resolver",
                "account_producer",
                "reviewer",
                "auditor",
                "formal_retriever",
            },
        )
        self.assertIn("content_processing", route_ids)
        self.assertIn("account_learning", route_ids)
        self.assertIn("content_review", route_ids)
        self.assertIn("user_setup", route_ids)
        self.assertIn("system_audit", route_ids)
        self.assertIn("creator_db_export", route_ids)
        self.assertIn("formal_retrieval", route_ids)
        self.assertEqual(payload["clarification_policy"]["max_questions"], 3)
        topic_route = next(route for route in payload["routes"] if route["id"] == "topic_generation")
        script_route = next(route for route in payload["routes"] if route["id"] == "script_generation")
        export_route = next(route for route in payload["routes"] if route["id"] == "creator_db_export")
        formal_route = next(route for route in payload["routes"] if route["id"] == "formal_retrieval")
        self.assertIn("我要出选题", topic_route["triggers"])
        self.assertIn("账号或明确不使用账号 Skill", topic_route["minimum_required"])
        self.assertIn("使用哪个账号 Skill？", topic_route["clarify_when_missing"])
        self.assertIn("我要写文案", script_route["triggers"])
        self.assertIn("输出形式", script_route["minimum_required"])
        self.assertIn("导出博主数据", export_route["triggers"])
        self.assertIn("博主名", export_route["minimum_required"])
        self.assertIn("tools.kb.cli export-creator-db", export_route["tools"])
        self.assertIn("tools.kb.cli search-formal", formal_route["tools"])
        self.assertEqual(formal_route["write_policy"].split("；", 1)[0], "只写可复现 runtime 检索缓存")
        for route in payload["routes"]:
            self.assertIn("triggers", route)
            self.assertIn("read_first", route)
            self.assertIn("output_contract", route)
            self.assertIn("write_policy", route)

    def test_legacy_agent_registry_module_is_removed(self):
        self.assertFalse(Path("tools/kb/agent_registry.py").exists())
        return


    def test_legacy_memory_candidate_module_is_removed(self):
        self.assertFalse(Path("tools/kb/memory.py").exists())
        return


    def test_cli_no_longer_exposes_auto_memory(self):
        completed = subprocess.run(
            [sys.executable, "-m", "tools.kb.cli", "--help"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotIn("\n    memory ", completed.stdout)
        return


    def test_cli_does_not_recreate_legacy_memory_directories(self):
        self.assertFalse(Path("20_User/syncable/memory").exists())
        self.assertFalse(Path("00_System/shareable/memory").exists())
        return


    def test_production_memory_replaces_session_auto_memory(self):
        self.assertTrue(Path("tools/kb/production_memory.py").exists())
        self.assertTrue(Path("00_System/shareable/config/production_memory_schema.json").exists())
        return


    def test_user_console_exposes_simple_at_knowledge_base_prompts(self):
        console = Path("00_System/shareable/docs/project_use/用户操作台.md")
        self.assertTrue(console.exists())
        text = console.read_text(encoding="utf-8")
        self.assertIn("@知识库 + 你的需求", text)
        self.assertIn("我要出选题", text)
        self.assertIn("我要写文案", text)
        self.assertIn("我要处理资料", text)
        self.assertIn("我要学习账号", text)
        self.assertIn("我要复盘", text)
        self.assertIn("账号 Skill", text)
        self.assertIn("生产记忆", text)
        self.assertIn("最多追问 3 个问题", text)
        self.assertIn("候选学习成果不可用于生产", text)

    def test_output_contracts_cover_runtime_routes(self):
        contracts = Path("00_System/shareable/config/output_contracts.json")
        doc = Path("00_System/shareable/rules/输出契约.md")
        self.assertTrue(contracts.exists())
        self.assertTrue(doc.exists())
        payload = json.loads(contracts.read_text(encoding="utf-8"))
        self.assertEqual(payload["clarification_policy"]["max_questions"], 3)
        route_ids = {contract["route_id"] for contract in payload["contracts"]}
        self.assertIn("topic_generation", route_ids)
        self.assertIn("script_generation", route_ids)
        self.assertIn("account_learning", route_ids)
        self.assertIn("external_use", route_ids)
        self.assertIn("system_audit", route_ids)
        for contract in payload["contracts"]:
            self.assertTrue(contract["required_fields"])
            self.assertTrue(contract["must_not"])
        account_contract = next(contract for contract in payload["contracts"] if contract["route_id"] == "account_learning")
        self.assertIn("流派观察", account_contract["required_fields"])
        self.assertIn("账号Skill候选", account_contract["required_fields"])
        self.assertIn("不直接激活账号 Skill", account_contract["must_not"])
        script_contract = next(contract for contract in payload["contracts"] if contract["route_id"] == "script_generation")
        self.assertIn("account_skill_id", script_contract["required_fields"])
        self.assertIn("topic_id", script_contract["required_fields"])
        self.assertIn("content_id", script_contract["required_fields"])
        self.assertIn("不绕过账号 Skill", script_contract["must_not"])
        self.assertIn("机器权威源", doc.read_text(encoding="utf-8"))

    def test_script_generation_route_supports_post_topic_image_text_generation(self):
        payload = json.loads(Path("00_System/shareable/index/controller_routes.json").read_text(encoding="utf-8"))
        route = next(route for route in payload["routes"] if route["id"] == "script_generation")
        self.assertIn("图文", route["triggers"])
        self.assertIn("20_User/config/account_skill_registry.json", route["read_first"])
        self.assertIn("tools.kb.cli account-skill-resolve", route["tools"])
        self.assertIn("tools.kb.cli production-memory-record", route["tools"])
        self.assertIn("content_id", route["output_contract"])

    def test_account_learning_route_supports_image_text_branch(self):
        payload = json.loads(Path("00_System/shareable/index/controller_routes.json").read_text(encoding="utf-8"))
        route = next(route for route in payload["routes"] if route["id"] == "account_learning")
        processing = next(route for route in payload["routes"] if route["id"] == "content_processing")

        self.assertIn("图文学习", route["triggers"])
        self.assertIn("tools.kb.cli image-text-ingest", processing["tools"])
        self.assertIn("tools.kb.cli image-text-learn", processing["tools"])
        self.assertIn("00_System/shareable/skills/active/account-learning/SKILL.md", route["read_first"])
        genre = Path("00_System/shareable/skills/active/account-learning/references/genre-adapters.md")
        self.assertIn("图文", genre.read_text(encoding="utf-8"))

    def test_dashboard_writes_runtime_registry_and_report(self):
        from tools.kb.dashboard import write_dashboard

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "10_Knowledge" / "evidence" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "rules").mkdir(parents=True)
            (root / "00_System" / "shareable" / "config").mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "agents").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "references").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "agents").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "references").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skills" / "active").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skills" / "proposals").mkdir(parents=True)
            (root / "00_System" / "shareable" / "docs" / "project_use").mkdir(parents=True)
            (root / "知识库入口.md").write_text("索引 controller_routes.json\n", encoding="utf-8")
            (root / "README.md").write_text("README\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "docs" / "project_use" / "项目调用规则.md").write_text("禁止全盘扫库 数据\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "rules" / "用户操作台.md").write_text("@知识库 + 你的需求\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "rules" / "输出契约.md").write_text("# 输出契约\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "skills" / "active" / "JSON入库Skill_v1.md").write_text("active", encoding="utf-8")
            (root / "10_Knowledge" / "candidates" / "generated_assets").mkdir(parents=True)
            (root / "10_Knowledge" / "candidates" / "generated_assets" / "candidate_topics.jsonl").write_text(
                json.dumps({"source_id": "s1", "领域": "赚钱"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "10_Knowledge" / "evidence" / "index" / "knowledge_index.json").write_text('{"files":[]}', encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "knowledge_index_summary.md").write_text("# 知识库索引摘要\n", encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "formal_knowledge_index.json").write_text('{"items":[]}', encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "candidate_asset_index.json").write_text('{"items":[]}', encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "raw_blocked_index.json").write_text('{"items":[{"path":"数据/"}]}', encoding="utf-8")
            (root / "00_System" / "shareable" / "index" / "task_entry_index.md").write_text("controller_routes.json\n", encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "account_knowledge_index.json").write_text(
                json.dumps({"accounts": [{"account_name": "测试账号", "platform": "抖音", "directions": [{"direction": "赚钱"}]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            route_ids = (
                "topic_generation",
                "script_generation",
                "account_learning",
                "skill_evolution",
                "json_ingest",
                "screenshot_review",
                "table_review",
                "external_use",
                "system_audit",
                "memory_capture",
                "agent_registry",
            )
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "default_entry": "@知识库",
                        "global_priority": True,
                        "agents": [{"id": f"agent_{index}"} for index in range(8)],
                        "routes": [{"id": route_id, "triggers": [route_id], "agents": ["agent_0"], "read_first": [], "output_contract": "x", "write_policy": "x"} for route_id in route_ids],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "config" / "output_contracts.json").write_text(
                json.dumps({"contracts": [{"route_id": route_id, "required_fields": ["x"], "must_not": ["y"]} for route_id in route_ids]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "SKILL.md").write_text("全盘扫库 数据/ controller_routes.json\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "agents" / "openai.yaml").write_text('display_name: "知识库"\n总控\n', encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "references" / "calling-rules.md").write_text("rules", encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "SKILL.md").write_text("@知识库 全盘扫库 数据/ controller_routes.json\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "agents" / "openai.yaml").write_text('display_name: "知识库"\n总控\n', encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base-zh" / "references" / "calling-rules.md").write_text("rules", encoding="utf-8")

            result = write_dashboard(root)

            self.assertTrue((root / result["registry"]).exists())
            self.assertTrue((root / result["dashboard"]).exists())
            registry = json.loads((root / result["registry"]).read_text(encoding="utf-8"))
            self.assertEqual(registry["candidate_topic_count"] if "candidate_topic_count" in registry else registry["candidates"]["candidate_topic_count"], 1)
            self.assertEqual(result["active_skill_count"], 1)
            self.assertEqual(result["pending_proposal_count"], 0)

    def test_candidate_search_finds_account_topic_from_assets_and_raw_records(self):
        from tools.kb.candidate_search import search_candidates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            assets.mkdir(parents=True)
            asset_rows = [{
                "platform": "douyin",
                "领域": "校园大学生",
                "account_name": "剧情账号乙",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["《高考采访》\u2028@大伟老三 #剧情账号乙 #高考生的精选"],
                "score": 1520931.2,
                "rank": 3,
            }, {
                "platform": "douyin",
                "领域": "升学焦虑",
                "account_name": "剧情账号乙",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["高考采访"],
                "score": 1520931.2,
                "rank": 3,
            }]
            (assets / "candidate_topics.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in asset_rows) + "\n", encoding="utf-8")

            result = search_candidates(root, query="高考", account_name="剧情账号乙", limit=10)

            self.assertEqual(result["count"], 1)
            self.assertEqual(result["skipped_asset_lines"], 0)
            self.assertEqual(result["items"][0]["source_id"], "a1")
            self.assertEqual(result["items"][0]["direction"], "校园大学生、升学焦虑")
            self.assertEqual(result["items"][0]["directions"], ["校园大学生", "升学焦虑"])

            data_dir = root / "数据" / "douyin" / "json" / "剧情账号乙"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a2",
                    "title": "祝大家高考顺利！！！ #剧情账号乙",
                    "desc": "高考生加油",
                    "nickname": "剧情账号乙",
                    "liked_count": 100,
                    "collected_count": 50,
                    "comment_count": 20,
                    "share_count": 30,
                    "aweme_url": "https://www.douyin.com/video/a2",
                }
            ]
            (data_dir / "creator_contents.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            raw_result = search_candidates(root, query="高考", account_name="剧情账号乙", limit=10, include_raw=True)

            source_ids = {item["source_id"] for item in raw_result["items"]}
            self.assertIn("a1", source_ids)
            self.assertIn("a2", source_ids)

    def test_candidate_search_skips_broken_jsonl_lines(self):
        from tools.kb.candidate_search import search_candidates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            assets.mkdir(parents=True)
            good_row = {
                "platform": "douyin",
                "领域": "校园大学生",
                "account_name": "剧情账号乙",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["高考采访"],
                "score": 100,
                "rank": 1,
            }
            content = '{"broken": "line\n' + json.dumps(good_row, ensure_ascii=False) + "\n"
            (assets / "candidate_topics.jsonl").write_text(content, encoding="utf-8")

            result = search_candidates(root, query="高考", account_name="剧情账号乙", limit=10)

            self.assertEqual(result["count"], 1)
            self.assertEqual(result["skipped_asset_lines"], 1)

    def test_candidate_search_reads_candidate_assets_from_knowledge_layer(self):
        from tools.kb.candidate_search import search_candidates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            assets.mkdir(parents=True)
            assets.joinpath("candidate_topics.jsonl").write_text(
                json.dumps(
                    {
                        "account_name": "知识账号甲",
                        "领域": "赚钱",
                        "source_id": "legacy",
                        "可生成标题": ["赚钱选题"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = search_candidates(root, query="赚钱", account_name="知识账号甲", limit=10)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["items"][0]["source_id"], "legacy")

    def test_candidate_search_cli_reads_candidate_assets_from_knowledge_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            assets.mkdir(parents=True)
            assets.joinpath("candidate_topics.jsonl").write_text(
                json.dumps({"account_name": "知识账号甲", "领域": "赚钱", "source_id": "legacy"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(root),
                    "search-candidates",
                    "--query",
                    "赚钱",
                ],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["count"], 1)

    def test_resolve_call_reports_ambiguous_routes_instead_of_using_route_order(self):
        from tools.kb.call_resolver import resolve_call

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "10_Knowledge" / "evidence" / "index"
            config = root / "00_System" / "shareable" / "config"
            index.mkdir(parents=True)
            config.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "routes": [
                            {"id": "screenshot_review", "triggers": ["我要复盘"], "read_first": ["a.md"]},
                            {"id": "table_review", "triggers": ["我要复盘"], "read_first": ["b.md"]},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index.joinpath("account_knowledge_index.json").write_text('{"accounts":[]}', encoding="utf-8")
            config.joinpath("output_contracts.json").write_text('{"contracts":[]}', encoding="utf-8")

            result = resolve_call(root, "@知识库 我要复盘")

            self.assertFalse(result["ok"])
            self.assertIn("route_ambiguous", result["errors"])
            self.assertEqual({item["route_id"] for item in result["route_candidates"]}, {"screenshot_review", "table_review"})
            self.assertTrue(result["clarification_questions"])

    def test_resolve_route_uses_unique_specific_trigger_to_break_shared_trigger_tie(self):
        from tools.kb.call_resolver import resolve_call

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "10_Knowledge" / "evidence" / "index"
            config = root / "00_System" / "shareable" / "config"
            index.mkdir(parents=True)
            config.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "routes": [
                            {"id": "screenshot_review", "triggers": ["我要复盘", "截图复盘"], "read_first": []},
                            {"id": "table_review", "triggers": ["我要复盘", "表格复盘"], "read_first": []},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index.joinpath("account_knowledge_index.json").write_text('{"accounts":[]}', encoding="utf-8")
            config.joinpath("output_contracts.json").write_text('{"contracts":[]}', encoding="utf-8")

            result = resolve_call(root, "@知识库 我要复盘 表格复盘")

            self.assertTrue(result["ok"])
            self.assertEqual(result["route_id"], "table_review")

    def test_resolve_call_reports_declared_but_missing_read_paths(self):
        from tools.kb.call_resolver import resolve_call

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "10_Knowledge" / "evidence" / "index"
            config = root / "00_System" / "shareable" / "config"
            index.mkdir(parents=True)
            config.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "exists.md").write_text("exists", encoding="utf-8")
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {"routes": [{"id": "external_use", "triggers": ["查"], "read_first": ["exists.md", "missing.md"]}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index.joinpath("account_knowledge_index.json").write_text('{"accounts":[]}', encoding="utf-8")
            config.joinpath("output_contracts.json").write_text('{"contracts":[]}', encoding="utf-8")

            result = resolve_call(root, "@知识库 查")

            self.assertEqual(result["read_paths"], ["exists.md"])
            self.assertEqual(result["missing_read_paths"], ["missing.md"])

    def test_search_terms_config_is_required_and_schema_validated(self):
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                "知识库入口.md",
                "README.md",
                "00_System/shareable/docs/project_use/项目调用规则.md",
                "00_System/shareable/docs/project_use/用户操作台.md",
                "00_System/shareable/rules/初始化生命周期.md",
                "00_System/shareable/rules/输出契约.md",
                "00_System/shareable/config/output_contracts.json",
                "00_System/shareable/index/controller_routes.json",
                "10_Knowledge/evidence/index/knowledge_index.json",
                "10_Knowledge/evidence/index/knowledge_index_summary.md",
                "10_Knowledge/evidence/index/formal_knowledge_index.json",
                "10_Knowledge/evidence/index/candidate_asset_index.json",
                "10_Knowledge/evidence/index/raw_blocked_index.json",
                "00_System/shareable/index/task_entry_index.md",
                "00_System/shareable/skill_packages/knowledge-base/SKILL.md",
                "00_System/shareable/skill_packages/knowledge-base/agents/openai.yaml",
                "00_System/shareable/skill_packages/knowledge-base/references/calling-rules.md",
                "00_System/shareable/skill_packages/knowledge-base-zh/SKILL.md",
                "00_System/shareable/skill_packages/knowledge-base-zh/agents/openai.yaml",
                "00_System/shareable/skill_packages/knowledge-base-zh/references/calling-rules.md",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")

            result = validate_system(root)

            self.assertIn("missing:00_System/shareable/config/search_terms.json", result["failed"])

            search_terms = root / "00_System" / "shareable" / "config" / "search_terms.json"
            search_terms.write_text('{"synonym_groups":[],"direction_terms":{"赚钱":[""]}}', encoding="utf-8")
            result = validate_system(root)
            self.assertIn("search_terms_missing_synonym_groups", result["failed"])
            self.assertIn("search_terms_empty_direction_term:赚钱", result["failed"])

    def test_candidate_search_reports_broken_raw_files_and_keeps_valid_results(self):
        from tools.kb.candidate_search import search_candidates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "剧情账号乙"
            data_dir.mkdir(parents=True)
            (data_dir / "broken.json").write_text('{"broken": ', encoding="utf-8")
            (data_dir / "valid.json").write_text(
                json.dumps(
                    [
                        {
                            "aweme_id": "a1",
                            "title": "高考生加油",
                            "desc": "高考采访",
                            "nickname": "剧情账号乙",
                            "aweme_url": "https://www.douyin.com/video/a1",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = search_candidates(
                root,
                query="高考",
                account_name="剧情账号乙",
                include_raw=True,
            )

            self.assertEqual(result["items"][0]["source_id"], "a1")
            self.assertTrue(result["partial_success"])
            self.assertEqual(result["failed_files"][0]["path"], "数据/douyin/json/剧情账号乙/broken.json")
            report = (root / result["report"]).read_text(encoding="utf-8")
            self.assertIn("损坏原始文件", report)
            self.assertIn("数据/douyin/json/剧情账号乙/broken.json", report)

    def test_candidate_search_expands_synonyms_and_explains_ranking(self):
        from tools.kb.candidate_search import search_candidates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            assets.mkdir(parents=True)
            rows = [
                {
                    "platform": "douyin",
                    "领域": "商业机会",
                    "account_name": "知识账号甲",
                    "source_id": "synonym",
                    "source_url": "https://www.douyin.com/video/synonym",
                    "可生成标题": ["普通人增加收入的三个方法"],
                    "痛点": "副业没有稳定变现路径",
                    "内容承诺": "找到可执行的商业机会",
                    "正文/脚本方向": "从技能到收入",
                    "score": 500,
                    "rank": 2,
                },
                {
                    "platform": "douyin",
                    "领域": "赚钱",
                    "account_name": "知识账号甲",
                    "source_id": "exact",
                    "source_url": "https://www.douyin.com/video/exact",
                    "可生成标题": ["赚钱不是靠运气"],
                    "痛点": "不知道如何开始",
                    "内容承诺": "建立赚钱路径",
                    "正文/脚本方向": "先找到需求",
                    "score": 100,
                    "rank": 1,
                },
            ]
            (assets / "candidate_topics.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            result = search_candidates(root, query="赚钱", account_name="知识账号甲", limit=10)

            self.assertEqual(result["backend"], "weighted_jsonl_v1")
            self.assertEqual([item["source_id"] for item in result["items"]], ["exact", "synonym"])
            self.assertIn("收入", result["query_expansions"])
            self.assertIn("变现", result["query_expansions"])
            self.assertNotIn("投资", result["query_expansions"])
            self.assertGreater(result["items"][0]["match_score"], result["items"][1]["match_score"])
            self.assertIn("title", result["items"][0]["matched_fields"])
            self.assertIn("赚钱", result["items"][0]["matched_terms"])

    def test_scanner_uses_real_file_mtime_and_keeps_it_stable(self):
        from tools.kb.scanner import scan_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "README.md"
            target.write_text("# KB\n", encoding="utf-8")
            expected_epoch = 1_700_000_000
            os.utime(target, (expected_epoch, expected_epoch))

            first = scan_files(root)
            second = scan_files(root)
            first_item = next(item for item in first["files"] if item["path"] == "README.md")
            second_item = next(item for item in second["files"] if item["path"] == "README.md")

            self.assertEqual(first_item["modified_at"], second_item["modified_at"])
            self.assertEqual(datetime.fromisoformat(first_item["modified_at"]).timestamp(), expected_epoch)

    def test_resolve_call_routes_user_prompt_through_account_search_and_contract(self):
        from tools.kb.account_skills import sync_registry
        from tools.kb.call_resolver import resolve_call
        from tools.kb.user_layer import initialize_user_layer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index_dir = root / "10_Knowledge" / "evidence" / "index"
            config_dir = root / "00_System" / "shareable" / "config"
            assets_dir = root / "10_Knowledge" / "candidates" / "generated_assets"
            account_dir = root / "10_Knowledge" / "formal" / "accounts" / "知识账号甲"
            direction_dir = account_dir / "directions" / "赚钱"
            index_dir.mkdir(parents=True)
            config_dir.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            assets_dir.mkdir(parents=True)
            direction_dir.mkdir(parents=True)
            skill = account_dir / "skill" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: account-knowledge_account_a\ndescription: Use for account production.\n---\n\n"
                "topic-memory-check topic-memory-record production-memory-record\n",
                encoding="utf-8",
            )
            for name in ("production.md", "style.md", "boundaries.md", "acceptance.md"):
                target = skill.parent / "references" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# {name}\n", encoding="utf-8")
            (account_dir / "ACCOUNT_SKILL_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "account_skill_id": "knowledge_account_a",
                        "account_name": "知识账号甲",
                        "platform": "抖音",
                        "skill_name": "account-knowledge_account_a",
                        "version": "1.0",
                        "status": "active",
                        "aliases": ["知识账号甲"],
                        "canonical_skill_path": "10_Knowledge/formal/accounts/知识账号甲/skill/SKILL.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (direction_dir / "方向方法论总结.md").write_text("# 方法论\n", encoding="utf-8")
            (direction_dir / "粗扫内容和选题.md").write_text("# 粗扫\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "routes": [
                            {
                                "id": "topic_generation",
                                "triggers": ["我要出选题", "出选题", "选题"],
                                "read_first": ["10_Knowledge/evidence/index/account_knowledge_index.md"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (index_dir / "account_knowledge_index.json").write_text(
                json.dumps(
                    {
                        "accounts": [
                            {
                                "account_id": "knowledge_account_a",
                                "account_name": "知识账号甲",
                                "formal_account_dir": str(account_dir.relative_to(root)),
                                "directions": [
                                    {
                                        "direction": "赚钱",
                                        "status": "formal_ingested",
                                        "formal_direction_dir": str(direction_dir.relative_to(root)),
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (index_dir / "account_knowledge_index.md").write_text("# account index\n", encoding="utf-8")
            initialize_user_layer(root)
            sync_registry(root)
            (config_dir / "output_contracts.json").write_text(
                json.dumps(
                    {
                        "contracts": [
                            {
                                "route_id": "topic_generation",
                                "required_fields": ["选题标题", "证据边界"],
                                "must_not": ["不把候选资产写成正式知识"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            candidate = {
                "platform": "douyin",
                "领域": "赚钱",
                "account_name": "知识账号甲",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["赚钱先解决真实需求"],
                "score": 100,
                "rank": 1,
            }
            (assets_dir / "candidate_topics.jsonl").write_text(
                json.dumps(candidate, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            result = resolve_call(root, "@知识库 按知识账号甲的方式出2个赚钱选题，并追溯候选证据")

            self.assertEqual(result["route_id"], "topic_generation")
            self.assertEqual(result["account_name"], "知识账号甲")
            self.assertEqual(result["direction"], "赚钱")
            self.assertEqual(result["requested_count"], 2)
            self.assertEqual(result["search"]["items"][0]["source_id"], "a1")
            self.assertIn("选题标题", result["output_contract"]["required_fields"])
            self.assertTrue(all((root / path).exists() for path in result["read_paths"]))
            self.assertIn(str(skill.relative_to(root)), result["read_paths"])
            self.assertNotIn(str((direction_dir / "方向方法论总结.md").relative_to(root)), result["read_paths"])
            self.assertTrue(result["account_skill"]["ok"])
            self.assertEqual(result["knowledge_boundary"]["candidate_assets"], "candidate_evidence_only")

    def test_resolve_call_prefers_specific_task_over_generic_external_entry(self):
        from tools.kb.call_resolver import resolve_route

        routes = [
            {"id": "external_use", "triggers": ["@知识库", "knowledge-base"]},
            {"id": "topic_generation", "triggers": ["出选题", "选题"]},
        ]

        result = resolve_route("@知识库 按知识账号甲的方式出2个赚钱选题", routes)

        self.assertEqual(result["id"], "topic_generation")

    def test_resolve_call_asks_only_for_missing_minimum_inputs(self):
        from tools.kb.call_resolver import resolve_call

        result = resolve_call(Path.cwd(), "我要出选题")

        self.assertFalse(result["ok"])
        self.assertEqual(result["route_id"], "topic_generation")
        self.assertIn("missing_required_input", result["errors"])
        self.assertLessEqual(len(result["clarification_questions"]), 3)
        self.assertEqual(result["search"]["status"], "not_run_missing_input")
        self.assertEqual(result["knowledge_boundary"]["candidate_assets"], "not_read")

    def test_resolve_call_parses_common_output_count_units(self):
        from tools.kb.call_resolver import resolve_call, resolve_requested_count

        self.assertEqual(resolve_requested_count("生成5条个人成长选题"), 5)
        self.assertEqual(resolve_requested_count("写三篇长文案"), 3)
        self.assertEqual(resolve_requested_count("给我十二个方向"), 12)
        self.assertNotIn("需要生成多少个选题？", resolve_call(Path.cwd(), "知识账号甲生成五条个人成长选题")["clarification_questions"])
        self.assertIsNone(resolve_call(Path.cwd(), "我要出选题")["requested_count"])

    def test_resolve_call_understands_flexible_account_learning_word_order(self):
        from tools.kb.call_resolver import resolve_call

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "20_User/config"
            config.mkdir(parents=True)
            (config / "account_skill_registry.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "accounts": [
                            {
                                "account_skill_id": "story_account_b",
                                "account_name": "剧情账号乙",
                                "aliases": ["剧情账号乙"],
                                "status": "active",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            account_index = root / "10_Knowledge/evidence/index/account_knowledge_index.json"
            account_index.parent.mkdir(parents=True)
            account_index.write_text(
                json.dumps(
                    {
                        "accounts": [
                            {
                                "account_id": "story_account_b",
                                "account_name": "剧情账号乙",
                                "directions": [],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            route_path = root / "00_System/shareable/index/controller_routes.json"
            route_path.parent.mkdir(parents=True)
            route_path.write_text(
                json.dumps(
                    {
                        "routes": [
                            {
                                "id": "account_learning",
                                "triggers": ["学习账号", "账号学习", "学习"],
                                "read_first": [],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = resolve_call(root, "学习剧情账号乙账号")

        self.assertEqual(result["route_id"], "account_learning")
        self.assertEqual(result["account_name"], "剧情账号乙")
        self.assertEqual(result["clarification_questions"], ["要学习哪批已经处理完成的证据？"])

    def test_resolve_call_prefers_script_generation_for_confirmed_topic_image_text(self):
        from tools.kb.call_resolver import resolve_route

        routes = [
            {"id": "topic_generation", "triggers": ["出选题", "选题"]},
            {"id": "script_generation", "triggers": ["图文", "标题", "封面"]},
        ]

        result = resolve_route("基于刚才确认的选题，生成小红书图文，允许调用 image2 生图", routes)

        self.assertEqual(result["id"], "script_generation")

    def test_resolve_call_cli_returns_nonzero_for_unresolved_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index_dir = root / "10_Knowledge" / "evidence" / "index"
            config_dir = root / "00_System" / "shareable" / "config"
            index_dir.mkdir(parents=True)
            config_dir.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps({"routes": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (index_dir / "account_knowledge_index.json").write_text(
                json.dumps({"accounts": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config_dir / "output_contracts.json").write_text(
                json.dumps({"contracts": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(root),
                    "resolve-call",
                    "--text",
                    "这是一条无法识别的请求",
                ],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=False,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(payload["ok"])
            self.assertIn("route_not_resolved", payload["errors"])

    def test_resolve_call_does_not_search_candidates_for_system_audit(self):
        from tools.kb.call_resolver import resolve_call

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index_dir = root / "10_Knowledge" / "evidence" / "index"
            config_dir = root / "00_System" / "shareable" / "config"
            index_dir.mkdir(parents=True)
            config_dir.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "routes": [
                            {
                                "id": "system_audit",
                                "triggers": ["我要看状态"],
                                "read_first": ["00_System/shareable/index/controller_routes.json"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (index_dir / "account_knowledge_index.json").write_text(
                json.dumps({"accounts": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config_dir / "output_contracts.json").write_text(
                json.dumps(
                    {
                        "contracts": [
                            {
                                "route_id": "system_audit",
                                "required_fields": ["验证结果"],
                                "must_not": ["不只检查文件存在"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = resolve_call(root, "@知识库 我要看状态")

            self.assertEqual(result["route_id"], "system_audit")
            self.assertEqual(result["search"]["status"], "not_applicable")
            self.assertFalse((root / "00_System" / "runtime" / "reports").exists())

    def test_legacy_evolution_report_is_removed_from_cli(self):
        completed = subprocess.run(
            [sys.executable, "-m", "tools.kb.cli", "--help"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotIn("evolution-report", completed.stdout)
        self.assertFalse(Path("tools/kb/evolution.py").exists())
        return

    def test_account_index_is_rebuilt_from_direct_formal_manifests(self):
        from tools.kb.account_skills import write_account_indexes
        from tools.kb.validator import validate_account_structure_and_index

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account = root / "10_Knowledge/formal/accounts/样例账号"
            skill = account / "skill/SKILL.md"
            card = account / "directions/知识分享/cards/sample.md"
            skill.parent.mkdir(parents=True)
            card.parent.mkdir(parents=True)
            skill.write_text("---\nname: account-sample\ndescription: Sample.\n---\n", encoding="utf-8")
            card.write_text("# card\n", encoding="utf-8")
            (account / "ACCOUNT_SKILL_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "account_skill_id": "sample",
                        "account_name": "样例账号",
                        "platform": "示例平台",
                        "canonical_skill_path": "10_Knowledge/formal/accounts/样例账号/skill/SKILL.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = write_account_indexes(root)
            payload = json.loads(
                (root / "10_Knowledge/evidence/index/account_knowledge_index.json").read_text(encoding="utf-8")
            )
            validation = validate_account_structure_and_index(root, payload)

            self.assertTrue(result["ok"])
            self.assertEqual(payload["accounts"][0]["formal_account_dir"], "10_Knowledge/formal/accounts/样例账号")
            self.assertEqual(payload["accounts"][0]["formal_card_count"], 1)
            self.assertEqual(validation["errors"], [])

    def test_account_index_rejects_theme_wrapper(self):
        from tools.kb.account_skills import build_account_knowledge_index
        from tools.kb.validator import validate_account_structure_and_index

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "10_Knowledge/formal/accounts/主题方法论/账号中心/样例账号").mkdir(parents=True)

            payload = build_account_knowledge_index(root)
            result = validate_account_structure_and_index(root, payload)

            self.assertTrue(any("formal_account_manifest_missing_or_invalid" in item for item in result["errors"]))

    def test_distribution_audit_detects_account_leaks_and_exports_clean_package(self):
        from tools.kb.distribution import audit_distribution, export_system_package

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            output = Path(tmp) / "export"
            (root / "00_System/shareable").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)
            (root / "20_User/config").mkdir(parents=True)
            (root / "00_System/shareable/share_manifest.json").write_text(
                json.dumps({"include": ["00_System/shareable/", "tools/"], "exclude": ["20_User/"]}),
                encoding="utf-8",
            )
            (root / "20_User/config/content_rough_scan_profiles.json").write_text(
                json.dumps({"profiles": {"sample": {"account_name": "真实账号"}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            tool = root / "tools/runner.py"
            tool.write_text("ACCOUNT = '真实账号'\n", encoding="utf-8")
            self.assertFalse(audit_distribution(root)["ok"])

            tool.write_text("ACCOUNT = 'runtime input'\n", encoding="utf-8")
            audit = audit_distribution(root)
            exported = export_system_package(root, output)

            self.assertTrue(audit["portable"])
            self.assertFalse(audit["open_source_ready"])
            self.assertEqual(audit["legal_release_blocker"], "missing_license")
            self.assertTrue(exported["ok"])
            self.assertTrue((output / "tools/runner.py").exists())
            self.assertFalse((output / "20_User").exists())

    def test_distribution_audit_accepts_scoped_apache_system_license(self):
        from tools.kb.distribution import audit_distribution

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "00_System/shareable").mkdir(parents=True)
            (root / "00_System/shareable/share_manifest.json").write_text(
                json.dumps(
                    {
                        "include": [
                            "00_System/shareable/",
                            "LICENSE",
                            "LICENSE_SCOPE.md",
                            "NOTICE",
                        ],
                        "exclude": ["10_Knowledge/", "20_User/"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
            (root / "LICENSE_SCOPE.md").write_text(
                "SPDX-License-Identifier: Apache-2.0\n"
                "00_System/shareable/share_manifest.json\n"
                "## 不在 Apache-2.0 授权范围内\n"
                "- 10_Knowledge/\n",
                encoding="utf-8",
            )
            (root / "NOTICE").write_text("Knowledge Base System\n", encoding="utf-8")

            audit = audit_distribution(root)

            self.assertTrue(audit["ok"])
            self.assertTrue(audit["open_source_ready"])
            self.assertEqual(audit["license_id"], "Apache-2.0")
            self.assertEqual(audit["license_scope"], "portable_system_package_only")
            self.assertEqual(audit["legal_release_blocker"], "")

    def test_candidate_hygiene_rejects_e2e_outputs_in_real_candidate_layer(self):
        from tools.kb.validator import validate_candidate_layer_hygiene

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "10_Knowledge/candidates/learning_cards/image_text_e2e_account/card.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# test artifact\n", encoding="utf-8")

            result = validate_candidate_layer_hygiene(root)

            self.assertTrue(result["errors"])
            self.assertIn("image_text_e2e_account", result["paths"][0])



if __name__ == "__main__":
    unittest.main()
