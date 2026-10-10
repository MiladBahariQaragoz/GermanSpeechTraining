import json

import pytest

from gst.drills import DrillError, level_markdown, load_level
from gst.transcript import iter_conversations

GROCERY_DRILL = {
    "conversation": 1,
    "question_de": "Was möchtest du heute Abend kochen?",
    "question_en": "What would you like to cook tonight?",
    "answer_de": "Ich möchte Pasta machen.",
    "answer_en": "I want to make pasta.",
    "hints": ["möchte", "Pasta", "machen"],
    "source_lines": [4, 5],
}
LIBRARY_DRILL = {
    "conversation": 10,
    "question_de": "Wo sind die Bücher?",
    "question_en": "Where are the books?",
    "answer_de": "Die Bücher sind dort drüben.",
    "answer_en": "The books are over there.",
    "hints": ["Bücher", "drüben"],
    "source_lines": [1, 2],
}


def _write(tmp_path, drills, level=1):
    path = tmp_path / f"level-{level:02d}.json"
    path.write_text(json.dumps({"level": level, "drills": drills}, ensure_ascii=False), encoding="utf-8")
    return path


def _level1(ocr_root):
    return list(iter_conversations(ocr_root, levels=[1]))


def test_load_level_fills_derived_fields_from_the_conversation(tmp_path, ocr_root):
    drills = load_level(_write(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL]), _level1(ocr_root))

    first, second = drills
    assert (first.id, first.level, first.cefr) == ("L01-D01", 1, "A1")
    assert (first.topic_de, first.topic_en) == ("Im Lebensmittelgeschäft", "At the grocery store")
    assert first.hints == ["möchte", "Pasta", "machen"]
    assert first.source_lines == [4, 5]
    assert (second.id, second.topic_de) == ("L01-D02", "Die Bibliothek besuchen")


def test_load_level_rejects_unknown_conversation(tmp_path, ocr_root):
    with pytest.raises(DrillError, match="drill 1.*conversation 7"):
        load_level(_write(tmp_path, [{**GROCERY_DRILL, "conversation": 7}]), _level1(ocr_root))


def test_load_level_rejects_missing_field(tmp_path, ocr_root):
    incomplete = {k: v for k, v in GROCERY_DRILL.items() if k != "answer_en"}

    with pytest.raises(DrillError, match="drill 1.*answer_en"):
        load_level(_write(tmp_path, [incomplete]), _level1(ocr_root))


def test_load_level_rejects_level_mismatch(tmp_path, ocr_root):
    with pytest.raises(DrillError, match="level"):
        load_level(_write(tmp_path, [GROCERY_DRILL], level=2), _level1(ocr_root))


def test_markdown_lists_every_question_answer_and_hint(tmp_path, ocr_root):
    drills = load_level(_write(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL]), _level1(ocr_root))

    markdown = level_markdown(drills)

    assert markdown.startswith("# Level 1 · A1 — 2 speaking drills")
    for drill in (GROCERY_DRILL, LIBRARY_DRILL):
        for text in (drill["question_de"], drill["question_en"], drill["answer_de"], drill["answer_en"]):
            assert text in markdown
        assert " · ".join(drill["hints"]) in markdown
