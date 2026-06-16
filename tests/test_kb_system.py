import json
import tempfile
import unittest
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
            candidate_path = root / "14_KB_System" / "assets" / "candidate_topics.jsonl"
            top10_path = root / "14_KB_System" / "assets" / "candidate_top10_by_category.md"
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
            finish_task(root, task["task_id"], "done", summary="scan completed", outputs=["14_KB_System/index/knowledge_index.json"])

            task_dir = root / "14_KB_System" / "tasks" / "done" / task["task_id"]
            self.assertTrue((task_dir / "status.json").exists())
            self.assertTrue((task_dir / "action_log.md").exists())
            self.assertTrue((task_dir / "summary_report.md").exists())
            self.assertTrue((task_dir / "errors.log").exists())
            self.assertTrue((task_dir / "outputs_manifest.json").exists())
            status = json.loads((task_dir / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["task_status"], "done")

    def test_indexer_writes_machine_and_human_indexes(self):
        from tools.kb.indexer import write_indexes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "知识库入口.md").write_text("# 入口\n", encoding="utf-8")
            (root / "00_Inbox").mkdir()
            (root / "00_Inbox" / "raw.json").write_text("[]", encoding="utf-8")

            result = write_indexes(root)

            self.assertEqual(result["index_files"], 4)
            knowledge_index = root / "14_KB_System" / "index" / "knowledge_index.json"
            task_index = root / "14_KB_System" / "index" / "task_entry_index.md"
            data = json.loads(knowledge_index.read_text(encoding="utf-8"))
            self.assertTrue(any(item["path"] == "知识库入口.md" for item in data["files"]))
            self.assertIn("其他项目调用", task_index.read_text(encoding="utf-8"))

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
            (root / "00_Inbox").mkdir()
            (root / "数据").mkdir()
            (root / "JSON入库清洗规则.md").write_text("# rule\n", encoding="utf-8")
            (root / "验收报告_2026-06-14.md").write_text("# report\n", encoding="utf-8")
            (root / "feishu_doc_read").mkdir()
            (root / "feishu_doc_read" / "doc.md").write_text("# imported\n", encoding="utf-8")
            (root / ".DS_Store").write_text("mac", encoding="utf-8")

            plan = plan_reorganization(root)

            actions = {item["path"]: item for item in plan["actions"]}
            self.assertEqual(actions["JSON入库清洗规则.md"]["action"], "move")
            self.assertEqual(actions["JSON入库清洗规则.md"]["target"], "14_KB_System/rules/JSON入库清洗规则.md")
            self.assertEqual(actions["验收报告_2026-06-14.md"]["target"], "14_KB_System/reports/history/验收报告_2026-06-14.md")
            self.assertEqual(actions["feishu_doc_read"]["target"], "99_Archive/feishu_doc_read")
            self.assertEqual(actions[".DS_Store"]["action"], "delete_candidate")
            self.assertNotIn("00_Inbox", actions)
            self.assertNotIn("数据", actions)

    def test_validate_system_checks_call_rules_and_core_outputs(self):
        from tools.kb.validator import validate_system

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "14_KB_System" / "index").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "agents").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "references").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "知识库" / "agents").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "知识库" / "references").mkdir(parents=True)
            (root / "13_Evolving_Skills" / "active").mkdir(parents=True)
            (root / "13_Evolving_Skills" / "proposals").mkdir(parents=True)
            (root / "11_Project_Use").mkdir()
            (root / "知识库入口.md").write_text("先读索引，禁止全盘扫库\n", encoding="utf-8")
            (root / "README.md").write_text("14_KB_System\n", encoding="utf-8")
            (root / "11_Project_Use" / "项目调用规则.md").write_text("禁止全盘扫库，按索引按需调用，禁止读取数据目录\n", encoding="utf-8")
            (root / "14_KB_System" / "index" / "knowledge_index.json").write_text('{"files":[]}', encoding="utf-8")
            (root / "14_KB_System" / "index" / "task_entry_index.md").write_text("按需调用\n", encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "SKILL.md").write_text(
                "description: 禁止全盘扫库，默认不读取 数据/\n", encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "知识库"\n', encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "references" / "calling-rules.md").write_text(
                "按索引调用\n", encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "知识库" / "SKILL.md").write_text(
                "description: @知识库，禁止全盘扫库，默认不读取 数据/\n", encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "知识库" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "知识库"\n', encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "知识库" / "references" / "calling-rules.md").write_text(
                "@知识库\n", encoding="utf-8"
            )

            result = validate_system(root)

            self.assertTrue(result["ok"])
            self.assertEqual(result["failed"], [])

    def test_knowledge_base_skill_package_is_a_single_index_first_entry(self):
        skill = Path("14_KB_System/skill_packages/knowledge-base/SKILL.md")
        ui = Path("14_KB_System/skill_packages/knowledge-base/agents/openai.yaml")
        rules = Path("14_KB_System/skill_packages/knowledge-base/references/calling-rules.md")
        zh_skill = Path("14_KB_System/skill_packages/知识库/SKILL.md")
        zh_ui = Path("14_KB_System/skill_packages/知识库/agents/openai.yaml")

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
        self.assertIn("/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md", skill_text)
        self.assertIn("Do not scan the whole knowledge base", skill_text)
        self.assertIn("display_name: \"知识库\"", ui_text)
        self.assertIn("name: 知识库", zh_skill_text)
        self.assertIn("@知识库", zh_skill_text)
        self.assertIn("display_name: \"知识库\"", zh_ui_text)

    def test_evolution_report_writes_candidate_only_without_active_skill_changes(self):
        from tools.kb.evolution import write_evolution_report

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "13_Evolving_Skills" / "active"
            active.mkdir(parents=True)
            active_file = active / "JSON入库Skill_v1.md"
            active_file.write_text("active skill", encoding="utf-8")
            (root / "14_KB_System" / "assets").mkdir(parents=True)
            (root / "14_KB_System" / "assets" / "candidate_topics.jsonl").write_text('{"topic_id":"t1"}\n', encoding="utf-8")

            result = write_evolution_report(root)

            self.assertEqual(active_file.read_text(encoding="utf-8"), "active skill")
            report = root / result["report"]
            self.assertTrue(report.exists())
            self.assertIn("只生成候选", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
