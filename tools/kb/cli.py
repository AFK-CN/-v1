from __future__ import annotations

import argparse
import json
from pathlib import Path

from .asset_builder import build_candidate_assets
from .agent_registry import write_agent_registry, validate_agent_registry
from .candidate_search import search_candidates
from .call_resolver import resolve_call
from .dashboard import write_dashboard
from .evolution import write_evolution_report
from .indexer import write_indexes
from .memory import create_memory_candidate, evaluate_memory_capture, list_memory
from .reorganizer import apply_reorganization_plan, initialize_layer_structure, write_reorganization_plan
from .review_report import write_review_report
from .runtime import doctor_runtime, health_gate, initialize_runtime, mark_dirty, repair_runtime
from .skill_package import write_skill_packages
from .web_console import serve as serve_web_console
from .scanner import write_scan_report
from .system_cleaner import audit_system_boundaries, rewrite_legacy_path_references
from .task_runner import create_task, finish_task
from .validator import validate_system
from tools.creator_db_export import export_creator_database
from tools.sqlite_ingest import ingest_sqlite_database, sqlite_ingest_status
from tools.video_learning_account_ingest import AccountIngestConfig, ingest_directions as ingest_video_learning_directions
from tools.video_learning_card_validator import validate_cards as validate_video_learning_cards


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base system tools.")
    parser.add_argument("--root", default=".", help="Knowledge base root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan files and cleanup candidates")
    subparsers.add_parser("index", help="Write knowledge indexes")
    account_validate_parser = subparsers.add_parser("account-validate-cards", help="Validate learned cards for one account profile")
    account_validate_parser.add_argument("--profile", required=True)
    account_ingest_parser = subparsers.add_parser("account-ingest-direction", help="Ingest one learned direction into a formal account center")
    account_ingest_parser.add_argument("--profile", required=True)
    account_ingest_parser.add_argument("--account-id", required=True)
    account_ingest_parser.add_argument("--account-name", required=True)
    account_ingest_parser.add_argument("--formal-account-dir", required=True)
    account_ingest_parser.add_argument("--direction", required=True)
    account_ingest_parser.add_argument("--platform", default="抖音")
    assets_parser = subparsers.add_parser("assets", help="Build candidate asset pools")
    assets_parser.add_argument("--top-n", type=int, default=10)
    search_parser = subparsers.add_parser("search-candidates", help="Search candidate assets by query/account/direction")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--account", default="")
    search_parser.add_argument("--direction", default="")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--include-raw", action="store_true")
    resolve_parser = subparsers.add_parser("resolve-call", help="Resolve a user prompt into a deterministic KB call plan")
    resolve_parser.add_argument("--text", required=True)
    subparsers.add_parser("report", help="Write review report")
    subparsers.add_parser("plan-reorg", help="Plan root directory reorganization")
    subparsers.add_parser("init-layers", help="Create the target layered directory skeleton")
    apply_reorg_parser = subparsers.add_parser("apply-reorg", help="Apply a reviewed root reorganization plan")
    apply_reorg_parser.add_argument("--plan", required=True)
    apply_reorg_parser.add_argument("--allow-delete", action="store_true")
    subparsers.add_parser("validate-system", help="Validate minimum KB system behavior")
    clean_parser = subparsers.add_parser("clean-system-boundaries", help="Rewrite legacy knowledge paths and audit rule/knowledge boundaries")
    clean_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("dashboard", help="Write KB runtime dashboard and registry")
    subparsers.add_parser("skill-packages", help="Regenerate Skill packages from the shared contract")
    agents_parser = subparsers.add_parser("agents", help="Regenerate or validate the user-syncable agent registry")
    agents_parser.add_argument("--validate-only", action="store_true")
    memory_parser = subparsers.add_parser("memory", help="List memory locations or create a pending memory candidate")
    memory_parser.add_argument("--title", default="")
    memory_parser.add_argument("--content", default="")
    memory_parser.add_argument("--category", default="session_summary")
    memory_parser.add_argument("--source", default="manual")
    memory_parser.add_argument("--evaluate-text", default="")
    memory_parser.add_argument("--dry-run", action="store_true")
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
    subparsers.add_parser("evolution-report", help="Write candidate-only evolution report")
    task_parser = subparsers.add_parser("task", help="Create a manual wakeup task")
    task_parser.add_argument("name")
    task_parser.add_argument("--task-command", default="")
    finish_parser = subparsers.add_parser("finish-task", help="Finish a manual wakeup task")
    finish_parser.add_argument("task_id")
    finish_parser.add_argument("status", choices=["done", "failed", "paused"])
    finish_parser.add_argument("--summary", default="")
    web_parser = subparsers.add_parser("web", help="Run the local knowledge-base console")
    web_parser.add_argument("--root", default=".")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8787)
    web_parser.add_argument("--no-worker", action="store_true")
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
    subparsers.add_parser("sqlite-status", help="Show SQLite ingest state")

    args = parser.parse_args()
    root = Path(args.root).resolve()
    exit_code = 0
    if args.command == "scan":
        result = write_scan_report(root)
    elif args.command == "index":
        result = write_indexes(root)
    elif args.command == "account-validate-cards":
        result = validate_video_learning_cards(root, args.profile)
        if not result.get("valid", False):
            exit_code = 2
    elif args.command == "account-ingest-direction":
        config = AccountIngestConfig.for_profile(
            profile_id=args.profile,
            account_id=args.account_id,
            account_name=args.account_name,
            platform=args.platform,
            formal_account_dir=Path(args.formal_account_dir),
        )
        result = ingest_video_learning_directions(root, config, [args.direction])
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
    elif args.command == "clean-system-boundaries":
        rewrite_result = rewrite_legacy_path_references(root, dry_run=args.dry_run)
        audit_result = audit_system_boundaries(root)
        result = {"ok": audit_result["ok"], "rewrite": rewrite_result, "audit": audit_result}
        if not result["ok"]:
            exit_code = 2
    elif args.command == "dashboard":
        result = write_dashboard(root)
    elif args.command == "skill-packages":
        result = write_skill_packages(root)
    elif args.command == "agents":
        result = validate_agent_registry(root) if args.validate_only else write_agent_registry(root)
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "memory":
        if args.evaluate_text:
            result = evaluate_memory_capture(root, args.evaluate_text, source=args.source, dry_run=args.dry_run)
        elif args.title or args.content:
            if not args.title or not args.content:
                result = {"ok": False, "error": "memory_requires_title_and_content"}
                exit_code = 2
            else:
                result = create_memory_candidate(root, args.title, args.content, category=args.category, source=args.source)
        else:
            result = list_memory(root)
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
    elif args.command == "evolution-report":
        result = write_evolution_report(root)
    elif args.command == "task":
        result = create_task(root, args.name, command=args.task_command)
    elif args.command == "web":
        return serve_web_console(root, host=args.host, port=args.port, start_worker=not args.no_worker)
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
        if not result.get("ok", False):
            exit_code = 2
    elif args.command == "sqlite-status":
        result = sqlite_ingest_status(root)
        if not result.get("ok", False):
            exit_code = 2
    else:
        result = finish_task(root, args.task_id, args.status, summary=args.summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
