import threading
from types import SimpleNamespace

import pytest

from gst.shortlist import (
    QUESTIONS,
    CachedJudge,
    JevJudge,
    JudgeError,
    exchanges,
    shortlist,
    shortlist_digest,
)
from gst.transcript import load_conversation
from tests.conftest import GROCERY_LINES, write_conversation


class FakeJudge:
    """Scores each exchange by looking its question up in `scores` (default: lowest)."""

    name = "fake"

    def __init__(self, scores=None):
        self.scores = scores or {}
        self.calls = []
        self._lock = threading.Lock()

    def ask(self, state, questions):
        with self._lock:
            self.calls.append((state, questions))
        question = state["exchange"][0]["german"]
        return self.scores.get(question, {name: 0.0 for name in questions})


def _conversation(tmp_path, lines, number=1, topic=("Im Park", "At the park")):
    level = "13 - Level 13 - A2 - Beginner"
    folder = write_conversation(tmp_path, level, f"{number} -{topic[0]}", topic, lines)
    return load_conversation(folder)


def test_exchanges_pair_questions_with_the_lines_that_answer_them(tmp_path):
    conv = _conversation(tmp_path, [
        ("Was machst du gern?", "What do you like doing?"),
        ("Ich lese gern.", "I like reading."),
        ("Ich laufe auch.", "I run too."),
        ("Ich koche nie.", "I never cook."),
        ("Und du?", "And you?"),
        ("Was isst du gern?", "What do you like to eat?"),
        ("Pasta.", "Pasta."),
    ])

    found = [(e.question.number, [a.number for a in e.answers]) for e in exchanges(conv, max_answer_lines=2)]

    assert found == [(1, [2, 3]), (6, [7])]


def test_shortlist_keeps_the_best_exchanges_in_line_order(tmp_path):
    conv = _conversation(tmp_path, [
        ("Wie geht es dir?", "How are you?"), ("Gut.", "Fine."),
        ("Was brauchst du?", "What do you need?"), ("Ich brauche Brot und Milch.", "I need bread and milk."),
        ("Wie viel kostet das?", "How much is it?"), ("Drei Euro.", "Three euros."),
    ])
    judge = FakeJudge({
        "Was brauchst du?": {"relevance": 3.0, "speaking_value": 2.0},
        "Wie viel kostet das?": {"relevance": 2.0, "speaking_value": 1.0},
    })

    picks = shortlist([conv], judge, per_conversation=2)

    assert [p.exchange.question.number for p in picks] == [3, 5]
    assert picks[0].rank == pytest.approx((3 / 3 + 2 / 3) / 2)


def test_judge_sees_the_topic_and_the_exchange(tmp_path):
    conv = _conversation(tmp_path, GROCERY_LINES, topic=("Im Lebensmittelgeschäft", "At the grocery store"))
    judge = FakeJudge()

    shortlist([conv], judge)

    state, questions = next(c for c in judge.calls if c[0]["exchange"][0]["german"] == "Was wirst du kochen?")
    assert state["topic"] == {"german": "Im Lebensmittelgeschäft", "english": "At the grocery store"}
    assert state["exchange"][1] == {"german": "Ich möchte Pasta machen.", "english": "I want to make pasta."}
    assert questions is QUESTIONS


def test_cached_judge_asks_once_per_request_even_across_instances(tmp_path):
    inner = FakeJudge()
    state = {"topic": {"german": "Im Park", "english": "At the park"},
             "exchange": [{"german": "Was machst du?", "english": "What are you doing?"}]}

    first = CachedJudge(inner, tmp_path / "jev").ask(state, QUESTIONS)
    second = CachedJudge(inner, tmp_path / "jev").ask(state, QUESTIONS)

    assert first == second == {"relevance": 0.0, "speaking_value": 0.0}
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

    assert answers == {"relevance": 1.5, "speaking_value": 1.5}
    _, sent, model = client.calls[0]
    assert model == "jev-test"
    assert isinstance(sent["relevance"], sdk.Score)
    assert list(sent["relevance"].criteria) == QUESTIONS["relevance"]["criteria"]


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


def test_shortlist_digest_shows_rank_and_transcript_line_numbers(tmp_path):
    conv = _conversation(tmp_path, GROCERY_LINES, topic=("Im Lebensmittelgeschäft", "At the grocery store"))
    judge = FakeJudge({"Was wirst du kochen?": {"relevance": 3.0, "speaking_value": 3.0}})

    text = shortlist_digest([conv], shortlist([conv], judge, per_conversation=1))

    assert "## C01 · Im Lebensmittelgeschäft — At the grocery store" in text
    assert "[1.00] 04 ? Was wirst du kochen? | What will you cook?" in text
    assert "       05   Ich möchte Pasta machen. | I want to make pasta." in text
    assert "Wie geht es dir heute?" not in text
