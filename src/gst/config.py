"""Default locations; each can be overridden with an environment variable."""

import os
from pathlib import Path

COURSE_ROOT = Path(
    "/run/media/sudo/Vesno & Graphic/shadow/Udemy - Master German with 800 Real-Life Conversations 2025-5"
)
OCR_ROOT = Path(os.environ.get("GST_OCR_ROOT", COURSE_ROOT / "_slide_ocr" / "output"))
WORK_DIR = Path(os.environ.get("GST_WORK_DIR", COURSE_ROOT / "_speaking_drills"))
DRILLS_DIR = Path("data/drills")
