from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_REPORTS_DIR = Path("00_System/runtime/reports/image_text_learning")
RUNTIME_CACHE_DIR = Path("00_System/runtime/cache/image_text_learning")
RUNTIME_STATE_DIR = Path("00_System/runtime/state/image_text_learning")
CANDIDATE_ACCOUNT_ASSETS_DIR = Path("10_Knowledge/candidates/account_assets/image_text_learning")
CANDIDATE_CARD_DIR = Path("10_Knowledge/candidates/learning_cards/image_text_cards")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
SUPPORTED_OCR_ENGINES = {"none", "tesseract", "paddleocr"}


@dataclass(frozen=True)
class WorkflowPaths:
    root: Path
    workflow_id: str
    account_id: str

    @property
    def state_dir(self) -> Path:
        return self.root / RUNTIME_STATE_DIR / self.workflow_id

    @property
    def cache_dir(self) -> Path:
        return self.root / RUNTIME_CACHE_DIR / self.workflow_id

    @property
    def reports_dir(self) -> Path:
        return self.root / RUNTIME_REPORTS_DIR / self.workflow_id

    @property
    def account_assets_dir(self) -> Path:
        return self.root / CANDIDATE_ACCOUNT_ASSETS_DIR / self.account_id / self.workflow_id

    @property
    def card_dir(self) -> Path:
        return self.root / CANDIDATE_CARD_DIR / self.account_id / self.workflow_id


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
    return cleaned or "account"


def first_line(value: str, limit: int = 160) -> str:
    line = str(value or "").strip().splitlines()[0] if str(value or "").strip() else ""
    return line[:limit]


def make_workflow_id(account_name: str, input_dir: Path) -> str:
    digest = hashlib.sha1(str(input_dir).encode("utf-8")).hexdigest()[:8]
    return f"image_text_{slug(account_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{digest}"


def ensure_dirs(paths: WorkflowPaths) -> None:
    for directory in (paths.state_dir, paths.cache_dir, paths.reports_dir, paths.account_assets_dir, paths.card_dir):
        directory.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def manifest_path(paths: WorkflowPaths) -> Path:
    return paths.state_dir / "image_text_manifest.json"


def structured_path(paths: WorkflowPaths) -> Path:
    return paths.cache_dir / "structured_posts.jsonl"


def selected_path(paths: WorkflowPaths) -> Path:
    return paths.state_dir / "selected_image_text_learning.json"


def status_path(paths: WorkflowPaths) -> Path:
    return paths.state_dir / "latest_image_text_status.json"


def load_manifest(root: Path, workflow_id: str) -> tuple[dict[str, Any], WorkflowPaths]:
    state_dir = root / RUNTIME_STATE_DIR / workflow_id
    manifest = read_json(state_dir / "image_text_manifest.json")
    paths = WorkflowPaths(root=root, workflow_id=workflow_id, account_id=manifest["account_id"])
    ensure_dirs(paths)
    return manifest, paths


