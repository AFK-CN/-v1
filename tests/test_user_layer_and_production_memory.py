import json
import tempfile
import unittest
from pathlib import Path


class UserLayerAndProductionMemoryTests(unittest.TestCase):
    def test_user_layer_init_is_idempotent_and_builds_database(self) -> None:
        from tools.kb.user_layer import initialize_user_layer, validate_user_layer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = initialize_user_layer(root)
            second = initialize_user_layer(root)

            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertEqual(second["created"], [])
            self.assertEqual(second["written_defaults"], [])
            self.assertTrue((root / "20_User/data/content_production.sqlite").exists())
            profiles = json.loads(
                (root / "20_User/config/content_rough_scan_profiles.json").read_text(encoding="utf-8")
            )
            self.assertEqual(profiles["profiles"], {})
            self.assertEqual(profiles["video_learning_classification"]["account_directions"], {})
            validation = validate_user_layer(root)
            self.assertTrue(validation["production_memory"]["ok"])

    def test_topic_check_returns_compact_conflicts_without_full_history(self) -> None:
        from tools.kb.production_memory import check_topics, record_topics

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_topics(
                root,
                "sample-account",
                [
                    {
                        "topic_id": "topic_1",
                        "title": "普通人如何提高认知",
                        "audience": "普通人",
                        "problem": "提高认知",
                        "direction": "个人成长",
                        "angle": "三个行动步骤",
                        "mechanism": "输入后通过行动验证",
                        "content_type": "知识口播",
                    }
                ],
            )

            result = check_topics(
                root,
                "sample-account",
                [
                    {
                        "candidate_id": "new_1",
                        "title": "普通人提高认知的三个办法",
                        "audience": "普通人",
                        "problem": "提高认知",
                        "direction": "个人成长",
                        "angle": "三个行动步骤",
                        "mechanism": "输入后通过行动验证",
                        "content_type": "知识口播",
                    }
                ],
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["checked_history_count"], 1)
            self.assertEqual(result["results"][0]["status"], "blocked")
            self.assertEqual(len(result["results"][0]["conflicts"]), 1)
            self.assertEqual(result["token_boundary"], "compact_conflicts_only")

    def test_production_feedback_is_linked_by_content_id(self) -> None:
        from tools.kb.production_memory import (
            record_feedback,
            record_production,
            record_topics,
            review_context,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_topics(
                root,
                "sample-account",
                [{"topic_id": "topic_1", "title": "测试选题"}],
            )
            record_production(
                root,
                {
                    "content_id": "content_1",
                    "topic_id": "topic_1",
                    "account_skill_id": "sample-account",
                    "skill_version": "1.0",
                },
            )
            record_feedback(
                root,
                {
                    "feedback_id": "feedback_1",
                    "content_id": "content_1",
                    "source_type": "table",
                    "metrics": {"views": 100},
                    "assessment": "钩子弱",
                },
            )

            context = review_context(root, "content_1")

            self.assertTrue(context["ok"])
            self.assertEqual(context["content"]["topic_id"], "topic_1")
            self.assertEqual(context["feedback"][0]["metrics"]["views"], 100)
            self.assertEqual(context["token_boundary"], "one_content_only")

    def test_account_visual_gate_blocks_unvalidated_production_and_records_lineage(self) -> None:
        from tools.kb.production_memory import record_production, record_topics, review_context

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account_dir = root / "10_Knowledge/formal/accounts/视觉账号"
            skill_path = account_dir / "skill/SKILL.md"
            skill_path.parent.mkdir(parents=True)
            skill_path.write_text("---\nname: visual-account\ndescription: test\n---\n", encoding="utf-8")
            (account_dir / "ACCOUNT_SKILL_MANIFEST.json").write_text(
                json.dumps({
                    "account_skill_id": "visual-account",
                    "required_production_gates": ["visual_package"],
                }),
                encoding="utf-8",
            )
            registry = root / "20_User/config/account_skill_registry.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(
                json.dumps({
                    "accounts": [{
                        "account_skill_id": "visual-account",
                        "skill_path": "10_Knowledge/formal/accounts/视觉账号/skill/SKILL.md",
                    }]
                }),
                encoding="utf-8",
            )
            record_topics(root, "visual-account", [{"topic_id": "topic_visual", "title": "视觉测试"}])
            base_payload = {
                "content_id": "content_visual",
                "topic_id": "topic_visual",
                "account_skill_id": "visual-account",
                "skill_version": "1.9",
            }
            with self.assertRaisesRegex(ValueError, "visual_status=approved"):
                record_production(root, base_payload)

            visual_path = root / "visual-lineage.json"
            visual_path.write_text(
                json.dumps({
                    "account_skill_id": "visual-account",
                    "skill_version": "1.9",
                    "content_id": "content_visual",
                    "golden_package_version": "1.0",
                    "generator": {"name": "imagegen", "model_version": "test-model"},
                    "references": [{"id": "golden-ref"}],
                    "pages": [{
                        "id": "master",
                        "status": "approved",
                        "visual_review": {"texture_naturalness": "passed"},
                    }],
                    "calibration_gate": {"status": "passed"},
                    "validation": {
                        "status": "passed",
                        "validator": "visual-package-v1.0",
                        "validated_at": "2026-07-19T12:00:00+08:00",
                        "prompt_set_sha256": "a" * 64,
                    },
                }),
                encoding="utf-8",
            )
            recorded = record_production(root, {
                **base_payload,
                "visual_status": "approved",
                "visual_manifest_path": "visual-lineage.json",
            })
            context = review_context(root, "content_visual")

            self.assertTrue(recorded["ok"])
            self.assertEqual(recorded["required_production_gates"], ["visual_package"])
            self.assertEqual(context["content"]["visual_status"], "approved")
            self.assertEqual(context["content"]["visual_golden_version"], "1.0")
            self.assertEqual(context["content"]["reference_assets"], ["golden-ref"])
            self.assertEqual(context["content"]["visual_qa"]["master"]["texture_naturalness"], "passed")

    def test_account_skill_registry_resolves_alias_to_account_center_skill(self) -> None:
        from tools.kb.account_skills import resolve_account_skill, sync_registry, validate_registry
        from tools.kb.user_layer import initialize_user_layer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_user_layer(root)
            account_dir = root / "10_Knowledge/formal/accounts/样例账号"
            skill = account_dir / "skill/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: account-sample\ndescription: Use for sample account production.\n---\n\n# Skill\n\n"
                "Run topic-memory-check before production, topic-memory-record after confirmation, "
                "and production-memory-record after delivery.\n",
                encoding="utf-8",
            )
            for reference in ("production.md", "style.md", "boundaries.md", "acceptance.md"):
                target = skill.parent / "references" / reference
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# {reference}\n", encoding="utf-8")
            for view in ("账号整体方法论.md", "内容生产使用说明.md", "减少AI味输出规则.md", "内容输出标准模板.md"):
                (account_dir / view).write_text(
                    "<!-- account-view: source=skill; sync=required -->\n\n账号 Skill 版本：1.0\n",
                    encoding="utf-8",
                )
            (account_dir / "ACCOUNT_SKILL_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "account_skill_id": "sample",
                        "account_name": "样例账号",
                        "platform": "抖音",
                        "skill_name": "account-sample",
                        "version": "1.0",
                        "status": "active",
                        "aliases": ["样例账号"],
                        "canonical_skill_path": "10_Knowledge/formal/accounts/样例账号/skill/SKILL.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index = root / "10_Knowledge/evidence/index/account_knowledge_index.json"
            index.parent.mkdir(parents=True)
            index.write_text(
                json.dumps(
                    {
                        "accounts": [
                            {
                                "account_id": "sample",
                                "account_name": "样例账号",
                                "platform": "抖音",
                                "formal_account_dir": str(account_dir.relative_to(root)),
                                "directions": [],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            synced = sync_registry(root)
            resolved = resolve_account_skill(root, "请按样例账号生成选题")

            self.assertTrue(synced["ok"])
            self.assertTrue(validate_registry(root)["ok"])
            self.assertTrue(resolved["ok"])
            self.assertEqual(resolved["account_skill_id"], "sample")
            self.assertTrue(resolved["skill_path"].endswith("skill/SKILL.md"))

    def test_account_skill_registry_rejects_missing_human_view(self) -> None:
        from tools.kb.account_skills import sync_registry, validate_registry
        from tools.kb.user_layer import initialize_user_layer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initialize_user_layer(root)
            account_dir = root / "10_Knowledge/formal/accounts/样例账号"
            skill = account_dir / "skill/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: account-sample\ndescription: sample\n---\n"
                "topic-memory-check topic-memory-record production-memory-record\n",
                encoding="utf-8",
            )
            for reference in ("production.md", "style.md", "boundaries.md", "acceptance.md"):
                target = skill.parent / "references" / reference
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# reference\n", encoding="utf-8")
            (account_dir / "ACCOUNT_SKILL_MANIFEST.json").write_text(
                json.dumps(
                    {
                        "account_skill_id": "sample",
                        "account_name": "样例账号",
                        "version": "1.0",
                        "status": "active",
                        "canonical_skill_path": "10_Knowledge/formal/accounts/样例账号/skill/SKILL.md",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index = root / "10_Knowledge/evidence/index/account_knowledge_index.json"
            index.parent.mkdir(parents=True)
            index.write_text(
                json.dumps(
                    {
                        "accounts": [
                            {
                                "account_id": "sample",
                                "account_name": "样例账号",
                                "formal_account_dir": "10_Knowledge/formal/accounts/样例账号",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            sync_registry(root)
            validation = validate_registry(root)

            self.assertFalse(validation["ok"])
            self.assertIn(
                "account_skill_view_file_missing:sample:账号整体方法论.md",
                validation["errors"],
            )


if __name__ == "__main__":
    unittest.main()
