from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.video_learning_card_validator import validate_card as validate_card
from tools.video_learning_card_validator import validate_cards as _validate_cards


def validate_cards(root: Path) -> dict[str, Any]:
    result = _validate_cards(root, "jianghushuo")
    return {key: value for key, value in result.items() if key != "profile_id"}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate Jianghushuo deep-learning card template.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = validate_cards(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
