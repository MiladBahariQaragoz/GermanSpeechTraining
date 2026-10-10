"""Still frames for the practice video: warm off-white canvas, serif German, muted English."""

import subprocess
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from gst.drills import Drill

WIDTH, HEIGHT = 1280, 720
MARGIN = 96
CONTENT_WIDTH = WIDTH - 2 * MARGIN

CANVAS = "#F7F6F3"
HEADLINE = "#111111"
INK = "#2F3437"
MUTED = "#787774"
RULE = "#E3E1DC"
PASTELS = {  # (background, text)
    "blue": ("#E1F3FE", "#1F6C9F"),
    "green": ("#EDF3EC", "#346538"),
    "red": ("#FDEBEC", "#9F2F2D"),
    "yellow": ("#FBF3DB", "#956400"),
}

# Countdown track; video.py animates the fill over this rectangle (x, y, width, height).
BAR = (MARGIN, 648, CONTENT_WIDTH, 8)
BAR_FILL = HEADLINE

_FAMILIES = {
    "serif": "Noto Serif",
    "sans": "Noto Sans",
    "sans-bold": "Noto Sans:bold",
    "mono": "Noto Sans Mono",
}


@lru_cache
def font_path(family: str) -> str:
    result = subprocess.run(
        ["fc-match", _FAMILIES[family], "-f", "%{file}"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@lru_cache
def font(family: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(family), size)


def wrap(text: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word wrap; a single word wider than `max_width` gets a line of its own."""
    lines: list[str] = []
    for word in text.split():
        candidate = f"{lines[-1]} {word}" if lines else word
        if lines and face.getlength(candidate) <= max_width:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines


def fit(text: str, family: str, max_width: int, max_lines: int, size: int, min_size: int):
    """Largest font size (stepping down by 4) whose wrapped text fits in `max_lines`."""
    while True:
        face = font(family, size)
        lines = wrap(text, face, max_width)
        if len(lines) <= max_lines or size <= min_size:
            return face, lines
        size = max(min_size, size - 4)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), CANVAS)
    return image, ImageDraw.Draw(image)


def _tracked(draw, xy, text, face, fill, tracking=2):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=face, fill=fill)
        x += face.getlength(char) + tracking
    return x


def _tracked_width(text, face, tracking=2):
    return sum(face.getlength(c) + tracking for c in text)


def _pill(draw, xy, text, colour, face=None, pad=(14, 6)) -> int:
    """Uppercase label on a pastel pill; returns the pill's right edge."""
    face = face or font("sans-bold", 15)
    background, foreground = PASTELS[colour]
    x, y = xy
    width = _tracked_width(text, face) + 2 * pad[0]
    height = face.size + 2 * pad[1] + 4
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=background)
    _tracked(draw, (x + pad[0], y + pad[1]), text, face, foreground)
    return x + width


def _header(draw, drill: Drill) -> None:
    mono = font("mono", 17)
    _tracked(draw, (MARGIN, 52), f"LEVEL {drill.level} · {drill.cefr}", mono, MUTED)
    topic = font("sans", 20)
    draw.text((WIDTH - MARGIN - topic.getlength(drill.topic_de), 49), drill.topic_de, font=topic, fill=MUTED)
    draw.line((MARGIN, 96, WIDTH - MARGIN, 96), fill=RULE, width=1)


def _block(draw, y, lines, face, fill, leading=1.18) -> int:
    for line in lines:
        draw.text((MARGIN, y), line, font=face, fill=fill)
        y += round(face.size * leading)
    return y


def _hints(draw, y, hints) -> None:
    _tracked(draw, (MARGIN, y), "HINWEISE", font("mono", 15), MUTED)
    face = font("sans", 28)
    background, foreground = PASTELS["yellow"]
    x, y = MARGIN, y + 32
    for hint in hints:
        width = face.getlength(hint) + 40
        if x + width > WIDTH - MARGIN:
            x, y = MARGIN, y + 60
        draw.rounded_rectangle((x, y, x + width, y + 48), radius=24, fill=background)
        draw.text((x + 20, y + 6), hint, font=face, fill=foreground)
        x += width + 14


def question_card(drill: Drill, countdown: bool = False) -> Image.Image:
    """The question with its translation and hints; `countdown` marks the learner's turn."""
    image, draw = _canvas()
    _header(draw, drill)
    if countdown:
        _pill(draw, (MARGIN, 140), "JETZT DU", "red")
    else:
        _pill(draw, (MARGIN, 140), "FRAGE", "blue")

    face, lines = fit(drill.question_de, "serif", CONTENT_WIDTH, 3, size=60, min_size=36)
    y = _block(draw, 196, lines, face, HEADLINE)
    english, english_lines = fit(drill.question_en, "sans", CONTENT_WIDTH, 2, size=28, min_size=22)
    _block(draw, y + 24, english_lines, english, MUTED, leading=1.35)

    _hints(draw, 500, drill.hints)
    if countdown:
        x, y, width, height = BAR
        draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=RULE)
    return image


def answer_card(drill: Drill) -> Image.Image:
    image, draw = _canvas()
    _header(draw, drill)

    question, question_lines = fit(drill.question_de, "serif", CONTENT_WIDTH, 2, size=30, min_size=24)
    y = _block(draw, 134, question_lines, question, MUTED)
    draw.line((MARGIN, y + 20, WIDTH - MARGIN, y + 20), fill=RULE, width=1)

    y = max(y + 52, 250)
    _pill(draw, (MARGIN, y), "ANTWORT", "green")
    face, lines = fit(drill.answer_de, "serif", CONTENT_WIDTH, 3, size=60, min_size=32)
    y = _block(draw, y + 56, lines, face, HEADLINE)
    english, english_lines = fit(drill.answer_en, "sans", CONTENT_WIDTH, 2, size=28, min_size=22)
    _block(draw, y + 24, english_lines, english, MUTED, leading=1.35)
    return image


def title_card(title: str, subtitle: str, note: str = "HÖR ZU · SPRICH · VERGLEICHE") -> Image.Image:
    image, draw = _canvas()
    _tracked(draw, (MARGIN, 236), "SPRECHTRAINING", font("mono", 18), MUTED)
    draw.text((MARGIN, 268), title, font=font("serif", 104), fill=HEADLINE)
    draw.text((MARGIN, 408), subtitle, font=font("sans", 32), fill=INK)
    draw.line((MARGIN, 600, WIDTH - MARGIN, 600), fill=RULE, width=1)
    _tracked(draw, (MARGIN, 622), note, font("mono", 16), MUTED)
    return image
