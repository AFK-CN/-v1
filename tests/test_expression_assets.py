import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from tools.kb.expression_assets import (
    canonical_sha256,
    load_expression_asset_contract,
    validate_expression_asset_file,
    validate_expression_asset_record,
)
from tools.kb.validator import validate_expression_asset_contract


class ExpressionAssetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(
            Path("00_System/shareable/config/expression_asset_contract.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def valid_record(account_id: str = "account-alpha", asset_id: str = "asset-001") -> dict:
        registry = {
            "source_registry_id": f"registry-{asset_id}",
            "source_id": f"source-{asset_id}",
            "source_type": "account_source_positive",
            "account_id": account_id,
            "source_path_or_url": f"evidence/{account_id}/{asset_id}.md",
            "sha256": "a" * 64,
        }
        registry_hash = canonical_sha256(registry)
        authority = {
            "authority_record_id": f"authority-{asset_id}",
            "source_id": registry["source_id"],
            "source_type": registry["source_type"],
            "account_id": account_id,
            "source_path_or_url": registry["source_path_or_url"],
            "sha256": registry["sha256"],
        }
        authority_hash = canonical_sha256(authority)
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
            "transition_history": [
                {
                    "from": "observed",
                    "to": "sampled",
                    "evidence_coordinate": f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/sample.md:L1-L2",
                    "evidence_sha256": "b" * 64,
                }
            ],
            "gate_evidence": {
                "sample_selection": [
                    {
                        "evidence_coordinate": f"10_Knowledge/evidence/index/account_validation_authority/{account_id}/sample.md:L1-L2",
                        "evidence_sha256": "b" * 64,
                    }
                ]
            },
            "source": {
                "source_id": registry["source_id"],
                "source_registry_id": registry["source_registry_id"],
                "source_type": "account_source_positive",
                "source_account_id": account_id,
                "source_path_or_url": registry["source_path_or_url"],
                "evidence_coordinate": f"{registry['source_path_or_url']}:L10-L12",
                "sha256": "a" * 64,
                "registry_record_sha256": registry_hash,
                "authority_manifest_path": f"10_Knowledge/evidence/index/account_source_authority/{account_id}/sources.jsonl",
                "authority_record_id": authority["authority_record_id"],
                "authority_record_sha256": authority_hash,
            },
            "source_excerpt": "一段仅保存在账号候选区的来源摘录",
            "abstracted_pattern": "具体处境 + 明确矛盾 + 继续阅读收益",
            "pattern_variables": {
                "hook_role": "conflict",
                "situation": "具体处境",
                "tension": "明确矛盾",
                "payoff": "继续阅读收益",
            },
            "adaptation_template": "当[具体处境]出现[明确矛盾]时，承诺后文给出[可验证收益]。",
            "source_usage": {
                "display_eligible": True,
                "retrieval_eligible": True,
                "generation_eligible": False,
            },
            "pattern_usage": {
                "candidate_reference_eligible": True,
                "production_eligible": False,
                "requires_user_confirmation": True,
            },
            "structural_usefulness_score": 78,
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

    @staticmethod
    def authority_for(record: dict) -> dict:
        source = record["source"]
        item = {
            "authority_record_id": source["authority_record_id"],
            "source_id": source["source_id"],
            "source_type": source["source_type"],
            "account_id": source["source_account_id"],
            "source_path_or_url": source["source_path_or_url"],
            "sha256": source["sha256"],
        }
        item["authority_record_sha256"] = canonical_sha256(item)
        return item

    @classmethod
    def prepare_authority_and_evidence(cls, root: Path, records: list[dict]) -> None:
        authorities: dict[str, list[dict]] = {}
        for record in records:
            source = record["source"]
            source_path = root / source["source_path_or_url"]
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(f"evidence for {record['asset_id']}\n", encoding="utf-8")
            source["sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
            for transition in record["transition_history"]:
                report_path = root / transition["evidence_coordinate"].rsplit(":L", 1)[0]
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text("sample report\n", encoding="utf-8")
                transition["evidence_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
            for evidence_items in record["gate_evidence"].values():
                for item in evidence_items:
                    report_path = root / item["evidence_coordinate"].rsplit(":L", 1)[0]
                    item["evidence_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
            authority = cls.authority_for(record)
            source["authority_record_sha256"] = authority["authority_record_sha256"]
            registry = cls.registry_for(record)
            source["registry_record_sha256"] = registry["registry_record_sha256"]
            authorities.setdefault(record["account_id"], []).append(authority)
        for account_id, items in authorities.items():
            path = root / f"10_Knowledge/evidence/index/account_source_authority/{account_id}/sources.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")

    @staticmethod
    def registry_for(record: dict) -> dict:
        source = record["source"]
        item = {
            "source_registry_id": source["source_registry_id"],
            "source_id": source["source_id"],
            "source_type": source["source_type"],
            "account_id": source["source_account_id"],
            "source_path_or_url": source["source_path_or_url"],
            "sha256": source["sha256"],
        }
        item["registry_record_sha256"] = canonical_sha256(item)
        return item

    def test_contract_is_generic_and_integrated_into_the_single_active_pipeline(self) -> None:
        failures: list[str] = []
        validate_expression_asset_contract(self.contract, failures)

        self.assertEqual(failures, [])
        self.assertEqual(self.contract["scope"], "generic_contract_and_active_pipeline")
        self.assertTrue(self.contract["activation_boundary"]["active_account_learning_integration"])
        self.assertFalse(self.contract["activation_boundary"]["needs_user_confirmation"])
        pipeline = json.loads(
            Path("00_System/shareable/config/account_learning_pipeline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(pipeline["version"], "3.0")
        self.assertIn("expression_asset_learning", pipeline)
        self.assertEqual([item["id"] for item in pipeline["stages"]], [
            "stage0_account_overview",
            "stage1_parallel_extraction",
            "stage2_triple_verification",
            "stage3_ria_construction",
            "stage4_method_linking",
            "stage5_pressure_test",
            "stage6_learning_delivery",
        ])
        active_skill = Path("00_System/shareable/skills/active/account-learning/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("expression-asset-learning.md", active_skill)
        self.assertIn("同一七阶段", active_skill)
        proposal = Path(
            "00_System/shareable/skills/proposals/account-learning-expression-assets-v3.0.md"
        ).read_text(encoding="utf-8")
        self.assertIn("status: approved_and_implemented", proposal)
        self.assertIn("needs_user_confirmation: false", proposal)

    def test_valid_candidate_record_separates_source_pattern_score_and_performance(self) -> None:
        record = self.valid_record()

        errors = validate_expression_asset_record(record, self.contract, expected_account_id="account-alpha")

        self.assertEqual(errors, [])
        self.assertNotEqual(record["source_excerpt"], record["abstracted_pattern"])
        self.assertEqual(record["performance_evidence"]["status"], "not_claimed")

    def test_candidate_record_rejects_activation_cross_account_and_false_performance_claims(self) -> None:
        record = self.valid_record()
        record["callable"] = True
        record["method_evidence_eligible"] = True
        record["source"]["source_account_id"] = "account-beta"
        record["performance_evidence"] = {
            "status": "validated_with_evidence",
            "evidence_coordinates": ["trust-me"],
            "evidence_kind": "transcript_only",
            "metric": "viral",
            "sample_size": 1,
            "observation_window": "one item",
            "source_hashes": ["not-a-hash"],
        }

        errors = validate_expression_asset_record(record, self.contract, expected_account_id="account-alpha")

        self.assertIn("candidate_must_not_be_callable", errors)
        self.assertIn("candidate_must_not_be_method_evidence", errors)
        self.assertIn("source_account_isolation_failed", errors)
        self.assertIn("validated_performance_requires_traceable_coordinates", errors)
        self.assertIn("validated_performance_evidence_kind_invalid", errors)
        self.assertIn("validated_performance_sample_too_small", errors)
        self.assertIn("validated_performance_source_hashes_invalid", errors)

    def test_rejected_output_is_validation_only(self) -> None:
        record = self.valid_record()
        record["source"]["source_type"] = "user_rejected_output"
        record["intended_usage"] = ["generation_reference"]

        errors = validate_expression_asset_record(record, self.contract)

        self.assertIn("rejected_output_must_be_validation_only", errors)
        self.assertIn("rejected_output_must_be_rejected_anti_pattern", errors)

    def test_rejected_output_can_only_be_a_non_generating_rejected_anti_pattern(self) -> None:
        record = self.valid_record()
        record["asset_type"] = "anti_pattern"
        record["lifecycle_state"] = "rejected"
        record["transition_history"] = [
            {
                "from": "observed",
                "to": "rejected",
                "evidence_coordinate": "10_Knowledge/evidence/index/account_validation_authority/account-alpha/rejection.md:L1-L2",
                "evidence_sha256": "b" * 64,
            }
        ]
        record["gate_evidence"] = {}
        record["source"]["source_type"] = "user_rejected_output"
        record["intended_usage"] = ["validation_only"]

        errors = validate_expression_asset_record(record, self.contract)

        self.assertEqual(errors, [])

    def test_source_coordinate_state_and_unknown_effect_claim_cannot_bypass_contract(self) -> None:
        record = self.valid_record()
        record["source"]["evidence_coordinate"] = "evidence/account-beta/other.md:L1-L2"
        record["lifecycle_state"] = "pressure_tested"
        record["claimed_effectiveness"] = "proven viral"
        record["source_usage"]["generation_input"] = True
        record["pattern_usage"]["auto_publish"] = True

        errors = validate_expression_asset_record(record, self.contract)

        self.assertIn("evidence_coordinate_source_mismatch", errors)
        self.assertIn("transition_history_does_not_reach_state", errors)
        self.assertIn("unknown_field:claimed_effectiveness", errors)
        self.assertIn("source_usage_unknown_field:generation_input", errors)
        self.assertIn("pattern_usage_unknown_field:auto_publish", errors)

    def test_transition_and_gate_evidence_cannot_use_another_account_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            record = self.valid_record()
            self.prepare_authority_and_evidence(root, [record])
            beta_report = root / "10_Knowledge/evidence/index/account_validation_authority/account-beta/sample.md"
            beta_report.parent.mkdir(parents=True)
            beta_report.write_text("real beta report\n", encoding="utf-8")
            beta_sha = hashlib.sha256(beta_report.read_bytes()).hexdigest()
            beta_coordinate = "10_Knowledge/evidence/index/account_validation_authority/account-beta/sample.md:L1-L1"
            record["transition_history"][0]["evidence_coordinate"] = beta_coordinate
            record["transition_history"][0]["evidence_sha256"] = beta_sha
            record["gate_evidence"]["sample_selection"][0]["evidence_coordinate"] = beta_coordinate
            record["gate_evidence"]["sample_selection"][0]["evidence_sha256"] = beta_sha
            target = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha/expression_assets.sample.jsonl"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            (target.parent / "source_registry.jsonl").write_text(
                json.dumps(self.registry_for(record), ensure_ascii=False) + "\n", encoding="utf-8"
            )

            result = validate_expression_asset_file(root, target, expected_account_id="account-alpha")

            self.assertFalse(result["ok"])
            self.assertTrue(any("account_validation_namespace_mismatch" in item for item in result["errors"]))

    def test_file_validator_rejects_cross_account_mixing_and_wrong_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            target = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha/expression_assets.sample.jsonl"
            target.parent.mkdir(parents=True)
            first = self.valid_record()
            second = self.valid_record(account_id="account-beta", asset_id="asset-002")
            self.prepare_authority_and_evidence(root, [first, second])
            target.write_text(
                json.dumps(first, ensure_ascii=False)
                + "\n"
                + json.dumps(second, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            registry = target.parent / "source_registry.jsonl"
            registry.write_text(
                json.dumps(self.registry_for(first), ensure_ascii=False)
                + "\n"
                + json.dumps(self.registry_for(second), ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            result = validate_expression_asset_file(root, target)

            self.assertFalse(result["ok"])
            self.assertIn("file_cross_account_mixing_forbidden", result["errors"])
            self.assertIn("file_account_directory_mismatch", result["errors"])

    def test_file_validator_binds_sources_to_registry_and_enforces_sample_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            target = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha/expression_assets.sample.jsonl"
            target.parent.mkdir(parents=True)
            records = [self.valid_record(asset_id=f"asset-{index:03d}") for index in range(21)]
            self.prepare_authority_and_evidence(root, records)
            records[0]["source"]["source_path_or_url"] = "evidence/account-beta/forged.md"
            records[0]["source"]["evidence_coordinate"] = "evidence/account-beta/forged.md:L1-L2"
            forged_registry = self.registry_for(records[0])
            records[0]["source"]["registry_record_sha256"] = forged_registry["registry_record_sha256"]
            registries = [self.registry_for(item) for item in records]
            target.write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8"
            )
            (target.parent / "source_registry.jsonl").write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in registries), encoding="utf-8"
            )

            result = validate_expression_asset_file(root, target, expected_account_id="account-alpha")

            self.assertFalse(result["ok"])
            self.assertIn("sample_item_limit_exceeded", result["errors"])
            self.assertTrue(any("source_authority_binding_mismatch:source_path_or_url" in item for item in result["errors"]))

    def test_sample_file_passes_only_with_authority_and_real_evidence_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            record = self.valid_record()
            self.prepare_authority_and_evidence(root, [record])
            target = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha/expression_assets.sample.jsonl"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            (target.parent / "source_registry.jsonl").write_text(
                json.dumps(self.registry_for(record), ensure_ascii=False) + "\n", encoding="utf-8"
            )

            result = validate_expression_asset_file(root, target, expected_account_id="account-alpha")

            self.assertTrue(result["ok"], result["errors"])

    def test_validated_performance_must_resolve_to_independent_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            record = self.valid_record()
            self.prepare_authority_and_evidence(root, [record])
            metric_path = root / "metrics/account-alpha/performance.md"
            metric_path.parent.mkdir(parents=True)
            metric_path.write_text("registered nowhere\n", encoding="utf-8")
            metric_hash = hashlib.sha256(metric_path.read_bytes()).hexdigest()
            record["performance_evidence"] = {
                "status": "validated_with_evidence",
                "evidence_coordinates": ["metrics/account-alpha/performance.md:L1-L1"],
                "evidence_kind": "platform_metrics",
                "metric": "completion_rate",
                "sample_size": 999,
                "observation_window": "7d",
                "source_hashes": [metric_hash],
                "authority_manifest_path": "10_Knowledge/evidence/index/performance_authority/account-alpha/metrics.jsonl",
                "authority_record_ids": ["performance-001"],
            }
            target = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha/expression_assets.sample.jsonl"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            (target.parent / "source_registry.jsonl").write_text(
                json.dumps(self.registry_for(record), ensure_ascii=False) + "\n", encoding="utf-8"
            )

            result = validate_expression_asset_file(root, target, expected_account_id="account-alpha")

            self.assertFalse(result["ok"])
            self.assertTrue(any("performance_authority:authority_manifest_missing" in item for item in result["errors"]))

    def test_full_file_cannot_use_self_signed_acceptance_without_real_sample(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            record = self.valid_record()
            self.prepare_authority_and_evidence(root, [record])
            target = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha/expression_assets.jsonl"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            registry_path = target.parent / "source_registry.jsonl"
            registry_path.write_text(json.dumps(self.registry_for(record), ensure_ascii=False) + "\n", encoding="utf-8")
            audit_path = root / "10_Knowledge/evidence/index/account_validation_authority/account-alpha/acceptance.md"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text("self signed\n", encoding="utf-8")
            acceptance = {
                "status": "accepted",
                "account_id": "account-alpha",
                "validator_version": "expression_asset_validator_v3.0",
                "sample_count": 1,
                "sample_file_sha256": "c" * 64,
                "sample_record_hashes": [canonical_sha256(record)],
                "sample_validation_sha256": "",
                "source_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
                "completed_checks": self.contract["gates"]["sample_acceptance"],
                "audit_report_coordinate": "10_Knowledge/evidence/index/account_validation_authority/account-alpha/acceptance.md:L1-L1",
                "audit_report_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                "evidence_coordinates": ["10_Knowledge/evidence/index/account_validation_authority/account-alpha/acceptance.md:L1-L1"],
            }
            (target.parent / "sample_acceptance.json").write_text(
                json.dumps(acceptance, ensure_ascii=False), encoding="utf-8"
            )

            result = validate_expression_asset_file(root, target, expected_account_id="account-alpha")

            self.assertFalse(result["ok"])
            self.assertIn("accepted_sample_file_missing", result["errors"])

    def test_alpha_full_cannot_use_beta_sample_even_with_matching_acceptance_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "00_System/shareable/config"
            config.mkdir(parents=True)
            (config / "expression_asset_contract.json").write_text(
                json.dumps(self.contract, ensure_ascii=False), encoding="utf-8"
            )
            alpha = self.valid_record(account_id="account-alpha", asset_id="asset-alpha")
            beta = self.valid_record(account_id="account-beta", asset_id="asset-beta")
            self.prepare_authority_and_evidence(root, [alpha, beta])
            directory = root / "10_Knowledge/candidates/account_assets/expression_assets/account-alpha"
            directory.mkdir(parents=True)
            full_path = directory / "expression_assets.jsonl"
            sample_path = directory / "expression_assets.sample.jsonl"
            full_path.write_text(json.dumps(alpha, ensure_ascii=False) + "\n", encoding="utf-8")
            sample_path.write_text(json.dumps(beta, ensure_ascii=False) + "\n", encoding="utf-8")
            registry_path = directory / "source_registry.jsonl"
            registry_path.write_text(
                json.dumps(self.registry_for(alpha), ensure_ascii=False)
                + "\n"
                + json.dumps(self.registry_for(beta), ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            sample_validation = validate_expression_asset_file(root, sample_path, expected_account_id="account-alpha")
            receipt = {
                key: sample_validation.get(key)
                for key in (
                    "ok",
                    "status",
                    "path",
                    "record_count",
                    "account_ids",
                    "errors",
                    "contract_version",
                    "activation_boundary",
                )
            }
            receipt_sha = hashlib.sha256(
                json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            audit_path = root / "10_Knowledge/evidence/index/account_validation_authority/account-alpha/acceptance.md"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text("alpha acceptance\n", encoding="utf-8")
            acceptance = {
                "status": "accepted",
                "account_id": "account-alpha",
                "validator_version": "expression_asset_validator_v3.0",
                "sample_count": 1,
                "sample_file_sha256": hashlib.sha256(sample_path.read_bytes()).hexdigest(),
                "sample_record_hashes": [canonical_sha256(beta)],
                "sample_validation_sha256": receipt_sha,
                "source_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
                "completed_checks": self.contract["gates"]["sample_acceptance"],
                "audit_report_coordinate": "10_Knowledge/evidence/index/account_validation_authority/account-alpha/acceptance.md:L1-L1",
                "audit_report_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                "evidence_coordinates": ["10_Knowledge/evidence/index/account_validation_authority/account-alpha/acceptance.md:L1-L1"],
            }
            (directory / "sample_acceptance.json").write_text(
                json.dumps(acceptance, ensure_ascii=False), encoding="utf-8"
            )

            result = validate_expression_asset_file(root, full_path, expected_account_id="account-alpha")

            self.assertFalse(result["ok"])
            self.assertTrue(any("sample_validation_failed:file_account_directory_mismatch" in item for item in result["errors"]))

    def test_malformed_contract_fails_safe_validation(self) -> None:
        payload = deepcopy(self.contract)
        payload["storage"]["candidate_root_template"] = "00_System/shareable/assets/{account_id}/"
        payload["activation_boundary"]["active_account_learning_integration"] = False
        failures: list[str] = []

        validate_expression_asset_contract(payload, failures)

        self.assertIn("expression_asset_candidate_root_invalid", failures)
        self.assertIn("expression_asset_activation_boundary_invalid", failures)


if __name__ == "__main__":
    unittest.main()
