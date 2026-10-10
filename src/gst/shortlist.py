"""Rank every line of a level's conversations with Jev, so drills are written from the best ones.

Jev (TypeSafe System One) only judges: for each line it scores how valuable that line is for a learner
to practise saying, given the learner's level, the situation and the nearby lines. Code builds the
requests, ranks and formats the shortlist; Claude still writes every drill.

Chosen in a bake-off against 180 hand-picked drills (levels 10-12): this per-line, learner-framed Score
found 77 % of them in the top 12 lines per conversation, against 68 % in ~17 lines for scoring
question→answer pairs and 67 % for one Choice over the whole conversation (its probabilities go flat
after ~10 lines).
"""

import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from gst.transcript import Conversation, Line

INSTALL_HINT = (
    "the TypeSafe SDK (typesafe-sdk) is missing: run `uv sync --extra jev` and set TYPESAFE_API_KEY"
)

QUESTIONS: dict[str, dict[str, Any]] = {
    "value": {
        "type": "score",
        "instructions": {
            "question": "How valuable is `candidate` for `learner` to practise saying aloud? "
                        "`context` holds the lines just before and after it in the conversation.",
            "prefer": [
                "complete sentences the learner could reuse in this situation in real life",
                "concrete content: items, amounts, times, places, preferences, reasons, requests, problems",
                "the typical vocabulary and sentence patterns of `situation`",
            ],
            "avoid": [
                "greetings, thanks, goodbyes and small talk",
                "bare yes/no answers and reactions such as 'Okay.', 'Gute Idee!', 'Wow!'",
                "lines that only make sense inside this one dialogue, such as 'Hier ist sie.' "
                "or a character's name",
            ],
        },
        "criteria": [
            "Greeting, small talk, thanks, goodbye, a bare yes/no or a reaction",
            "A sentence that only makes sense inside this dialogue, or has little to reuse",
            "A useful complete sentence for this situation with some concrete content",
            "A sentence the learner would very likely need to say in this situation, "
            "with concrete reusable content",
        ],
    },
}

# Lines of context Jev sees around the candidate.
CONTEXT_BEFORE, CONTEXT_AFTER = 3, 1


class JudgeError(Exception):
    """The judging service could not answer (missing SDK or key, network, refused request)."""


class Judge(Protocol):
    name: str

    def ask(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        """Raw Score value per question name."""
        ...


@dataclass(frozen=True)
class Pick:
    conversation: Conversation
    line: Line
    rank: float  # 0..1, the normalised Score


def _is_question(line: Line) -> bool:
    return line.de.rstrip().endswith("?")


def _line(line: Line) -> dict:
    return {"line": line.number, "german": line.de, "english": line.en}


def line_state(conv: Conversation, line: Line) -> dict:
    """What Jev sees for one candidate: who is learning, the situation, the line and its neighbours."""
    i = line.number - 1
    return {
        "learner": {
            "cefr_level": conv.cefr,
            "goal": f"to speak German confidently in this situation: {conv.topic_en or conv.topic_de}",
            "practice": "hears a question, then answers aloud with one sentence from the course",
        },
        "situation": {"german": conv.topic_de, "english": conv.topic_en},
        "context": [_line(near) for near in conv.lines[max(0, i - CONTEXT_BEFORE): i + 1 + CONTEXT_AFTER]],
        "candidate": _line(line),
    }


def _rank(answers: dict[str, float]) -> float:
    parts = [answers[name] / (len(q["criteria"]) - 1) for name, q in QUESTIONS.items()]
    return sum(parts) / len(parts)


def shortlist(conversations: list[Conversation], judge: Judge, per_conversation: int = 12,
              workers: int = 8) -> list[Pick]:
    """The best `per_conversation` lines of each conversation, conversations in order, lines in order."""
    candidates = [(conv, line) for conv in conversations for line in conv.lines]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        ranks = list(pool.map(lambda c: _rank(judge.ask(line_state(*c), QUESTIONS)), candidates))

    picks = []
    for conv in conversations:
        mine = [Pick(c, line, r) for (c, line), r in zip(candidates, ranks, strict=True) if c is conv]
        best = sorted(mine, key=lambda p: p.rank, reverse=True)[:per_conversation]
        picks += sorted(best, key=lambda p: p.line.number)
    return picks


def _row(line: Line, prefix: str) -> str:
    mark = "?" if _is_question(line) else " "
    return f"{prefix}{line.number:02d} {mark} {line.de} | {line.en}"


def shortlist_digest(conversations: list[Conversation], picks: list[Pick]) -> str:
    """Digest-style view of the picks with their rank and `Line.number`; a picked line that answers a
    question gets that question above it for context."""
    first = conversations[0]
    out = [f"# Level {first.level} · {first.cefr} · Jev shortlist", ""]
    for conv in conversations:
        out.append(f"## C{conv.number:02d} · {conv.topic_de} — {conv.topic_en}")
        mine = [p for p in picks if p.conversation is conv]
        picked = {p.line.number for p in mine}
        for pick in mine:
            before = pick.line.number - 1
            if before >= 1 and before not in picked and _is_question(conv.lines[before - 1]):
                out.append(_row(conv.lines[before - 1], " " * 7))
            out.append(_row(pick.line, f"[{pick.rank:.2f}] "))
        out.append("")
    return "\n".join(out)


def _sdk_client():
    from typesafe_sdk import TypeSafeClient

    return TypeSafeClient()


class JevJudge:
    """Asks TypeSafe System One (Jev) through the official SDK; the client is built on first use."""

    def __init__(self, client_factory: Callable[[], Any] = _sdk_client, model: str | None = None):
        self.client_factory = client_factory
        self.model = model
        self.name = f"jev:{model or 'default'}"
        self._client = None

    def ask(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        try:
            from typesafe_sdk import Score, TypeSafeError
        except ImportError as error:
            raise JudgeError(INSTALL_HINT) from error
        try:
            if self._client is None:
                self._client = self.client_factory()
            sdk_questions = {
                name: Score(instructions=q["instructions"], criteria=q["criteria"])
                for name, q in questions.items()
            }
            response = self._client.system_one(state, sdk_questions, model=self.model)
        except ImportError as error:
            raise JudgeError(INSTALL_HINT) from error
        except TypeSafeError as error:
            raise JudgeError(str(error)) from error
        return {name: float(response.answers[name].score) for name in questions}


class CachedJudge:
    """Keeps every answer on disk, keyed by judge, state and questions, so reruns cost nothing."""

    def __init__(self, inner: Judge, cache_dir: Path):
        self.inner = inner
        self.name = inner.name
        self.cache_dir = Path(cache_dir)

    def ask(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        request = json.dumps({"judge": self.inner.name, "state": state, "questions": questions},
                             sort_keys=True, ensure_ascii=False)
        path = self.cache_dir / f"{hashlib.sha256(request.encode()).hexdigest()}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        answers = self.inner.ask(state, questions)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        partial.write_text(json.dumps(answers), encoding="utf-8")
        partial.replace(path)
        return answers
