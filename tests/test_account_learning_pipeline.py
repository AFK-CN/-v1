from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import account_learning_pipeline


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_RELATIVE = Path("00_System/shareable/config/account_learning_pipeline.json")


class AccountLearningPipelineTest(unittest.TestCase):
    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        config = root / CONFIG_RELATIVE
        config.parent.mkdir(parents=True)
        config.write_text((REPO_ROOT / CONFIG_RELATIVE).read_text(encoding="utf-8"), encoding="utf-8")
        return root

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_jsonl(self, path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")

    def _write_account_skill_candidate(self, base: Path, method_ids: list[str]) -> None:
        skill_root = base / "account_skill_candidate"
        skill_root.mkdir(parents=True, exist_ok=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: account-test\ndescription: Use for test account content production.\n---\n\n"
            "# Test account skill\n\nBefore ideation run topic-memory-check. After confirmation run "
            "topic-memory-record. After delivery run production-memory-record.\n",
            encoding="utf-8",
        )
        for reference in ("production.md", "style.md", "boundaries.md", "acceptance.md"):
            target = skill_root / "references" / reference
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {reference}\n\nCandidate evidence.\n", encoding="utf-8")
        (skill_root / "references" / "visual-evidence.md").write_text(
            "# Visual evidence\n\n"
            "- account_source_positive: generation_reality_calibration_and_validation\n"
            "- user_accepted_ai_output: page_continuity_and_composition_regression_only\n"
            "- user_rejected_output: validation_only\n"
            "- external_reference: explicit_scope_only\n",
            encoding="utf-8",
        )
        for view in ("账号整体方法论.md", "内容生产使用说明.md", "减少AI味输出规则.md", "内容输出标准模板.md"):
            target = skill_root / "account_views" / view
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {view}\n\nCandidate account view.\n", encoding="utf-8")
        self._write_json(
            skill_root / "ACCOUNT_SKILL_MANIFEST.json",
            {
                "schema_version": "account_skill_candidate_v1",
                "status": "ready_for_review",
                "account_skill_id": "test-account",
                "source_method_ids": method_ids,
                "formal_write": False,
                "callable": False,
                "user_review_required": True,
            },
        )
        skill_hash = hashlib.sha256((skill_root / "SKILL.md").read_bytes()).hexdigest()
        self._write_json(
            skill_root / "UPGRADE_COMPATIBILITY.json",
            {
                "schema_version": "account_skill_upgrade_compatibility_v1",
                "account_skill_id": "test-account",
                "base_version": "0",
                "target_version": "1.0",
                "upgrade_scope": "initial_registration",
                "candidate_only": True,
                "formal_write": False,
                "callable": False,
                "user_review_required": True,
                "previous_capability_ids": [],
                "new_capability_ids": ["test-production-baseline"],
                "capabilities": [
                    {
                        "id": "test-production-baseline",
                        "introduced_in": "1.0",
                        "status": "active",
                        "source_paths": ["account_skill_candidate/SKILL.md"],
                    }
                ],
                "changed_capabilities": [],
                "source_snapshot": [
                    {
                        "path": "account_skill_candidate/SKILL.md",
                        "sha256": skill_hash,
                    }
                ],
                "regression_package_manifests": [],
                "isolation": {
                    "same_account_only": True,
                    "cross_account_merge": False,
                    "system_rule_contamination": False,
                    "absolute_or_nas_paths": False,
                },
                "rollback": {"mode": "remove_unapproved_candidate"},
            },
        )
        visual_root = base / "visual_reference_candidate"
        visual_items = []
        roles = ["cover_or_primary_result", "process_or_proof", "detail_or_outcome"]
        risks = ["morphology_sensitive", "material_sensitive", "temporal_state_sensitive"]
        for index, (role, risk) in enumerate(zip(roles, risks), 1):
            asset = visual_root / "assets" / f"reference-{index}.jpg"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(f"account-owned-reference-{index}".encode("utf-8"))
            visual_items.append(
                {
                    "id": f"visual-positive-{index}",
                    "source_kind": "account_source_positive",
                    "source_account_name": "测试账号",
                    "source_id": f"source-{index}",
                    "evidence_coordinate": f"source-{index}#image:{index}",
                    "path": f"assets/reference-{index}.jpg",
                    "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                    "production_roles": [role],
                    "risk_dimensions": [risk],
                    "allowed_use": ["generation_reference", "validation"],
                    "method_evidence_eligible": False,
                    "origin_kind": "account_original",
                    "ai_generated": False,
                    "authenticity_authority": True,
                    "realism_authority": True,
                    "generation_reference_eligible": True,
                }
            )
        self._write_json(
            visual_root / "manifest.json",
            {
                "schema_version": "production_visual_asset_manifest_v1",
                "status": "ready_for_review",
                "account_name": "测试账号",
                "source_kind": "account_source_positive",
                "sampling": "role_and_risk",
                "formal_write": False,
                "callable": False,
                "user_review_required": True,
                "required_roles": roles,
                "required_risk_dimensions": risks,
                "items": visual_items,
            },
        )
        self._write_json(
            base / "VISUAL_REFERENCE_PROFILE.json",
            {
                "schema_version": "production_visual_reference_v1",
                "status": "ready_for_review",
                "account_name": "测试账号",
                "formal_write": False,
                "callable": False,
                "user_review_required": True,
                "visual_applicability": "applicable",
                "sampling_profiles": {
                    "audit_offline_source": "direction_balanced",
                    "production_visual_source": "role_and_risk",
                },
                "production_role_inventory": roles,
                "risk_dimension_inventory": risks,
                "positive_manifest": "visual_reference_candidate/manifest.json",
                "negative_manifest": "",
                "source_separation": {
                    "account_source_positive": "generation_reality_calibration_and_validation",
                    "user_accepted_ai_output": "page_continuity_and_composition_regression_only",
                    "user_rejected_output": "validation_only",
                    "external_reference": "explicit_scope_only",
                },
            },
        )

    def _init(self, root: Path) -> Path:
        result = account_learning_pipeline.init_workflow(
            root,
            account_name="测试账号",
            source_scope="用户指定的 20 条视频和 10 篇图文",
            media_branches=["video", "image_text"],
            profile_id="test-account",
        )
        self.assertTrue(result["ok"])
        return root / result["workflow_dir"]

    def _complete_stage0(self, root: Path, base: Path) -> None:
        (base / "ACCOUNT_OVERVIEW.md").write_text(
            "# 整体理解\n\n## 1. 账号结构\n结构\n\n## 2. 关键术语与定位\n定位\n\n"
            "## 3. 批判与偏差\n偏差\n\n## 4. 学习应用潜力\n应用\n",
            encoding="utf-8",
        )
        self._write_json(
            base / "ACCOUNT_OVERVIEW.json",
            {
                "one_line_theme": "用真实案例解释内容创作方法",
                "content_pillars": ["选题", "结构", "表达"],
                "terminology": ["问题切入", "证据收束", "行动建议"],
                "limitations": ["样本期较短", "平台偏差", "商业内容未完全隔离"],
                "evidence_refs": ["xhs_001", "douyin_002"],
            },
        )
        blocked = account_learning_pipeline.complete_stage(root, "test-account", "stage0_account_overview")
        self.assertEqual(blocked["error"], "user_confirmation_required")
        completed = account_learning_pipeline.complete_stage(
            root, "test-account", "stage0_account_overview", user_confirmed=True
        )
        self.assertTrue(completed["ok"])

    def _complete_stage1(self, root: Path, base: Path) -> list[dict]:
        candidates = []
        for index, filename in enumerate(account_learning_pipeline.LENS_FILES, 1):
            candidate = {
                "id": f"m{index}",
                "title": f"方法 {index}",
                "type": filename.removesuffix(".jsonl"),
                "source_refs": [f"source_{index}"],
                "summary": "这是由独立视角提取的候选方法单元。",
                "tags": ["account-learning"],
            }
            if candidate["type"] == "structures":
                candidate.update(
                    {
                        "observation_schema": "deep_structure_expression_v1",
                        "observation": {
                            "status": "single_card_observation",
                            "dimensions_considered": [
                                "initial_problem_or_context",
                                "concrete_actions",
                                "obstacle_or_conflict",
                            ],
                            "observed_units": [
                                {
                                    "unit": "initial_problem_or_context",
                                    "evidence": "先交代具体问题",
                                    "source_coordinate": "source_3#transcript:1-3",
                                }
                            ],
                            "unit_order": ["initial_problem_or_context"],
                            "missing_or_uncertain_units": ["concrete_actions", "obstacle_or_conflict"],
                            "evidence_coordinates": ["source_3#transcript:1-3"],
                            "structure_fingerprint": "问题语境；单卡草案，待多卡验证",
                        },
                    }
                )
            elif candidate["type"] == "expression":
                publish_dimensions = [
                    "title_promise_and_information_gap",
                    "title_specificity_and_voice",
                    "opening_entry",
                    "body_information_sequence",
                    "operational_or_argument_detail_density",
                    "story_explanation_balance",
                    "lived_experience_signal",
                    "closing_mode",
                    "topic_strategy",
                    "publish_visual_alignment",
                ]
                candidate.update(
                    {
                        "observation_schema": "deep_structure_expression_v1",
                        "observation": {
                            "status": "single_card_observation",
                            "dimensions_considered": ["opening_voice", "concrete_detail", "beneficiary_landing"],
                            "observed_signals": [
                                {
                                    "signal": "concrete_detail",
                                    "evidence": "先说具体经历",
                                    "source_coordinate": "source_4#transcript:2-5",
                                }
                            ],
                            "missing_or_uncertain_signals": ["opening_voice", "beneficiary_landing"],
                            "evidence_coordinates": ["source_4#transcript:2-5"],
                            "expression_fingerprint": "具体经历先行；单卡草案，待多卡验证",
                        },
                        "publish_copy_observation_refs": ["publish-copy-source_4"],
                        "publish_copy_observation": {
                            "schema": "publish_copy_observation_v1",
                            "status": "single_card_observation",
                            "dimensions_considered": publish_dimensions,
                            "observed_signals": [
                                {
                                    "signal": "title_promise_and_information_gap",
                                    "evidence": "标题先承诺具体问题",
                                    "source_coordinate": "card:cards/source_4.md#section:发布内容层学习",
                                }
                            ],
                            "missing_or_uncertain_signals": publish_dimensions[1:],
                            "evidence_coordinates": ["card:cards/source_4.md#section:发布内容层学习"],
                            "publish_layer_status": "observed",
                            "source_facets": {
                                "title": {
                                    "status": "observed_raw",
                                    "evidence": "一个具体问题如何解决",
                                    "source_coordinate": "card:cards/source_4.md#section:发布内容层学习",
                                },
                                "body": {
                                    "status": "observed_analysis",
                                    "evidence": "正文从经历进入并补充步骤",
                                    "source_coordinate": "card:cards/source_4.md#section:发布内容层学习",
                                },
                                "topics": {
                                    "status": "explicitly_missing",
                                    "evidence": "未提供显式话题或标签证据",
                                    "source_coordinate": "card:cards/source_4.md#section:发布内容层学习",
                                },
                                "coordination": {
                                    "status": "observed_analysis",
                                    "evidence": "标题承诺问题，正文完成解释",
                                    "source_coordinate": "card:cards/source_4.md#section:发布内容层学习",
                                },
                            },
                            "publish_copy_fingerprint": "title_promise_and_information_gap；单卡草案，待多卡验证",
                        },
                    }
                )
            candidates.append(candidate)
            self._write_jsonl(base / "candidates" / filename, [candidate])
        publish_record = {
            "id": "publish-copy-source_4",
            "type": "publish_copy_observation",
            "source_refs": ["source_4"],
            "expression_candidate_ids": ["m4"],
            "card_path": "cards/source_4.md",
            "card_schema": "unified_three_layer_v2",
            "compatibility_mode": "unified_card",
            "status": "candidate_observation",
            "callable": False,
            "publish_copy_observation": candidates[3]["publish_copy_observation"],
        }
        publish_path = base / "candidates/publish_copy_observations.jsonl"
        self._write_jsonl(publish_path, [publish_record])
        self._write_json(
            base / "PUBLISH_COPY_SPECIAL_STUDY.json",
            {
                "schema_version": "publish_copy_special_study_v1",
                "workflow_id": "test-account",
                "account_name": "测试账号",
                "status": "completed",
                "observation_schema": "publish_copy_observation_v1",
                "observation_file": "candidates/publish_copy_observations.jsonl",
                "observation_sha256": hashlib.sha256(publish_path.read_bytes()).hexdigest(),
                "expected_source_count": 1,
                "completed_source_count": 1,
                "deferred_source_count": 0,
                "deferred_source_ids": [],
                "unified_card_count": 1,
                "legacy_publish_evidence_count": 0,
                "dimension_coverage": {
                    dimension: {
                        "observed_source_count": 1 if dimension == "title_promise_and_information_gap" else 0,
                        "missing_source_count": 0 if dimension == "title_promise_and_information_gap" else 1,
                    }
                    for dimension in publish_dimensions
                },
                "facet_coverage": {
                    "title": {"observed_raw": 1},
                    "body": {"observed_analysis": 1},
                    "topics": {"explicitly_missing": 1},
                    "coordination": {"observed_analysis": 1},
                },
                "cross_card_pattern_candidates": [
                    {
                        "id": "publish-pattern-test",
                        "signals": ["title_promise_and_information_gap"],
                        "source_count": 1,
                        "source_refs": ["source_4"],
                        "status": "candidate_only",
                        "callable": False,
                        "triple_verification_required": True,
                    }
                ],
                "formal_write": False,
                "callable": False,
                "user_review_required": True,
            },
        )
        (base / "PUBLISH_COPY_SPECIAL_STUDY.md").write_text(
            "# 测试账号发布文案专项学习报告\n\n- 专项观察：1 / 1\n",
            encoding="utf-8",
        )
        state_path = base / "PIPELINE_STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.update(
            {
                "publish_copy_expected_count": 1,
                "publish_copy_completed_count": 1,
                "publish_copy_deferred_count": 0,
            }
        )
        self._write_json(state_path, state)
        (base / "REAL_ACCEPTANCE_REPORT_2026-07-14.md").write_text(
            "# 真实验收\n\n分层样本已回看源证据，未发现未处理严重问题。\n", encoding="utf-8"
        )
        self._write_json(
            base / "REAL_ACCEPTANCE_SUMMARY.json",
            {
                "schema_version": "2.2",
                "status": "passed",
                "report_file": "REAL_ACCEPTANCE_REPORT_2026-07-14.md",
                "sample_method": "fixed-stratified-seed-1",
                "sampled_source_ids": ["source_1", "source_2"],
                "strata": {
                    "normal_visual": {"status": "passed"},
                    "normal_long_transcript": {"status": "passed"},
                    "product_ad": {"status": "not_applicable", "reason": "测试样本无商品广告"},
                    "platform_project": {"status": "not_applicable", "reason": "测试样本无平台项目"},
                    "collaboration_ownership": {"status": "passed"},
                    "low_information_or_asr_risk": {"status": "passed"},
                },
                "severe_issues": [],
                "expanded_audit": {"required": False, "completed": True},
                "semantic_consistency": {"passed": True, "contradiction_count": 0},
                "overview_scope": {"overview_count": 30, "learned_count": 30, "consistent": True},
                "commercial_learning": {
                    "product_ads": {"total": 0, "audited": 0, "artifact": ""},
                    "platform_projects": {"total": 0, "audited": 0, "artifact": ""},
                },
                "formal_write": False,
                "callable": False,
            },
        )
        result = account_learning_pipeline.complete_stage(root, "test-account", "stage1_parallel_extraction")
        self.assertTrue(result["ok"], result)
        return candidates

    def _write_clusters(self, base: Path, candidates: list[dict]) -> None:
        clusters = []
        for item in candidates:
            candidate_id = item["id"]
            is_core = candidate_id == "m1"
            clusters.append(
                {
                    "id": candidate_id,
                    "title": item["title"],
                    "cluster_type": "method_candidate" if is_core else "boundary_rule",
                    "core_mechanism": item["summary"],
                    "candidate_ids": [candidate_id],
                    "source_refs": item["source_refs"],
                    **({"mechanism_kind": "positioning"} if is_core else {}),
                    "lens_roles": {
                        "method_core": [candidate_id] if is_core else [],
                        "support": [],
                        "boundary": [] if is_core else [candidate_id],
                        "evidence_gate": [],
                    },
                }
            )
        self._write_jsonl(base / "candidate_clusters.jsonl", clusters)

    def _complete_stage2(self, root: Path, base: Path, candidates: list[dict]) -> None:
        self._write_clusters(base, candidates)
        verified = {
            "id": "m1",
            "title": "方法 1",
            "triple_verification": {
                "v1_cross_context": {
                    "passed": True,
                    "reason": "在不同平台和不同主题中重复出现",
                    "evidence_refs": ["xhs_001", "douyin_002", "douyin_003"],
                    "relation_or_scene_types": ["职场", "家庭"],
                },
                "v2_predictive_usefulness": {"passed": True, "reason": "能指导新选题判断"},
                "v3_account_exclusivity": {"passed": True, "reason": "不是平台通用常识"},
            },
        }
        rejected = [
            {
                "id": item["id"],
                "title": item["title"],
                "failed_checks": ["v3_account_exclusivity"],
                "reason": "属于行业常识",
                "disposition": "retained_boundary",
            }
            for item in candidates[1:]
        ]
        self._write_jsonl(base / "verified.jsonl", [verified])
        self._write_jsonl(base / "rejected.jsonl", rejected)
        result = account_learning_pipeline.complete_stage(
            root, "test-account", "stage2_triple_verification", user_confirmed=True
        )
        self.assertTrue(result["ok"])

    def _complete_stage3(self, root: Path, base: Path) -> None:
        method_dir = base / "methods" / "m1"
        method_dir.mkdir(parents=True)
        (method_dir / "METHOD.md").write_text(
            "# 方法 1\n\n"
            "## R - 原始证据\n证据\n\n"
            "## I - 方法论解释\n解释\n\n"
            "## A1 - 已发生案例\n案例\n\n"
            "## A2 - 未来触发场景\n触发\n\n"
            "## E - 可执行步骤\n步骤\n\n"
            "## B - 边界与反例\n边界\n",
            encoding="utf-8",
        )
        self._write_json(
            method_dir / "method.json",
            {
                "id": "m1",
                "schema_version": "2.1",
                "version": 1,
                "status": "verified_candidate",
                "callable": False,
                "account_scope": "test-account",
                "title": "方法 1",
                "trigger_signals": ["需要判断新选题是否符合账号"],
                "trigger_model": {
                    "mechanism": "先建立错误规则，再用结果反证",
                    "applicable_relations": ["同学", "同事"],
                    "transferable_scenes": ["校园", "职场"],
                    "do_not_trigger_on": ["只有场景词相同但没有反证结构"],
                },
                "do_not_use": ["纯数据查询"],
                "execution_steps": ["识别问题", "匹配证据", "给出边界"],
                "source_refs": ["xhs_001", "douyin_002", "douyin_003"],
            },
        )
        result = account_learning_pipeline.complete_stage(root, "test-account", "stage3_ria_construction")
        self.assertTrue(result["ok"])

    def test_full_seven_stage_pipeline_is_candidate_only_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._complete_stage0(root, base)
            candidates = self._complete_stage1(root, base)
            self._complete_stage2(root, base, candidates)
            self._complete_stage3(root, base)

            self._write_json(
                base / "METHOD_INDEX.json",
                {"methods": [{"id": "m1", "title": "方法 1"}], "relations": []},
            )
            (base / "GLOSSARY.md").write_text("# 术语\n\n- 问题切入：从具体问题开始。\n", encoding="utf-8")
            self.assertTrue(
                account_learning_pipeline.complete_stage(root, "test-account", "stage4_method_linking")["ok"]
            )

            method_dir = base / "methods" / "m1"
            test_cases = [
                {"id": "positive", "type": "should_trigger", "prompt": "这个选题符合账号吗？"},
                {
                    "id": "negative",
                    "type": "should_not_trigger",
                    "decoy_kind": "lexical_overlap_without_mechanism",
                    "prompt": "只出现同一场景词，但没有方法机制。",
                },
                {"id": "edge", "type": "edge_case", "prompt": "只有一条例子能否形成规律？"},
                {
                    "id": "transfer",
                    "type": "cross_scene_transfer",
                    "source_scene": "职场",
                    "target_scene": "校园",
                    "mechanism_preserved": True,
                    "prompt": "把职场方法迁移到校园，机制仍成立吗？",
                },
                {
                    "id": "commercial",
                    "type": "commercial_contamination",
                    "prompt": "增加商品广告样本后，自然方法证据权重不得增加。",
                },
            ]
            prompts_path = method_dir / "test-prompts.json"
            self._write_json(prompts_path, {"skill": "m1", "test_cases": test_cases})
            case_results = [
                {"id": item["id"], "passed": True, "actual_decision": "expected", "evidence": "独立执行结果"}
                for item in test_cases
            ]
            self._write_json(
                method_dir / "test-results.json",
                {
                    "executor": "independent-test-agent",
                    "executed_at": "2026-01-01T00:00:00+08:00",
                    "prompt_set_sha256": hashlib.sha256(prompts_path.read_bytes()).hexdigest(),
                    "case_results": case_results,
                    "total": 5,
                    "passed": 5,
                    "failed": 0,
                    "pass_rate": 1.0,
                },
            )
            self.assertTrue(
                account_learning_pipeline.complete_stage(root, "test-account", "stage5_pressure_test")["ok"]
            )

            (base / "LEARNING_DIGEST.md").write_text(
                "# 学习交付\n\n这是测试账号的候选方法交付。方法 1 已通过三重验证和压力测试，"
                "可进入用户审核；被淘汰的方法保留在 rejected.jsonl 中，不进入正式账号中心。\n",
                encoding="utf-8",
            )
            self._write_json(
                base / "promotion_manifest.json",
                {
                    "status": "ready_for_review",
                    "method_ids": ["m1"],
                    "formal_write": False,
                    "callable": False,
                    "user_review_required": True,
                },
            )
            self._write_json(
                base / "ACCOUNT_PRODUCTION_HANDOFF.json",
                {
                    "schema_version": "account_production_handoff_v1",
                    "status": "ready_for_review",
                    "formal_write": False,
                    "callable": False,
                    "user_review_required": True,
                    "source_method_ids": ["m1"],
                    "coverage": {
                        "structures": "insufficient_evidence",
                        "expression": "insufficient_evidence",
                        "anti_ai": "insufficient_evidence",
                        "production_templates": "insufficient_evidence",
                        "acceptance": "insufficient_evidence",
                    },
                    "structure_library_candidates": [],
                    "expression_fingerprint_candidates": [],
                    "anti_ai_rule_candidates": [],
                    "production_template_mappings": [],
                    "acceptance_checks": [],
                },
            )
            self._write_account_skill_candidate(base, ["m1"])
            final = account_learning_pipeline.complete_stage(root, "test-account", "stage6_learning_delivery")
            self.assertTrue(final["ok"])
            self.assertEqual(final["next_stage"], "completed")

            status = account_learning_pipeline.workflow_status(root, "test-account")
            self.assertEqual(status["status"], "completed")
            self.assertFalse(status["formal_write_allowed"])
            self.assertFalse((root / "10_Knowledge" / "formal").exists())
            validation = account_learning_pipeline.validate_workflow(root, "test-account")
            self.assertTrue(validation["ok"])

            (base / "account_skill_candidate" / "ACCOUNT_SKILL_MANIFEST.json").unlink()
            invalid_status = account_learning_pipeline.workflow_status(root, "test-account")
            self.assertFalse(invalid_status["ok"])
            self.assertEqual(invalid_status["status"], "completed_with_validation_errors")
            self.assertEqual(invalid_status["completed_stage_failures"], ["stage6_learning_delivery"])

    def test_triple_verification_rejects_unaccounted_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._complete_stage0(root, base)
            candidates = self._complete_stage1(root, base)
            self._write_clusters(base, candidates)
            self._write_jsonl(
                base / "verified.jsonl",
                [
                    {
                        "id": "m1",
                        "title": "方法 1",
                        "triple_verification": {
                            "v1_cross_context": {"passed": True, "reason": "跨场景", "evidence_refs": ["a", "b", "c"], "relation_or_scene_types": ["职场", "家庭"]},
                            "v2_predictive_usefulness": {"passed": True, "reason": "可预测"},
                            "v3_account_exclusivity": {"passed": True, "reason": "账号独特"},
                        },
                    }
                ],
            )
            self._write_jsonl(base / "rejected.jsonl", [])
            result = account_learning_pipeline.validate_stage(root, "test-account", "stage2_triple_verification")
            self.assertFalse(result["ok"])
            self.assertTrue(any(error.startswith("verification_missing_decisions") for error in result["errors"]))
            self.assertEqual(len(candidates), 5)

    def test_structure_method_requires_multi_card_production_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._complete_stage0(root, base)
            candidates = self._complete_stage1(root, base)
            clusters = []
            for item in candidates:
                is_structure = item["type"] == "structures"
                clusters.append(
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "cluster_type": "method_candidate" if is_structure else "boundary_rule",
                        "core_mechanism": item["summary"],
                        "candidate_ids": [item["id"]],
                        "source_refs": item["source_refs"],
                        **({"mechanism_kind": "content_structure"} if is_structure else {}),
                        "lens_roles": {
                            "method_core": [item["id"]] if is_structure else [],
                            "support": [],
                            "boundary": [] if is_structure else [item["id"]],
                            "evidence_gate": [],
                        },
                    }
                )
            self._write_jsonl(base / "candidate_clusters.jsonl", clusters)
            self._write_jsonl(
                base / "verified.jsonl",
                [
                    {
                        "id": "m3",
                        "title": "结构方法",
                        "triple_verification": {
                            "v1_cross_context": {
                                "passed": True,
                                "reason": "跨内容出现",
                                "evidence_refs": ["a", "b", "c"],
                                "relation_or_scene_types": ["职场", "家庭"],
                            },
                            "v2_predictive_usefulness": {"passed": True, "reason": "可指导新任务"},
                            "v3_account_exclusivity": {"passed": True, "reason": "账号独特"},
                        },
                    }
                ],
            )
            self._write_jsonl(
                base / "rejected.jsonl",
                [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "failed_checks": ["v3_account_exclusivity"],
                        "reason": "边界观察",
                        "disposition": "retained_boundary",
                    }
                    for item in candidates
                    if item["id"] != "m3"
                ],
            )

            result = account_learning_pipeline.validate_stage(root, "test-account", "stage2_triple_verification")

            self.assertFalse(result["ok"])
            self.assertIn("cluster:m3:missing_production_analysis", result["errors"])

    def test_production_handoff_verified_coverage_requires_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_jsonl(base / "verified.jsonl", [{"id": "m1", "title": "方法 1"}])
            (base / "LEARNING_DIGEST.md").write_text(
                "# 学习交付\n\n这是一个足够长的候选交付说明，用于记录结构、表达、证据边界、拒绝项和后续审核要求，"
                "不会直接写入正式账号中心。\n",
                encoding="utf-8",
            )
            self._write_json(
                base / "promotion_manifest.json",
                {
                    "status": "ready_for_review",
                    "method_ids": ["m1"],
                    "formal_write": False,
                    "callable": False,
                    "user_review_required": True,
                },
            )
            self._write_json(
                base / "ACCOUNT_PRODUCTION_HANDOFF.json",
                {
                    "schema_version": "account_production_handoff_v1",
                    "status": "ready_for_review",
                    "formal_write": False,
                    "callable": False,
                    "user_review_required": True,
                    "source_method_ids": ["m1"],
                    "coverage": {
                        "structures": "verified",
                        "expression": "insufficient_evidence",
                        "anti_ai": "insufficient_evidence",
                        "production_templates": "insufficient_evidence",
                        "acceptance": "insufficient_evidence",
                    },
                    "structure_library_candidates": [],
                    "expression_fingerprint_candidates": [],
                    "anti_ai_rule_candidates": [],
                    "production_template_mappings": [],
                    "acceptance_checks": [],
                },
            )
            self._write_account_skill_candidate(base, ["m1"])

            result = account_learning_pipeline.validate_stage(root, "test-account", "stage6_learning_delivery")

            self.assertFalse(result["ok"])
            self.assertIn("production_handoff:structures_verified_but_empty", result["errors"])

    def test_visual_reference_rejects_cross_account_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_account_skill_candidate(base, ["m1"])
            manifest_path = base / "visual_reference_candidate" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["items"][0]["source_account_name"] = "另一个账号"
            self._write_json(manifest_path, manifest)

            result = account_learning_pipeline.validate_stage(
                root, "test-account", "stage6_learning_delivery"
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "visual_reference:visual-positive-1:cross_account_asset_forbidden",
                result["errors"],
            )

    def test_v29_stage6_requires_upgrade_compatibility_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_account_skill_candidate(base, ["m1"])
            (base / "account_skill_candidate/UPGRADE_COMPATIBILITY.json").unlink()

            result = account_learning_pipeline.validate_stage(
                root, "test-account", "stage6_learning_delivery"
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "missing:account_skill_candidate/UPGRADE_COMPATIBILITY.json",
                result["errors"],
            )

    def test_v29_stage6_blocks_silent_capability_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_account_skill_candidate(base, ["m1"])
            path = base / "account_skill_candidate/UPGRADE_COMPATIBILITY.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["previous_capability_ids"] = ["lost-capability"]
            self._write_json(path, payload)

            result = account_learning_pipeline.validate_stage(
                root, "test-account", "stage6_learning_delivery"
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "account_skill_upgrade_silent_capability_loss:lost-capability",
                result["errors"],
            )

    def test_visual_reference_requires_declared_role_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_account_skill_candidate(base, ["m1"])
            manifest_path = base / "visual_reference_candidate" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["items"][2]["production_roles"] = ["process_or_proof"]
            self._write_json(manifest_path, manifest)

            result = account_learning_pipeline.validate_stage(
                root, "test-account", "stage6_learning_delivery"
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "visual_reference:role_not_covered:detail_or_outcome", result["errors"]
            )

    def test_visual_reference_rejects_ai_output_mislabeled_as_account_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_account_skill_candidate(base, ["m1"])
            manifest_path = base / "visual_reference_candidate" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["items"][0]["origin_kind"] = "ai_generated"
            manifest["items"][0]["ai_generated"] = True
            self._write_json(manifest_path, manifest)

            result = account_learning_pipeline.validate_stage(
                root, "test-account", "stage6_learning_delivery"
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "visual_reference:visual-positive-1:ai_generated_positive_forbidden",
                result["errors"],
            )

    def test_user_accepted_ai_output_cannot_become_generation_or_realism_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_account_skill_candidate(base, ["m1"])
            profile_path = base / "VISUAL_REFERENCE_PROFILE.json"
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["accepted_ai_output_manifest"] = "visual_regression_candidate/accepted.json"
            self._write_json(profile_path, profile)
            self._write_json(
                base / "visual_regression_candidate" / "accepted.json",
                {
                    "source_kind": "user_accepted_ai_output",
                    "origin_kind": "ai_generated",
                    "reference_policy": "page_continuity_and_composition_regression_only",
                    "account_name": "测试账号",
                    "items": [
                        {
                            "id": "accepted-ai-1",
                            "source_kind": "user_accepted_ai_output",
                            "origin_kind": "ai_generated",
                            "source_account_name": "测试账号",
                            "allowed_use": ["generation_reference"],
                            "authenticity_authority": True,
                            "realism_authority": True,
                            "master_reference_eligible": False,
                            "golden_positive_eligible": False,
                            "method_evidence_eligible": False,
                            "generation_reference_eligible": True,
                        }
                    ],
                },
            )

            result = account_learning_pipeline.validate_stage(
                root, "test-account", "stage6_learning_delivery"
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "visual_reference:accepted-ai-1:allowed_use_invalid", result["errors"]
            )
            self.assertIn(
                "visual_reference:accepted-ai-1:authenticity_authority_must_be_false",
                result["errors"],
            )
            self.assertIn(
                "visual_reference:accepted-ai-1:generation_reference_eligible_must_be_false",
                result["errors"],
            )

    def test_user_accepted_ai_output_allows_only_continuity_and_composition_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            contract = account_learning_pipeline.load_config(root)[
                "stage6_visual_reference_package"
            ]["accepted_ai_output_contract"]
            self._write_json(
                root / "accepted.json",
                {
                    "source_kind": "user_accepted_ai_output",
                    "origin_kind": "ai_generated",
                    "reference_policy": "page_continuity_and_composition_regression_only",
                    "account_name": "测试账号",
                    "items": [
                        {
                            "id": "accepted-ai-regression-1",
                            "source_kind": "user_accepted_ai_output",
                            "origin_kind": "ai_generated",
                            "source_account_name": "测试账号",
                            "allowed_use": [
                                "page_continuity_regression",
                                "composition_regression",
                            ],
                            "authenticity_authority": False,
                            "realism_authority": False,
                            "master_reference_eligible": False,
                            "golden_positive_eligible": False,
                            "method_evidence_eligible": False,
                            "generation_reference_eligible": False,
                        }
                    ],
                },
            )
            errors: list[str] = []

            account_learning_pipeline._validate_accepted_ai_output_manifest(
                root,
                "accepted.json",
                "测试账号",
                contract,
                set(),
                set(),
                errors,
            )

            self.assertEqual(errors, [])

    def test_stage1_rejects_missing_real_acceptance_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            for index, filename in enumerate(account_learning_pipeline.LENS_FILES, 1):
                self._write_jsonl(
                    base / "candidates" / filename,
                    [
                        {
                            "id": f"m{index}",
                            "title": f"方法 {index}",
                            "type": filename.removesuffix(".jsonl"),
                            "source_refs": [f"source_{index}"],
                            "summary": "独立候选",
                            "tags": ["account-learning"],
                        }
                    ],
                )

            result = account_learning_pipeline.validate_stage(root, "test-account", "stage1_parallel_extraction")

            self.assertFalse(result["ok"])
            self.assertIn("real_acceptance:missing_report", result["errors"])
            self.assertIn("real_acceptance:missing_summary:REAL_ACCEPTANCE_SUMMARY.json", result["errors"])

    def test_kb_cli_initializes_pipeline_in_candidate_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(root),
                    "account-learning-init",
                    "--account-name",
                    "CLI 测试账号",
                    "--source-scope",
                    "指定样本",
                    "--media-branch",
                    "video",
                    "--workflow-id",
                    "cli-test",
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue((root / payload["workflow_dir"] / "PIPELINE_STATE.json").exists())
            self.assertFalse((root / "10_Knowledge" / "formal").exists())

    def test_pressure_test_requires_sibling_method_decoy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            base = self._init(root)
            self._write_jsonl(base / "verified.jsonl", [{"id": "m1"}, {"id": "m2"}])
            for method_id in ("m1", "m2"):
                method_dir = base / "methods" / method_id
                cases = [
                    {"id": "positive", "type": "should_trigger", "prompt": "正向场景"},
                    {
                        "id": "negative",
                        "type": "should_not_trigger",
                        "decoy_kind": "lexical_overlap_without_mechanism",
                        "prompt": "只有词相同但机制不同",
                    },
                    {"id": "edge", "type": "edge_case", "prompt": "边界场景"},
                    {
                        "id": "transfer",
                        "type": "cross_scene_transfer",
                        "source_scene": "场景A",
                        "target_scene": "场景B",
                        "mechanism_preserved": True,
                        "prompt": "跨场景但保留机制",
                    },
                    {
                        "id": "commercial",
                        "type": "commercial_contamination",
                        "prompt": "广告样本不得增加自然方法权重",
                    },
                ]
                prompts_path = method_dir / "test-prompts.json"
                self._write_json(prompts_path, {"skill": method_id, "test_cases": cases})
                self._write_json(
                    method_dir / "test-results.json",
                    {
                        "executor": "independent-test-agent",
                        "executed_at": "2026-01-01T00:00:00+08:00",
                        "prompt_set_sha256": hashlib.sha256(prompts_path.read_bytes()).hexdigest(),
                        "case_results": [
                            {"id": item["id"], "passed": True, "actual_decision": "expected", "evidence": "结果"}
                            for item in cases
                        ],
                        "total": 4,
                        "passed": 4,
                        "failed": 0,
                        "pass_rate": 1.0,
                    },
                )

            result = account_learning_pipeline.validate_stage(root, "test-account", "stage5_pressure_test")

            self.assertFalse(result["ok"])
            self.assertIn("pressure_test:m1:missing_sibling_decoy", result["errors"])
            self.assertIn("pressure_test:m2:missing_sibling_decoy", result["errors"])


if __name__ == "__main__":
    unittest.main()
