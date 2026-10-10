from gst.digest import level_digest
from gst.transcript import iter_conversations


def test_digest_has_a_header_per_conversation(ocr_root):
    digest = level_digest(list(iter_conversations(ocr_root, levels=[1])))

    assert digest.startswith("# Level 1 · A1\n")
    assert "## C01 · Im Lebensmittelgeschäft — At the grocery store" in digest
    assert digest.index("## C02 ·") < digest.index("## C10 ·")


def test_digest_numbers_lines_and_marks_questions(ocr_root):
    digest = level_digest(list(iter_conversations(ocr_root, levels=[1])))

    assert "01   Hallo, Maria! | Hello, Maria!" in digest
    assert "04 ? Was wirst du kochen? | What will you cook?" in digest


def test_digest_line_numbers_match_the_loaded_lines(ocr_root):
    conversation = next(iter_conversations(ocr_root, levels=[1]))
    digest = level_digest([conversation])

    for line in conversation.lines:
        assert f"{line.number:02d} " in digest
        assert line.de in digest
