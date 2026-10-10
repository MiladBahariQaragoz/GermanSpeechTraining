"""`gst` command line: digest, check and render speaking drills."""

import argparse
from pathlib import Path

from gst.check import check_level
from gst.config import DRILLS_DIR, OCR_ROOT, WORK_DIR
from gst.digest import level_digest
from gst.drills import DrillError, level_markdown, load_level
from gst.render import Voices, render_level
from gst.transcript import iter_conversations
from gst.tts import TTS, CachedTTS, ElevenLabsTTS, PiperTTS

# Answers use the higher-quality voice, since they are what the learner imitates.
PIPER_VOICES = Voices(question="de_DE-kerstin-low", answer="de_DE-thorsten-high")


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


def _checked_drills(level: int, args) -> list | None:
    """The level's drills when they pass every check; otherwise print why and return None."""
    path = args.drills_dir / f"level-{level:02d}.json"
    if not path.exists():
        print(f"level {level}: {path} not found")
        return None
    conversations = list(iter_conversations(args.ocr_root, levels=[level]))
    try:
        drills = load_level(path, conversations)
    except DrillError as error:
        print(f"level {level}: {error}")
        return None
    problems = check_level(
        drills, conversations,
        min_drills=args.min_drills, cap=args.cap, min_conversations=args.min_conversations,
    )
    if problems:
        print("\n".join(problems))
        return None
    return drills


def _check(args) -> int:
    failed = False
    for level in args.levels:
        drills = _checked_drills(level, args)
        if drills is None:
            failed = True
            continue
        markdown = args.drills_dir / f"level-{level:02d}.md"
        markdown.write_text(level_markdown(drills), encoding="utf-8")
        print(f"level {level}: OK ({len(drills)} drills)")
    return 1 if failed else 0


def make_tts(name: str, work_dir: Path) -> TTS:
    if name == "elevenlabs":
        return ElevenLabsTTS()
    return PiperTTS(work_dir / "voices")


def _render(args) -> int:
    if args.tts == "elevenlabs" and not (args.question_voice and args.answer_voice):
        print("ElevenLabs needs --question-voice and --answer-voice (voice ids)")
        return 1
    defaults = PIPER_VOICES if args.tts == "piper" else Voices("", "")
    voices = Voices(args.question_voice or defaults.question, args.answer_voice or defaults.answer)
    tts = CachedTTS(make_tts(args.tts, args.work_dir), args.work_dir / "tts")
    failed = False
    for level in args.levels:
        drills = _checked_drills(level, args)
        if drills is None:
            failed = True
            continue
        video = render_level(drills, tts, voices, args.work_dir)
        print(f"level {level}: {video}")
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
    check.set_defaults(run=_check)

    render = commands.add_parser("render", help="synthesize speech and render one video per level")
    render.add_argument("--tts", choices=["piper", "elevenlabs"], default="piper")
    render.add_argument("--question-voice", help=f"default (piper): {PIPER_VOICES.question}")
    render.add_argument("--answer-voice", help=f"default (piper): {PIPER_VOICES.answer}")
    render.add_argument("--work-dir", type=Path, default=WORK_DIR)
    render.set_defaults(run=_render)

    for command in (check, render):
        command.add_argument("--levels", type=_levels, required=True, help='e.g. "1-10" or "1,3"')
        command.add_argument("--drills-dir", type=Path, default=DRILLS_DIR)
        command.add_argument("--min-drills", type=int, default=40)
        command.add_argument("--cap", type=int, default=4, help="max drills per conversation")
        command.add_argument("--min-conversations", type=int, default=15)
    for command in (digest, check, render):
        command.add_argument("--ocr-root", type=Path, default=OCR_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.run(args)
