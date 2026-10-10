import wave
from pathlib import Path

SAMPLE_RATE = 22050


def write_silence(path: Path, seconds: float, rate: int = SAMPLE_RATE) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * round(seconds * rate))


class FakeTTS:
    """Writes silence whose length grows with the text, and counts calls."""

    name = "fake"

    def __init__(self, seconds_per_char: float = 0.05):
        self.seconds_per_char = seconds_per_char
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, voice: str, out: Path) -> None:
        self.calls.append((text, voice))
        write_silence(out, max(0.2, len(text) * self.seconds_per_char))
