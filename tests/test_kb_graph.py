from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.kb.graph.builder import build_graph, graph_status
from tools.kb.graph.query import query_graph


class KBGraphTests(unittest.TestCase):
    def _seed(self, root: Path) -> None:
        (root / "00_System/shareable/config").mkdir(parents=True)
        (root / "00_System/shareable/index").mkdir(parents=True)
        (root / "10_Knowledge/evidence/index").mkdir(parents=True)
        (root / "10_Knowledge/formal/methods").mkdir(parents=True)
        (root / "10_Knowledge/candidates/private_cards").mkdir(parents=True)
        (root / "数据").mkdir(parents=True)
        (root / "知识库入口.md").write_text("# 知识库入口\n\n[方法](10_Knowledge/formal/methods/test.md)\n", encoding="utf-8")
        (root / "10_Knowledge/formal/methods/test.md").write_text("# 钩子方法\n\n## 适用边界\n", encoding="utf-8")
        (root / "10_Knowledge/candidates/private_cards/card.md").write_text("# 不应读取\n", encoding="utf-8")
        (root / "数据/raw.md").write_text("# 原始资料\n", encoding="utf-8")
        (root / "00_System/shareable/index/controller_routes.json").write_text(
            json.dumps(
                {
                    "routes": [
                        {
                            "id": "topic_generation",
                            "name": "出选题",
                            "read_first": ["10_Knowledge/formal/methods/test.md"],
                            "tools": ["tools.kb.cli search-candidates"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "00_System/shareable/config/account_learning_pipeline.json").write_text(
            json.dumps(
                {
                    "confirmation_gates": ["stage0"],
                    "stages": [
                        {"id": "stage0", "name": "整体理解", "required_artifacts": ["overview.md"]},
                        {"id": "stage1", "name": "并行提取", "required_artifacts": ["candidates.jsonl"]},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "10_Knowledge/evidence/index/formal_knowledge_index.json").write_text(
            json.dumps(
                {
                    "item_count": 1,
                    "items": [
                        {
                            "path": "10_Knowledge/formal/methods/test.md",
                            "purpose": "formal_knowledge",
                            "content_status": "approved",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "10_Knowledge/evidence/index/candidate_asset_index.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-07-14T00:00:00+08:00",
                    "item_count": 1,
                    "items": [{"path": "10_Knowledge/candidates/private_cards/card.md"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_build_uses_graphify_but_preserves_knowledge_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)

            result = build_graph(root)
            graph = json.loads((root / "00_System/runtime/graphify/graph.json").read_text(encoding="utf-8"))
            manifest = json.loads((root / "00_System/runtime/graphify/manifest.json").read_text(encoding="utf-8"))
            source_files = {str(node.get("source_file") or "") for node in graph["nodes"]}

            self.assertTrue(result["ok"])
            self.assertEqual(graph["engine"]["name"], "Graphify")
            self.assertEqual(graph["engine"]["version"], "0.9.15")
            self.assertNotIn("数据/raw.md", source_files)
            self.assertNotIn("10_Knowledge/candidates/private_cards/card.md", source_files)
            self.assertNotIn("数据/raw.md", manifest["allowed_sources"])
            self.assertEqual(manifest["source_policy"]["candidate"], "summary_only")
            summary = next(node for node in graph["nodes"] if node["id"] == "summary:candidate_assets")
            self.assertEqual(summary["item_count"], 1)

    def test_five_views_query_and_source_recheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed(root)
            build_graph(root)

            status = graph_status(root)
            query = query_graph(root, "出选题 钩子方法", view="cross_layer", depth=2, limit=20)
            html = (root / "00_System/runtime/graphify/index.html").read_text(encoding="utf-8")

            self.assertTrue(status["checks"]["five_views_present"])
            self.assertTrue(query["ok"])
            self.assertTrue(query["source_recheck_required"])
            self.assertTrue(any(item["path"] == "10_Knowledge/formal/methods/test.md" for item in query["sources"]))
            self.assertIn("跨层关系", html)
            self.assertIn("关系来源", html)
            self.assertIn("最低可信度", html)
            self.assertIn("forceAtlas2Based", html)
            self.assertIn("社区网络", html)
            self.assertIn("data-community", html)


if __name__ == "__main__":
    unittest.main()