def list_images(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def update_status(paths: WorkflowPaths, status: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "workflow_id": paths.workflow_id,
        "account_id": paths.account_id,
        "status": status,
        "updated_at": now_iso(),
        "state_dir": str(paths.state_dir.relative_to(paths.root)),
        "cache_dir": str(paths.cache_dir.relative_to(paths.root)),
        "reports_dir": str(paths.reports_dir.relative_to(paths.root)),
        "candidate_account_assets_dir": str(paths.account_assets_dir.relative_to(paths.root)),
        "candidate_card_dir": str(paths.card_dir.relative_to(paths.root)),
    }
    if extra:
        payload.update(extra)
    write_json(status_path(paths), payload)
    write_json(paths.root / RUNTIME_STATE_DIR / "latest_image_text_status.json", payload)
    return payload


def import_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def image_text_env_report(image2_command: str = "", paddleocr_command: str = "") -> dict[str, Any]:
    image2 = image2_command or os.environ.get("IMAGE_TEXT_IMAGE2_COMMAND", "") or shutil.which("image2") or ""
    paddleocr = paddleocr_command or os.environ.get("IMAGE_TEXT_PADDLEOCR_COMMAND", "")
    return {
        "ok": import_available("PIL") and import_available("cv2") and (import_available("paddleocr") or bool(paddleocr)),
        "packages": {
            "pillow": import_available("PIL"),
            "opencv": import_available("cv2"),
            "paddleocr": import_available("paddleocr"),
        },
        "commands": {
            "image2": shutil.which("image2") or "",
        },
        "configured": {
            "paddleocr_command": paddleocr,
            "optional_external_image2_command": image2,
            "codex_image2": "available_in_session",
        },
        "notes": [
            "Pillow/OpenCV/PaddleOCR 只生成图文学习证据，不生成账号学习结论。",
            "PaddleOCR 可通过当前 Python 环境导入，或通过 IMAGE_TEXT_PADDLEOCR_COMMAND / ingest --paddleocr-command 调用外部安装环境。",
            "默认 image2 是 Codex 会话内的看图能力，不是第三方 CLI；结构化阶段标记待 Codex 视觉审核，学习阶段由 Codex 补充视觉证据。",
            "如将来有外部图片转述命令，也可通过 IMAGE_TEXT_IMAGE2_COMMAND 或 ingest --image2-command 作为可选增强。",
        ],
    }


def command_ingest(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    input_dir = Path(args.input_dir).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"input_dir not found or not a directory: {input_dir}")
    ocr_engine = getattr(args, "ocr_engine", "none")
    ocr_lang = getattr(args, "ocr_lang", "chi_sim+eng")
    ocr_psm = getattr(args, "ocr_psm", 6)
    visual_feature_engine = getattr(args, "visual_feature_engine", "opencv")
    paddleocr_command = getattr(args, "paddleocr_command", "") or os.environ.get("IMAGE_TEXT_PADDLEOCR_COMMAND", "")
    image2_mode = getattr(args, "image2_mode", "codex")
    image2_command = getattr(args, "image2_command", "") or os.environ.get("IMAGE_TEXT_IMAGE2_COMMAND", "") or shutil.which("image2") or ""
    image2_timeout = getattr(args, "image2_timeout", 60)
    if ocr_engine not in SUPPORTED_OCR_ENGINES:
        raise SystemExit(f"unsupported ocr engine: {ocr_engine}")

    account_id = args.profile_id or slug(args.account_name)
    workflow_id = args.workflow_id or make_workflow_id(account_id, input_dir)
    paths = WorkflowPaths(root=root, workflow_id=workflow_id, account_id=account_id)
    ensure_dirs(paths)

    images = list_images(input_dir)
    manifest = {
        "workflow_id": workflow_id,
        "profile_id": account_id,
        "account_id": account_id,
        "account_name": args.account_name,
        "platform": args.platform,
        "media_branch": "image_text",
        "input_dir": str(input_dir),
        "created_at": now_iso(),
        "ocr_engine": ocr_engine,
        "ocr_lang": ocr_lang,
        "ocr_psm": ocr_psm,
        "visual_feature_engine": visual_feature_engine,
        "paddleocr_command": paddleocr_command,
        "image2_mode": image2_mode,
        "image2_command": image2_command,
        "image2_timeout": image2_timeout,
        "ocr_status": "pending" if ocr_engine == "none" else "configured",
        "images": [
            {
                "image_index": index,
                "path": str(path),
                "filename": path.name,
                "source_id": f"{workflow_id}_{index:04d}",
            }
            for index, path in enumerate(images, start=1)
        ],
        "rules": {
            "raw_images_readonly": True,
            "formal_account_write_requires_review": True,
        },
    }
    write_json(manifest_path(paths), manifest)
    update_status(paths, "ingested", {"image_count": len(images), "manifest": str(manifest_path(paths).relative_to(root))})
    return manifest


def image_role(index: int, total: int) -> str:
    if index == 1:
        return "cover"
    if index == total:
        return "summary_or_cta"
    return "body"


def ocr_image_tesseract(path: Path, lang: str = "chi_sim+eng", psm: int = 6) -> dict[str, Any]:
    from PIL import Image
    import pytesseract

    with Image.open(path) as image:
        text = pytesseract.image_to_string(image, lang=lang, config=f"--psm {psm}").strip()
    return {
        "ocr_text": text,
        "ocr_status": "completed" if text else "empty",
        "ocr_engine": "tesseract",
        "ocr_lang": lang,
        "text_blocks": [],
    }


def normalize_paddleocr_result(result: Any) -> tuple[str, list[dict[str, Any]]]:
    blocks: list[dict[str, Any]] = []

    def add_block(text: str, confidence: Any = None, bbox: Any = None) -> None:
        stripped = str(text).strip()
        if not stripped:
            return
        block: dict[str, Any] = {"text": stripped}
        if confidence is not None:
            try:
                block["confidence"] = float(confidence)
            except (TypeError, ValueError):
                block["confidence"] = confidence
        if bbox is not None:
            block["bbox"] = bbox
        blocks.append(block)

    if isinstance(result, dict):
        texts = result.get("rec_texts") or result.get("texts") or []
        scores = result.get("rec_scores") or result.get("scores") or []
        boxes = result.get("rec_polys") or result.get("dt_polys") or result.get("boxes") or []
        for index, text in enumerate(texts):
            add_block(text, scores[index] if index < len(scores) else None, boxes[index].tolist() if hasattr(boxes[index], "tolist") else boxes[index] if index < len(boxes) else None)
        return "\n".join(block["text"] for block in blocks), blocks

    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                text, nested_blocks = normalize_paddleocr_result(item)
                if text:
                    blocks.extend(nested_blocks)
                continue
            if isinstance(item, list):
                # PaddleOCR classic shape: [[bbox, (text, score)], ...] or [page_result]
                if len(item) == 2 and isinstance(item[1], (tuple, list)) and item[1]:
                    text = item[1][0]
                    score = item[1][1] if len(item[1]) > 1 else None
                    bbox = item[0]
                    add_block(text, score, bbox)
                else:
                    text, nested_blocks = normalize_paddleocr_result(item)
                    if text:
                        blocks.extend(nested_blocks)
    return "\n".join(block["text"] for block in blocks), blocks


def run_tool_command(path: Path, command: str, timeout: int) -> dict[str, Any]:
    command_parts = shlex.split(command)
    if any("{image}" in part for part in command_parts):
        command_parts = [part.replace("{image}", str(path)) for part in command_parts]
    else:
        command_parts.append(str(path))
    try:
        completed = subprocess.run(
            command_parts,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "error": str(exc), "stdout": "", "stderr": ""}
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "returncode": completed.returncode,
    }


