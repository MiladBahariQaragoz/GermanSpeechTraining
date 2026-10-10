"""Word-level helpers for comparing German sentences."""

import re

_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")

# Pronouns, articles, conjunctions, prepositions and auxiliaries: words that carry no topic.
STOP_WORDS = frozenset(
    """
    ich du er sie es wir ihr mich dich sich uns euch mir dir ihm ihn ihnen
    mein meine meinen meinem meiner dein deine deinen deinem deiner sein seine ihre unser unsere
    der die das den dem des ein eine einen einem einer eines kein keine
    und oder aber doch denn sondern wenn weil dass ob als wie
    in im ins an am auf aus bei beim mit nach von vom zu zum zur für um über unter vor hinter neben
    bin bist ist sind seid war waren habe hast hat haben hatte werde wirst wird werden
    ja nein nicht auch so sehr noch schon dann da hier dort mal nur
    """.split()
)


def words(text: str) -> list[str]:
    return [w.replace("’", "'") for w in _WORD.findall(text.lower())]


def content_words(text: str) -> list[str]:
    return [w for w in words(text) if w not in STOP_WORDS]


def normalise(text: str) -> str:
    return " ".join(words(text))
