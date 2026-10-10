from pathlib import Path

import pytest

from gst.drills import Drill
from gst.timeline import TimelineConfig, plan_drill, plan_level

Q_AUDIO, A_AUDIO = Path("q.wav"), Path("a.wav")


def drill(n=1):
    return Drill(
        id=f"L01-D{n:02d}", level=1, cefr="A1", conversation=1,
        topic_de="Im Lebensmittelgeschäft", topic_en="At the grocery store",
        question_de=f"Frage {n}?", question_en=f"Question {n}?",
        answer_de="Ich möchte Pasta machen.", answer_en="I want to make pasta.",
        hints=["Pasta", "machen"], source_lines=[10],
    )


def test_drill_is_question_then_speaking_pause_then_answer():
    segments = plan_drill(drill(), Q_AUDIO, 2.0, A_AUDIO, 3.0, TimelineConfig())

    assert [s.kind for s in segments] == ["question", "speak", "answer"]
    assert [s.duration for s in segments] == pytest.approx([2.6, 6.5, 4.2])
    assert [s.audio for s in segments] == [Q_AUDIO, None, A_AUDIO]


def test_short_answers_still_get_the_minimum_speaking_time():
    segments = plan_drill(drill(), Q_AUDIO, 2.0, A_AUDIO, 1.0, TimelineConfig())

    assert segments[1].duration == pytest.approx(5.0)


def test_level_wraps_drills_in_intro_and_outro_with_chapters():
    items = [(drill(n), Q_AUDIO, 2.0, A_AUDIO, 3.0) for n in (1, 2, 3)]

    segments, chapters = plan_level(items, TimelineConfig())

    assert [s.kind for s in segments] == ["intro"] + ["question", "speak", "answer"] * 3 + ["outro"]
    assert segments[0].duration == pytest.approx(3.0)
    assert segments[-1].duration == pytest.approx(2.0)
    assert [c.title for c in chapters] == [
        "Intro", "L01-D01 · Frage 1?", "L01-D02 · Frage 2?", "L01-D03 · Frage 3?",
    ]
    assert [c.start for c in chapters] == pytest.approx([0.0, 3.0, 16.3, 29.6])