def ocr_image_external_paddleocr(path: Path, command: str, lang: str, timeout: int) -> dict[str, Any]:
    completed = run_tool_command(path, command, timeout)
    if completed["status"] != "completed":
        return {
            "ocr_text": "",
            "ocr_status": "failed",
            "ocr_engine": "paddleocr_command",
            "ocr_lang": lang,
            "text_blocks": [],
            "evidence_flags": ["ocr_failed"],
            "ocr_error": completed.get("stderr") or completed.get("error", ""),
        }
    output = completed.get("stdout", "")
    if not output:
        return {
            "ocr_text": "",
            "ocr_status": "empty",
            "ocr_engine": "paddleocr_command",
            "ocr_lang": lang,
            "text_blocks": [],
        }
    try:
        payload = json.loads(output)
        if isinstance(payload, dict):
            text = payload.get("ocr_text") or payload.get("text") or ""
            blocks = payload.get("text_blocks") or payload.get("blocks") or []
            if not text and blocks:
                text = "\n".join(str(block.get("text", "")).strip() for block in blocks if isinstance(block, dict) and block.get("text"))
            return {
                "ocr_text": str(text).strip(),
                "ocr_status": "completed" if str(text).strip() else "empty",
                "ocr_engine": "paddleocr_command",
                "ocr_lang": payload.get("ocr_lang", lang),
                "text_blocks": blocks,
            }
        text, blocks = normalize_paddleocr_result(payload)
        return {
            "ocr_text": text,
            "ocr_status": "completed" if text else "empty",
            "ocr_engine": "paddleocr_command",
            "ocr_lang": lang,
            "text_blocks": blocks,
        }
    except json.JSONDecodeError:
        return {
            "ocr_text": output,
            "ocr_status": "completed",
            "ocr_engine": "paddleocr_command",
            "ocr_lang": lang,
            "text_blocks": [{"text": output}],
        }


def ocr_image_paddleocr(path: Path, lang: str = "ch") -> dict[str, Any]:
    from paddleocr import PaddleOCR

    try:
        ocr = PaddleOCR(use_angle_cls=True, lang=lang)
    except ValueError:
        ocr = PaddleOCR(lang=lang)

    if hasattr(ocr, "ocr"):
        try:
            result = ocr.ocr(str(path), cls=True)
        except TypeError:
            result = ocr.ocr(str(path))
    else:
        result = ocr.predict(str(path))
    text, blocks = normalize_paddleocr_result(result)
    return {
        "ocr_text": text,
        "ocr_status": "completed" if text else "empty",
        "ocr_engine": "paddleocr",
        "ocr_lang": lang,
        "text_blocks": blocks,
    }


