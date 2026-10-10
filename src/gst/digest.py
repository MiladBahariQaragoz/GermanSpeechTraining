"""Compact, numbered view of a level's conversations, used when writing drills."""

from gst.transcript import Conversation


def level_digest(conversations: list[Conversation]) -> str:
    """One block per conversation; `?` marks question lines, numbers are `Line.number`."""
    first = conversations[0]
    out = [f"# Level {first.level} · {first.cefr}", ""]
    for conv in conversations:
        out.append(f"## C{conv.number:02d} · {conv.topic_de} — {conv.topic_en}")
        for line in conv.lines:
            mark = "?" if line.de.rstrip().endswith("?") else " "
            out.append(f"{line.number:02d} {mark} {line.de} | {line.en}")
        out.append("")
    return "\n".join(out)
