import pytest

from gst.check import check_level
from gst.drills import Drill
from gst.transcript import iter_conversations


@pytest.fixture
def conversations(ocr_root):
    return list(iter_conversations(ocr_root, levels=[1]))


def drill(n=1, **overrides):
    fields = dict(
        id=f"L01-D{n:02d}", level=1, cefr="A1", conversation=1,
        topic_de="Im Lebensmittelgeschäft", topic_en="At the grocery store",
        question_de="Was möchtest du heute Abend kochen?", question_en="What would you like to cook tonight?",
        answer_de="Ich möchte Pasta machen.", answer_en="I want to make pasta.",
        hints=["möchte", "Pasta", "machen"], source_lines=[4, 5],
    )
    fields.update(overrides)
    return Drill(**fields)


def valid_level():
    return [
        drill(1),
        drill(2, conversation=2, topic_de="Nach dem Weg fragen", question_de="Wo ist der Bahnhof?",
              answer_de="Der Bahnhof ist geradeaus.", hints=["Bahnhof", "geradeaus"], source_lines=[1, 2]),
        drill(3, conversation=10, topic_de="Die Bibliothek besuchen", question_de="Wo findest du die Bücher?",
              answer_de="Die Bücher sind dort drüben.", hints=["Bücher", "drüben"], source_lines=[1, 2]),
    ]


def check(drills, conversations, **limits):
    return check_level(drills, conversations, **{"min_drills": 3, "cap": 2, "min_conversations": 3, **limits})


def test_valid_level_has_no_problems(conversations):
    assert check(valid_level(), conversations) == []


def test_too_few_drills(conversations):
    assert check(valid_level(), conversations, min_drills=40) == ["level 1: 3 drills, need at least 40"]


def test_hint_missing_from_answer(conversations):
    drills = valid_level()
    drills[0] = drill(1, hints=["möchte", "Spaghetti"])

    assert check(drills, conversations) == ["L01-D01: hint 'Spaghetti' is not in the answer"]


@pytest.mark.parametrize("hints", [["Pasta"], ["Ich", "möchte", "Pasta", "machen", "Ich", "möchte"]])
def test_hint_count_must_be_two_to_five(conversations, hints):
    drills = valid_level()
    drills[0] = drill(1, hints=hints)

    assert check(drills, conversations) == [f"L01-D01: {len(hints)} hints, need 2 to 5"]


@pytest.mark.parametrize("lines", [[], [0], [7]])
def test_source_lines_must_exist(conversations, lines):
    drills = valid_level()
    drills[0] = drill(1, source_lines=lines)

    assert check(drills, conversations) == [f"L01-D01: source_lines {lines} not within 1..6"]


def test_answer_must_be_grounded_in_its_source_lines(conversations):
    drills = valid_level()
    drills[0] = drill(1, answer_de="Ich koche heute Abend Suppe.", hints=["koche", "Suppe"])

    assert check(drills, conversations) == ["L01-D01: only 0% of the answer's words are in its source lines"]


def test_question_must_end_with_question_mark(conversations):
    drills = valid_level()
    drills[0] = drill(1, question_de="Erzähl mir, was du kochst.")

    assert check(drills, conversations) == ["L01-D01: question does not end with '?'"]


def test_conversation_cap(conversations):
    drills = [*valid_level(), drill(4, question_de="Was kochst du?"), drill(5, question_de="Was machst du?")]

    assert check(drills, conversations) == ["conversation 1: 3 drills, cap is 2"]


def test_too_few_conversations(conversations):
    drills = [drill(1), drill(2, question_de="Was kochst du?"), valid_level()[1]]

    assert check(drills, conversations) == ["level 1: 2 conversations represented, need at least 3"]


def test_duplicate_questions(conversations):
    drills = valid_level()
    drills[1] = drill(2, conversation=2, question_de="was möchtest du heute abend kochen")

    problems = check(drills, conversations)

    assert "L01-D02: duplicate of L01-D01's question" in problems
