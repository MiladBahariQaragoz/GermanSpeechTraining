"""`gst` command line: digest, check and render speaking drills."""

import argparse
import os
from pathlib import Path

from gst.check import check_level
from gst.digest import level_digest
from gst.drills import DrillError, level_markdown, load_level
from gst.transcript import iter_conversations

COURSE_ROOT = Path(
    "/run/media/sudo/Vesno & Graphic/shadow/Udemy - Master German with 800 Real-Life Conversations 2025-5"
)
DEFAULT_OCR_ROOT = Path(os.environ.get("GST_OCR_ROOT", COURSE_ROOT / "_slide_ocr" / "output"))
DEFAULT_DRILLS_DIR = Path("data/drills")


def parse_levels(text: str) -> list[int]:
    """"1-3,7" -> [1, 2, 3, 7]."""
    levels: list[int] = []
    for part in text.split(","):
        start, _, end = part.partition("-")
        first, last = int(start), int(end or start)
        if not 1 <= first <= last:
            raise ValueError(f"bad level range: {part!r}")
        levels += range(first, last + 1)
    return levels


def _digest(args) -> int:
    print(level_digest(list(iter_conversations(args.ocr_root, levels=[args.level]))))
    return 0


def _check(args) -> int:
    failed = False
    for level in args.levels:
        path = args.drills_dir / f"level-{level:02d}.json"
        if not path.exists():
            print(f"level {level}: {path} not found")
            failed = True
            continue
        conversations = list(iter_conversations(args.ocr_root, levels=[level]))
        try:
            drills = load_level(path, conversations)
        except DrillError as error:
            print(f"level {level}: {error}")
            failed = True
            continue
        problems = check_level(
            drills, conversations,
            min_drills=args.min_drills, cap=args.cap, min_conversations=args.min_conversations,
        )
        if problems:
            print("\n".join(problems))
            failed = True
        else:
            path.with_suffix(".md").write_text(level_markdown(drills), encoding="utf-8")
            print(f"level {level}: OK ({len(drills)} drills)")
    return 1 if failed else 0


def _levels(text: str) -> list[int]:
    try:
        return parse_levels(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gst", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    digest = commands.add_parser("digest", help="print a level's numbered transcripts for authoring")
    digest.add_argument("--level", type=int, required=True)
    digest.set_defaults(run=_digest)

    check = commands.add_parser("check", help="validate data/drills/level-NN.json and refresh level-NN.md")
    check.add_argument("--levels", type=_levels, required=True, help='e.g. "1-10" or "1,3"')
    check.add_argument("--drills-dir", type=Path, default=DEFAULT_DRILLS_DIR)
    check.add_argument("--min-drills", type=int, default=40)
    check.add_argument("--cap", type=int, default=4, help="max drills per conversation")
    check.add_argument("--min-conversations", type=int, default=15)
    check.set_defaults(run=_check)

    for command in (digest, check):
        command.add_argument("--ocr-root", type=Path, default=DEFAULT_OCR_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.run(args)
