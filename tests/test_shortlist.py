import threading
from types import SimpleNamespace

import pytest

from gst.shortlist import (
    QUESTIONS,
    CachedJudge,
    JevJudge,
    JudgeError,
    line_state,
    shortlist,
    shortlist_digest,
)
from gst.transcript import load_conversation
from tests.conftest import GROCERY_LINES, write_conversation


class FakeJudge:
    """Scores each candidate line by looking its German text up in `scores` (default: lowest)."""

    name = "fake"

    def __init__(self, scores=None):
        self.scores = scores or {}
        self.calls = []
        self._lock = threading.Lock()

    def ask(self, state, questions):
        with self._lock:
            self.calls.append((state, questions))
        return {"value": self.scores.get(state["candidate"]["german"], 0.0)}


def _conversation(tmp_path, lines, number=1, topic=("Im Park", "At the park")):
    level = "13 - Level 13 - A2 - Beginner"
    folder = write_conversation(tmp_path, level, f"{number} -{topic[0]}", topic, lines)
    return load_conversation(folder)


def _grocery(tmp_path):
    return _conversation(tmp_path, GROCERY_LINES, topic=("Im Lebensmittelgeschäft", "At the grocery store"))


def test_line_state_frames_the_learner_and_shows_the_nearby_lines(tmp_path):
    conv = _grocery(tmp_path)

    state = line_state(conv, conv.lines[4])

    assert state["learner"]["cefr_level"] == "A2"
    assert state["situation"] == {"german": "Im Lebensmittelgeschäft", "english": "At the grocery store"}
    assert state["candidate"] == {"line": 5, "german": "Ich möchte Pasta machen.",
                                  "english": "I want to make pasta."}
    assert [line["line"] for line in state["context"]] == [2, 3, 4, 5, 6]


def test_line_state_context_stops_at_the_start_of_the_conversation(tmp_path):
    conv = _grocery(tmp_path)

    assert [line["line"] for line in line_state(conv, conv.lines[0])["context"]] == [1, 2]


def test_shortlist_keeps_the_best_lines_in_line_order(tmp_path):
    conv = _conversation(tmp_path, [
        ("Wie geht es dir?", "How are you?"), ("Gut.", "Fine."),
        ("Was brauchst du?", "What do you need?"), ("Ich brauche Brot und Milch.", "I need bread and milk."),
        ("Wie viel kostet das?", "How much is it?"), ("Drei Euro.", "Three euros."),
    ])
    judge = FakeJudge({"Ich brauche Brot und Milch.": 3.0, "Drei Euro.": 2.0})

    picks = shortlist([conv], judge, per_conversation=2)

    assert [p.line.number for p in picks] == [4, 6]
    assert [p.rank for p in picks] == pytest.approx([1.0, 2 / 3])


def test_judge_is_asked_once_per_line_with_the_shared_questions(tmp_path):
    conv = _grocery(tmp_path)
    judge = FakeJudge()

    shortlist([conv], judge)

    assert sorted(state["candidate"]["line"] for state, _ in judge.calls) == [1, 2, 3, 4, 5, 6]
    assert all(questions is QUESTIONS for _, questions in judge.calls)


def test_cached_judge_asks_once_per_request_even_across_instances(tmp_path):
    inner = FakeJudge()
    conv = _grocery(tmp_path)
    state = line_state(conv, conv.lines[4])

    first = CachedJudge(inner, tmp_path / "jev").ask(state, QUESTIONS)
    second = CachedJudge(inner, tmp_path / "jev").ask(state, QUESTIONS)

    assert first == second == {"value": 0.0}
    assert len(inner.calls) == 1


class FakeClient:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def system_one(self, state, questions, *, model=None):
        if self.error:
            raise self.error
        self.calls.append((state, questions, model))
        return SimpleNamespace(answers={name: SimpleNamespace(score=1.5) for name in questions})


def test_jev_judge_sends_score_questions_and_reads_the_scores():
    sdk = pytest.importorskip("typesafe_sdk")
    client = FakeClient()

    answers = JevJudge(client_factory=lambda: client, model="jev-test").ask({"x": 1}, QUESTIONS)

    assert answers == {"value": 1.5}
    _, sent, model = client.calls[0]
    assert model == "jev-test"
    assert isinstance(sent["value"], sdk.Score)
    assert list(sent["value"].criteria) == QUESTIONS["value"]["criteria"]


def test_jev_judge_turns_sdk_failures_into_judge_errors():
    sdk = pytest.importorskip("typesafe_sdk")
    failing = JevJudge(client_factory=lambda: FakeClient(sdk.TypeSafeError("No API key was provided.")))

    with pytest.raises(JudgeError, match="No API key"):
        failing.ask({"x": 1}, QUESTIONS)


def test_jev_judge_explains_a_missing_sdk():
    def missing():
        raise ImportError("No module named 'typesafe_sdk'")

    with pytest.raises(JudgeError, match="typesafe-sdk"):
        JevJudge(client_factory=missing).ask({"x": 1}, QUESTIONS)


def test_shortlist_digest_shows_the_question_a_picked_line_answers(tmp_path):
    conv = _grocery(tmp_path)
    judge = FakeJudge({"Ich möchte Pasta machen.": 3.0})

    text = shortlist_digest([conv], shortlist([conv], judge, per_conversation=1))

    assert "## C01 · Im Lebensmittelgeschäft — At the grocery store" in text
    assert ("       04 ? Was wirst du kochen? | What will you cook?\n"
            "[1.00] 05   Ich möchte Pasta machen.") in text
    assert "Wie geht es dir heute?" not in text


def test_shortlist_digest_does_not_repeat_a_picked_question_as_context(tmp_path):
    conv = _grocery(tmp_path)
    judge = FakeJudge({"Was wirst du kochen?": 2.0, "Ich möchte Pasta machen.": 3.0})

    text = shortlist_digest([conv], shortlist([conv], judge, per_conversation=2))

    assert ("[0.67] 04 ? Was wirst du kochen? | What will you cook?\n"
            "[1.00] 05   Ich möchte Pasta machen.") in text
    assert text.count("Was wirst du kochen?") == 1
