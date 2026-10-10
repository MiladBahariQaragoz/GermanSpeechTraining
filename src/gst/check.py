"""Validate authored drills against the plan's success criteria 1–4."""

from collections import Counter

from gst.drills import Drill
from gst.text import content_words, normalise, words
from gst.transcript import Conversation

MIN_GROUNDING = 0.5
TEXT_FIELDS = ("question_de", "question_en", "answer_de", "answer_en")


def _drill_problems(d: Drill, conv: Conversation) -> list[str]:
    problems = [f"{d.id}: {field} is empty" for field in TEXT_FIELDS if not getattr(d, field).strip()]
    if not d.question_de.rstrip().endswith("?"):
        problems.append(f"{d.id}: question does not end with '?'")

    if not 2 <= len(d.hints) <= 5:
        problems.append(f"{d.id}: {len(d.hints)} hints, need 2 to 5")
    answer_words = set(words(d.answer_de))
    for hint in d.hints:
        if not words(hint):
            problems.append(f"{d.id}: hint {hint!r} has no words")
        elif not set(words(hint)) <= answer_words:
            problems.append(f"{d.id}: hint {hint!r} is not in the answer")

    count = len(conv.lines)
    if not d.source_lines or not all(1 <= n <= count for n in d.source_lines):
        problems.append(f"{d.id}: source_lines {d.source_lines} not within 1..{count}")
        return problems

    # Short answers can consist of function words only ("Ja, ich auch."); then compare every word.
    pick = content_words if content_words(d.answer_de) else words
    answer = pick(d.answer_de)
    if answer:
        source = set(pick(" ".join(conv.lines[n - 1].de for n in d.source_lines)))
        grounded = sum(w in source for w in answer) / len(answer)
        if grounded < MIN_GROUNDING:
            problems.append(f"{d.id}: only {grounded:.0%} of the answer's words are in its source lines")
    return problems


def check_level(
    drills: list[Drill],
    conversations: list[Conversation],
    min_drills: int = 40,
    cap: int = 4,
    min_conversations: int = 15,
) -> list[str]:
    """Every problem found, as human-readable lines; an empty list means the level passes."""
    level = conversations[0].level
    by_number = {c.number: c for c in conversations}
    problems = []

    seen: dict[str, str] = {}
    for d in drills:
        problems += _drill_problems(d, by_number[d.conversation])
        key = normalise(d.question_de)
        if key in seen:
            problems.append(f"{d.id}: duplicate of {seen[key]}'s question")
        seen.setdefault(key, d.id)

    per_conversation = Counter(d.conversation for d in drills)
    for number, n in sorted(per_conversation.items()):
        if n > cap:
            problems.append(f"conversation {number}: {n} drills, cap is {cap}")
    if len(per_conversation) < min_conversations:
        problems.append(
            f"level {level}: {len(per_conversation)} conversations represented, "
            f"need at least {min_conversations}"
        )
    if len(drills) < min_drills:
        problems.append(f"level {level}: {len(drills)} drills, need at least {min_drills}")
    return problems
