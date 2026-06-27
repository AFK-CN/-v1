import json
import os
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
            data_dir = root / "数据" / "douyin" / "json" / "姜胡说"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#创业 普通人先行动",
                    "desc": "不要想太多，先做一个小实验",
                    "nickname": "姜胡说",
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
            self.assertEqual(candidate["account_name"], "姜胡说")
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

    def test_indexer_writes_machine_and_human_indexes(self):
        from tools.kb.indexer import write_indexes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "知识库入口.md").write_text("# 入口\n", encoding="utf-8")
            (root / "02_Viral_Methods").mkdir()
            (root / "02_Viral_Methods" / "method.md").write_text("# 方法\n", encoding="utf-8")
            (root / "04_Platform_Knowledge").mkdir()
            (root / "04_Platform_Knowledge" / "douyin.md").write_text("# 平台\n", encoding="utf-8")
            (root / "05_Sub_KB_Candidates").mkdir()
            (root / "05_Sub_KB_Candidates" / "candidate.md").write_text("# 候选\n", encoding="utf-8")
            runtime_assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            runtime_assets.mkdir(parents=True)
            (runtime_assets / "candidate_topics.jsonl").write_text('{"topic_id":"t1"}\n', encoding="utf-8")
            (runtime_assets / "candidate_method_cards.md").write_text("# candidate\n", encoding="utf-8")
            (root / "00_Inbox").mkdir()
            (root / "00_Inbox" / "raw.json").write_text("[]", encoding="utf-8")

            result = write_indexes(root)

            self.assertEqual(result["index_files"], 8)
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
            self.assertTrue(any(item["path"] == "02_Viral_Methods/method.md" for item in formal["items"]))
            self.assertTrue(any(item["path"] == "04_Platform_Knowledge/douyin.md" for item in formal["items"]))
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
            (root / "10_Knowledge" / "formal" / "methods").mkdir(parents=True)
            (root / "10_Knowledge" / "formal" / "methods" / "method.md").write_text("# method\n", encoding="utf-8")
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

            self.assertIn("10_Knowledge/formal/methods/method.md", formal_paths)
            self.assertNotIn("00_System/shareable/skills/active/JSON入库Skill_v1.md", formal_paths)
            self.assertIn("10_Knowledge/candidates/topics/candidate.md", candidate_paths)
            self.assertEqual(scopes["00_System/shareable/skills/active/JSON入库Skill_v1.md"], "system_internal")
            self.assertNotIn("80_Local/paths.md", scopes)
            self.assertIn("80_Local/", blocked_paths)

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
            self.assertEqual(actions["JSON入库清洗规则.md"]["target"], "00_System/shareable/rules/JSON入库清洗规则.md")
            self.assertEqual(actions["验收报告_2026-06-14.md"]["target"], "00_System/runtime/reports/history/验收报告_2026-06-14.md")
            self.assertEqual(actions["feishu_doc_read"]["target"], "99_Archive/feishu_doc_read")
            self.assertEqual(actions[".DS_Store"]["action"], "delete_candidate")
            self.assertNotIn("00_Inbox", actions)
            self.assertNotIn("00_System", actions)
            self.assertNotIn("10_Knowledge", actions)
            self.assertNotIn("20_User", actions)
            self.assertNotIn("80_Local", actions)
            self.assertNotIn("90_Temp", actions)
            self.assertNotIn("数据", actions)
            preview = {item["source"]: item for item in plan["migration_preview"]}
            self.assertEqual(preview["13_Evolving_Skills"]["target"], "00_System/shareable/skills")

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
                "20_User/syncable",
                "20_User/private",
                "80_Local",
                "90_Temp/inbox",
            ):
                self.assertTrue((root / relative).is_dir(), relative)
            self.assertTrue((root / result["report"]).exists())

    def test_validate_system_checks_call_rules_and_core_outputs(self):
        from tools.kb.agent_registry import write_agent_registry
        from tools.kb.skill_package import write_skill_packages
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "10_Knowledge" / "evidence" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "rules").mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "agents").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "knowledge-base" / "references").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "agents").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "references").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skills" / "active").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skills" / "proposals").mkdir(parents=True)
            (root / "00_System" / "shareable" / "docs" / "project_use").mkdir(parents=True)
            (root / "知识库入口.md").write_text("先读索引和 controller_routes.json，禁止全盘扫库\n", encoding="utf-8")
            (root / "README.md").write_text("00_System/shareable\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "docs" / "project_use" / "项目调用规则.md").write_text("禁止全盘扫库，按索引按需调用，禁止读取数据目录\n", encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "knowledge_index.json").write_text('{"files":[]}', encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "knowledge_index_summary.md").write_text("# 知识库索引摘要\n", encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "formal_knowledge_index.json").write_text('{"items":[]}', encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "candidate_asset_index.json").write_text('{"items":[]}', encoding="utf-8")
            (root / "10_Knowledge" / "evidence" / "index" / "raw_blocked_index.json").write_text('{"items":[{"path":"数据/"}]}', encoding="utf-8")
            (root / "00_System" / "shareable" / "index" / "task_entry_index.md").write_text("按需调用 controller_routes.json\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "rules" / "初始化生命周期.md").write_text(
                "kb init health-gate maintenance lock\n",
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "default_entry": "@知识库",
                        "global_priority": True,
                        "agent_model": "logical_roles",
                        "agents": [{"id": f"agent_{index}", "name": "测试", "kind": "logical_role", "responsibility": "测试"} for index in range(8)],
                        "routes": [
                            {
                                "id": route_id,
                                "triggers": [route_id],
                                "agents": ["agent_0"],
                                "read_first": ["知识库入口.md"],
                                "output_contract": "测试输出",
                                "write_policy": "测试写入边界",
                            }
                            for route_id in (
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
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "10_Knowledge" / "evidence" / "index" / "account_knowledge_index.json").write_text(
                json.dumps({"accounts": [{"directions": [{"direction": "赚钱"}]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "config").mkdir(exist_ok=True)
            (root / "00_System" / "shareable" / "config" / "output_contracts.json").write_text(
                json.dumps(
                    {
                        "contracts": [
                            {"route_id": route_id, "required_fields": ["字段"], "must_not": ["禁止项"]}
                            for route_id in (
                                "topic_generation",
                                "script_generation",
                                "account_learning",
                                "json_ingest",
                                "screenshot_review",
                                "table_review",
                                "external_use",
                                "skill_evolution",
                                "system_audit",
                                "memory_capture",
                                "agent_registry",
                            )
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "rules").mkdir(exist_ok=True)
            (root / "00_System" / "shareable" / "rules" / "用户操作台.md").write_text("@知识库 + 你的需求\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "rules" / "输出契约.md").write_text("# 输出契约\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "rules" / "规则权威源.md").write_text(
                "controller_routes.json skill_contract.json schemas.py\n不要在 Markdown 文档里再维护一份并行规则清单\n",
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "config" / "search_terms.json").write_text(
                '{"synonym_groups":[["赚钱","变现"]],"direction_terms":{"赚钱":["副业"]}}',
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "config" / "layer_map.json").write_text(
                json.dumps(
                    {
                        "target_layers": {
                            "00_System": {},
                            "10_Knowledge": {},
                            "20_User": {},
                            "80_Local": {},
                            "90_Temp": {},
                            "99_Archive": {},
                            "数据": {},
                        },
                        "legacy_mapping": {},
                        "share_exclusions": ["00_System/runtime/", "80_Local/", "20_User/private/", "数据/"],
                        "default_blocked_dirs": ["数据/", "00_Inbox/", "99_Archive/", "80_Local/"],
                        "candidate_asset_roots": ["10_Knowledge/candidates/"],
                        "formal_knowledge_roots": ["10_Knowledge/formal/"],
                        "system_skill_roots": ["00_System/shareable/skills/"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "00_System" / "shareable" / "config" / "skill_contract.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "kb_root": str(root),
                        "startup_read_order": ["知识库入口.md", "00_System/shareable/index/task_entry_index.md"],
                        "blocked_dirs": ["数据/", "00_Inbox/"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self._write_memory_agent_fixture(root)
            write_skill_packages(root)
            write_agent_registry(root)

            result = validate_system(root)

            self.assertTrue(result["ok"])
            self.assertEqual(result["failed"], [])
            self.assertEqual(result["health"]["route_count"], 11)
            self.assertEqual(result["health"]["agent_count"], 8)
            self.assertEqual(result["health"]["account_count"], 1)
            self.assertEqual(result["health"]["contract_count"], 11)

    def test_knowledge_base_skill_package_is_a_single_index_first_entry(self):
        skill = Path("00_System/shareable/skill_packages/knowledge-base/SKILL.md")
        ui = Path("00_System/shareable/skill_packages/knowledge-base/agents/openai.yaml")
        rules = Path("00_System/shareable/skill_packages/knowledge-base/references/calling-rules.md")
        zh_skill = Path("00_System/shareable/skill_packages/知识库/SKILL.md")
        zh_ui = Path("00_System/shareable/skill_packages/知识库/agents/openai.yaml")

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
        self.assertIn("name: 知识库", zh_skill_text)
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
            zh = root / "00_System" / "shareable" / "skill_packages" / "知识库" / "SKILL.md"
            self.assertIn("Do not scan the whole knowledge base", en.read_text(encoding="utf-8"))
            self.assertIn("logical AI roles", en.read_text(encoding="utf-8"))
            self.assertIn("@知识库", zh.read_text(encoding="utf-8"))
            self.assertIn("search-candidates", zh.read_text(encoding="utf-8"))

    def test_validate_system_detects_generated_skill_package_drift(self):
        from tools.kb.skill_package import write_skill_packages
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)
            write_skill_packages(root)
            skill = root / "00_System" / "shareable" / "skill_packages" / "知识库" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nmanual drift\n", encoding="utf-8")

            result = validate_system(root)

            self.assertIn("skill_package_drift:00_System/shareable/skill_packages/知识库/SKILL.md", result["failed"])

    def test_controller_declares_agents_as_logical_roles_not_process_boundaries(self):
        routes_path = Path("00_System/shareable/index/controller_routes.json")
        payload = json.loads(routes_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["agent_model"], "logical_roles")
        self.assertIn("不是独立进程", payload["agent_model_notice"])
        self.assertTrue(all(agent.get("kind") == "logical_role" for agent in payload["agents"]))

    def test_rule_authority_document_assigns_each_rule_family_to_one_source(self):
        authority = Path("00_System/shareable/rules/规则权威源.md")
        self.assertTrue(authority.exists())
        text = authority.read_text(encoding="utf-8")

        self.assertIn("controller_routes.json", text)
        self.assertIn("skill_contract.json", text)
        self.assertIn("schemas.py", text)
        self.assertIn("不要在 Markdown 文档里再维护一份并行规则清单", text)

    def test_end_to_end_user_call_chain_acceptance(self):
        from tools.kb.call_resolver import resolve_call
        from tools.kb.runtime import health_gate, initialize_runtime, runtime_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)
            account_center = root / "10_Knowledge" / "formal" / "accounts" / "姜胡说" / "账号中心"
            account_center.mkdir(parents=True)
            for name in ("账号索引.md", "内容生产使用说明.md", "减少AI味输出规则.md", "内容输出标准模板.md"):
                (account_center / name).write_text(name, encoding="utf-8")
            index = root / "10_Knowledge" / "evidence" / "index"
            system_index = root / "00_System" / "shareable" / "index"
            account_index = {
                "accounts": [
                    {
                        "account_name": "姜胡说",
                        "formal_account_dir": "10_Knowledge/formal/accounts/姜胡说/账号中心",
                        "directions": [{"direction": "赚钱"}],
                    }
                ]
            }
            index.joinpath("account_knowledge_index.json").write_text(json.dumps(account_index, ensure_ascii=False), encoding="utf-8")
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
                        "account_name": "姜胡说",
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
            result = resolve_call(root, "@知识库 姜胡说 赚钱 我要出选题 1个")

            self.assertEqual(gate["status"], "healthy")
            self.assertTrue(result["ok"])
            self.assertEqual(result["route_id"], "topic_generation")
            self.assertEqual(result["search"]["status"], "ok")
            self.assertEqual(result["search"]["count"], 1)
            self.assertIn("10_Knowledge/formal/accounts/姜胡说/账号中心/账号索引.md", result["read_paths"])
            self.assertEqual(result["missing_read_paths"], [])
            self.assertEqual(result["output_contract"]["route_id"], "topic_generation")
            self.assertEqual(result["knowledge_boundary"]["raw_data"], "blocked_by_default")

    def _write_minimum_valid_system_fixture(self, root: Path) -> None:
        from tools.kb.agent_registry import write_agent_registry

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
        for directory in (
            "00_System/shareable/docs/project_use",
            "00_System/shareable/rules",
            "00_System/shareable/config",
            "00_System/shareable/index",
            "10_Knowledge/evidence/index",
        ):
            (root / directory).mkdir(parents=True, exist_ok=True)
        self._write_memory_agent_fixture(root)
        (root / "知识库入口.md").write_text("索引 controller_routes.json\n", encoding="utf-8")
        (root / "README.md").write_text("规则权威源\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "docs" / "project_use" / "项目调用规则.md").write_text("禁止全盘扫库 数据\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "rules" / "用户操作台.md").write_text("@知识库 + 你的需求\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "rules" / "初始化生命周期.md").write_text("初始化生命周期\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "rules" / "输出契约.md").write_text("# 输出契约\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "rules" / "规则权威源.md").write_text("controller_routes.json skill_contract.json schemas.py\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "config" / "search_terms.json").write_text(
            '{"synonym_groups":[["赚钱","变现"]],"direction_terms":{"赚钱":["副业"]}}',
            encoding="utf-8",
        )
        (root / "00_System" / "shareable" / "config" / "skill_contract.json").write_text(
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
        (root / "00_System" / "shareable" / "index" / "controller_routes.json").write_text(
            json.dumps(
                {
                    "default_entry": "@知识库",
                    "global_priority": True,
                    "agent_model": "logical_roles",
                    "agents": [{"id": f"agent_{index}", "kind": "logical_role"} for index in range(8)],
                    "routes": [
                        {
                            "id": route_id,
                            "triggers": [route_id],
                            "agents": ["agent_0"],
                            "read_first": ["知识库入口.md"],
                            "output_contract": "测试输出",
                            "write_policy": "测试写入边界",
                        }
                        for route_id in route_ids
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "10_Knowledge" / "evidence" / "index" / "account_knowledge_index.json").write_text(
            '{"accounts":[{"directions":[{"direction":"赚钱"}]}]}',
            encoding="utf-8",
        )
        (root / "00_System" / "shareable" / "config" / "output_contracts.json").write_text(
            json.dumps(
                {"contracts": [{"route_id": route_id, "required_fields": ["字段"], "must_not": ["禁止项"]} for route_id in route_ids]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        for name, content in (
            ("knowledge_index.json", '{"files":[]}'),
            ("knowledge_index_summary.md", "# 摘要"),
            ("formal_knowledge_index.json", '{"items":[]}'),
            ("candidate_asset_index.json", '{"items":[]}'),
            ("raw_blocked_index.json", '{"items":[{"path":"数据/"}]}'),
            ("task_entry_index.md", "controller_routes.json"),
        ):
            target_dir = root / "00_System" / "shareable" / "index" if name == "task_entry_index.md" else root / "10_Knowledge" / "evidence" / "index"
            (target_dir / name).write_text(content, encoding="utf-8")
        write_agent_registry(root)

    def _write_memory_agent_fixture(self, root: Path) -> None:
        for directory in (
            "00_System/shareable/memory",
            "00_System/shareable/agents",
            "20_User/syncable/memory",
            "20_User/syncable/agents",
            "10_Knowledge/evidence/memory/session_summaries",
            "10_Knowledge/evidence/memory/resolved_issues",
        ):
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / "00_System" / "shareable" / "memory" / "memory_rules.md").write_text("记忆判定规则\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "memory" / "retention_policy.md").write_text("保留策略\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "memory" / "memory_workflow.md").write_text("记忆工作流\n", encoding="utf-8")
        (root / "00_System" / "shareable" / "memory" / "memory_schema.json").write_text(
            json.dumps(
                {
                    "required_fields": ["memory_id", "title", "category", "target_layer", "content", "created_at"],
                    "categories": ["session_summary", "resolved_issue"],
                    "target_layers": ["user_private", "knowledge_evidence"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "00_System" / "shareable" / "agents" / "agent_registry_schema.json").write_text(
            json.dumps(
                {
                    "required_fields": ["agent_id", "primary_function", "auth_status", "memory_scope", "blocked_actions"],
                    "auth_statuses": ["not_required", "configured"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "00_System" / "shareable" / "agents" / "agent_capability_rules.md").write_text("智能体能力规则\n", encoding="utf-8")
        (root / "20_User" / "syncable" / "memory" / "记忆总入口.md").write_text("记忆总入口\n", encoding="utf-8")
        (root / "20_User" / "syncable" / "memory" / "用户偏好与决策.md").write_text("用户偏好\n", encoding="utf-8")
        (root / "10_Knowledge" / "evidence" / "memory" / "README.md").write_text("记忆证据区\n", encoding="utf-8")
        (root / "10_Knowledge" / "evidence" / "memory" / "session_summaries" / "README.md").write_text("会话摘要\n", encoding="utf-8")
        (root / "10_Knowledge" / "evidence" / "memory" / "resolved_issues" / "README.md").write_text("已解决问题\n", encoding="utf-8")

    def test_controller_routes_define_required_agents_and_routes(self):
        routes_path = Path("00_System/shareable/index/controller_routes.json")
        self.assertTrue(routes_path.exists())
        payload = json.loads(routes_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["default_entry"], "@知识库")
        self.assertTrue(payload["global_priority"])
        agent_ids = {agent["id"] for agent in payload["agents"]}
        route_ids = {route["id"] for route in payload["routes"]}
        self.assertIn("skill_evolution", agent_ids)
        self.assertIn("account_knowledge", agent_ids)
        self.assertIn("content_generator", agent_ids)
        self.assertIn("account_learning", route_ids)
        self.assertIn("skill_evolution", route_ids)
        self.assertIn("system_audit", route_ids)
        self.assertIn("memory_capture", route_ids)
        self.assertIn("agent_registry", route_ids)
        self.assertIn("creator_db_export", route_ids)
        self.assertEqual(payload["clarification_policy"]["max_questions"], 3)
        self.assertIn("我要出选题", payload["clarification_policy"]["generic_entry_examples"])
        self.assertIn("我要导出博主数据", payload["clarification_policy"]["generic_entry_examples"])
        topic_route = next(route for route in payload["routes"] if route["id"] == "topic_generation")
        script_route = next(route for route in payload["routes"] if route["id"] == "script_generation")
        export_route = next(route for route in payload["routes"] if route["id"] == "creator_db_export")
        self.assertIn("我要出选题", topic_route["triggers"])
        self.assertIn("主题或方向", topic_route["minimum_required"])
        self.assertIn("你要哪个方向或主题？", topic_route["clarify_when_missing"])
        self.assertIn("我要写文案", script_route["triggers"])
        self.assertIn("输出形式", script_route["minimum_required"])
        self.assertIn("导出博主数据", export_route["triggers"])
        self.assertIn("博主名", export_route["minimum_required"])
        self.assertIn("tools.kb.cli export-creator-db", export_route["tools"])
        for route in payload["routes"]:
            self.assertIn("triggers", route)
            self.assertIn("read_first", route)
            self.assertIn("output_contract", route)
            self.assertIn("write_policy", route)

    def test_agent_registry_is_generated_from_controller_routes(self):
        from tools.kb.agent_registry import write_agent_registry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimum_valid_system_fixture(root)

            result = write_agent_registry(root)

            self.assertTrue(result["ok"])
            registry = root / "20_User" / "syncable" / "agents" / "agent_registry.md"
            text = registry.read_text(encoding="utf-8")
            self.assertIn("| agent_0 |", text)
            self.assertIn("真实登录状态放在 `20_User/private/agents/`", text)
            self.assertNotIn("真实密钥", text)

    def test_memory_candidate_goes_to_runtime_pending_and_flags_sensitive_content(self):
        from tools.kb.memory import create_memory_candidate, list_memory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = create_memory_candidate(
                root,
                "会话规则",
                "以后同类任务先做验证再总结",
                category="workflow",
                source="unit_test",
            )
            sensitive = create_memory_candidate(
                root,
                "登录信息",
                "password=example",
                category="session_summary",
                source="unit_test",
            )
            summary = list_memory(root)

            self.assertTrue(result["ok"])
            self.assertEqual(result["candidate"]["target_layer"], "knowledge_evidence")
            self.assertTrue(sensitive["candidate"]["sensitive_warning"])
            self.assertEqual(sensitive["candidate"]["target_layer"], "user_private")
            self.assertEqual(summary["pending_count"], 2)
            self.assertEqual(summary["pending_sensitive_count"], 1)

    def test_memory_auto_capture_only_writes_when_signal_reaches_threshold(self):
        from tools.kb.memory import evaluate_memory_capture, list_memory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            skipped = evaluate_memory_capture(root, "好的，辛苦了", source="unit_test")
            captured = evaluate_memory_capture(
                root,
                "以后系统结构调整必须先判断系统层、用户层、知识层和私有边界，验证通过后再总结。",
                source="unit_test",
            )
            summary = list_memory(root)

            self.assertEqual(skipped["status"], "skipped")
            self.assertIn("below_threshold", skipped["skipped_reasons"])
            self.assertEqual(captured["status"], "captured")
            self.assertGreaterEqual(captured["score"], captured["threshold"])
            self.assertEqual(captured["candidate"]["capture_mode"], "auto_evaluated")
            self.assertEqual(summary["pending_count"], 1)

    def test_memory_auto_capture_dry_run_does_not_write_candidate(self):
        from tools.kb.memory import evaluate_memory_capture, list_memory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = evaluate_memory_capture(
                root,
                "智能体登录状态只放用户私有层，功能表放可同步层。",
                source="unit_test",
                dry_run=True,
            )
            summary = list_memory(root)

            self.assertEqual(result["status"], "would_capture")
            self.assertEqual(summary["pending_count"], 0)

    def test_memory_auto_capture_does_not_hard_skip_policy_text_that_mentions_one_off_content(self):
        from tools.kb.memory import evaluate_memory_capture

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = evaluate_memory_capture(
                root,
                "以后任务结束前必须判断是否值得生成记忆候选，普通结束语和一次性过程不生成候选。",
                source="unit_test",
                dry_run=True,
            )

            self.assertEqual(result["status"], "would_capture")
            self.assertIn("weaken:一次性", result["reasons"])

    def test_user_console_exposes_simple_at_knowledge_base_prompts(self):
        console = Path("00_System/shareable/rules/用户操作台.md")
        self.assertTrue(console.exists())
        text = console.read_text(encoding="utf-8")
        self.assertIn("@知识库 + 你的需求", text)
        self.assertIn("我要出选题", text)
        self.assertIn("我要写文案", text)
        self.assertIn("我要查账号", text)
        self.assertIn("需求不清晰时先反问", text)
        self.assertIn("最多问 3 个关键问题", text)
        self.assertIn("出选题", text)
        self.assertIn("学习账号", text)
        self.assertIn("Skill proposal", text)
        self.assertIn("候选资产不是正式知识", text)

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
        self.assertIn("固定高级入口缺少最低信息时", doc.read_text(encoding="utf-8"))

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
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "agents").mkdir(parents=True)
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "references").mkdir(parents=True)
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
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "SKILL.md").write_text("@知识库 全盘扫库 数据/ controller_routes.json\n", encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "agents" / "openai.yaml").write_text('display_name: "知识库"\n总控\n', encoding="utf-8")
            (root / "00_System" / "shareable" / "skill_packages" / "知识库" / "references" / "calling-rules.md").write_text("rules", encoding="utf-8")

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
                "account_name": "李宗恒",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["《高考采访》\u2028@大伟老三 #李宗恒 #高考生的精选"],
                "score": 1520931.2,
                "rank": 3,
            }, {
                "platform": "douyin",
                "领域": "升学焦虑",
                "account_name": "李宗恒",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["高考采访"],
                "score": 1520931.2,
                "rank": 3,
            }]
            (assets / "candidate_topics.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in asset_rows) + "\n", encoding="utf-8")

            result = search_candidates(root, query="高考", account_name="李宗恒", limit=10)

            self.assertEqual(result["count"], 1)
            self.assertEqual(result["skipped_asset_lines"], 0)
            self.assertEqual(result["items"][0]["source_id"], "a1")
            self.assertEqual(result["items"][0]["direction"], "校园大学生、升学焦虑")
            self.assertEqual(result["items"][0]["directions"], ["校园大学生", "升学焦虑"])

            data_dir = root / "数据" / "douyin" / "json" / "李宗恒"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a2",
                    "title": "祝大家高考顺利！！！ #李宗恒",
                    "desc": "高考生加油",
                    "nickname": "李宗恒",
                    "liked_count": 100,
                    "collected_count": 50,
                    "comment_count": 20,
                    "share_count": 30,
                    "aweme_url": "https://www.douyin.com/video/a2",
                }
            ]
            (data_dir / "creator_contents.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            raw_result = search_candidates(root, query="高考", account_name="李宗恒", limit=10, include_raw=True)

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
                "account_name": "李宗恒",
                "source_id": "a1",
                "source_url": "https://www.douyin.com/video/a1",
                "可生成标题": ["高考采访"],
                "score": 100,
                "rank": 1,
            }
            content = '{"broken": "line\n' + json.dumps(good_row, ensure_ascii=False) + "\n"
            (assets / "candidate_topics.jsonl").write_text(content, encoding="utf-8")

            result = search_candidates(root, query="高考", account_name="李宗恒", limit=10)

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
                        "account_name": "姜胡说",
                        "领域": "赚钱",
                        "source_id": "legacy",
                        "可生成标题": ["赚钱选题"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = search_candidates(root, query="赚钱", account_name="姜胡说", limit=10)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["items"][0]["source_id"], "legacy")

    def test_candidate_search_cli_reads_candidate_assets_from_knowledge_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "10_Knowledge" / "candidates" / "generated_assets"
            assets.mkdir(parents=True)
            assets.joinpath("candidate_topics.jsonl").write_text(
                json.dumps({"account_name": "姜胡说", "领域": "赚钱", "source_id": "legacy"}, ensure_ascii=False)
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
                "00_System/shareable/rules/用户操作台.md",
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
                "00_System/shareable/skill_packages/知识库/SKILL.md",
                "00_System/shareable/skill_packages/知识库/agents/openai.yaml",
                "00_System/shareable/skill_packages/知识库/references/calling-rules.md",
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
            data_dir = root / "数据" / "douyin" / "json" / "李宗恒"
            data_dir.mkdir(parents=True)
            (data_dir / "broken.json").write_text('{"broken": ', encoding="utf-8")
            (data_dir / "valid.json").write_text(
                json.dumps(
                    [
                        {
                            "aweme_id": "a1",
                            "title": "高考生加油",
                            "desc": "高考采访",
                            "nickname": "李宗恒",
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
                account_name="李宗恒",
                include_raw=True,
            )

            self.assertEqual(result["items"][0]["source_id"], "a1")
            self.assertTrue(result["partial_success"])
            self.assertEqual(result["failed_files"][0]["path"], "数据/douyin/json/李宗恒/broken.json")
            report = (root / result["report"]).read_text(encoding="utf-8")
            self.assertIn("损坏原始文件", report)
            self.assertIn("数据/douyin/json/李宗恒/broken.json", report)

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
                    "account_name": "姜胡说",
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
                    "account_name": "姜胡说",
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

            result = search_candidates(root, query="赚钱", account_name="姜胡说", limit=10)

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
        from tools.kb.call_resolver import resolve_call

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index_dir = root / "10_Knowledge" / "evidence" / "index"
            config_dir = root / "00_System" / "shareable" / "config"
            assets_dir = root / "10_Knowledge" / "candidates" / "generated_assets"
            account_dir = root / "10_Knowledge" / "formal" / "accounts" / "知识成长自媒体方法论" / "账号中心" / "姜胡说"
            direction_dir = account_dir / "directions" / "赚钱"
            index_dir.mkdir(parents=True)
            config_dir.mkdir(parents=True)
            (root / "00_System" / "shareable" / "index").mkdir(parents=True)
            assets_dir.mkdir(parents=True)
            direction_dir.mkdir(parents=True)
            (account_dir / "账号索引.md").write_text("# 账号索引\n", encoding="utf-8")
            (account_dir / "内容生产使用说明.md").write_text("# 使用说明\n", encoding="utf-8")
            (account_dir / "内容输出标准模板.md").write_text("# 模板\n", encoding="utf-8")
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
                                "account_id": "jianghushuo",
                                "account_name": "姜胡说",
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
                "account_name": "姜胡说",
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

            result = resolve_call(root, "@知识库 按姜胡说的方式出2个赚钱选题")

            self.assertEqual(result["route_id"], "topic_generation")
            self.assertEqual(result["account_name"], "姜胡说")
            self.assertEqual(result["direction"], "赚钱")
            self.assertEqual(result["requested_count"], 2)
            self.assertEqual(result["search"]["items"][0]["source_id"], "a1")
            self.assertIn("选题标题", result["output_contract"]["required_fields"])
            self.assertTrue(all((root / path).exists() for path in result["read_paths"]))
            self.assertIn(
                str((direction_dir / "方向方法论总结.md").relative_to(root)),
                result["read_paths"],
            )
            self.assertIn(
                str((direction_dir / "粗扫内容和选题.md").relative_to(root)),
                result["read_paths"],
            )
            self.assertEqual(result["knowledge_boundary"]["candidate_assets"], "candidate_evidence_only")

    def test_resolve_call_prefers_specific_task_over_generic_external_entry(self):
        from tools.kb.call_resolver import resolve_route

        routes = [
            {"id": "external_use", "triggers": ["@知识库", "knowledge-base"]},
            {"id": "topic_generation", "triggers": ["出选题", "选题"]},
        ]

        result = resolve_route("@知识库 按姜胡说的方式出2个赚钱选题", routes)

        self.assertEqual(result["id"], "topic_generation")

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

    def test_evolution_report_writes_candidate_only_without_active_skill_changes(self):
        from tools.kb.evolution import write_evolution_report

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "00_System" / "shareable" / "skills" / "active"
            active.mkdir(parents=True)
            active_file = active / "JSON入库Skill_v1.md"
            active_file.write_text("active skill", encoding="utf-8")
            (root / "10_Knowledge" / "candidates" / "generated_assets").mkdir(parents=True)
            (root / "10_Knowledge" / "candidates" / "generated_assets" / "candidate_topics.jsonl").write_text('{"topic_id":"t1"}\n', encoding="utf-8")

            result = write_evolution_report(root)

            self.assertEqual(active_file.read_text(encoding="utf-8"), "active skill")
            report = root / result["report"]
            self.assertTrue(report.exists())
            self.assertIn("只生成候选", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
