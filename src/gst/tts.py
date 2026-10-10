"""Text-to-speech backends and an on-disk cache of synthesized WAV files."""

import hashlib
import os
import subprocess
import time
import unicodedata
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class TTSError(RuntimeError):
    pass


class TTS(Protocol):
    name: str

    def synthesize(self, text: str, voice: str, out: Path) -> None: ...


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def compose_phonemes(phonemes: list[str], id_map) -> list[str]:
    """Merge a combining mark into the phoneme before it when only the merged form is known.

    espeak spells the German ich-sound as "c" + combining cedilla; the low-quality German
    voices only know the precomposed "ç", so without this "ich" loses its ç.
    """
    out: list[str] = []
    for phoneme in phonemes:
        if out and unicodedata.combining(phoneme) and phoneme not in id_map:
            merged = unicodedata.normalize("NFC", out[-1] + phoneme)
            if merged in id_map:
                out[-1] = merged
                continue
        out.append(phoneme)
    return out


class PiperTTS:
    """Local, offline speech. Voices are downloaded into `voices_dir` on first use."""

    name = "piper"

    def __init__(self, voices_dir: Path, length_scale: float = 1.0):
        self.voices_dir = Path(voices_dir)
        self.length_scale = length_scale
        self._voices = {}

    def _voice(self, name: str):
        if name not in self._voices:
            from piper import PiperVoice
            from piper.download_voices import download_voice

            model = self.voices_dir / f"{name}.onnx"
            if not model.exists():
                self.voices_dir.mkdir(parents=True, exist_ok=True)
                download_voice(name, self.voices_dir)
            voice = PiperVoice.load(model)
            phonemize, id_map = voice.phonemize, voice.config.phoneme_id_map
            voice.phonemize = lambda text: [compose_phonemes(s, id_map) for s in phonemize(text)]
            self._voices[name] = voice
        return self._voices[name]

    def synthesize(self, text: str, voice: str, out: Path) -> None:
        from piper.config import SynthesisConfig

        config = SynthesisConfig(length_scale=self.length_scale)
        with wave.open(str(out), "wb") as wav:
            self._voice(voice).synthesize_wav(text, wav, syn_config=config)


def _edge_fetch(text: str, voice: str) -> bytes:
    import edge_tts

    audio = bytearray()
    for chunk in edge_tts.Communicate(text, voice).stream_sync():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    if not audio:
        raise TTSError(f"edge-tts returned no audio for {text!r}")
    return bytes(audio)


class EdgeTTS:
    """Microsoft's neural voices via edge-tts: free, no key, but the endpoint rate-limits (HTTP 403).

    Failed requests are retried with growing pauses; `voice` is e.g. "de-DE-KillianNeural".
    """

    name = "edge"

    def __init__(
        self,
        fetch: Callable[[str, str], bytes] = _edge_fetch,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 5,
        backoff: float = 8.0,
    ):
        self.fetch = fetch
        self.sleep = sleep
        self.attempts = attempts
        self.backoff = backoff

    def synthesize(self, text: str, voice: str, out: Path) -> None:
        for attempt in range(1, self.attempts + 1):
            try:
                mp3 = self.fetch(text, voice)
                break
            except Exception as error:
                if attempt == self.attempts:
                    raise TTSError(f"edge-tts failed {attempt} times for {text!r}: {error}") from error
                self.sleep(self.backoff * attempt)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", "pipe:0", "-ac", "1", str(out)], input=mp3, check=True
        )


def _httpx_post(url: str, headers: dict, json: dict) -> bytes:
    try:
        import httpx
    except ImportError as error:
        raise TTSError("the ElevenLabs backend needs httpx: uv sync --extra elevenlabs") from error

    response = httpx.post(url, headers=headers, json=json, timeout=60)
    response.raise_for_status()
    return response.content


class ElevenLabsTTS:
    """ElevenLabs API; `voice` is an ElevenLabs voice id. Needs ELEVENLABS_API_KEY."""

    name = "elevenlabs"
    RATE = 22050

    def __init__(
        self,
        api_key: str | None = None,
        post: Callable[..., bytes] = _httpx_post,
        model_id: str = "eleven_multilingual_v2",
    ):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise TTSError("set ELEVENLABS_API_KEY to use the ElevenLabs backend")
        self.post = post
        self.model_id = model_id

    def synthesize(self, text: str, voice: str, out: Path) -> None:
        pcm = self.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_{self.RATE}",
            headers={"xi-api-key": self.api_key},
            json={"text": text, "model_id": self.model_id},
        )
        with wave.open(str(out), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.RATE)
            wav.writeframes(pcm)


class CachedTTS:
    """Synthesizes each (backend, voice, text) once; later calls reuse the WAV file."""

    def __init__(self, inner: TTS, cache_dir: Path):
        self.inner = inner
        self.cache_dir = Path(cache_dir)

    def get(self, text: str, voice: str) -> Path:
        key = hashlib.sha256(f"{self.inner.name}\0{voice}\0{text}".encode()).hexdigest()[:20]
        path = self.cache_dir / f"{key}.wav"
        if not path.exists():
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".partial.wav")
            self.inner.synthesize(text, voice, partial)
            partial.rename(path)
        return path
