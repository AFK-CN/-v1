from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path("10_Knowledge/candidates/learning_cards/learned_cards/jianghushuo")

REQUIRED_SECTIONS = [
    "## 1. 为什么值得学习",
    "## 2. 核心观点",
    "## 3. 内容结构",
    "## 4. 表达素材与金句提炼",
    "## 5. 视频层学习",
    "## 6. 可复用案例",
    "## 7. 可复用方法论",
    "## 8. 可复用模板",
    "## 9. 证据缺口/后续问题",
    "## 10. 入库判断",
]

REQUIRED_METADATA = ["source_id:", "原视频链接", "账号：", "平台：", "主方向：", "状态："]


def validate_card(path: Path, root: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    errors: list[str] = []
    for field in REQUIRED_METADATA:
        if field not in text:
            errors.append(f"missing metadata {field}")
    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"missing section {section}")
    if "结尾金句/互动引导" in text:
        errors.append("old ending field remains")
    if "收尾/互动引导" not in text:
        errors.append("missing 收尾/互动引导")
    if "可延展选题" in text:
        errors.append("card contains 可延展选题")
    return [f"{path.relative_to(root)}: {error}" for error in errors]


def validate_cards(root: Path) -> dict[str, Any]:
    root = root.resolve()
    cards = sorted((root / BASE_DIR).glob("*/cards/*.md"))
    errors: list[str] = []
    for card in cards:
        errors.extend(validate_card(card, root))
    return {
        "card_count": len(cards),
        "valid": not errors,
        "errors": errors,
    }


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