def ocr_image(path: Path, engine: str, lang: str, psm: int, paddleocr_command: str = "", timeout: int = 120) -> dict[str, Any]:
    if engine == "none":
        return {
            "ocr_text": "",
            "ocr_status": "pending",
            "ocr_engine": "none",
            "ocr_lang": lang,
            "text_blocks": [],
            "evidence_flags": ["ocr_not_connected"],
        }
    if engine == "tesseract":
        try:
            result = ocr_image_tesseract(path, lang=lang, psm=psm)
            result["evidence_flags"] = [] if result["ocr_status"] == "completed" else ["ocr_empty"]
            return result
        except Exception as exc:  # noqa: BLE001 - OCR failures should degrade per image.
            return {
                "ocr_text": "",
                "ocr_status": "failed",
                "ocr_engine": "tesseract",
                "ocr_lang": lang,
                "text_blocks": [],
                "evidence_flags": ["ocr_failed"],
                "ocr_error": str(exc),
            }
    if engine == "paddleocr":
        if paddleocr_command:
            result = ocr_image_external_paddleocr(path, paddleocr_command, lang, timeout)
            result["evidence_flags"] = [] if result["ocr_status"] == "completed" else ["ocr_empty" if result["ocr_status"] == "empty" else "ocr_failed"]
            return result
        try:
            result = ocr_image_paddleocr(path, lang=lang)
            result["evidence_flags"] = [] if result["ocr_status"] == "completed" else ["ocr_empty"]
            return result
        except Exception as exc:  # noqa: BLE001 - OCR failures should degrade per image.
            return {
                "ocr_text": "",
                "ocr_status": "failed",
                "ocr_engine": "paddleocr",
                "ocr_lang": lang,
                "text_blocks": [],
                "evidence_flags": ["ocr_failed"],
                "ocr_error": str(exc),
            }
    raise ValueError(f"unsupported ocr engine: {engine}")


def rgb_to_hex(color: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def visual_features_pillow(path: Path) -> dict[str, Any]:
    from PIL import Image, ImageStat

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        small = rgb.resize((1, 1))
        average = small.getpixel((0, 0))
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        brightness = float(stat.mean[0]) / 255.0
        contrast = float(stat.stddev[0]) / 255.0
        palette = rgb.resize((80, 80)).getcolors(maxcolors=6400) or []
        palette = sorted(palette, reverse=True)[:5]
        colors = [rgb_to_hex(color) for _, color in palette]
    return {
        "engine": "pillow",
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4) if height else 0,
        "average_color": rgb_to_hex(average),
        "dominant_colors": colors,
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
    }


def visual_features_opencv(path: Path) -> dict[str, Any]:
    import cv2
    import numpy as np

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("opencv_cannot_read_image")
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    brightness = float(np.mean(gray)) / 255.0
    contrast = float(np.std(gray)) / 255.0
    saturation = float(np.mean(hsv[:, :, 1])) / 255.0
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)
    pixels = image.reshape((-1, 3)).astype("float32")
    if len(pixels) > 12000:
        step = max(1, len(pixels) // 12000)
        pixels = pixels[::step]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
    _compactness, labels, centers = cv2.kmeans(pixels, 5, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=len(centers))
    order = np.argsort(counts)[::-1]
    dominant = []
    for index in order:
        b, g, r = centers[index].astype("uint8").tolist()
        dominant.append(rgb_to_hex((r, g, b)))
    return {
        "engine": "opencv",
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 4) if height else 0,
        "dominant_colors": dominant,
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "saturation": round(saturation, 4),
        "sharpness": round(sharpness, 4),
        "edge_density": round(edge_density, 4),
        "complexity_signal": "high" if edge_density > 0.18 else "medium" if edge_density > 0.08 else "low",
    }


