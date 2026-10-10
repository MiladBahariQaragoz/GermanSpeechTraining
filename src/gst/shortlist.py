"""Rank a level's question→answer exchanges with Jev, so drills are written from the best ones.

Jev (TypeSafe System One) only judges: it scores each exchange for topic relevance and speaking value.
Code builds the candidates, ranks them and formats the shortlist; Claude still writes every drill.
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
    "relevance": {
        "type": "score",
        "instructions": (
            "`exchange` is a question and its answer from a German conversation about `topic`. "
            "How central is this exchange to that situation?"
        ),
        "criteria": [
            "Greeting, small talk, thanks or goodbye that could happen in any conversation",
            "Loosely connected: it could happen in this situation, but the situation is not about it",
            "A typical exchange for this situation",
            "A core exchange of this situation that a learner would most need to handle it",
        ],
    },
    "speaking_value": {
        "type": "score",
        "instructions": (
            "A language learner will practise saying the answer in `exchange` "
            "(the lines after the question). "
            "How much useful speaking practice does that answer give?"
        ),
        "criteria": [
            "A single word, a bare yes or no, or a reaction such as 'Okay.' or 'Gute Idee!'",
            "A short complete sentence with little concrete content",
            "A complete sentence with concrete information such as items, amounts, times, places, "
            "preferences or reasons",
            "Two or more sentences of concrete information the learner could reuse about their own life",
        ],
    },
}


class JudgeError(Exception):
    """The judging service could not answer (missing SDK or key, network, refused request)."""


class Judge(Protocol):
    name: str

    def ask(self, state: dict, questions: dict[str, dict]) -> dict[str, float]:
        """Raw Score value per question name."""
        ...


@dataclass(frozen=True)
class Exchange:
    conversation: Conversation
    question: Line
    answers: tuple[Line, ...]


@dataclass(frozen=True)
class Pick:
    exchange: Exchange
    rank: float  # 0..1, mean of the normalised scores


def _is_question(line: Line) -> bool:
    return line.de.rstrip().endswith("?")


def exchanges(conv: Conversation, max_answer_lines: int = 2) -> list[Exchange]:
    """Each question line with the (up to `max_answer_lines`) lines that answer it."""
    found = []
    lines = conv.lines
    for i, line in enumerate(lines):
        if not _is_question(line):
            continue
        answers = []
        for following in lines[i + 1 : i + 1 + max_answer_lines]:
            if _is_question(following):
                break
            answers.append(following)
        if answers:
            found.append(Exchange(conv, line, tuple(answers)))
    return found


def _state(exchange: Exchange) -> dict:
    conv = exchange.conversation
    return {
        "topic": {"german": conv.topic_de, "english": conv.topic_en},
        "exchange": [
            {"german": line.de, "english": line.en}
            for line in (exchange.question, *exchange.answers)
        ],
    }


def _rank(answers: dict[str, float]) -> float:
    parts = [answers[name] / (len(q["criteria"]) - 1) for name, q in QUESTIONS.items()]
    return sum(parts) / len(parts)


def shortlist(conversations: list[Conversation], judge: Judge, per_conversation: int = 6,
              workers: int = 8) -> list[Pick]:
    """The best `per_conversation` exchanges of each conversation, conversations in order, lines in order."""
    candidates = [e for conv in conversations for e in exchanges(conv)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        ranks = list(pool.map(lambda e: _rank(judge.ask(_state(e), QUESTIONS)), candidates))

    picks = []
    for conv in conversations:
        mine = [Pick(e, r) for e, r in zip(candidates, ranks, strict=True) if e.conversation is conv]
        best = sorted(mine, key=lambda p: p.rank, reverse=True)[:per_conversation]
        picks += sorted(best, key=lambda p: p.exchange.question.number)
    return picks


def shortlist_digest(conversations: list[Conversation], picks: list[Pick]) -> str:
    """Digest-style view of the picks: rank, then the transcript lines with their `Line.number`."""
    first = conversations[0]
    out = [f"# Level {first.level} · {first.cefr} · Jev shortlist", ""]
    for conv in conversations:
        out.append(f"## C{conv.number:02d} · {conv.topic_de} — {conv.topic_en}")
        mine = [p for p in picks if p.exchange.conversation is conv]
        if not mine:
            out.append("(no question→answer exchanges; read the full digest)")
        for pick in mine:
            q = pick.exchange.question
            out.append(f"[{pick.rank:.2f}] {q.number:02d} ? {q.de} | {q.en}")
            out += [f"       {a.number:02d}   {a.de} | {a.en}" for a in pick.exchange.answers]
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
