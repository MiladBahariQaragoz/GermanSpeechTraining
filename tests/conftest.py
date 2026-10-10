import json
from pathlib import Path

import pytest

INTRO = (
    "First, you will listen to the dialogue naturally between the characters. "
    "Then, you will be able to hear all the sentences with pauses to repeat."
)
MARKER = "Now you will be able to listen and repeat all the sentences from the conversation. Let's go!"


def _slide(index, german, english):
    return {
        "index": index,
        "start": float(index),
        "end": float(index + 1),
        "image": f"slides/{index:04d}.png",
        "flag": "de",
        "german": german,
        "english": english,
    }


def write_conversation(root, level_dir, conversation_dir, title, lines, marker=True):
    """Write a slides.json shaped like the course OCR output and return its folder.

    `title` is a (german, english) pair, `lines` a list of (german, english) pairs.
    The dialogue is written twice around the "listen and repeat" marker, like the real videos.
    """
    texts = [("", ""), ("", INTRO), ("", ""), title, *lines]
    if marker:
        texts += [("", MARKER), *lines]
    slides = [_slide(i + 1, de, en) for i, (de, en) in enumerate(texts)]
    folder = Path(root) / level_dir / conversation_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "slides.json").write_text(
        json.dumps({"video": f"{conversation_dir}.mp4", "slides": slides}, ensure_ascii=False),
        encoding="utf-8",
    )
    return folder


GROCERY_LINES = [
    ("Hallo, Maria!", "Hello, Maria!"),
    ("Wie geht es dir heute?", "How are you today?"),
    ("Mir geht's gut, danke.", "I am fine, thank you."),
    ("Was wirst du kochen?", "What will you cook?"),
    ("Ich möchte Pasta machen.", "I want to make pasta."),
    ("Magst du Pasta?", "Do you like pasta?"),
]


@pytest.fixture
def ocr_root(tmp_path):
    """Two levels with two conversations each (level 1 deliberately lists conversation 10 before 2)."""
    root = tmp_path / "ocr"
    level1 = "1 - Level 1 - A1 - Beginner"
    write_conversation(
        root, level1, "1 -Im Lebensmittelgeschäft",
        ("Im Lebensmittelgeschäft", "At the grocery store"), GROCERY_LINES,
    )
    write_conversation(
        root, level1, "10 -Die Bibliothek besuchen", ("Die Bibliothek besuchen", "Visiting the library"),
        [("Wo sind die Bücher?", "Where are the books?"), ("Dort drüben.", "Over there.")],
    )
    write_conversation(
        root, level1, "2 -Nach dem Weg fragen", ("Nach dem Weg fragen", "Asking for directions"),
        [("Wo ist der Bahnhof?", "Where is the station?"), ("Geradeaus.", "Straight ahead.")],
    )
    level2 = "2 - Level 2 - A1 - Beginner"
    write_conversation(root, level2, "1 -Im Café", ("Im Café", "At the café"),
                       [("Was möchtest du trinken?", "What would you like to drink?"),
                        ("Einen Kaffee, bitte.", "A coffee, please.")])
    return root