def visual_features(path: Path, engine: str) -> dict[str, Any]:
    if engine == "none":
        return {"engine": "none", "status": "skipped", "evidence_flags": ["visual_features_disabled"]}
    if engine == "opencv":
        try:
            result = visual_features_opencv(path)
            result["status"] = "completed"
            result["evidence_flags"] = []
            return result
        except Exception as exc:  # noqa: BLE001 - fall back to Pillow below.
            try:
                pillow_result = visual_features_pillow(path)
                pillow_result["status"] = "completed_degraded"
                pillow_result["fallback_from"] = "opencv"
                pillow_result["fallback_error"] = str(exc)
                pillow_result["evidence_flags"] = ["opencv_failed_pillow_fallback"]
                return pillow_result
            except Exception as fallback_exc:  # noqa: BLE001 - bad images should be review items.
                return {
                    "engine": "opencv",
                    "status": "failed",
                    "evidence_flags": ["visual_features_failed"],
                    "error": str(fallback_exc),
                    "fallback_error": str(exc),
                }
    if engine == "pillow":
        try:
            result = visual_features_pillow(path)
            result["status"] = "completed"
            result["evidence_flags"] = []
            return result
        except Exception as exc:  # noqa: BLE001 - bad images should be review items.
            return {"engine": "pillow", "status": "failed", "evidence_flags": ["visual_features_failed"], "error": str(exc)}
    raise ValueError(f"unsupported visual feature engine: {engine}")


def run_image2_command(path: Path, command: str, timeout: int) -> dict[str, Any]:
    if not command:
        return {"status": "skipped", "evidence_flags": ["image2_not_configured"]}
    completed = run_tool_command(path, command, timeout)
    output = completed.get("stdout", "")
    if completed["status"] != "completed":
        return {"status": "failed", "evidence_flags": ["image2_failed"], "error": completed.get("stderr") or completed.get("error", "") or output}
    if not output:
        return {"status": "empty", "evidence_flags": ["image2_empty"]}
    try:
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            parsed.setdefault("status", "completed")
            parsed.setdefault("evidence_flags", [])
            return parsed
    except json.JSONDecodeError:
        pass
    return {"status": "completed", "visual_description": output, "evidence_flags": []}


def codex_image2_placeholder(path: Path, image_index: int, image_role_value: str) -> dict[str, Any]:
    return {
        "status": "pending_codex_review",
        "provider": "codex_image2",
        "image_path": str(path),
        "image_index": image_index,
        "image_role_hint": image_role_value,
        "visual_description": "",
        "layout_type": "",
        "evidence_flags": ["codex_image2_pending"],
    }


def image2_evidence(path: Path, image_index: int, image_role_value: str, mode: str, command: str, timeout: int) -> dict[str, Any]:
    if mode == "none":
        return {"status": "skipped", "provider": "none", "evidence_flags": ["image2_disabled"]}
    if mode == "external":
        return run_image2_command(path, command, timeout)
    if mode == "codex":
        return codex_image2_placeholder(path, image_index, image_role_value)
    raise ValueError(f"unsupported image2 mode: {mode}")


