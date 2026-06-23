from __future__ import annotations

import argparse
import json
from pathlib import Path

from .asset_builder import build_candidate_assets
from .candidate_search import search_candidates
from .dashboard import write_dashboard
from .evolution import write_evolution_report
from .indexer import write_indexes
from .reorganizer import apply_reorganization_plan, write_reorganization_plan
from .review_report import write_review_report
from .web_console import serve as serve_web_console
from .scanner import write_scan_report
from .task_runner import create_task, finish_task
from .validator import validate_system
from tools.jianghushuo_learning_index import write_learning_index
from tools.jianghushuo_card_validator import validate_cards
from tools.jianghushuo_account_ingest import ingest_direction


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base system tools.")
    parser.add_argument("--root", default=".", help="Knowledge base root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan files and cleanup candidates")
    subparsers.add_parser("index", help="Write knowledge indexes")
    subparsers.add_parser("jianghushuo-index", help="Write Jianghushuo account-level learning index")
    subparsers.add_parser("jianghushuo-validate-cards", help="Validate Jianghushuo learning card templates")
    ingest_parser = subparsers.add_parser("jianghushuo-ingest-direction", help="Ingest one Jianghushuo learned direction into formal account center")
    ingest_parser.add_argument("--direction", required=True)
    assets_parser = subparsers.add_parser("assets", help="Build candidate asset pools")
    assets_parser.add_argument("--top-n", type=int, default=10)
    search_parser = subparsers.add_parser("search-candidates", help="Search candidate assets by query/account/direction")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--account", default="")
    search_parser.add_argument("--direction", default="")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--include-raw", action="store_true")
    subparsers.add_parser("report", help="Write review report")
    subparsers.add_parser("plan-reorg", help="Plan root directory reorganization")
    apply_reorg_parser = subparsers.add_parser("apply-reorg", help="Apply a reviewed root reorganization plan")
    apply_reorg_parser.add_argument("--plan", required=True)
    apply_reorg_parser.add_argument("--allow-delete", action="store_true")
    subparsers.add_parser("validate-system", help="Validate minimum KB system behavior")
    subparsers.add_parser("dashboard", help="Write KB runtime dashboard and registry")
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

    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == "scan":
        result = write_scan_report(root)
    elif args.command == "index":
        result = write_indexes(root)
    elif args.command == "jianghushuo-index":
        result = write_learning_index(root)
    elif args.command == "jianghushuo-validate-cards":
        result = validate_cards(root)
    elif args.command == "jianghushuo-ingest-direction":
        result = ingest_direction(root, args.direction)
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
    elif args.command == "report":
        result = write_review_report(root)
    elif args.command == "plan-reorg":
        result = write_reorganization_plan(root)
    elif args.command == "apply-reorg":
        result = apply_reorganization_plan(root, root / args.plan, allow_delete=args.allow_delete)
    elif args.command == "validate-system":
        result = validate_system(root)
    elif args.command == "dashboard":
        result = write_dashboard(root)
    elif args.command == "evolution-report":
        result = write_evolution_report(root)
    elif args.command == "task":
        result = create_task(root, args.name, command=args.task_command)
    elif args.command == "web":
        return serve_web_console(root, host=args.host, port=args.port, start_worker=not args.no_worker)
    else:
        result = finish_task(root, args.task_id, args.status, summary=args.summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
