"""Authored drill files (data/drills/level-NN.json) and their Markdown view."""

import json
from dataclasses import dataclass
from pathlib import Path

from gst.transcript import Conversation

AUTHORED_FIELDS = (
    "conversation", "question_de", "question_en", "answer_de", "answer_en", "hints", "source_lines",
)


class DrillError(ValueError):
    pass


@dataclass(frozen=True)
class Drill:
    id: str
    level: int
    cefr: str
    conversation: int
    topic_de: str
    topic_en: str
    question_de: str
    question_en: str
    answer_de: str
    answer_en: str
    hints: list[str]
    source_lines: list[int]


def load_level(path: Path, conversations: list[Conversation]) -> list[Drill]:
    """Read authored drills and fill in the fields that come from the conversations."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    by_number = {c.number: c for c in conversations}
    level = data.get("level")
    if any(c.level != level for c in conversations):
        raise DrillError(f"{path}: level {level} does not match the conversations' level")

    drills = []
    for position, raw in enumerate(data["drills"], start=1):
        missing = [f for f in AUTHORED_FIELDS if f not in raw]
        if missing:
            raise DrillError(f"drill {position}: missing {', '.join(missing)}")
        conv = by_number.get(raw["conversation"])
        if conv is None:
            raise DrillError(f"drill {position}: unknown conversation {raw['conversation']}")
        drills.append(Drill(
            id=f"L{level:02d}-D{position:02d}",
            level=level,
            cefr=conv.cefr,
            topic_de=conv.topic_de,
            topic_en=conv.topic_en,
            **{f: raw[f] for f in AUTHORED_FIELDS},
        ))
    return drills


def level_markdown(drills: list[Drill]) -> str:
    first = drills[0]
    out = [f"# Level {first.level} · {first.cefr} — {len(drills)} speaking drills", ""]
    topic = None
    for d in drills:
        if d.conversation != topic:
            topic = d.conversation
            out += [f"## C{d.conversation:02d} · {d.topic_de} — {d.topic_en}", ""]
        out += [
            f"**{d.id}** {d.question_de} — *{d.question_en}*  ",
            f"Hints: {' · '.join(d.hints)}  ",
            f"Answer: {d.answer_de} — *{d.answer_en}*",
            "",
        ]
    return "\n".join(out)