def command_structure(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest, paths = load_manifest(root, args.workflow_id)
    images = manifest.get("images", [])
    total = len(images)
    ocr_engine = str(manifest.get("ocr_engine", "none"))
    ocr_lang = str(manifest.get("ocr_lang", "chi_sim+eng"))
    ocr_psm = int(manifest.get("ocr_psm", 6))
    visual_feature_engine = str(manifest.get("visual_feature_engine", "opencv"))
    paddleocr_command = str(manifest.get("paddleocr_command", ""))
    image2_mode = str(manifest.get("image2_mode", "codex"))
    image2_command = str(manifest.get("image2_command", ""))
    image2_timeout = int(manifest.get("image2_timeout", 60))
    rows: list[dict[str, Any]] = []
    ocr_counts = {"completed": 0, "empty": 0, "failed": 0, "pending": 0}
    visual_counts: dict[str, int] = {}
    image2_counts: dict[str, int] = {}
    for image in images:
        index = int(image["image_index"])
        image_path = Path(image["path"])
        role = image_role(index, total)
        ocr = ocr_image(image_path, engine=ocr_engine, lang=ocr_lang, psm=ocr_psm, paddleocr_command=paddleocr_command, timeout=image2_timeout)
        features = visual_features(image_path, engine=visual_feature_engine)
        image2 = image2_evidence(image_path, index, role, image2_mode, image2_command, image2_timeout)
        ocr_counts[ocr["ocr_status"]] = ocr_counts.get(ocr["ocr_status"], 0) + 1
        visual_counts[str(features.get("status", "unknown"))] = visual_counts.get(str(features.get("status", "unknown")), 0) + 1
        image2_counts[str(image2.get("status", "unknown"))] = image2_counts.get(str(image2.get("status", "unknown")), 0) + 1
        rows.append(
            {
                "workflow_id": manifest["workflow_id"],
                "profile_id": manifest["profile_id"],
                "account_id": manifest["account_id"],
                "account_name": manifest["account_name"],
                "platform": manifest["platform"],
                "media_branch": "image_text",
                "source_id": image["source_id"],
                "title": "",
                "caption": "",
                "tags": [],
                "images": [
                    {
                        "image_index": index,
                        "path": image["path"],
                        "image_role": role,
                        "ocr_text": ocr["ocr_text"],
                        "ocr_status": ocr["ocr_status"],
                        "ocr_engine": ocr["ocr_engine"],
                        "ocr_lang": ocr["ocr_lang"],
                        "text_blocks": ocr.get("text_blocks", []),
                        "visual_features": features,
                        "image2_evidence": image2,
                        "visual_summary": image2.get("visual_description", ""),
                        "layout_type": image2.get("layout_type", ""),
                        "evidence_flags": sorted(set(ocr["evidence_flags"] + features.get("evidence_flags", []) + image2.get("evidence_flags", []))),
                        **({"ocr_error": ocr["ocr_error"]} if ocr.get("ocr_error") else {}),
                    }
                ],
                "content_structure": [],
                "topic_direction": "待粗学归类",
                "quality_flags": sorted(
                    set(
                        ([f"ocr_{ocr['ocr_status']}"] if ocr["ocr_status"] != "completed" else [])
                        + ([f"visual_{features.get('status')}"] if features.get("status") != "completed" else [])
                        + ([f"image2_{image2.get('status')}"] if image2.get("status") != "completed" else [])
                    )
                ),
            }
        )

    write_jsonl(structured_path(paths), rows)
    report = [
        "# 图文结构化报告",
        "",
        f"- workflow_id: {paths.workflow_id}",
        f"- 账号: {manifest['account_name']}",
        f"- 平台: {manifest['platform']}",
        f"- 图片数量: {total}",
        f"- OCR 引擎: {ocr_engine}",
        f"- OCR 语言: {ocr_lang}",
        f"- OCR 完成: {ocr_counts.get('completed', 0)}",
        f"- OCR 空结果: {ocr_counts.get('empty', 0)}",
        f"- OCR 失败: {ocr_counts.get('failed', 0)}",
        f"- OCR 待接入: {ocr_counts.get('pending', 0)}",
        f"- 视觉特征引擎: {visual_feature_engine}",
        f"- 视觉特征状态: {json.dumps(visual_counts, ensure_ascii=False)}",
        f"- image2 模式: {image2_mode}",
        f"- image2 状态: {json.dumps(image2_counts, ensure_ascii=False)}",
        "",
        "## 证据缺口",
        "",
    ]
    if ocr_engine == "none":
        report.append("- OCR 工具尚未启用，当前只登记图片路径、顺序和默认图片角色。")
    if ocr_counts.get("failed", 0):
        report.append("- 部分图片 OCR 失败，必须在学习卡和审核清单中保留证据缺口。")
    if image2_counts.get("pending_codex_review", 0):
        report.append("- image2 是 Codex 会话内看图能力；本次已标记待 Codex 视觉审核，后续由 Codex 基于图片补视觉证据。")
    if image2_counts.get("skipped", 0):
        report.append("- image2 已禁用，本次只保留 OCR 和客观视觉特征。")
    if image2_counts.get("failed", 0):
        report.append("- 部分图片 image2 转述失败，不能把视觉描述当成完整证据。")
    report.append("- 工具只生成图片证据；账号规律、封面策略和分图结构仍由 Codex 基于证据学习。")
    report_path = paths.reports_dir / "structure_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    status = update_status(
        paths,
        "structured",
        {
            "structured_posts": len(rows),
            "ocr_counts": ocr_counts,
            "visual_counts": visual_counts,
            "image2_counts": image2_counts,
            "structure_report": str(report_path.relative_to(root)),
        },
    )
    return status


