from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
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
DEEP_VISUAL_DIMENSIONS = (
    "subject_and_action",
    "composition_and_viewpoint",
    "visual_hierarchy",
    "text_annotation_design",
    "typography_hierarchy",
    "color_light_texture",
    "state_or_result",
    "authenticity_cues",
    "narrative_function",
)
CROSS_IMAGE_DIMENSIONS = (
    "cover_hook",
    "image_role_sequence",
    "information_progression",
    "visual_consistency_and_variation",
    "action_to_result_chain",
    "cross_modal_alignment",
    "save_worthiness",
)


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


def normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        compact = value.replace("＃", "#").strip()
        if not compact:
            return []
        if "#" in compact:
            return [item.strip(" #\t\r\n") for item in compact.split("#") if item.strip(" #\t\r\n")]
        return [item.strip() for item in re.split(r"[,，|｜\s]+", compact) if item.strip()]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            if isinstance(item, dict):
                item = item.get("name") or item.get("title") or item.get("tag") or ""
            text = str(item).strip().lstrip("#＃")
            if text:
                values.append(text)
        return list(dict.fromkeys(values))
    return [str(value).strip()] if str(value).strip() else []


def read_post_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows = read_jsonl(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and isinstance(payload.get("posts"), list):
            rows = payload["posts"]
        elif isinstance(payload, dict):
            rows = [payload]
        else:
            raise ValueError(f"unsupported posts manifest shape: {path}")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"posts manifest must contain objects: {path}")
    return rows


def resolve_posts_file(args: argparse.Namespace, input_dir: Path) -> Path | None:
    configured = str(getattr(args, "posts_file", "") or "").strip()
    if configured:
        path = Path(configured).resolve()
        if not path.exists() or not path.is_file():
            raise SystemExit(f"posts_file not found or not a file: {path}")
        return path
    conventional = input_dir / "posts.jsonl"
    return conventional if conventional.exists() else None


def post_image_paths(row: dict[str, Any], *, base_dir: Path, input_dir: Path) -> list[Path]:
    values = row.get("images") or row.get("image_paths") or row.get("local_images") or []
    if isinstance(values, (str, dict)):
        values = [values]
    paths: list[Path] = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("path") or item.get("local_path") or item.get("file") or item.get("filename") or ""
        raw = str(item).strip()
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            from_manifest = (base_dir / candidate).resolve()
            from_input = (input_dir / candidate).resolve()
            candidate = from_manifest if from_manifest.exists() else from_input
        candidate = candidate.resolve()
        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"post image not found: {candidate}")
        if candidate.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"unsupported post image type: {candidate}")
        paths.append(candidate)
    return paths


def build_posts_from_manifest(path: Path, *, input_dir: Path, workflow_id: str) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(read_post_records(path), start=1):
        source_id = str(row.get("source_id") or row.get("note_id") or row.get("id") or f"{workflow_id}_post_{index:04d}").strip()
        if not source_id:
            raise ValueError(f"empty source_id in posts manifest row {index}")
        if source_id in seen:
            raise ValueError(f"duplicate source_id in posts manifest: {source_id}")
        seen.add(source_id)
        paths = post_image_paths(row, base_dir=path.parent, input_dir=input_dir)
        if not paths:
            raise ValueError(f"post has no local images: {source_id}")
        title = str(row.get("title") or row.get("publish_title") or "").strip()
        caption = str(row.get("caption") or row.get("body") or row.get("desc") or row.get("content") or row.get("publish_body") or "").strip()
        tags_field_present = any(key in row for key in ("tags", "topics", "hashtags"))
        tags = normalize_tags(row.get("tags") or row.get("topics") or row.get("hashtags"))
        posts.append(
            {
                "source_id": source_id,
                "title": title,
                "caption": caption,
                "tags": tags,
                "tags_field_present": tags_field_present,
                "url": str(row.get("url") or row.get("link") or row.get("source_url") or "").strip(),
                "published_at": str(row.get("published_at") or row.get("publish_time") or "").strip(),
                "images": [
                    {"image_index": image_index, "path": str(image_path), "filename": image_path.name}
                    for image_index, image_path in enumerate(paths, start=1)
                ],
                "source_record_index": index,
            }
        )
    return posts


