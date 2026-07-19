from __future__ import annotations

import argparse
import json
from pathlib import Path

from .asset_builder import build_candidate_assets
from .account_skills import (
    audit_account_skill_v29_compatibility,
    resolve_account_skill,
    sync_registry,
    upgrade_all_formal_account_skills_v29,
    upgrade_formal_account_skill_v29,
    validate_registry,
    write_account_indexes,
)
from .candidate_search import search_candidates
from .call_resolver import resolve_call
from .dashboard import write_dashboard
from .distribution import audit_distribution, export_system_package
from .expression_assets import validate_expression_asset_file
from .formal_search import build_formal_search_index, search_formal
from .indexer import write_indexes
from .production_memory import (
    check_topics,
    initialize_database as initialize_production_memory,
    record_feedback,
    record_production,
    record_topics,
    review_context,
)
from .release_gate import DEFAULT_MAX_SEARCH_MS, DEFAULT_SMOKE_QUERY, run_release_gate
from .reorganizer import apply_reorganization_plan, initialize_layer_structure, write_reorganization_plan
from .review_report import write_review_report
from .runtime import doctor_runtime, health_gate, initialize_runtime, mark_dirty, repair_runtime
from .skill_package import sync_installed_skill_packages, write_skill_packages
from .scanner import write_scan_report
from .system_cleaner import audit_system_boundaries, rewrite_legacy_path_references
from .task_runner import create_task, finish_task
from .user_layer import initialize_user_layer, validate_user_layer
from .validator import validate_system
from tools.creator_db_export import export_creator_database
from tools import account_learning_pipeline, image_text_learning
from tools.account_learning_card import validate_card_file
from tools.sqlite_ingest import ingest_sqlite_database, sqlite_ingest_status


def compact_sqlite_result(root: Path, payload: dict) -> dict:
    database = str(payload.get("database") or "")
    try:
        database_path = Path(database)
        if database_path.is_absolute():
            database = str(database_path.resolve().relative_to(root.resolve()))
    except (OSError, ValueError):
        database = Path(database).name if database else ""
    accounts = []
    for item in payload.get("accounts", []) if isinstance(payload.get("accounts"), list) else []:
        if not isinstance(item, dict):
            continue
        accounts.append(
            {
                "platform": item.get("platform", ""),
                "account_name": item.get("account_name", ""),
                "content_count": item.get("content_count", 0),
            }
        )
    tables = [item for item in payload.get("tables", []) if isinstance(item, dict)]
    result = {
        key: payload[key]
        for key in ("ok", "status", "batch_id", "latest_batch_id", "latest_batch_dir", "content", "comments", "candidate_count", "missing_stable_ids")
        if key in payload
    }
    result.update(
        {
            "database": database,
            "account_count": len(accounts),
            "accounts": accounts,
            "tables": {
                "count": len(tables),
                "nonempty_count": sum(int(item.get("count", 0) or 0) > 0 for item in tables),
                "row_count": sum(int(item.get("count", 0) or 0) for item in tables),
            },
            "output_mode": "compact",
        }
    )
    last = payload.get("last_result")
    if isinstance(last, dict):
        result["last_result"] = {
            key: last[key]
            for key in ("ok", "status", "batch_id", "content", "comments", "candidate_count", "missing_stable_ids")
            if key in last
        }
    return result


