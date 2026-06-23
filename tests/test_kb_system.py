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
            (root / "知识库入口.md").write_text("先读索引和 controller_routes.json，禁止全盘扫库\n", encoding="utf-8")
            (root / "README.md").write_text("14_KB_System\n", encoding="utf-8")
            (root / "11_Project_Use" / "项目调用规则.md").write_text("禁止全盘扫库，按索引按需调用，禁止读取数据目录\n", encoding="utf-8")
            (root / "14_KB_System" / "index" / "knowledge_index.json").write_text('{"files":[]}', encoding="utf-8")
            (root / "14_KB_System" / "index" / "task_entry_index.md").write_text("按需调用 controller_routes.json\n", encoding="utf-8")
            (root / "14_KB_System" / "index" / "controller_routes.json").write_text(
                json.dumps(
                    {
                        "default_entry": "@知识库",
                        "global_priority": True,
                        "agents": [{"id": f"agent_{index}", "name": "测试", "responsibility": "测试"} for index in range(8)],
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
                            )
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "14_KB_System" / "index" / "account_knowledge_index.json").write_text(
                json.dumps({"accounts": [{"directions": [{"direction": "赚钱"}]}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "14_KB_System" / "config").mkdir(exist_ok=True)
            (root / "14_KB_System" / "config" / "output_contracts.json").write_text(
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
                                "skill_evolution",
                                "system_audit",
                            )
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "14_KB_System" / "rules").mkdir(exist_ok=True)
            (root / "14_KB_System" / "rules" / "用户操作台.md").write_text("@知识库 + 你的需求\n", encoding="utf-8")
            (root / "14_KB_System" / "rules" / "输出契约.md").write_text("# 输出契约\n", encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "SKILL.md").write_text(
                "description: 禁止全盘扫库，默认不读取 数据/，controller_routes.json\n", encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "知识库"\n  short_description: "总控"\n', encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "references" / "calling-rules.md").write_text(
                "按索引调用\n", encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "知识库" / "SKILL.md").write_text(
                "description: @知识库，禁止全盘扫库，默认不读取 数据/，controller_routes.json\n", encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "知识库" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "知识库"\n  short_description: "总控"\n', encoding="utf-8"
            )
            (root / "14_KB_System" / "skill_packages" / "知识库" / "references" / "calling-rules.md").write_text(
                "@知识库\n", encoding="utf-8"
            )

            result = validate_system(root)

            self.assertTrue(result["ok"])
            self.assertEqual(result["failed"], [])
            self.assertEqual(result["health"]["route_count"], 9)
            self.assertEqual(result["health"]["agent_count"], 8)
            self.assertEqual(result["health"]["account_count"], 1)
            self.assertEqual(result["health"]["contract_count"], 8)

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
        self.assertIn("/Users/lao_wu/codexAI/知识库/14_KB_System/index/controller_routes.json", skill_text)
        self.assertIn("/Users/lao_wu/codexAI/知识库/14_KB_System/index/task_entry_index.md", skill_text)
        self.assertIn("Do not scan the whole knowledge base", skill_text)
        self.assertIn("Controller Behavior", skill_text)
        self.assertIn("display_name: \"知识库\"", ui_text)
        self.assertIn("总控", ui_text)
        self.assertIn("name: 知识库", zh_skill_text)
        self.assertIn("@知识库", zh_skill_text)
        self.assertIn("controller_routes.json", zh_skill_text)
        self.assertIn("display_name: \"知识库\"", zh_ui_text)
        self.assertIn("总控", zh_ui_text)
        self.assertIn("search-candidates", zh_skill_text)

    def test_controller_routes_define_required_agents_and_routes(self):
        routes_path = Path("14_KB_System/index/controller_routes.json")
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
        self.assertEqual(payload["clarification_policy"]["max_questions"], 3)
        self.assertIn("我要出选题", payload["clarification_policy"]["generic_entry_examples"])
        topic_route = next(route for route in payload["routes"] if route["id"] == "topic_generation")
        script_route = next(route for route in payload["routes"] if route["id"] == "script_generation")
        self.assertIn("我要出选题", topic_route["triggers"])
        self.assertIn("主题或方向", topic_route["minimum_required"])
        self.assertIn("你要哪个方向或主题？", topic_route["clarify_when_missing"])
        self.assertIn("我要写文案", script_route["triggers"])
        self.assertIn("输出形式", script_route["minimum_required"])
        for route in payload["routes"]:
            self.assertIn("triggers", route)
            self.assertIn("read_first", route)
            self.assertIn("output_contract", route)
            self.assertIn("write_policy", route)

    def test_user_console_exposes_simple_at_knowledge_base_prompts(self):
        console = Path("14_KB_System/rules/用户操作台.md")
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
        contracts = Path("14_KB_System/config/output_contracts.json")
        doc = Path("14_KB_System/rules/输出契约.md")
        self.assertTrue(contracts.exists())
        self.assertTrue(doc.exists())
        payload = json.loads(contracts.read_text(encoding="utf-8"))
        self.assertEqual(payload["clarification_policy"]["max_questions"], 3)
        route_ids = {contract["route_id"] for contract in payload["contracts"]}
        self.assertIn("topic_generation", route_ids)
        self.assertIn("script_generation", route_ids)
        self.assertIn("account_learning", route_ids)
        self.assertIn("system_audit", route_ids)
        for contract in payload["contracts"]:
            self.assertTrue(contract["required_fields"])
            self.assertTrue(contract["must_not"])
        self.assertIn("固定高级入口缺少最低信息时", doc.read_text(encoding="utf-8"))

    def test_dashboard_writes_runtime_registry_and_report(self):
        from tools.kb.dashboard import write_dashboard

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "14_KB_System" / "index").mkdir(parents=True)
            (root / "14_KB_System" / "rules").mkdir(parents=True)
            (root / "14_KB_System" / "config").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "agents").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "references").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "知识库" / "agents").mkdir(parents=True)
            (root / "14_KB_System" / "skill_packages" / "知识库" / "references").mkdir(parents=True)
            (root / "13_Evolving_Skills" / "active").mkdir(parents=True)
            (root / "13_Evolving_Skills" / "proposals").mkdir(parents=True)
            (root / "11_Project_Use").mkdir()
            (root / "知识库入口.md").write_text("索引 controller_routes.json\n", encoding="utf-8")
            (root / "README.md").write_text("README\n", encoding="utf-8")
            (root / "11_Project_Use" / "项目调用规则.md").write_text("禁止全盘扫库 数据\n", encoding="utf-8")
            (root / "14_KB_System" / "rules" / "用户操作台.md").write_text("@知识库 + 你的需求\n", encoding="utf-8")
            (root / "14_KB_System" / "rules" / "输出契约.md").write_text("# 输出契约\n", encoding="utf-8")
            (root / "13_Evolving_Skills" / "active" / "JSON入库Skill_v1.md").write_text("active", encoding="utf-8")
            (root / "14_KB_System" / "assets").mkdir()
            (root / "14_KB_System" / "assets" / "candidate_topics.jsonl").write_text(
                json.dumps({"source_id": "s1", "领域": "赚钱"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "14_KB_System" / "index" / "knowledge_index.json").write_text('{"files":[]}', encoding="utf-8")
            (root / "14_KB_System" / "index" / "task_entry_index.md").write_text("controller_routes.json\n", encoding="utf-8")
            (root / "14_KB_System" / "index" / "account_knowledge_index.json").write_text(
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
            )
            (root / "14_KB_System" / "index" / "controller_routes.json").write_text(
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
            (root / "14_KB_System" / "config" / "output_contracts.json").write_text(
                json.dumps({"contracts": [{"route_id": route_id, "required_fields": ["x"], "must_not": ["y"]} for route_id in route_ids if route_id != "external_use"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "SKILL.md").write_text("全盘扫库 数据/ controller_routes.json\n", encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "agents" / "openai.yaml").write_text('display_name: "知识库"\n总控\n', encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "knowledge-base" / "references" / "calling-rules.md").write_text("rules", encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "知识库" / "SKILL.md").write_text("@知识库 全盘扫库 数据/ controller_routes.json\n", encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "知识库" / "agents" / "openai.yaml").write_text('display_name: "知识库"\n总控\n', encoding="utf-8")
            (root / "14_KB_System" / "skill_packages" / "知识库" / "references" / "calling-rules.md").write_text("rules", encoding="utf-8")

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
            assets = root / "14_KB_System" / "assets"
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
            assets = root / "14_KB_System" / "assets"
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
