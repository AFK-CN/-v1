from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from tools import account_learning_pipeline
from tools.account_expression_assets import build_expression_asset_package
from tools.kb.expression_assets import canonical_sha256, validate_expression_asset_file


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("00_System/shareable/config/expression_asset_contract.json")
PIPELINE_PATH = Path("00_System/shareable/config/account_learning_pipeline.json")


class AccountExpressionAssetTests(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        for relative in (CONTRACT_PATH, PIPELINE_PATH):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((REPO_ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")
        return root

    @staticmethod
    def _record(account_id: str, asset_id: str) -> dict:
        source_path = f"evidence/{account_id}/{asset_id}.md"
        registry = {
            "source_registry_id": f"registry-{asset_id}",
            "source_id": f"source-{asset_id}",
            "source_type": "account_source_positive",
            "account_id": account_id,
            "source_path_or_url": source_path,
            "sha256": "a" * 64,
        }
        authority = {
            "authority_record_id": f"authority-{asset_id}",
            "source_id": registry["source_id"],
            "source_type": registry["source_type"],
            "account_id": account_id,
            "source_path_or_url": source_path,
            "sha256": registry["sha256"],
        }
        return {
            "asset_id": asset_id,
            "asset_type": "hook",
            "account_id": account_id,
            "source_surface": "video_spoken_middle",
            "content_position": "middle",
            "functional_role": "retention",
            "knowledge_layer": "candidate",
            "callable": False,
            "method_evidence_eligible": False,
            "generation_eligible": False,
            "lifecycle_state": "sampled",
            "transition_history": [{
                "from": "observed",
                "to": "sampled",
                "evidence_coordinate": f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/sample.md:L1-L2",
                "evidence_sha256": "b" * 64,
            }],
            "gate_evidence": {"sample_selection": [{
                "evidence_coordinate": f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/sample.md:L1-L2",
                "evidence_sha256": "b" * 64,
            }]},
            "source": {
                "source_id": registry["source_id"],
                "source_registry_id": registry["source_registry_id"],
                "source_type": registry["source_type"],
                "source_account_id": account_id,
                "source_path_or_url": source_path,
                "evidence_coordinate": f"{source_path}:L1-L2",
                "sha256": registry["sha256"],
                "registry_record_sha256": canonical_sha256(registry),
                "authority_manifest_path": f"10_Knowledge/evidence/index/account_source_authority/{account_id}/sources.jsonl",
                "authority_record_id": authority["authority_record_id"],
                "authority_record_sha256": canonical_sha256(authority),
            },
            "source_excerpt": "到了中段，真正的问题才出现。",
            "abstracted_pattern": "在中段揭示前文未说明的核心矛盾，重新建立继续观看收益。",
            "pattern_variables": {"hook_role": "conflict", "hidden_tension": "核心矛盾"},
            "adaptation_template": "完成[前置行动]后，揭示真正影响结果的是[核心矛盾]。",
            "source_usage": {"display_eligible": True, "retrieval_eligible": True, "generation_eligible": False},
            "pattern_usage": {"candidate_reference_eligible": True, "production_eligible": False, "requires_user_confirmation": True},
            "structural_usefulness_score": 82,
            "performance_evidence": {
                "status": "not_claimed",
                "evidence_coordinates": [],
                "evidence_kind": "",
                "metric": "",
                "sample_size": 0,
                "observation_window": "",
                "source_hashes": [],
                "authority_manifest_path": "",
                "authority_record_ids": [],
            },
            "intended_usage": ["candidate_structure_reference"],
            "risk_flags": ["context_dependence"],
        }

    def _prepare(self, root: Path, output: Path, records: list[dict]) -> None:
        output.mkdir(parents=True, exist_ok=True)
        registries = []
        authorities = []
        for record in records:
            source = record["source"]
            evidence = root / source["source_path_or_url"]
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(f"source evidence for {record['asset_id']}\n", encoding="utf-8")
            source["sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
            report = root / f"10_Knowledge/evidence/index/account_validation_authority/{record['account_id']}/sample.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("sample selection evidence\n", encoding="utf-8")
            report_hash = hashlib.sha256(report.read_bytes()).hexdigest()
            record["transition_history"][0]["evidence_sha256"] = report_hash
            record["gate_evidence"]["sample_selection"][0]["evidence_sha256"] = report_hash
            registry = {
                "source_registry_id": source["source_registry_id"],
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "account_id": source["source_account_id"],
                "source_path_or_url": source["source_path_or_url"],
                "sha256": source["sha256"],
            }
            registry["registry_record_sha256"] = canonical_sha256(registry)
            source["registry_record_sha256"] = registry["registry_record_sha256"]
            registries.append(registry)
            authority = {
                "authority_record_id": source["authority_record_id"],
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "account_id": source["source_account_id"],
                "source_path_or_url": source["source_path_or_url"],
                "sha256": source["sha256"],
            }
            authority["authority_record_sha256"] = canonical_sha256(authority)
            source["authority_record_sha256"] = authority["authority_record_sha256"]
            authorities.append(authority)
        (output / "source_registry.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in registries), encoding="utf-8"
        )
        authority_path = root / f"10_Knowledge/evidence/index/account_source_authority/{records[0]['account_id']}/sources.jsonl"
        authority_path.parent.mkdir(parents=True, exist_ok=True)
        authority_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in authorities), encoding="utf-8"
        )

    def _accept_sample(self, root: Path, output: Path, account_id: str, workflow_id: str, records: list[dict]) -> None:
        sample_path = output / "expression_assets.sample.jsonl"
        sample_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8"
        )
        sample_validation = validate_expression_asset_file(
            root,
            sample_path,
            expected_account_id=account_id,
            expected_workflow_id=workflow_id,
        )
        self.assertTrue(sample_validation["ok"], sample_validation)
        receipt = {key: sample_validation.get(key) for key in (
            "ok", "status", "path", "record_count", "account_ids", "errors", "contract_version", "activation_boundary"
        )}
        receipt_sha = hashlib.sha256(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        audit = root / f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/acceptance.md"
        audit.write_text("sample acceptance audit\n", encoding="utf-8")
        registry = output / "source_registry.jsonl"
        retrieval_path = output / "retrieval_validation.json"
        retrieval = {
            "schema_version": "expression_asset_retrieval_validation_v1",
            "status": "passed",
            "account_id": account_id,
            "sample_file_sha256": hashlib.sha256(sample_path.read_bytes()).hexdigest(),
            "queries": [{"id": "middle-hook", "passed": True}],
            "checks": {
                "top_k_relevance": True,
                "source_traceability": True,
                "abstraction_quality": True,
                "adaptation_quality": True,
                "risk_detection": True,
                "account_isolation": True,
            },
        }
        retrieval_path.write_text(json.dumps(retrieval, ensure_ascii=False), encoding="utf-8")
        acceptance = {
            "status": "accepted",
            "account_id": account_id,
            "validator_version": "expression_asset_validator_v3.1",
            "sample_count": len(records),
            "sample_file_sha256": hashlib.sha256(sample_path.read_bytes()).hexdigest(),
            "sample_record_hashes": [canonical_sha256(item) for item in records],
            "sample_validation_sha256": receipt_sha,
            "retrieval_validation_sha256": hashlib.sha256(retrieval_path.read_bytes()).hexdigest(),
            "source_registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
            "completed_checks": [
                "top_k_relevance", "source_traceability", "abstraction_quality", "adaptation_quality", "risk_detection", "account_isolation"
            ],
            "audit_report_coordinate": f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/acceptance.md:L1-L1",
            "audit_report_sha256": hashlib.sha256(audit.read_bytes()).hexdigest(),
            "evidence_coordinates": [f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/acceptance.md:L1-L1"],
        }
        (output / "sample_acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False), encoding="utf-8")

    def test_package_lists_mid_content_hooks_and_keeps_source_non_generating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            workflow_id = "workflow-alpha"
            account_id = "account-alpha"
            initialized = account_learning_pipeline.init_workflow(
                root,
                account_name="虚构账号甲",
                source_scope="fictional fixture only",
                media_branches=["video", "image_text"],
                profile_id=account_id,
                workflow_id=workflow_id,
            )
            self.assertTrue(initialized["ok"])
            output = root / f"10_Knowledge/candidates/account_learning_workflows/{workflow_id}/expression_assets"
            hook = self._record(account_id, "asset-mid-hook")
            opening = deepcopy(self._record(account_id, "asset-opening-hook"))
            opening.update({"source_surface": "publish_title", "content_position": "title", "functional_role": "attention"})
            opening["pattern_variables"]["hook_role"] = "information_gap"
            opening["source_excerpt"] = "先别急着给答案，这一步才是关键。"
            golden = deepcopy(self._record(account_id, "asset-golden-line"))
            golden.update({"asset_type": "golden_line", "source_surface": "video_spoken_ending", "content_position": "ending", "functional_role": "naming"})
            golden["source_excerpt"] = "方法不是捷径，是把错误变得可检查。"
            records = [hook, opening, golden]
            self._prepare(root, output, records)
            self._accept_sample(root, output, account_id, workflow_id, records)
            full = output / "expression_assets.jsonl"
            full.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")

            result = build_expression_asset_package(
                root,
                full,
                expected_account_id=account_id,
                expected_workflow_id=workflow_id,
            )

            self.assertTrue(result["ok"], result)
            hook_view = (output / "钩子与留存机制图谱.md").read_text(encoding="utf-8")
            self.assertIn("asset-mid-hook", hook_view)
            self.assertIn("middle", hook_view)
            self.assertIn("来源原文（只读/不可生成）", hook_view)
            self.assertTrue((output / "hooks.jsonl").is_file())
            self.assertTrue((output / "golden_lines.jsonl").is_file())
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["boundaries"]["source_generation_eligible"])
            self.assertFalse(manifest["boundaries"]["cross_account_merge"])
            errors: list[str] = []
            metrics: dict = {}
            account_learning_pipeline._validate_expression_asset_stage(
                root,
                output.parent,
                initialized["state"],
                account_learning_pipeline.load_config(root),
                "stage6_learning_delivery",
                errors,
                metrics,
            )
            self.assertEqual(errors, [])
            self.assertEqual(metrics["expression_asset_count"], 3)

    def test_new_workflow_has_one_seven_stage_pipeline_with_expression_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            result = account_learning_pipeline.init_workflow(
                root,
                account_name="虚构测试账号",
                source_scope="fictional fixture only",
                media_branches=["video", "image_text"],
                profile_id="test-account",
            )
            self.assertTrue(result["ok"])
            state = result["state"]
            self.assertEqual(state["expression_asset_schema"], "expression_asset_learning_v3")
            self.assertEqual(state["expression_asset_contract_version"], "3.1")
            self.assertEqual(len(state["stages"]), 7)
            self.assertEqual(len({item["id"] for item in state["stages"]}), 7)
            self.assertTrue((root / result["workflow_dir"] / "expression_assets").is_dir())

    def test_saved_workflow_is_upgraded_in_place_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            initialized = account_learning_pipeline.init_workflow(
                root,
                account_name="虚构历史账号",
                source_scope="fictional fixture only",
                media_branches=["video"],
                profile_id="legacy-account",
            )
            base = root / initialized["workflow_dir"]
            state_path = base / "PIPELINE_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.pop("expression_asset_schema")
            state.pop("expression_asset_contract_version")
            state["schema_version"] = "2.9"
            before_stage_ids = [item["id"] for item in state["stages"]]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            blocked = account_learning_pipeline.upgrade_expression_asset_lane(root, "legacy-account")
            self.assertEqual(blocked["error"], "user_confirmation_required")
            upgraded = account_learning_pipeline.upgrade_expression_asset_lane(
                root,
                "legacy-account",
                user_confirmed=True,
            )

            self.assertTrue(upgraded["ok"])
            self.assertTrue(upgraded["same_workflow"])
            self.assertEqual(upgraded["stage_count"], 7)
            after = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in after["stages"]], before_stage_ids)
            self.assertEqual(after["expression_asset_upgrade"]["status"], "pending_backfill")
            workflow_root = root / "10_Knowledge/candidates/account_learning_workflows"
            self.assertEqual([item.name for item in workflow_root.iterdir() if item.is_dir()], ["legacy-account"])

    def test_expression_lane_stage_gates_cover_sample_linking_and_pressure_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            workflow_id = "gate-workflow"
            account_id = "gate-account"
            initialized = account_learning_pipeline.init_workflow(
                root,
                account_name="虚构门禁账号",
                source_scope="fictional fixture only",
                media_branches=["video"],
                profile_id=account_id,
                workflow_id=workflow_id,
            )
            base = root / initialized["workflow_dir"]
            output = base / "expression_assets"
            record = self._record(account_id, "asset-gate-hook")
            self._prepare(root, output, [record])
            sample_path = output / "expression_assets.sample.jsonl"
            sample_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            (output / "audit_report.json").write_text(
                json.dumps({
                    "schema_version": "expression_asset_audit_v1",
                    "status": "completed",
                    "account_id": account_id,
                    "source_count": 1,
                    "surface_coverage": {"video_spoken_middle": 1},
                    "extraction_started": False,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            config = account_learning_pipeline.load_config(root)

            stage1_errors: list[str] = []
            account_learning_pipeline._validate_expression_asset_stage(
                root, base, initialized["state"], config, "stage1_parallel_extraction", stage1_errors, {}
            )
            self.assertEqual(stage1_errors, [])

            self._accept_sample(root, output, account_id, workflow_id, [record])
            stage2_errors: list[str] = []
            account_learning_pipeline._validate_expression_asset_stage(
                root, base, initialized["state"], config, "stage2_triple_verification", stage2_errors, {}
            )
            self.assertEqual(stage2_errors, [])

            (output / "asset_method_links.jsonl").write_text(
                json.dumps({
                    "asset_id": record["asset_id"],
                    "method_id": "method-fictional",
                    "relation": "supports",
                    "evidence_coordinate": "evidence/gate-account/asset-gate-hook.md:L1-L2",
                }, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            for name in ("钩子与留存机制图谱.md", "金句与句式图谱.md", "内容结构完整图谱.md"):
                (output / name).write_text(f"# {name}\n\n" + "候选机制拆解与来源边界。" * 8, encoding="utf-8")
            stage4_errors: list[str] = []
            account_learning_pipeline._validate_expression_asset_stage(
                root, base, initialized["state"], config, "stage4_method_linking", stage4_errors, {}
            )
            self.assertEqual(stage4_errors, [])

            pressure_path = output / "pressure_test_report.json"
            pressure = {
                "schema_version": "expression_asset_pressure_test_v1",
                "status": "passed",
                "account_id": account_id,
                "test_results": {
                    "retrieval": True,
                    "adaptation": True,
                    "source_copying": True,
                    "unsupported_performance_claim": True,
                    "cross_account_contamination": True,
                    "cross_surface_mismatch": True,
                },
                "failures": [],
            }
            pressure_path.write_text(json.dumps(pressure, ensure_ascii=False), encoding="utf-8")
            stage5_errors: list[str] = []
            account_learning_pipeline._validate_expression_asset_stage(
                root, base, initialized["state"], config, "stage5_pressure_test", stage5_errors, {}
            )
            self.assertEqual(stage5_errors, [])
            pressure["test_results"]["cross_account_contamination"] = False
            pressure_path.write_text(json.dumps(pressure, ensure_ascii=False), encoding="utf-8")
            blocked_errors: list[str] = []
            account_learning_pipeline._validate_expression_asset_stage(
                root, base, initialized["state"], config, "stage5_pressure_test", blocked_errors, {}
            )
            self.assertIn("expression_assets:pressure_test_not_passed", blocked_errors)


if __name__ == "__main__":
    unittest.main()
