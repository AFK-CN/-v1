from __future__ import annotations

from datetime import datetime
from typing import Any


CONTENT_STATUSES = (
    "new",
    "scanned",
    "cleaned",
    "candidate",
    "review_needed",
    "approved",
    "used",
    "archived",
    "rejected",
)

TASK_STATUSES = ("pending", "running", "stale", "done", "failed", "paused")

RAW_INPUT_DIRS = ("00_Inbox", "数据")
FORMAL_KNOWLEDGE_DIRS = (
    "02_Viral_Methods",
    "03_Topic_Ideas",
    "04_Platform_Knowledge",
    "06_Sub_KB",
    "08_Content_Factory",
    "13_Evolving_Skills",
)
SYSTEM_DIR = "14_KB_System"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def validate_content_status(status: str) -> str:
    if status not in CONTENT_STATUSES:
        raise ValueError(f"invalid content status: {status}")
    return status


def validate_task_status(status: str) -> str:
    if status not in TASK_STATUSES:
        raise ValueError(f"invalid task status: {status}")
    return status


def as_posix(path: Any) -> str:
    return str(path).replace("\\", "/")