def compact_account_learning_result(payload: dict) -> dict:
    stages = payload.get("stages", []) if isinstance(payload.get("stages"), list) else []
    validations = payload.get("validations", {})
    if isinstance(validations, list):
        validation_by_stage = {
            str(item.get("stage_id") or ""): item for item in validations if isinstance(item, dict)
        }
    elif isinstance(validations, dict):
        validation_by_stage = validations
    else:
        validation_by_stage = {}
    stage_summary = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("id") or "")
        validation = validation_by_stage.get(stage_id, {})
        stage_summary.append(
            {
                "id": stage_id,
                "status": stage.get("status", ""),
                "validation_ok": validation.get("ok") if isinstance(validation, dict) else None,
            }
        )
    if not stage_summary:
        for stage_id, validation in validation_by_stage.items():
            stage_summary.append(
                {
                    "id": stage_id,
                    "validation_ok": validation.get("ok") if isinstance(validation, dict) else None,
                }
            )
    return {
        key: payload[key]
        for key in (
            "ok",
            "workflow_id",
            "account_name",
            "status",
            "current_stage",
            "completed_stage_failures",
            "formal_write_allowed",
        )
        if key in payload
    } | {
        "stage_count": len(stages) or len(validation_by_stage),
        "stages": stage_summary,
        "output_mode": "compact",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base system tools.")
    parser.add_argument("--root", default=".", help="Knowledge base root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan files and cleanup candidates")
    subparsers.add_parser("index", help="Write knowledge indexes")
    account_learning_init = subparsers.add_parser("account-learning-init", help="Initialize the professional seven-stage account learning pipeline")
    account_learning_init.add_argument("--account-name", required=True)
    account_learning_init.add_argument("--source-scope", required=True)
    account_learning_init.add_argument("--media-branch", action="append", required=True)
    account_learning_init.add_argument("--profile-id", default="")
    account_learning_init.add_argument("--workflow-id", default="")
    for account_learning_command in ("status", "validate"):
        command = subparsers.add_parser(f"account-learning-{account_learning_command}", help=f"{account_learning_command.title()} a professional account learning workflow")
        command.add_argument("--workflow-id", required=True)
        command.add_argument("--verbose", action="store_true", help="Return full per-stage validation details")
    account_learning_refresh = subparsers.add_parser("account-learning-refresh", help="Refresh stored validation evidence for a rebuilt workflow")
    account_learning_refresh.add_argument("--workflow-id", required=True)
    account_learning_refresh.add_argument("--source-scope", default="")
    account_learning_migrate = subparsers.add_parser(
        "account-learning-migrate",
        help="Backfill stage-6 account Skill candidate packages from approved formal account Skills",
    )
    account_learning_migrate_scope = account_learning_migrate.add_mutually_exclusive_group(required=True)
    account_learning_migrate_scope.add_argument("--workflow-id")
    account_learning_migrate_scope.add_argument("--all", action="store_true")
    account_learning_migrate.add_argument("--force", action="store_true")
    subparsers.add_parser(
        "account-learning-v29-audit",
        help="Audit all registered account workflows and same-account Skill snapshots against v2.9",
    )
    subparsers.add_parser(
        "account-skills-v29-audit",
        help="Audit every registered formal account Skill for the v2.9 no-loss upgrade contract",
    )
    account_skills_v29_upgrade = subparsers.add_parser(
        "account-skills-v29-upgrade",
        help="Add the v2.9 no-loss upgrade guard to registered formal account Skills",
    )
    account_skills_v29_scope = account_skills_v29_upgrade.add_mutually_exclusive_group(required=True)
    account_skills_v29_scope.add_argument("--account-skill-id")
    account_skills_v29_scope.add_argument("--all", action="store_true")
    account_skills_v29_upgrade.add_argument("--user-confirmed", action="store_true")
    account_learning_complete = subparsers.add_parser("account-learning-complete-stage", help="Validate and complete one professional account learning stage")
    account_learning_complete.add_argument("--workflow-id", required=True)
    account_learning_complete.add_argument("--stage", required=True)
    account_learning_complete.add_argument("--user-confirmed", action="store_true")
    account_learning_card = subparsers.add_parser("account-learning-validate-card", help="Validate one learning card against the unified three-layer contract")
    account_learning_card.add_argument("--path", required=True)
    assets_parser = subparsers.add_parser("assets", help="Build candidate asset pools")
    assets_parser.add_argument("--top-n", type=int, default=10)
    search_parser = subparsers.add_parser("search-candidates", help="Search candidate assets by query/account/direction")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--account", default="")
    search_parser.add_argument("--direction", default="")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--include-raw", action="store_true")
    subparsers.add_parser("formal-search-index", help="Rebuild the formal-only hybrid retrieval cache")
    formal_search_parser = subparsers.add_parser(
        "search-formal",
        help="Search approved formal knowledge with BM25, local vector similarity, filters and reranking",
    )
    formal_search_parser.add_argument("--query", required=True)
    formal_search_parser.add_argument("--account", default="")
    formal_search_parser.add_argument("--direction", default="")
    formal_search_parser.add_argument("--role", default="")
    formal_search_parser.add_argument("--limit", type=int, default=8)
    formal_search_parser.add_argument("--rebuild", action="store_true")
    expression_validate_parser = subparsers.add_parser(
        "expression-assets-validate",
        help="Validate a per-account expression-asset candidate JSONL without activating account learning",
    )
    expression_validate_parser.add_argument("--path", required=True)
    expression_validate_parser.add_argument("--account-id", default="")
    resolve_parser = subparsers.add_parser("resolve-call", help="Resolve a user prompt into a deterministic KB call plan")
    resolve_parser.add_argument("--text", required=True)
    subparsers.add_parser("report", help="Write review report")
    subparsers.add_parser("plan-reorg", help="Plan root directory reorganization")
    subparsers.add_parser("init-layers", help="Create the target layered directory skeleton")
    apply_reorg_parser = subparsers.add_parser("apply-reorg", help="Apply a reviewed root reorganization plan")
    apply_reorg_parser.add_argument("--plan", required=True)
    apply_reorg_parser.add_argument("--allow-delete", action="store_true")
    subparsers.add_parser("validate-system", help="Validate minimum KB system behavior")
    release_gate_parser = subparsers.add_parser(
        "release-gate",
        help="Run the complete engineering release gate for the current knowledge-base baseline",
    )
    release_gate_parser.add_argument("--query", default=DEFAULT_SMOKE_QUERY)
    release_gate_parser.add_argument("--max-search-ms", type=float, default=DEFAULT_MAX_SEARCH_MS)
    release_gate_parser.add_argument("--require-clean-git", action="store_true")
    subparsers.add_parser("distribution-audit", help="Audit the system-only share package for user data, machine paths and secrets")
    system_export_parser = subparsers.add_parser("system-export", help="Export a system-only package from the share manifest")
    system_export_parser.add_argument("--output", required=True)
    system_export_parser.add_argument("--force", action="store_true")
    clean_parser = subparsers.add_parser("clean-system-boundaries", help="Rewrite legacy knowledge paths and audit rule/knowledge boundaries")
    clean_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("dashboard", help="Write KB runtime dashboard and registry")
    subparsers.add_parser("skill-packages", help="Regenerate Skill packages from the shared contract")
    skill_install_parser = subparsers.add_parser(
        "skill-install",
        help="Install or synchronize the global knowledge-base Skill entrypoints",
    )
    skill_install_parser.add_argument("--target-root", default="", help="Skills directory; defaults to $CODEX_HOME/skills")
    skill_install_parser.add_argument("--dry-run", action="store_true")
    user_init_parser = subparsers.add_parser("user-init", help="Initialize the portable user-layer structure and local production database")
    user_init_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("user-validate", help="Validate user-layer configuration, account Skill registry and production database")
    subparsers.add_parser("account-skills-sync", help="Register formal account-center Skills in the user-layer registry")
    account_skill_resolve = subparsers.add_parser("account-skill-resolve", help="Resolve an account name or alias to its formal account Skill")
    account_skill_resolve.add_argument("--text", required=True)
    subparsers.add_parser("production-memory-init", help="Initialize the local topic, production and feedback database")
    for command_name in ("topic-memory-check", "topic-memory-record"):
        command = subparsers.add_parser(command_name, help=f"{command_name.replace('-', ' ').title()} from a JSON list")
        command.add_argument("--account-skill-id", required=True)
        command.add_argument("--input", required=True, help="JSON file containing a list or an object with a topics list")
    production_record = subparsers.add_parser("production-memory-record", help="Record one produced content item from JSON")
    production_record.add_argument("--input", required=True)
    feedback_record = subparsers.add_parser("feedback-memory-record", help="Record one feedback item from JSON")
    feedback_record.add_argument("--input", required=True)
    review_context_parser = subparsers.add_parser("review-context", help="Read compact production and feedback context for one content id")
    review_context_parser.add_argument("--content-id", required=True)
    init_parser = subparsers.add_parser("init", help="Initialize or migrate the KB runtime lifecycle")
    init_parser.add_argument("--no-rebuild", action="store_true")
    init_parser.add_argument("--no-migrate", action="store_true")
    init_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("health-gate", help="Check the shared daily health credential without scanning knowledge")
    subparsers.add_parser("doctor", help="Run a deep read-only KB runtime diagnosis")
    repair_parser = subparsers.add_parser("repair", help="Repair reproducible runtime outputs and mark stale tasks")
    repair_parser.add_argument("--no-rebuild", action="store_true")
    repair_parser.add_argument("--stale-after-seconds", type=int, default=600)
    repair_parser.add_argument("--dry-run", action="store_true")
    dirty_parser = subparsers.add_parser("mark-dirty", help="Increment the shared KB dirty generation")
    dirty_parser.add_argument("--reason", required=True)
    dirty_parser.add_argument("--path", action="append", default=[])
    task_parser = subparsers.add_parser("task", help="Create a manual wakeup task")
    task_parser.add_argument("name")
    task_parser.add_argument("--task-command", default="")
    finish_parser = subparsers.add_parser("finish-task", help="Finish a manual wakeup task")
    finish_parser.add_argument("task_id")
    finish_parser.add_argument("status", choices=["done", "failed", "paused"])
    finish_parser.add_argument("--summary", default="")
    export_parser = subparsers.add_parser("export-creator-db", help="Export one creator's database contents/comments and optionally write a Feishu sheet")
    export_parser.add_argument("--creator", required=True, help="Creator/blogger nickname to match")
    export_parser.add_argument("--platform", default="", help="Optional platform filter: douyin/xhs/weibo/bilibili/kuaishou/tieba/zhihu")
    export_parser.add_argument("--db-path", default="", help="SQLite database path, defaults to 数据/sqlite_tables.db")
    export_parser.add_argument("--output-dir", default="", help="Output directory, defaults to 90_Temp/exports/creator_db")
    export_parser.add_argument("--limit", type=int, default=0, help="Optional max content rows per content table")
    export_parser.add_argument("--no-comments", action="store_true", help="Do not export comments")
    export_parser.add_argument("--to-feishu", action="store_true", help="Create a Feishu spreadsheet and write exported rows")
    export_parser.add_argument("--public-share", action="store_true", help="Set Feishu link sharing to internet-readable after writing")
    export_parser.add_argument("--dry-run", action="store_true", help="Write local export and print Feishu dry-run requests if --to-feishu is set")
    sqlite_ingest_parser = subparsers.add_parser("sqlite-ingest", help="Read 数据/sqlite_tables.db and generate incremental candidate summaries")
    sqlite_ingest_mode = sqlite_ingest_parser.add_mutually_exclusive_group()
    sqlite_ingest_mode.add_argument("--apply", action="store_true", help="Write state, inbox candidates and lightweight indexes")
    sqlite_ingest_mode.add_argument("--dry-run", action="store_true", help="Preview changes without writing outputs")
    sqlite_ingest_parser.add_argument("--db-path", default="", help="SQLite database path, defaults to 数据/sqlite_tables.db")
    sqlite_ingest_parser.add_argument("--batch-id", default="", help="Optional deterministic batch id for tests or reruns")
    sqlite_ingest_parser.add_argument("--verbose", action="store_true", help="Return full account, user and table details")
    sqlite_status_parser = subparsers.add_parser("sqlite-status", help="Show SQLite ingest state")
    sqlite_status_parser.add_argument("--verbose", action="store_true", help="Return full account, user and table details")
    image_text_env_parser = subparsers.add_parser("image-text-env", help="Check image-text learning tool availability")
    image_text_env_parser.add_argument("--paddleocr-command", default="")
    image_text_env_parser.add_argument("--image2-command", default="")
    image_text_ingest_parser = subparsers.add_parser("image-text-ingest", help="Register a local image package for account learning")
    image_text_ingest_parser.add_argument("--account-name", required=True)
    image_text_ingest_parser.add_argument("--profile-id", default="")
    image_text_ingest_parser.add_argument("--platform", default="xhs")
    image_text_ingest_parser.add_argument("--input-dir", required=True)
    image_text_ingest_parser.add_argument("--posts-file", default="", help="JSON/JSONL manifest grouping ordered images with title, caption and tags")
    image_text_ingest_parser.add_argument("--workflow-id", default="")
    image_text_ingest_parser.add_argument("--ocr-engine", default="none")
    image_text_ingest_parser.add_argument("--ocr-lang", default="chi_sim+eng")
    image_text_ingest_parser.add_argument("--ocr-psm", type=int, default=6)
    image_text_ingest_parser.add_argument("--visual-feature-engine", default="opencv", choices=["none", "pillow", "opencv"])
    image_text_ingest_parser.add_argument("--paddleocr-command", default="")
    image_text_ingest_parser.add_argument("--image2-mode", default="codex", choices=["codex", "external", "none"])
    image_text_ingest_parser.add_argument("--image2-command", default="")
    image_text_ingest_parser.add_argument("--image2-timeout", type=int, default=60)
    for image_text_command in ("structure", "scan", "learn", "status"):
        command = subparsers.add_parser(f"image-text-{image_text_command}", help=f"Run image-text {image_text_command} step")
        command.add_argument("--workflow-id", required=True)
    image_text_select_parser = subparsers.add_parser("image-text-select", help="Select structured image-text posts for candidate learning")
    image_text_select_parser.add_argument("--workflow-id", required=True)
    image_text_select_parser.add_argument("--top-n", type=int, default=0)

    args = parser.parse_args()
    root = Path(args.root).resolve()
    exit_code = 0
    if args.command == "scan":
        result = write_scan_report(root)
    elif args.command == "index":
        result = write_indexes(root)
    elif args.command == "account-learning-init":
        result = account_learning_pipeline.init_workflow(
            root,
            account_name=args.account_name,
            source_scope=args.source_scope,
            media_branches=args.media_branch,
            profile_id=args.profile_id,
            workflow_id=args.workflow_id,
        )
    elif args.command == "account-learning-status":
        result = account_learning_pipeline.workflow_status(root, args.workflow_id)
        if not result.get("ok", False):
            exit_code = 2
        if not args.verbose:
            result = compact_account_learning_result(result)
    elif args.command == "account-learning-validate":
        result = account_learning_pipeline.validate_workflow(root, args.workflow_id)
        if not result.get("ok", False):
            exit_code = 2
        if not args.verbose:
            result = compact_account_learning_result(result)
    elif args.command == "account-learning-refresh":
        result = account_learning_pipeline.refresh_workflow(
            root,
            args.workflow_id,
            source_scope=args.source_scope,
        )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-learning-migrate":
        if args.all:
            result = account_learning_pipeline.migrate_all_account_skill_candidates(root, force=args.force)
        else:
            result = account_learning_pipeline.migrate_account_skill_candidate(
                root,
                args.workflow_id,
                force=args.force,
            )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-learning-v29-audit":
        result = account_learning_pipeline.audit_all_account_learning_v29(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-skills-v29-audit":
        result = audit_account_skill_v29_compatibility(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-skills-v29-upgrade":
        if args.all:
            result = upgrade_all_formal_account_skills_v29(
                root,
                user_confirmed=args.user_confirmed,
            )
        else:
            result = upgrade_formal_account_skill_v29(
                root,
                args.account_skill_id,
                user_confirmed=args.user_confirmed,
            )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-learning-complete-stage":
        result = account_learning_pipeline.complete_stage(
            root,
            args.workflow_id,
            args.stage,
            user_confirmed=args.user_confirmed,
        )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-learning-validate-card":
        card_path = Path(args.path)
        if not card_path.is_absolute():
            card_path = root / card_path
        result = validate_card_file(card_path, root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "assets":
        result = build_candidate_assets(root, top_n=max(args.top_n, 1))
    elif args.command == "search-candidates":
        result = search_candidates(
            root,
            query=args.query,
            account_name=args.account,
            direction=args.direction,
            limit=args.limit,
            include_raw=args.include_raw,
        )
        if result.get("status") == "requires_init":
            exit_code = 2
    elif args.command == "formal-search-index":
        result = build_formal_search_index(root)
    elif args.command == "search-formal":
        result = search_formal(
            root,
            query=args.query,
            account=args.account,
            direction=args.direction,
            document_role=args.role,
            limit=args.limit,
            rebuild=args.rebuild,
        )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "expression-assets-validate":
        result = validate_expression_asset_file(
            root,
            Path(args.path),
            expected_account_id=args.account_id,
        )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "resolve-call":
        result = resolve_call(root, args.text)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "report":
        result = write_review_report(root)
    elif args.command == "plan-reorg":
        result = write_reorganization_plan(root)
    elif args.command == "init-layers":
        result = initialize_layer_structure(root)
    elif args.command == "apply-reorg":
        result = apply_reorganization_plan(root, root / args.plan, allow_delete=args.allow_delete)
    elif args.command == "validate-system":
        result = validate_system(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "release-gate":
        result = run_release_gate(
            root,
            query=args.query,
            max_search_ms=max(float(args.max_search_ms), 1.0),
            require_clean_git=args.require_clean_git,
        )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "distribution-audit":
        result = audit_distribution(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "system-export":
        result = export_system_package(root, Path(args.output), force=args.force)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "clean-system-boundaries":
        rewrite_result = rewrite_legacy_path_references(root, dry_run=args.dry_run)
        audit_result = audit_system_boundaries(root)
        result = {"ok": audit_result["ok"], "rewrite": rewrite_result, "audit": audit_result}
        if not result["ok"]:
            exit_code = 2
    elif args.command == "dashboard":
        result = write_dashboard(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "skill-packages":
        result = write_skill_packages(root)
    elif args.command == "skill-install":
        result = sync_installed_skill_packages(
            root,
            Path(args.target_root) if args.target_root else None,
            dry_run=args.dry_run,
        )
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "user-init":
        result = initialize_user_layer(root, dry_run=args.dry_run)
    elif args.command == "user-validate":
        result = validate_user_layer(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "account-skills-sync":
        account_index_result = write_account_indexes(root)
        result = sync_registry(root)
        result["account_index"] = account_index_result
        registry_validation = validate_registry(root)
        result["validation"] = registry_validation
        if (
            not account_index_result.get("ok", False)
            or not result.get("ok", False)
            or not registry_validation.get("ok", False)
        ):
            exit_code = 2
    elif args.command == "account-skill-resolve":
        result = resolve_account_skill(root, args.text)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "production-memory-init":
        result = initialize_production_memory(root)
    elif args.command in {"topic-memory-check", "topic-memory-record"}:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = root / input_path
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        topics = payload.get("topics", []) if isinstance(payload, dict) else payload
        if not isinstance(topics, list):
            raise ValueError("topic input must be a JSON list or an object with a topics list")
        if args.command == "topic-memory-check":
            result = check_topics(root, args.account_skill_id, topics)
        else:
            result = record_topics(root, args.account_skill_id, topics)
    elif args.command in {"production-memory-record", "feedback-memory-record"}:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = root / input_path
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("production memory input must be a JSON object")
        result = record_production(root, payload) if args.command == "production-memory-record" else record_feedback(root, payload)
    elif args.command == "review-context":
        result = review_context(root, args.content_id)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "init":
        try:
            result = initialize_runtime(
                root,
                rebuild=not args.no_rebuild,
                migrate=not args.no_migrate,
                dry_run=args.dry_run,
            )
        except RuntimeError as exc:
            if str(exc) != "maintenance_in_progress":
                raise
            result = {"ok": False, "status": "maintenance_in_progress"}
            exit_code = 4
        if not result.get("ok", False):
            exit_code = exit_code or 3
    elif args.command == "health-gate":
        result = health_gate(root)
        exit_code = {
            "healthy": 0,
            "requires_init": 2,
            "requires_doctor": 2,
            "maintenance_in_progress": 4,
            "blocked": 3,
        }.get(result.get("status"), 3)
    elif args.command == "doctor":
        try:
            result = doctor_runtime(root)
        except RuntimeError as exc:
            if str(exc) != "maintenance_in_progress":
                raise
            result = {"status": "maintenance_in_progress", "checks": {}, "repair_actions": []}
        exit_code = {
            "healthy": 0,
            "repairable": 2,
            "requires_init": 2,
            "maintenance_in_progress": 4,
            "blocked": 3,
        }.get(result.get("status"), 3)
    elif args.command == "repair":
        try:
            result = repair_runtime(
                root,
                rebuild=not args.no_rebuild,
                stale_after_seconds=max(args.stale_after_seconds, 1),
                dry_run=args.dry_run,
            )
        except RuntimeError as exc:
            if str(exc) != "maintenance_in_progress":
                raise
            result = {"ok": False, "status": "maintenance_in_progress", "rerun_task_count": 0}
            exit_code = 4
        if not result.get("ok", False):
            exit_code = exit_code or 3
    elif args.command == "mark-dirty":
        result = mark_dirty(root, args.reason, args.path)
    elif args.command == "task":
        result = create_task(root, args.name, command=args.task_command)
    elif args.command == "export-creator-db":
        result = export_creator_database(
            root,
            args.creator,
            platform=args.platform or None,
            db_path=Path(args.db_path) if args.db_path else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            include_comments=not args.no_comments,
            limit=args.limit or None,
            dry_run=args.dry_run,
            to_feishu=args.to_feishu,
            public_share=args.public_share,
        )
    elif args.command == "sqlite-ingest":
        result = ingest_sqlite_database(
            root,
            apply=bool(args.apply),
            db_path=Path(args.db_path) if args.db_path else None,
            batch_id=args.batch_id or None,
        )
        if not args.verbose:
            result = compact_sqlite_result(root, result)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "sqlite-status":
        result = sqlite_ingest_status(root)
        if not args.verbose:
            result = compact_sqlite_result(root, result)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "image-text-env":
        result = image_text_learning.image_text_env_report(args.image2_command, args.paddleocr_command)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "image-text-ingest":
        result = image_text_learning.command_ingest(args)
    elif args.command == "image-text-structure":
        result = image_text_learning.command_structure(args)
    elif args.command == "image-text-scan":
        result = image_text_learning.command_scan(args)
    elif args.command == "image-text-select":
        result = image_text_learning.command_select(args)
    elif args.command == "image-text-learn":
        result = image_text_learning.command_learn(args)
    elif args.command == "image-text-status":
        result = image_text_learning.command_status(args)
    else:
        result = finish_task(root, args.task_id, args.status, summary=args.summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