def build_legacy_loose_image_posts(images: list[Path], *, workflow_id: str) -> list[dict[str, Any]]:
    return [
        {
            "source_id": f"{workflow_id}_{index:04d}",
            "title": "",
            "caption": "",
            "tags": [],
            "tags_field_present": False,
            "url": "",
            "published_at": "",
            "images": [{"image_index": 1, "path": str(path), "filename": path.name}],
            "source_record_index": index,
            "evidence_flags": ["legacy_loose_image", "post_grouping_unknown", "publish_layer_missing"],
        }
        for index, path in enumerate(images, start=1)
    ]


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
    tesseract = shutil.which("tesseract") or ""
    tesseract_available = import_available("pytesseract") and bool(tesseract)
    paddleocr_available = import_available("paddleocr") or bool(paddleocr)
    opencv_available = import_available("cv2")
    return {
        "ok": import_available("PIL") and (tesseract_available or paddleocr_available),
        "degraded": not opencv_available or not paddleocr_available,
        "packages": {
            "pillow": import_available("PIL"),
            "opencv": opencv_available,
            "pytesseract": import_available("pytesseract"),
            "paddleocr": import_available("paddleocr"),
        },
        "commands": {
            "tesseract": tesseract,
            "image2": shutil.which("image2") or "",
        },
        "configured": {
            "paddleocr_command": paddleocr,
            "optional_external_image2_command": image2,
            "codex_image2": "available_in_session",
        },
        "notes": [
            "Pillow、OpenCV 与 OCR 只生成图文学习证据，不生成账号学习结论。",
            "Tesseract 与 PaddleOCR 任一可用即可；PaddleOCR 是可选增强，不再阻断图文处理主流程。",
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
    posts_file = resolve_posts_file(args, input_dir)
    try:
        posts = (
            build_posts_from_manifest(posts_file, input_dir=input_dir, workflow_id=workflow_id)
            if posts_file
            else build_legacy_loose_image_posts(images, workflow_id=workflow_id)
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    registered_images = [image for post in posts for image in post.get("images", [])]
    manifest = {
        "workflow_id": workflow_id,
        "profile_id": account_id,
        "account_id": account_id,
        "account_name": args.account_name,
        "platform": args.platform,
        "media_branch": "image_text",
        "input_dir": str(input_dir),
        "posts_file": str(posts_file) if posts_file else "",
        "source_mode": "post_manifest_v2" if posts_file else "legacy_loose_images",
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
        "post_count": len(posts),
        "image_count": len(registered_images),
        "posts": posts,
        "images": registered_images,
        "learning_contract": {
            "unit": "one_published_post_with_ordered_images",
            "publish_layer_required": ["title", "caption", "tags_or_explicit_absence"],
            "per_image_visual_dimensions": list(DEEP_VISUAL_DIMENSIONS),
            "cross_image_dimensions": list(CROSS_IMAGE_DIMENSIONS),
        },
        "rules": {
            "raw_images_readonly": True,
            "formal_account_write_requires_review": True,
            "loose_images_do_not_imply_post_grouping": True,
            "ocr_does_not_replace_visual_review": True,
        },
    }
    write_json(manifest_path(paths), manifest)
    update_status(
        paths,
        "ingested",
        {
            "post_count": len(posts),
            "image_count": len(registered_images),
            "source_mode": manifest["source_mode"],
            "manifest": str(manifest_path(paths).relative_to(root)),
        },
    )
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


def deep_visual_observation(
    image2: dict[str, Any], *, path: Path, image_index: int, image_role_value: str
) -> dict[str, Any]:
    nested = image2.get("visual_analysis")
    source = nested if isinstance(nested, dict) else image2
    aliases = {
        "subject_and_action": ("subject_and_action", "subject", "action"),
        "composition_and_viewpoint": ("composition_and_viewpoint", "composition", "viewpoint", "camera_angle"),
        "visual_hierarchy": ("visual_hierarchy", "hierarchy", "focal_point"),
        "text_annotation_design": ("text_annotation_design", "annotation_design", "text_annotations", "annotation_style"),
        "typography_hierarchy": ("typography_hierarchy", "typography", "font_system", "text_hierarchy"),
        "color_light_texture": ("color_light_texture", "color_and_light", "color", "lighting", "texture"),
        "state_or_result": ("state_or_result", "state_change", "result_state", "result"),
        "authenticity_cues": ("authenticity_cues", "realness_cues", "lived_in_details", "imperfections"),
        "narrative_function": ("narrative_function", "image_role", "story_function", "content_function"),
    }
    observed: dict[str, Any] = {}
    for dimension, keys in aliases.items():
        values = [source.get(key) for key in keys if source.get(key) not in (None, "", [], {})]
        if values:
            observed[dimension] = values[0] if len(values) == 1 else values
    missing = [dimension for dimension in DEEP_VISUAL_DIMENSIONS if dimension not in observed]
    source_status = str(image2.get("status") or "unknown")
    if source_status == "pending_codex_review":
        status = "pending_codex_visual_review"
    elif not observed:
        status = "insufficient_visual_analysis"
    elif missing:
        status = "partial_visual_analysis"
    else:
        status = "complete_visual_analysis"
    return {
        "schema": "image_text_deep_visual_evidence_v1",
        "status": status,
        "image_index": image_index,
        "image_role": image_role_value,
        "evidence_coordinate": f"image:{path}#index:{image_index}",
        "dimensions_considered": list(DEEP_VISUAL_DIMENSIONS),
        "observed": observed,
        "missing_or_uncertain_dimensions": missing,
        "rule": "OCR only proves readable text; it does not prove composition, typography, action, state change or authenticity.",
    }


def command_structure(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest, paths = load_manifest(root, args.workflow_id)
    posts = manifest.get("posts", [])
    if not posts and manifest.get("images"):
        posts = build_legacy_loose_image_posts(
            [Path(image["path"]) for image in manifest.get("images", [])],
            workflow_id=str(manifest["workflow_id"]),
        )
    total_images = sum(len(post.get("images", [])) for post in posts)
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
    publish_counts = {"complete": 0, "partial": 0, "missing": 0}
    for post in posts:
        post_images = post.get("images", [])
        analyzed_images: list[dict[str, Any]] = []
        row_quality_flags = list(post.get("evidence_flags", []))
        for image in post_images:
            index = int(image["image_index"])
            image_path = Path(image["path"])
            role = image_role(index, len(post_images))
            ocr = ocr_image(
                image_path,
                engine=ocr_engine,
                lang=ocr_lang,
                psm=ocr_psm,
                paddleocr_command=paddleocr_command,
                timeout=image2_timeout,
            )
            features = visual_features(image_path, engine=visual_feature_engine)
            image2 = image2_evidence(image_path, index, role, image2_mode, image2_command, image2_timeout)
            deep_visual = deep_visual_observation(
                image2,
                path=image_path,
                image_index=index,
                image_role_value=role,
            )
            ocr_counts[ocr["ocr_status"]] = ocr_counts.get(ocr["ocr_status"], 0) + 1
            visual_counts[str(features.get("status", "unknown"))] = visual_counts.get(str(features.get("status", "unknown")), 0) + 1
            image2_counts[str(image2.get("status", "unknown"))] = image2_counts.get(str(image2.get("status", "unknown")), 0) + 1
            image_flags = sorted(
                set(ocr["evidence_flags"] + features.get("evidence_flags", []) + image2.get("evidence_flags", []))
            )
            row_quality_flags.extend(image_flags)
            if deep_visual["status"] != "complete_visual_analysis":
                row_quality_flags.append(deep_visual["status"])
            analyzed_images.append(
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
                    "deep_visual_observation": deep_visual,
                    "visual_summary": image2.get("visual_description", ""),
                    "layout_type": image2.get("layout_type", ""),
                    "evidence_flags": image_flags,
                    **({"ocr_error": ocr["ocr_error"]} if ocr.get("ocr_error") else {}),
                }
            )

        title = str(post.get("title") or "").strip()
        caption = str(post.get("caption") or "").strip()
        tags = normalize_tags(post.get("tags"))
        availability = {
            "title": bool(title),
            "caption": bool(caption),
            "tags": bool(tags) or bool(post.get("tags_field_present")),
        }
        available_count = sum(availability.values())
        publish_status = "complete" if available_count == 3 else "partial" if available_count else "missing"
        publish_counts[publish_status] += 1
        if publish_status != "complete":
            row_quality_flags.append(f"publish_layer_{publish_status}")
        sequence_status = (
            "ordered_post_sequence"
            if manifest.get("source_mode") == "post_manifest_v2"
            else "post_grouping_unknown"
        )
        rows.append(
            {
                "workflow_id": manifest["workflow_id"],
                "profile_id": manifest["profile_id"],
                "account_id": manifest["account_id"],
                "account_name": manifest["account_name"],
                "platform": manifest["platform"],
                "media_branch": "image_text",
                "source_id": post["source_id"],
                "url": post.get("url", ""),
                "published_at": post.get("published_at", ""),
                "title": title,
                "caption": caption,
                "tags": tags,
                "publish_layer": {
                    "schema": "image_text_publish_evidence_v1",
                    "status": publish_status,
                    "availability": availability,
                    "source": manifest.get("source_mode", "unknown"),
                    "title": title,
                    "body": caption,
                    "topics": tags,
                    "topics_status": "available" if tags else "explicit_absence" if post.get("tags_field_present") else "missing",
                    "missing_fields": [name for name, available in availability.items() if not available],
                },
                "images": analyzed_images,
                "visual_sequence": {
                    "schema": "image_text_visual_sequence_evidence_v1",
                    "status": sequence_status,
                    "image_count": len(analyzed_images),
                    "image_order": [image["image_index"] for image in analyzed_images],
                    "image_roles": [image["image_role"] for image in analyzed_images],
                    "dimensions_considered": list(CROSS_IMAGE_DIMENSIONS),
                    "analysis_status": "pending_cross_image_learning",
                },
                "content_structure": [],
                "topic_direction": "待粗学归类",
                "quality_flags": sorted(set(row_quality_flags)),
            }
        )

    write_jsonl(structured_path(paths), rows)
    report = [
        "# 图文结构化报告",
        "",
        f"- workflow_id: {paths.workflow_id}",
        f"- 账号: {manifest['account_name']}",
        f"- 平台: {manifest['platform']}",
        f"- 发布图文数量: {len(posts)}",
        f"- 图片数量: {total_images}",
        f"- 发布层状态: {json.dumps(publish_counts, ensure_ascii=False)}",
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
    if publish_counts.get("partial", 0) or publish_counts.get("missing", 0):
        report.append("- 部分图文缺发布标题、正文或话题；缺失必须进入学习卡，不能用 OCR 或图片内容补造发布文案。")
    if manifest.get("source_mode") == "legacy_loose_images":
        report.append("- 当前输入是散图兼容模式，不能假定多张图片属于同一条发布内容，也不能学习分图顺序。")
    report.append("- OCR 只证明图中文字；构图、文字设计、动作状态、成品呈现和组图叙事仍需逐图视觉复核。")
    report.append("- 工具只生成可学习证据；账号规律由 account-learning 基于多条发布内容跨卡验证。")
    report_path = paths.reports_dir / "structure_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    status = update_status(
        paths,
        "structured",
        {
            "structured_posts": len(rows),
            "image_count": total_images,
            "publish_counts": publish_counts,
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
        f"- 发布图文样本数: {len(rows)}",
        f"- 图片总数: {sum(len(row.get('images', [])) for row in rows)}",
        f"- 发布文案完整样本: {sum(row.get('publish_layer', {}).get('status') == 'complete' for row in rows)}",
        "- 当前状态: 候选粗学，未写入正式账号中心",
        "- 证据边界: 标题、正文、话题与有序组图共同组成一条发布内容；散图、OCR 或单张视觉摘要都不能代替完整图文证据。",
    ]
    rough_pool = [
        "# 粗学与选题池：图文候选",
        "",
        "## 待粗学归类",
        "",
    ]
    for row in rows:
        image_statuses = [image.get("deep_visual_observation", {}).get("status", "unknown") for image in row.get("images", [])]
        title = first_line(row.get("title", "")) or "无发布标题"
        rough_pool.append(
            f"- {row['source_id']}｜{title}｜发布层: {row.get('publish_layer', {}).get('status', 'missing')}｜"
            f"图片: {len(row.get('images', []))}｜视觉: {','.join(image_statuses)}"
        )

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
                "reason": "published_post_evidence_registered",
                "publish_layer_status": row.get("publish_layer", {}).get("status", "missing"),
                "image_count": len(row.get("images", [])),
                "post_grouping_status": row.get("visual_sequence", {}).get("status", "unknown"),
                "ocr_statuses": [image.get("ocr_status", "unknown") for image in row.get("images", [])],
                "visual_statuses": [image.get("visual_features", {}).get("status", "unknown") for image in row.get("images", [])],
                "deep_visual_statuses": [image.get("deep_visual_observation", {}).get("status", "unknown") for image in row.get("images", [])],
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
        publish = row.get("publish_layer", {})
        images = row.get("images", [])
        missing_publish = list(publish.get("missing_fields", []))
        pending_visual = [
            image["image_index"]
            for image in images
            if image.get("deep_visual_observation", {}).get("status") != "complete_visual_analysis"
        ]
        grouping_status = row.get("visual_sequence", {}).get("status", "unknown")
        readiness = (
            "evidence_ready_for_codex_learning"
            if not missing_publish and not pending_visual and grouping_status == "ordered_post_sequence"
            else "evidence_incomplete_requires_review"
        )
        caption = str(row.get("caption") or "").strip()
        caption_lines = [f"> {line}" if line else ">" for line in caption.splitlines()] if caption else ["> 【缺失】"]
        card = [
            f"# 图文深学证据卡：{item['source_id']}",
            "",
            f"workflow_id: {paths.workflow_id}",
            f"profile_id: {manifest['profile_id']}",
            f"account_name: {manifest['account_name']}",
            "media_branch: image_text",
            f"source_id: {item['source_id']}",
            f"source_url: {row.get('url') or '【缺失】'}",
            f"evidence_readiness: {readiness}",
            "",
            "## 1. 发布原文证据",
            "",
            f"- 发布层状态：{publish.get('status', 'missing')}",
            f"- 标题原文：{row.get('title') or '【缺失】'}",
            "- 正文原文：",
            *caption_lines,
            f"- 话题原文：{'、'.join(row.get('tags', [])) if row.get('tags') else '【无显式话题或缺失】'}",
            "",
            "## 2. 发布文案深学任务",
            "",
            "- 标题机制：识别承诺对象、具体程度、信息差、语气和点击理由；不得只摘抄标题。",
            "- 正文结构：标出开头入口、信息推进、操作或论证细节、转折、结果与收尾，不得只概括主题。",
            "- 细节密度：记录数量、单位、时长、动作、状态判断、人物处境和限制条件；缺少时明确写缺失。",
            "- 真人感：记录口语连接、自我修正、偏好、犹豫、生活痕迹和不对称细节；不得用“自然、有温度”等空词代替证据。",
            "- 结尾方式：区分自然停住、经验补充、行动提醒、情绪落点、互动和商业引导。",
            "- 话题策略：区分检索词、内容分类、身份或场景标签与平台项目标签；无显式话题时不补造。",
            "- 协同关系：解释标题、正文、话题是否共同兑现同一承诺，哪些信息由图片承担。",
            "",
            "## 3. 逐图视觉证据",
            "",
        ]
        for image in images:
            card.extend(
                [
                    f"### 图 {image['image_index']}｜{image['image_role']}",
                    "",
                    f"- 图片路径：{image['path']}",
                    f"- OCR 状态：{image['ocr_status']}",
                    f"- OCR 原文：{image.get('ocr_text') or '【无可用 OCR】'}",
                    f"- 客观视觉特征：{json.dumps(image.get('visual_features', {}), ensure_ascii=False)}",
                    f"- image2/Codex 视觉证据：{json.dumps(image.get('image2_evidence', {}), ensure_ascii=False)}",
                    f"- 深层视觉证据：{json.dumps(image.get('deep_visual_observation', {}), ensure_ascii=False)}",
                    "",
                ]
            )
        card.extend(
            [
                "## 4. 组图视觉深学任务",
                "",
                f"- 组图状态：{grouping_status}；图片数量：{len(images)}。",
                "- 封面钩子：学习主体选择、结果承诺、视觉焦点、留白、标题位置与第一眼识别顺序。",
                "- 分图角色：逐图写清封面、材料/背景、关键动作、过程状态、结果、总结或互动角色，并解释排序原因。",
                "- 构图与视角：学习景别、机位、裁切、主体占比、手或人物进入方式、空间关系和视觉动线。",
                "- 文字注释设计：学习注释贴纸、底板、字形、字号层级、对齐、位置、留白和与画面的指向关系；OCR 只负责读字，不能代替这项判断。",
                "- 动作与状态链：识别动作发生前后、关键手势、过程变化、熟度/质地/完成状态与结果证明。",
                "- 色彩光线质感：学习色调、光源、明暗、背景、器皿/服饰/道具和质感如何服务内容，不只记录色值。",
                "- 真人与生活感：识别自然手势、使用痕迹、轻微不完美、环境细节与非棚拍信号；不得凭想象补人物身份。",
                "- 组图叙事：解释信息如何逐页推进、重复和变化如何配合、为何值得收藏；单张好看不能代替组图完整性。",
                "",
                "## 5. 跨模态协同学习",
                "",
                "- 对齐检查：发布标题、正文、封面字、逐图 OCR 与画面是否指向同一承诺。",
                "- 分工检查：哪些信息只在正文、只在图片、两边重复或彼此矛盾。",
                "- 证据闭环：标题提出什么问题或结果，组图如何证明，正文如何补细节和边界，话题如何帮助检索或分类。",
                "",
                "## 6. 证据缺口与审核状态",
                "",
                f"- 发布字段缺口：{', '.join(missing_publish) if missing_publish else '无'}",
                f"- 待补视觉复核图片：{pending_visual if pending_visual else '无'}",
                f"- 组图归属与顺序：{grouping_status}",
                f"- 当前状态：{readiness}",
                "- 本卡是图文深学证据卡，不是账号稳定方法；完成逐条深学后仍需进入统一学习卡和跨卡三重验证。",
                "",
                "## 7. 后续学习动作",
                "",
                "- Codex 必须阅读全文并逐图查看原图，完成发布文案、逐图视觉和跨模态三个层面的实质判断。",
                "- 完成后生成 unified_three_layer_v2 学习卡；不能把本卡的任务清单直接复制成学习结论。",
            "",
            ]
        )
        card_path = paths.card_dir / f"{item['source_id']}.md"
        card_path.write_text("\n".join(card) + "\n", encoding="utf-8")
        learned += 1
        audit_items.append(
            {
                "source_id": item["source_id"],
                "status": "deep_learning_evidence_card_created",
                "evidence_readiness": readiness,
                "publish_layer_status": publish.get("status", "missing"),
                "pending_visual_images": pending_visual,
                "post_grouping_status": grouping_status,
                "card_path": str(card_path.relative_to(root)),
                "requires_codex_deep_learning": True,
                "requires_review": True,
            }
        )

    report_path = paths.reports_dir / "image_text_learning_report.md"
    report = [
        "# 图文账号学习报告",
        "",
        f"- workflow_id: {paths.workflow_id}",
        f"- 账号: {manifest['account_name']}",
        f"- 本次图文深学证据卡: {learned}",
        f"- 证据就绪: {sum(item.get('evidence_readiness') == 'evidence_ready_for_codex_learning' for item in audit_items)}",
        f"- 证据不完整: {sum(item.get('evidence_readiness') == 'evidence_incomplete_requires_review' for item in audit_items)}",
        "- 下一步: Codex 阅读完整发布原文并逐图看原图，生成统一学习卡；不得把证据卡当作已学完。",
        "",
        "## 审核清单",
        "",
    ]
    report.extend(f"- {item['source_id']}: {item['status']}" for item in audit_items)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    write_json(paths.reports_dir / "audit_checklist.json", {"workflow_id": paths.workflow_id, "items": audit_items})
    return update_status(
        paths,
        "learned_candidate",
        {
            "learned_cards": learned,
            "evidence_ready_count": sum(
                item.get("evidence_readiness") == "evidence_ready_for_codex_learning" for item in audit_items
            ),
            "evidence_incomplete_count": sum(
                item.get("evidence_readiness") == "evidence_incomplete_requires_review" for item in audit_items
            ),
            "learning_report": str(report_path.relative_to(root)),
        },
    )


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
    structured_rows = read_jsonl(structured_path(paths))
    status["structured_post_count"] = len(structured_rows)
    status["publish_layer_complete_count"] = sum(
        row.get("publish_layer", {}).get("status") == "complete" for row in structured_rows
    )
    status["ordered_post_sequence_count"] = sum(
        row.get("visual_sequence", {}).get("status") == "ordered_post_sequence" for row in structured_rows
    )
    status["pending_deep_visual_image_count"] = sum(
        image.get("deep_visual_observation", {}).get("status") != "complete_visual_analysis"
        for row in structured_rows
        for image in row.get("images", [])
    )
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
        f"- publish_layer_complete_count: {status['publish_layer_complete_count']}",
        f"- ordered_post_sequence_count: {status['ordered_post_sequence_count']}",
        f"- pending_deep_visual_image_count: {status['pending_deep_visual_image_count']}",
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
    ingest.add_argument("--posts-file", default="", help="JSON/JSONL manifest grouping ordered images with title, caption and tags")
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
