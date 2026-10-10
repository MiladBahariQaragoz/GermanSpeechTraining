import pytest

from gst.transcript import (
    Line,
    iter_conversations,
    load_conversation,
    parse_conversation_dir,
    parse_level_dir,
)
from tests.conftest import GROCERY_LINES, write_conversation


def test_parse_level_dir_reads_number_and_cefr():
    assert parse_level_dir("1 - Level 1 - A1 - Beginner") == (1, "A1")
    assert parse_level_dir("29 - Level 29 - B2 - Intermediate") == (29, "B2")


def test_parse_level_dir_rejects_other_folders():
    with pytest.raises(ValueError):
        parse_level_dir("_slide_ocr")


def test_parse_conversation_dir_reads_number_and_topic():
    assert parse_conversation_dir("1 -Im Lebensmittelgeschäft") == (1, "Im Lebensmittelgeschäft")
    assert parse_conversation_dir("12 - Kleidung einkaufen") == (12, "Kleidung einkaufen")


def test_load_conversation_keeps_only_the_first_pass_of_the_dialogue(ocr_root):
    conv = load_conversation(ocr_root / "1 - Level 1 - A1 - Beginner" / "1 -Im Lebensmittelgeschäft")

    assert conv.lines == [Line(n, de, en) for n, (de, en) in enumerate(GROCERY_LINES, start=1)]


def test_load_conversation_takes_metadata_from_folders_and_title_slide(ocr_root):
    conv = load_conversation(ocr_root / "1 - Level 1 - A1 - Beginner" / "1 -Im Lebensmittelgeschäft")

    assert (conv.level, conv.cefr, conv.number) == (1, "A1", 1)
    assert (conv.topic_de, conv.topic_en) == ("Im Lebensmittelgeschäft", "At the grocery store")
    assert all(line.de != conv.topic_de for line in conv.lines)


def test_title_slide_is_recognised_when_ocr_dropped_an_accent(tmp_path):
    folder = write_conversation(tmp_path, "2 - Level 2 - A1 - Beginner", "17 -Treffen im Café",
                                ("Treffen im Cafe", "Meeting at the cafe"), GROCERY_LINES[:2])

    conv = load_conversation(folder)

    assert conv.topic_en == "Meeting at the cafe"
    assert [line.de for line in conv.lines] == [de for de, _ in GROCERY_LINES[:2]]


def test_load_conversation_without_marker_keeps_every_line(tmp_path):
    folder = write_conversation(tmp_path, "3 - Level 3 - A1 - Beginner", "4 -An der Bushaltestelle",
                                ("An der Bushaltestelle", "At the bus stop"), GROCERY_LINES[:3], marker=False)

    assert [line.de for line in load_conversation(folder).lines] == [de for de, _ in GROCERY_LINES[:3]]


def test_iter_conversations_filters_levels_and_sorts_naturally(ocr_root):
    numbers = [(c.level, c.number) for c in iter_conversations(ocr_root, levels=[1])]

    assert numbers == [(1, 1), (1, 2), (1, 10)]


def test_iter_conversations_without_levels_yields_all(ocr_root):
    assert [(c.level, c.number) for c in iter_conversations(ocr_root)] == [(1, 1), (1, 2), (1, 10), (2, 1)]
