from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.video_learning_account_ingest import AccountIngestConfig
from tools.video_learning_account_ingest import ingest_direction_package as _ingest_direction_package
from tools.video_learning_account_ingest import ingest_directions as _ingest_directions


JIANGHUSHUO_CONFIG = AccountIngestConfig.for_profile(
    profile_id="jianghushuo",
    account_id="jianghushuo",
    account_name="姜胡说",
    formal_account_dir=Path("06_Sub_KB/知识成长自媒体方法论/账号中心/姜胡说"),
)


def ingest_direction_package(root: Path, direction: str, approved_ids: set[str] | None = None) -> dict[str, Any]:
    return _ingest_direction_package(root, JIANGHUSHUO_CONFIG, direction, approved_ids)


def ingest_directions(
    root: Path,
    directions: list[str],
    *,
    audit_register: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    return _ingest_directions(root, JIANGHUSHUO_CONFIG, directions, audit_register=audit_register, dry_run=dry_run)


def ingest_direction(root: Path, direction: str) -> dict[str, Any]:
    result = ingest_directions(root, [direction])
    return result["directions"][0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Jianghushuo learned directions into the formal account center.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--direction", action="append")
    parser.add_argument("--all-approved", action="store_true")
    parser.add_argument("--audit-register")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    audit_register = Path(args.audit_register) if args.audit_register else None
    directions = args.direction or []
    if args.all_approved:
        if audit_register is None:
            parser.error("--all-approved requires --audit-register")
        register_path = audit_register if audit_register.is_absolute() else root / audit_register
        payload = json.loads(register_path.read_text(encoding="utf-8"))
        directions = list(dict.fromkeys(str(item.get("direction", "")) for item in payload.get("items", []) if item.get("decision") == "pass"))
    if not directions:
        parser.error("provide --direction or --all-approved")
    print(json.dumps(ingest_directions(root, directions, audit_register=audit_register, dry_run=args.dry_run), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
