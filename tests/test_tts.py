import subprocess

import pytest

from gst.config import WORK_DIR
from gst.tts import (
    CachedTTS,
    EdgeTTS,
    ElevenLabsTTS,
    PiperTTS,
    TTSError,
    _edge_fetch,
    compose_phonemes,
    wav_duration,
)
from tests.fakes import FakeTTS, write_silence


def test_wav_duration_reads_frames_and_rate(tmp_path):
    path = tmp_path / "silence.wav"
    write_silence(path, 1.5)

    assert wav_duration(path) == pytest.approx(1.5)


def test_cached_tts_synthesizes_each_text_once(tmp_path):
    inner = FakeTTS()
    tts = CachedTTS(inner, tmp_path)

    first = tts.get("Hallo!", "voice-a")
    second = tts.get("Hallo!", "voice-a")

    assert first == second
    assert first.exists()
    assert inner.calls == [("Hallo!", "voice-a")]


def test_cached_tts_keeps_voices_apart(tmp_path):
    tts = CachedTTS(FakeTTS(), tmp_path)

    assert tts.get("Hallo!", "voice-a") != tts.get("Hallo!", "voice-b")


class FakePost:
    def __init__(self, body: bytes):
        self.body = body
        self.requests = []

    def __call__(self, url, headers, json):
        self.requests.append((url, headers, json))
        return self.body


def test_elevenlabs_posts_text_and_writes_wav(tmp_path):
    one_second_of_pcm = b"\x00\x00" * 22050
    post = FakePost(one_second_of_pcm)
    out = tmp_path / "out.wav"

    ElevenLabsTTS(api_key="secret", post=post).synthesize("Guten Tag!", "voice123", out)

    url, headers, body = post.requests[0]
    assert url.startswith("https://api.elevenlabs.io/v1/text-to-speech/voice123")
    assert "output_format=pcm_22050" in url
    assert headers["xi-api-key"] == "secret"
    assert body["text"] == "Guten Tag!"
    assert wav_duration(out) == pytest.approx(1.0)


def test_elevenlabs_needs_an_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    with pytest.raises(TTSError, match="ELEVENLABS_API_KEY"):
        ElevenLabsTTS()


CEDILLA = "\u0327"


def test_compose_phonemes_merges_marks_the_voice_does_not_know():
    id_map = {"ɪ": [1], "c": [2], "ç": [3], " ": [4]}

    assert compose_phonemes(["ɪ", "c", CEDILLA, " "], id_map) == ["ɪ", "ç", " "]


def test_compose_phonemes_keeps_marks_the_voice_knows():
    id_map = {"ɪ": [1], "c": [2], "ç": [3], CEDILLA: [5]}

    assert compose_phonemes(["ɪ", "c", CEDILLA], id_map) == ["ɪ", "c", CEDILLA]


@pytest.mark.slow
def test_low_quality_piper_voice_keeps_the_ich_sound(tmp_path, caplog):
    voices = WORK_DIR / "voices"
    if not (voices / "de_DE-kerstin-low.onnx").exists():
        pytest.skip("Piper voice not downloaded")

    PiperTTS(voices).synthesize("Ich möchte nicht.", "de_DE-kerstin-low", tmp_path / "ich.wav")

    assert "Missing phoneme" not in caplog.text


@pytest.mark.slow
def test_piper_speaks_german(tmp_path):
    voices = WORK_DIR / "voices"
    if not (voices / "de_DE-thorsten-high.onnx").exists():
        pytest.skip("Piper voice not downloaded; run `gst render` once first")
    out = tmp_path / "hallo.wav"

    PiperTTS(voices).synthesize("Hallo, wie geht's?", "de_DE-thorsten-high", out)

    assert wav_duration(out) > 0.5


def _mp3(tmp_path, seconds):
    path = tmp_path / "clip.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds),
         "-c:a", "libmp3lame", str(path)],
        check=True,
    )
    return path.read_bytes()


class FlakyFetch:
    """Fails `failures` times, then returns `audio`."""

    def __init__(self, audio: bytes, failures: int = 0):
        self.audio = audio
        self.failures = failures
        self.calls = []

    def __call__(self, text, voice):
        self.calls.append((text, voice))
        if len(self.calls) <= self.failures:
            raise ConnectionError("403, message='Invalid response status'")
        return self.audio


def test_edge_converts_the_mp3_it_fetches_to_wav(tmp_path):
    fetch = FlakyFetch(_mp3(tmp_path, 1.0))
    out = tmp_path / "out.wav"

    EdgeTTS(fetch=fetch, sleep=lambda s: None).synthesize("Hallo!", "de-DE-KillianNeural", out)

    assert fetch.calls == [("Hallo!", "de-DE-KillianNeural")]
    assert wav_duration(out) == pytest.approx(1.0, abs=0.1)


def test_edge_retries_with_growing_pauses_when_the_service_refuses(tmp_path):
    fetch = FlakyFetch(_mp3(tmp_path, 0.5), failures=2)
    pauses = []

    EdgeTTS(fetch=fetch, sleep=pauses.append, backoff=2.0).synthesize("Hallo!", "v", tmp_path / "out.wav")

    assert len(fetch.calls) == 3
    assert pauses == [2, 4]


def test_edge_defaults_tolerate_frequent_refusals():
    edge = EdgeTTS(fetch=lambda text, voice: b"", sleep=lambda s: None)

    assert edge.attempts >= 8
    assert edge.backoff <= 2.0


def test_edge_gives_up_after_the_last_attempt(tmp_path):
    fetch = FlakyFetch(b"", failures=99)

    with pytest.raises(TTSError, match="403"):
        EdgeTTS(fetch=fetch, sleep=lambda s: None, attempts=3).synthesize("Hallo!", "v", tmp_path / "out.wav")

    assert len(fetch.calls) == 3


@pytest.mark.network
def test_edge_speaks_german_for_real(tmp_path):
    out = tmp_path / "hallo.wav"

    EdgeTTS().synthesize("Hallo, wie geht's?", "de-DE-KillianNeural", out)

    assert wav_duration(out) > 0.5


class RefusingCommunicate:
    """Stands in for edge_tts.Communicate when the service answers 403."""

    def __init__(self, text, voice):
        pass

    async def stream(self):
        raise ConnectionError("403, message='Invalid response status'")
        yield  # pragma: no cover - makes this an async generator


class SpeakingCommunicate:
    def __init__(self, text, voice):
        pass

    async def stream(self):
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"abc"}
        yield {"type": "audio", "data": b"def"}


def test_edge_fetch_raises_instead_of_hanging_when_the_service_refuses():
    with pytest.raises(ConnectionError, match="403"):
        _edge_fetch("Hallo!", "v", communicate=RefusingCommunicate)


def test_edge_fetch_joins_the_audio_chunks():
    assert _edge_fetch("Hallo!", "v", communicate=SpeakingCommunicate) == b"abcdef"
