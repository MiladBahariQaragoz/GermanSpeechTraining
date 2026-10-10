import pytest

from gst.config import WORK_DIR
from gst.tts import CachedTTS, ElevenLabsTTS, PiperTTS, TTSError, wav_duration
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


@pytest.mark.slow
def test_piper_speaks_german(tmp_path):
    voices = WORK_DIR / "voices"
    if not (voices / "de_DE-thorsten-high.onnx").exists():
        pytest.skip("Piper voice not downloaded; run `gst render` once first")
    out = tmp_path / "hallo.wav"

    PiperTTS(voices).synthesize("Hallo, wie geht's?", "de_DE-thorsten-high", out)

    assert wav_duration(out) > 0.5
