from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def downgrade_cards(root: Path, account_id: str, account_dir: Path, apply: bool) -> dict[str, object]:
    root = root.resolve()
    account_dir = (root / account_dir).resolve() if not account_dir.is_absolute() else account_dir.resolve()
    try:
        relative_account_dir = account_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("account_dir must be inside the knowledge-base root") from exc

    source_cards = sorted(account_dir.glob("directions/*/cards/*.md"))
    snapshot_id = datetime.now().strftime("%Y-%m-%d")
    backup_root = root / "10_Knowledge/candidates/account_assets/downgraded_formal_cards" / account_id / snapshot_id
    entries: list[dict[str, str]] = []

    for source in source_cards:
        relative = source.relative_to(account_dir / "directions")
        target = backup_root / "directions" / relative
        entries.append(
            {
                "source": source.relative_to(root).as_posix(),
                "backup": target.relative_to(root).as_posix(),
                "sha256": sha256(source),
            }
        )

    result: dict[str, object] = {
        "ok": True,
        "apply": apply,
        "account_id": account_id,
        "source_account_dir": relative_account_dir.as_posix(),
        "backup_root": backup_root.relative_to(root).as_posix(),
        "card_count": len(entries),
    }
    if not apply:
        return result
    if not entries:
        raise ValueError("no formal account cards found to downgrade")
    if backup_root.exists():
        raise FileExistsError(f"backup snapshot already exists: {backup_root}")

    for entry, source in zip(entries, source_cards, strict=True):
        target = root / entry["backup"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256(target) != entry["sha256"]:
            raise RuntimeError(f"backup verification failed: {target}")

    manifest = {
        "schema_version": 1,
        "account_id": account_id,
        "knowledge_layer": "candidate_knowledge",
        "status": "downgraded_pending_relearning",
        "downgraded_at": datetime.now().isoformat(timespec="seconds"),
        "source_account_dir": relative_account_dir.as_posix(),
        "card_count": len(entries),
        "workflow_id": f"{account_id}-v2-full",
        "formal_callable": False,
        "entries": entries,
    }
    manifest_path = backup_root / "downgrade_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (backup_root / "README.md").write_text(
        "\n".join(
            [
                f"# {account_id} 旧正式知识卡降级备份",
                "",
                "- 知识层级：候选知识",
                "- 状态：等待按最新账号学习流程重学与重新审核",
                f"- 卡片数量：{len(entries)}",
                f"- 对应工作流：`{account_id}-v2-full`",
                "- 调用边界：本备份不可作为正式知识或可调用方法使用。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    for source in source_cards:
        source.unlink()

    result["manifest"] = manifest_path.relative_to(root).as_posix()
    result["source_remaining"] = len(list(account_dir.glob("directions/*/cards/*.md")))
    result["backup_verified"] = all(
        (root / entry["backup"]).is_file() and sha256(root / entry["backup"]) == entry["sha256"]
        for entry in entries
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Downgrade formal account cards into a verified candidate snapshot.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--account-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = downgrade_cards(Path(args.root), args.account_id, Path(args.account_dir), args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
