from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def import_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def command_path(name: str) -> str:
    return shutil.which(name) or ""


def command_output(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return completed.returncode, completed.stdout.strip()


def tesseract_languages() -> list[str]:
    if not command_path("tesseract"):
        return []
    code, output = command_output(["tesseract", "--list-langs"])
    if code != 0:
        return []
    return [line.strip() for line in output.splitlines() if line.strip() and "List of available languages" not in line]


def validate_system() -> tuple[bool, str]:
    command = [sys.executable, "-m", "tools.kb.cli", "--root", str(ROOT), "validate-system"]
    code, output = command_output(command)
    if code != 0:
        return False, output
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return False, output
    return bool(payload.get("ok")), output


def build_report() -> dict[str, Any]:
    languages = tesseract_languages()
    checks: dict[str, Any] = {
        "python": {
            "ok": sys.version_info >= (3, 12),
            "version": sys.version.split()[0],
            "executable": sys.executable,
        },
        "packages": {
            "pillow": import_available("PIL"),
            "faster_whisper": import_available("faster_whisper"),
            "scenedetect": import_available("scenedetect"),
            "pytesseract": import_available("pytesseract"),
        },
        "commands": {
            "ffmpeg": command_path("ffmpeg"),
            "ffprobe": command_path("ffprobe"),
            "tesseract": command_path("tesseract"),
        },
        "tesseract_languages": {
            "chi_sim": "chi_sim" in languages,
            "eng": "eng" in languages,
            "available": languages,
        },
    }
    system_ok, system_output = validate_system()
    checks["knowledge_base"] = {"validate_system": system_ok}

    missing: list[str] = []
    warnings: list[str] = []
    if not checks["python"]["ok"]:
        missing.append("python>=3.12")
    if not checks["packages"]["pillow"]:
        missing.append("Pillow")
    for command in ("ffmpeg", "ffprobe", "tesseract"):
        if not checks["commands"][command]:
            missing.append(command)
    for language in ("chi_sim", "eng"):
        if not checks["tesseract_languages"][language]:
            missing.append(f"tesseract_language:{language}")
    for package in ("faster_whisper", "scenedetect", "pytesseract"):
        if not checks["packages"][package]:
            warnings.append(f"optional_package_missing:{package}")
    if not system_ok:
        missing.append("knowledge_base_validate_system")
        checks["knowledge_base"]["output"] = system_output

    return {
        "ok": not missing,
        "root": str(ROOT),
        "checks": checks,
        "missing": missing,
        "warnings": warnings,
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
