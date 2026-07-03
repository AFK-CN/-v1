from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools.image_text_learning import ocr_image_paddleocr


def main() -> int:
    parser = argparse.ArgumentParser(description="PaddleOCR bridge for image_text_learning external command mode.")
    parser.add_argument("image")
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--cache-dir", default="00_System/runtime/cache/paddlex")
    args = parser.parse_args()

    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(Path(args.cache_dir).resolve()))
    result = ocr_image_paddleocr(Path(args.image), lang=args.lang)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
