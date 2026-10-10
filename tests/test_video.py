import subprocess

import pytest
from PIL import Image

from gst.cards import BAR, question_card
from gst.timeline import Chapter
from gst.tts import wav_duration
from gst.video import build_audio, encode_segment, mux, probe
from tests.fakes import write_silence
from tests.test_timeline import drill


@pytest.fixture
def still(tmp_path):
    path = tmp_path / "card.png"
    question_card(drill(), countdown=True).save(path)
    return path


def _frame(video, seconds, out):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(seconds), "-i", str(video), "-frames:v", "1", str(out)],
        check=True,
    )
    return Image.open(out).convert("L")


def _bar_fill(image):
    x, y, width, height = BAR
    return sum(1 for px in range(x, x + width) if image.getpixel((px, y + height // 2)) < 100)


def test_segment_is_a_silent_video_of_the_requested_length(still, tmp_path):
    out = tmp_path / "segment.mp4"

    encode_segment(still, 1.0, out)

    info = probe(out)
    assert info["duration"] == pytest.approx(1.0, abs=0.05)
    assert info["streams"] == ["video"]


def test_countdown_bar_shrinks_over_the_segment(still, tmp_path):
    out = tmp_path / "speak.mp4"

    encode_segment(still, 2.0, out, countdown=True)

    early = _bar_fill(_frame(out, 0.2, tmp_path / "early.png"))
    late = _bar_fill(_frame(out, 1.8, tmp_path / "late.png"))
    assert early > late > 0


def test_build_audio_places_clips_in_their_slots_and_pads_with_silence(tmp_path):
    clip = tmp_path / "clip.wav"
    write_silence(clip, 0.5, rate=22050)
    out = tmp_path / "track.wav"

    build_audio([(clip, 1.0), (None, 2.0), (clip, 0.5)], out)

    assert wav_duration(out) == pytest.approx(3.5, abs=0.001)


def test_mux_joins_segments_with_audio_and_chapters(still, tmp_path):
    segments = []
    for n in range(3):
        segments.append(tmp_path / f"s{n}.mp4")
        encode_segment(still, 1.0, segments[-1])
    audio = tmp_path / "track.wav"
    build_audio([(None, 3.0)], audio)
    out = tmp_path / "level.mp4"

    mux(segments, audio, [Chapter("Intro", 0.0), Chapter("L01-D01 · Frage?", 1.0)], out)

    info = probe(out)
    assert info["duration"] == pytest.approx(3.0, abs=0.1)
    assert (info["streams"].count("video"), info["streams"].count("audio")) == (1, 1)
    assert info["chapters"] == ["Intro", "L01-D01 · Frage?"]
