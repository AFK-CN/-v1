import json
import tempfile
import unittest
from pathlib import Path

from tools.kb.call_resolver import resolve_call
from tools.kb.formal_search import (
    build_formal_search_index,
    cache_paths,
    index_status,
    read_index_records,
    search_formal,
)
from tools.kb.validator import validate_formal_retrieval


class FormalSearchTests(unittest.TestCase):
    def make_root(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        config_dir = root / "00_System/shareable/config"
        config_dir.mkdir(parents=True)
        source_config = Path("00_System/shareable/config/formal_retrieval.json")
        (config_dir / "formal_retrieval.json").write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")
        return root

    @staticmethod
    def write(root: Path, relative: str, text: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def seed_sources(self, root: Path) -> None:
        self.write(
            root,
            "10_Knowledge/formal/accounts/账号甲/directions/测试方向/cards/card-a.md",
            "# 风险边界\n\n这个正式方法要求证据坐标和严格来源隔离。\n",
        )
        self.write(
            root,
            "10_Knowledge/formal/accounts/账号乙/directions/另一方向/cards/card-b.md",
            "# 风险边界\n\n另一个账号的正式方法，不得混入账号甲。\n",
        )
        self.write(
            root,
            "10_Knowledge/formal/accounts/账号甲/methods/method-a/METHOD.md",
            "# 结构方法\n\n先审计，再小样本验证，最后才允许推广。\n",
        )
        self.write(
            root,
            "10_Knowledge/formal/accounts/账号甲/轻量数据源/directions/测试方向/item/学习卡.md",
            "# 被排除的轻量资料\n\n不得进入正式检索缓存。\n",
        )
        self.write(
            root,
            "10_Knowledge/formal/accounts/账号甲/skill/proposals/deprecated-rule.md",
            "# 被排除的历史提案\n\n旧规则不得进入正式检索缓存。\n",
        )
        self.write(root, "10_Knowledge/candidates/account_assets/leak.md", "风险边界 候选污染")
        self.write(root, "00_Inbox/raw.md", "风险边界 原始污染")
        self.write(root, "数据/raw.md", "风险边界 数据污染")
        self.write(root, "00_System/shareable/rules/leak.md", "风险边界 系统污染")
        self.write(root, "20_User/private/leak.md", "风险边界 用户污染")

    def test_build_and_search_use_formal_only_with_traceable_coordinates(self) -> None:
        root = self.make_root()
        self.seed_sources(root)

        built = build_formal_search_index(root)
        index_path, _ = cache_paths(root)
        records = read_index_records(index_path)

        self.assertTrue(built["ok"])
        self.assertEqual(built["scope"], "formal_only")
        self.assertGreater(built["chunk_count"], 0)
        self.assertTrue(all(item["path"].startswith("10_Knowledge/formal/") for item in records))
        self.assertTrue(all("term_frequencies" not in item for item in records))
        self.assertTrue(all(len(item["vector"]) <= 96 for item in records))
        self.assertFalse(any("轻量数据源" in item["path"] for item in records))
        self.assertFalse(any("skill/proposals" in item["path"] for item in records))
        self.assertFalse(any("候选污染" in item["text"] for item in records))
        self.assertFalse(any("原始污染" in item["text"] for item in records))
        self.assertFalse(any("系统污染" in item["text"] for item in records))
        self.assertFalse(any("用户污染" in item["text"] for item in records))

        result = search_formal(
            root,
            query="风险边界 证据坐标",
            account="账号甲",
            direction="测试方向",
            document_role="formal_card",
            limit=5,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["scope"], "formal_only")
        self.assertEqual(result["count"], 1)
        item = result["items"][0]
        self.assertEqual(item["account"], "账号甲")
        self.assertEqual(item["direction"], "测试方向")
        self.assertEqual(item["document_role"], "formal_card")
        self.assertRegex(item["evidence_coordinate"], r":L\d+-L\d+$")
        self.assertEqual(set(item["score_details"]), {"bm25", "vector", "metadata", "rerank"})
        self.assertTrue(item["chunk_sha256"])

    def test_metadata_filters_are_strict_and_do_not_fall_back_cross_account(self) -> None:
        root = self.make_root()
        self.seed_sources(root)
        build_formal_search_index(root)

        result = search_formal(root, query="风险边界", account="不存在的账号", limit=10)

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["filters"]["account"], "不存在的账号")

    def test_stale_index_requires_explicit_rebuild(self) -> None:
        root = self.make_root()
        self.seed_sources(root)
        build_formal_search_index(root)
        self.assertTrue(index_status(root)["ok"])

        self.write(root, "10_Knowledge/formal/new.md", "# 新正式文档\n")

        status = index_status(root)
        result = search_formal(root, query="新正式文档")
        self.assertFalse(status["ok"])
        self.assertEqual(status["reason"], "index_stale")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "requires_rebuild")
        self.assertEqual(result["next_action"], "tools.kb.cli formal-search-index")

    def test_call_resolver_routes_to_formal_search_without_candidate_or_raw_reads(self) -> None:
        root = self.make_root()
        self.seed_sources(root)
        build_formal_search_index(root)
        index_dir = root / "00_System/shareable/index"
        index_dir.mkdir(parents=True, exist_ok=True)
        controller = {
            "clarification_policy": {"max_questions": 3, "rule": "missing only"},
            "routes": [
                {
                    "id": "formal_retrieval",
                    "triggers": ["查询正式知识"],
                    "read_first": ["00_System/shareable/config/formal_retrieval.json"],
                }
            ],
        }
        (index_dir / "controller_routes.json").write_text(
            json.dumps(controller, ensure_ascii=False), encoding="utf-8"
        )

        result = resolve_call(root, "@知识库 查询正式知识 风险边界")

        self.assertTrue(result["ok"])
        self.assertEqual(result["route_id"], "formal_retrieval")
        self.assertEqual(result["search"]["scope"], "formal_only")
        self.assertGreater(result["search"]["count"], 0)
        self.assertEqual(result["knowledge_boundary"]["candidate_assets"], "not_read")
        self.assertEqual(result["knowledge_boundary"]["raw_data"], "blocked_by_default")

    def test_formal_retrieval_contract_rejects_boundary_and_weight_drift(self) -> None:
        payload = json.loads(Path("00_System/shareable/config/formal_retrieval.json").read_text(encoding="utf-8"))
        failures: list[str] = []
        validate_formal_retrieval(payload, failures)
        self.assertEqual(failures, [])

        payload["allowed_roots"] = ["10_Knowledge/candidates/"]
        payload["weights"]["keyword"] = 0.9
        failures = []
        validate_formal_retrieval(payload, failures)
        self.assertIn("formal_retrieval_allowed_roots_invalid", failures)
        self.assertIn("formal_retrieval_weights_must_sum_to_one", failures)


if __name__ == "__main__":
    unittest.main()
