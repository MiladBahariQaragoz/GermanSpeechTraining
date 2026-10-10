import pytest

from gst.drills import load_level
from gst.render import Voices, render_level
from gst.timeline import TimelineConfig
from gst.transcript import iter_conversations
from gst.tts import CachedTTS
from gst.video import probe
from tests.fakes import FakeTTS
from tests.test_cli import ROUTE_DRILL, _drills_dir
from tests.test_drills import GROCERY_DRILL, LIBRARY_DRILL

FAST = TimelineConfig(intro=0.5, outro=0.5, speak_min=0.5, speak_extra=0.0, speak_factor=0.2)


@pytest.fixture
def drills(ocr_root, tmp_path):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL, ROUTE_DRILL])
    return load_level(folder / "level-01.json", list(iter_conversations(ocr_root, levels=[1])))


def test_render_level_writes_a_video_with_a_chapter_per_drill(drills, tmp_path):
    tts = FakeTTS(seconds_per_char=0.005)
    voices = Voices("q-voice", "a-voice")

    video = render_level(drills, CachedTTS(tts, tmp_path / "tts"), voices, tmp_path / "work", FAST)

    info = probe(video)
    assert video == tmp_path / "work" / "videos" / "level-01.mp4"
    assert (info["streams"].count("video"), info["streams"].count("audio")) == (1, 1)
    assert info["chapters"] == ["Intro"] + [f"{d.id} · {d.question_de}" for d in drills]
    assert ("Wo ist der Bahnhof?", "q-voice") in tts.calls
    assert ("Der Bahnhof ist geradeaus.", "a-voice") in tts.calls


def test_rendering_again_reuses_speech_and_segments(drills, tmp_path):
    work = tmp_path / "work"
    render_level(drills, CachedTTS(FakeTTS(0.005), tmp_path / "tts"), Voices("q", "a"), work, FAST)
    segments = {p: p.stat().st_mtime_ns for p in (work / "segments").iterdir()}
    again = FakeTTS(0.005)

    render_level(drills, CachedTTS(again, tmp_path / "tts"), Voices("q", "a"), work, FAST)

    assert again.calls == []
    assert {p: p.stat().st_mtime_ns for p in (work / "segments").iterdir()} == segments
