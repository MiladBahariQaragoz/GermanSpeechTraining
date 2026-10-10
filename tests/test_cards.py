from pathlib import Path

import pytest
from PIL import ImageChops

from gst.cards import HEIGHT, WIDTH, answer_card, fit, font, font_path, question_card, title_card, wrap
from tests.test_timeline import drill


@pytest.mark.parametrize("family", ["serif", "sans", "mono"])
def test_font_families_resolve_to_files(family):
    assert Path(font_path(family)).is_file()


def test_wrap_keeps_lines_within_width_and_keeps_every_word():
    text = "Entschuldigung, können Sie mir sagen, welcher Bus ins Stadtzentrum fährt?"
    face = font("serif", 60)

    lines = wrap(text, face, 500)

    assert len(lines) > 1
    assert all(face.getlength(line) <= 500 for line in lines)
    assert " ".join(lines).split() == text.split()


def test_fit_shrinks_long_text_until_it_fits():
    text = "Ich möchte Pasta machen, weil ich Pasta liebe. " * 4

    face, lines = fit(text, "serif", max_width=1000, max_lines=3, size=64, min_size=28)

    assert face.size < 64
    assert len(lines) <= 3


@pytest.mark.parametrize(
    "card",
    [
        lambda: question_card(drill()),
        lambda: question_card(drill(), countdown=True),
        lambda: answer_card(drill()),
        lambda: title_card("Level 1", "A1 · 60 Sprechübungen"),
    ],
)
def test_cards_are_full_hd_ready_rgb_frames(card):
    image = card()

    assert image.size == (WIDTH, HEIGHT) == (1280, 720)
    assert image.mode == "RGB"


def test_countdown_card_differs_from_question_card():
    assert ImageChops.difference(question_card(drill()), question_card(drill(), countdown=True)).getbbox()


def test_very_long_answer_still_renders():
    long = drill()
    long = type(long)(**{**long.__dict__, "answer_de": "Ich möchte Pasta machen. " * 8})

    assert answer_card(long).size == (WIDTH, HEIGHT)