def command_scan(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest, paths = load_manifest(root, args.workflow_id)
    rows = read_jsonl(structured_path(paths))
    if not rows:
        raise SystemExit("no structured posts found; run structure first")

    overview = [
        f"# 账号概述：{manifest['account_name']} 图文学习候选",
        "",
        f"- workflow_id: {paths.workflow_id}",
        f"- 媒介分支: image_text",
        f"- 平台: {manifest['platform']}",
        f"- 图文样本数: {len(rows)}",
        "- 当前状态: 候选粗学，未写入正式账号中心",
        "- 证据边界: OCR 和视觉解析尚未接入时，只能作为图片顺序和结构化占位，不作为正式结论。",
    ]
    rough_pool = [
        "# 粗学与选题池：图文候选",
        "",
        "## 待粗学归类",
        "",
    ]
    for row in rows:
        image = row["images"][0]
        rough_pool.append(f"- {row['source_id']}｜{image['image_role']}｜OCR: {image['ocr_status']}｜{Path(image['path']).name}")

    plan = {
        "workflow_id": paths.workflow_id,
        "profile_id": manifest["profile_id"],
        "media_branch": "image_text",
        "executor": "local_machine",
        "evidence_storage": "local_runtime_cache",
        "status": "candidate_plan",
        "items": [
            {
                "source_id": row["source_id"],
                "priority": "candidate",
                "reason": "image_text_structure_available",
                "ocr_status": row["images"][0]["ocr_status"],
                "visual_status": row["images"][0]["visual_features"].get("status"),
                "image2_status": row["images"][0]["image2_evidence"].get("status"),
            }
            for row in rows
        ],
    }
    (paths.account_assets_dir / "账号概述.md").write_text("\n".join(overview) + "\n", encoding="utf-8")
    (paths.account_assets_dir / "粗学与选题池.md").write_text("\n".join(rough_pool) + "\n", encoding="utf-8")
    write_json(paths.account_assets_dir / "deep_learning_plan.json", plan)
    status = update_status(paths, "scanned", {"candidate_items": len(rows), "deep_learning_plan": str((paths.account_assets_dir / "deep_learning_plan.json").relative_to(root))})
    return status


def command_select(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest, paths = load_manifest(root, args.workflow_id)
    rows = read_jsonl(structured_path(paths))
    if not rows:
        raise SystemExit("no structured posts found; run structure first")
    selected = rows[: args.top_n] if args.top_n else rows
    payload = {
        "workflow_id": paths.workflow_id,
        "profile_id": manifest["profile_id"],
        "media_branch": "image_text",
        "selected_count": len(selected),
        "items": [{"source_id": row["source_id"], "status": "pending", "reason": "selected_for_image_text_learning"} for row in selected],
    }
    write_json(selected_path(paths), payload)
    return update_status(paths, "selected", {"selected_count": len(selected), "selection": str(selected_path(paths).relative_to(root))})


def command_learn(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest, paths = load_manifest(root, args.workflow_id)
    rows_by_id = {row["source_id"]: row for row in read_jsonl(structured_path(paths))}
    selection = read_json(selected_path(paths))
    learned = 0
    audit_items: list[dict[str, Any]] = []
    for item in selection.get("items", []):
        row = rows_by_id.get(item["source_id"])
        if not row:
            audit_items.append({"source_id": item["source_id"], "status": "missing_structured_post"})
            continue
        image = row["images"][0]
        card = [
            f"# 图文深度学习卡：{item['source_id']}",
            "",
            f"workflow_id: {paths.workflow_id}",
            f"profile_id: {manifest['profile_id']}",
            f"account_name: {manifest['account_name']}",
            "media_branch: image_text",
            f"source_id: {item['source_id']}",
            "",
            "## 发布内容层",
            "",
            "- 标题：待补充",
            "- 正文：待补充",
            "- 话题：待补充",
            "",
            "## 图文结构层",
            "",
            f"- 图片角色：{image['image_role']}",
            f"- 图片路径：{image['path']}",
            f"- OCR 状态：{image['ocr_status']}",
            f"- OCR 文本：{first_line(image.get('ocr_text', ''))}",
            f"- 视觉特征：{json.dumps(image.get('visual_features', {}), ensure_ascii=False)}",
            f"- image2/Codex 视觉证据：{json.dumps(image.get('image2_evidence', {}), ensure_ascii=False)}",
            "",
            "## 候选学习结论",
            "",
            "- 当前卡片是图文证据卡，不能直接写入正式账号中心。",
            "- Codex 需要基于 OCR、视觉特征和会话内看图结果综合学习封面策略、分图结构和视觉风格。",
            "",
            "## 审核状态",
            "",
            "- pending_user_review",
        ]
        card_path = paths.card_dir / f"{item['source_id']}.md"
        card_path.write_text("\n".join(card) + "\n", encoding="utf-8")
        learned += 1
        audit_items.append({"source_id": item["source_id"], "status": "candidate_card_created", "card_path": str(card_path.relative_to(root)), "requires_review": True})

    report_path = paths.reports_dir / "image_text_learning_report.md"
    report = [
        "# 图文账号学习报告",
        "",
        f"- workflow_id: {paths.workflow_id}",
        f"- 账号: {manifest['account_name']}",
        f"- 本次候选学习卡: {learned}",
        "- 入库建议: 暂不直接入库，等待 OCR/视觉解析补证据或用户审核。",
        "",
        "## 审核清单",
        "",
    ]
    report.extend(f"- {item['source_id']}: {item['status']}" for item in audit_items)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    write_json(paths.reports_dir / "audit_checklist.json", {"workflow_id": paths.workflow_id, "items": audit_items})
    return update_status(paths, "learned_candidate", {"learned_cards": learned, "learning_report": str(report_path.relative_to(root))})


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest, paths = load_manifest(root, args.workflow_id)
    status = read_json(status_path(paths)) if status_path(paths).exists() else {}
    status.setdefault("workflow_id", paths.workflow_id)
    status.setdefault("account_id", manifest["account_id"])
    status["media_branch"] = "image_text"
    status["manifest"] = str(manifest_path(paths).relative_to(root))
    status["structured_exists"] = structured_path(paths).exists()
    status["selection_exists"] = selected_path(paths).exists()
    status["candidate_card_count"] = len(list(paths.card_dir.glob("*.md"))) if paths.card_dir.exists() else 0
    latest_report = paths.root / RUNTIME_REPORTS_DIR / "latest_image_text_report.md"
    report_lines = [
        "# 图文学习状态",
        "",
        f"- workflow_id: {paths.workflow_id}",
        f"- account_id: {manifest['account_id']}",
        f"- status: {status.get('status', 'unknown')}",
        f"- structured_exists: {status['structured_exists']}",
        f"- selection_exists: {status['selection_exists']}",
        f"- candidate_card_count: {status['candidate_card_count']}",
    ]
    latest_report.parent.mkdir(parents=True, exist_ok=True)
    latest_report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    write_json(paths.root / RUNTIME_STATE_DIR / "latest_image_text_status.json", status)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run image-text account learning workflow for the knowledge base.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Register a local image package for image-text learning")
    ingest.add_argument("--root", default=".")
    ingest.add_argument("--account-name", required=True)
    ingest.add_argument("--profile-id", default="")
    ingest.add_argument("--platform", default="xhs")
    ingest.add_argument("--input-dir", required=True)
    ingest.add_argument("--workflow-id", default="")
    ingest.add_argument("--ocr-engine", default="none")
    ingest.add_argument("--ocr-lang", default="chi_sim+eng")
    ingest.add_argument("--ocr-psm", type=int, default=6)
    ingest.add_argument("--visual-feature-engine", default="opencv", choices=["none", "pillow", "opencv"])
    ingest.add_argument("--paddleocr-command", default="")
    ingest.add_argument("--image2-mode", default="codex", choices=["codex", "external", "none"])
    ingest.add_argument("--image2-command", default="")
    ingest.add_argument("--image2-timeout", type=int, default=60)

    for name in ("structure", "scan", "learn", "status"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", default=".")
        command.add_argument("--workflow-id", required=True)

    select = subparsers.add_parser("select", help="Select structured image-text posts for candidate learning")
    select.add_argument("--root", default=".")
    select.add_argument("--workflow-id", required=True)
    select.add_argument("--top-n", type=int, default=0)

    env = subparsers.add_parser("env", help="Check image-text learning tool availability")
    env.add_argument("--paddleocr-command", default="")
    env.add_argument("--image2-command", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "ingest": command_ingest,
        "structure": command_structure,
        "scan": command_scan,
        "select": command_select,
        "learn": command_learn,
        "status": command_status,
        "env": lambda parsed: image_text_env_report(parsed.image2_command, parsed.paddleocr_command),
    }
    result = handlers[args.command](args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
