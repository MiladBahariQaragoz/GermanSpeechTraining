"""Load the course OCR output (slides.json per video) into conversations."""

import json
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# The EN-only slide between the natural dialogue and its "listen and repeat" replay.
REPLAY_MARKER = "listen and repeat"

_LEVEL_DIR = re.compile(r"^(\d+) - Level \d+ - ([ABC][12]) - ")
_CONVERSATION_DIR = re.compile(r"^(\d+)\s*-\s*(.+)$")


@dataclass(frozen=True)
class Line:
    number: int  # 1-based position in the dialogue
    de: str
    en: str


@dataclass(frozen=True)
class Conversation:
    level: int
    cefr: str
    number: int
    topic_de: str
    topic_en: str
    lines: list[Line]
    path: Path


def parse_level_dir(name: str) -> tuple[int, str]:
    """"1 - Level 1 - A1 - Beginner" -> (1, "A1")."""
    match = _LEVEL_DIR.match(name)
    if not match:
        raise ValueError(f"not a level folder: {name!r}")
    return int(match.group(1)), match.group(2)


def parse_conversation_dir(name: str) -> tuple[int, str]:
    """"1 -Im Lebensmittelgeschäft" -> (1, "Im Lebensmittelgeschäft")."""
    match = _CONVERSATION_DIR.match(name)
    if not match:
        raise ValueError(f"not a conversation folder: {name!r}")
    return int(match.group(1)), match.group(2).strip()


def _fold(text: str) -> str:
    """Casefold and strip accents, so OCR's "Cafe" matches the folder's "Café"."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip()


def load_conversation(folder: Path) -> Conversation:
    folder = Path(folder)
    level, cefr = parse_level_dir(folder.parent.name)
    number, topic_de = parse_conversation_dir(folder.name)
    slides = json.loads((folder / "slides.json").read_text(encoding="utf-8"))["slides"]

    marker = next(
        (i for i, s in enumerate(slides) if not s["german"] and REPLAY_MARKER in s["english"].lower()),
        len(slides),
    )
    first_pass = [s for s in slides[:marker] if s["german"]]
    topic_en = ""
    if first_pass and _fold(first_pass[0]["german"]) == _fold(topic_de):
        topic_en = first_pass.pop(0)["english"]

    lines = [Line(n, s["german"], s["english"]) for n, s in enumerate(first_pass, start=1)]
    return Conversation(level, cefr, number, topic_de, topic_en, lines, folder)


def iter_conversations(root: Path, levels: Iterable[int] | None = None) -> Iterator[Conversation]:
    """Every conversation under `root`, ordered by level then conversation number."""
    wanted = set(levels) if levels is not None else None
    found = []
    for level_dir in Path(root).iterdir():
        try:
            level, _ = parse_level_dir(level_dir.name)
        except ValueError:
            continue
        if wanted is not None and level not in wanted:
            continue
        for folder in level_dir.iterdir():
            if (folder / "slides.json").exists():
                found.append((level, parse_conversation_dir(folder.name)[0], folder))
    for _, _, folder in sorted(found):
        yield load_conversation(folder)
