import json

import pytest

from gst.cli import main, parse_levels
from gst.shortlist import JudgeError
from gst.tts import TTSError
from tests.fakes import FakeTTS
from tests.test_drills import GROCERY_DRILL, LIBRARY_DRILL

ROUTE_DRILL = {
    "conversation": 2,
    "question_de": "Wo ist der Bahnhof?",
    "question_en": "Where is the station?",
    "answer_de": "Der Bahnhof ist geradeaus.",
    "answer_en": "The station is straight ahead.",
    "hints": ["Bahnhof", "geradeaus"],
    "source_lines": [1, 2],
}
LENIENT = ["--min-drills", "3", "--min-conversations", "3"]


def test_parse_levels_accepts_ranges_and_lists():
    assert parse_levels("1-3,7") == [1, 2, 3, 7]
    assert parse_levels("5") == [5]


@pytest.mark.parametrize("text", ["a", "3-1", "", "0"])
def test_parse_levels_rejects_bad_input(text):
    with pytest.raises(ValueError):
        parse_levels(text)


def test_digest_prints_the_level(ocr_root, capsys):
    assert main(["digest", "--level", "1", "--ocr-root", str(ocr_root)]) == 0

    assert "## C01 · Im Lebensmittelgeschäft" in capsys.readouterr().out


def _drills_dir(tmp_path, drills):
    folder = tmp_path / "drills"
    folder.mkdir()
    (folder / "level-01.json").write_text(json.dumps({"level": 1, "drills": drills}, ensure_ascii=False))
    return folder


def _check(ocr_root, folder, *extra):
    return main(["check", "--levels", "1", "--ocr-root", str(ocr_root), "--drills-dir", str(folder), *extra])


def test_check_passes_and_writes_markdown_view(ocr_root, tmp_path, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL, ROUTE_DRILL])

    code = _check(ocr_root, folder, *LENIENT)

    assert code == 0
    assert "level 1: OK (3 drills)" in capsys.readouterr().out
    assert "Wo ist der Bahnhof?" in (folder / "level-01.md").read_text()


def test_check_fails_with_problems_listed(ocr_root, tmp_path, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL])

    code = _check(ocr_root, folder, *LENIENT)

    assert code == 1
    assert "level 1: 2 drills, need at least 3" in capsys.readouterr().out
    assert not (folder / "level-01.md").exists()


def test_check_reports_missing_drill_file(ocr_root, tmp_path, capsys):
    code = _check(ocr_root, tmp_path)

    assert code == 1
    assert "level-01.json not found" in capsys.readouterr().out


def _render(ocr_root, folder, work, *extra):
    return main([
        "render", "--levels", "1", "--ocr-root", str(ocr_root), "--drills-dir", str(folder),
        "--work-dir", str(work), *extra,
    ])


def test_render_builds_a_video_per_passing_level(ocr_root, tmp_path, monkeypatch, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL, ROUTE_DRILL])
    fake = FakeTTS(seconds_per_char=0.005)
    monkeypatch.setattr("gst.cli.make_tts", lambda name, work_dir: fake)

    code = _render(ocr_root, folder, tmp_path / "work", *LENIENT)

    assert code == 0
    assert (tmp_path / "work" / "videos" / "level-01.mp4").exists()
    assert "level-01.mp4" in capsys.readouterr().out
    assert ("Wo ist der Bahnhof?", "de-DE-FlorianMultilingualNeural") in fake.calls
    assert ("Der Bahnhof ist geradeaus.", "de-DE-KillianNeural") in fake.calls


def test_render_refuses_levels_that_fail_the_check(ocr_root, tmp_path, monkeypatch, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL])
    monkeypatch.setattr("gst.cli.make_tts", lambda name, work_dir: FakeTTS())

    code = _render(ocr_root, folder, tmp_path / "work", *LENIENT)

    assert code == 1
    assert not (tmp_path / "work" / "videos" / "level-01.mp4").exists()


def test_render_can_still_use_piper_voices(ocr_root, tmp_path, monkeypatch):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL, ROUTE_DRILL])
    fake = FakeTTS(seconds_per_char=0.005)
    monkeypatch.setattr("gst.cli.make_tts", lambda name, work_dir: fake)

    assert _render(ocr_root, folder, tmp_path / "work", "--tts", "piper", *LENIENT) == 0

    assert ("Wo ist der Bahnhof?", "de_DE-kerstin-low") in fake.calls


def test_digest_reports_a_level_without_conversations(ocr_root, capsys):
    assert main(["digest", "--level", "5", "--ocr-root", str(ocr_root)]) == 1

    assert "no conversations for level 5" in capsys.readouterr().out


def test_check_reports_a_level_without_conversations(ocr_root, tmp_path, capsys):
    folder = tmp_path / "drills"
    folder.mkdir()
    (folder / "level-05.json").write_text(json.dumps({"level": 5, "drills": [GROCERY_DRILL]}))

    code = main(["check", "--levels", "5", "--ocr-root", str(ocr_root), "--drills-dir", str(folder)])

    assert code == 1
    assert "no conversations for level 5" in capsys.readouterr().out


class BrokenTTS(FakeTTS):
    def synthesize(self, text, voice, out):
        raise TTSError("edge-tts failed 8 times for 'Hallo': 403")


def test_render_reports_speech_failures_without_a_traceback(ocr_root, tmp_path, monkeypatch, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL, ROUTE_DRILL])
    monkeypatch.setattr("gst.cli.make_tts", lambda name, work_dir: BrokenTTS())

    code = _render(ocr_root, folder, tmp_path / "work", *LENIENT)

    assert code == 1
    assert "level 1: edge-tts failed 8 times" in capsys.readouterr().out


def test_render_reports_a_missing_elevenlabs_key(ocr_root, tmp_path, monkeypatch, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL, LIBRARY_DRILL, ROUTE_DRILL])
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    code = _render(ocr_root, folder, tmp_path / "work", "--tts", "elevenlabs",
                   "--question-voice", "q", "--answer-voice", "a", *LENIENT)

    assert code == 1
    assert "ELEVENLABS_API_KEY" in capsys.readouterr().out


class ScriptedJudge:
    name = "scripted"

    def __init__(self, error=None):
        self.error = error

    def ask(self, state, questions):
        if self.error:
            raise self.error
        return {"relevance": 3.0, "speaking_value": 2.0}


def _shortlist(ocr_root, tmp_path, *extra):
    return main(["shortlist", "--level", "1", "--ocr-root", str(ocr_root),
                 "--work-dir", str(tmp_path), *extra])


def test_shortlist_prints_the_ranked_exchanges(ocr_root, tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_make_judge(model, work_dir):
        seen.update(model=model, work_dir=work_dir)
        return ScriptedJudge()

    monkeypatch.setattr("gst.cli.make_judge", fake_make_judge)

    assert _shortlist(ocr_root, tmp_path, "--model", "jev-test") == 0

    out = capsys.readouterr().out
    assert "[0.83] 04 ? Was wirst du kochen? | What will you cook?" in out
    assert seen == {"model": "jev-test", "work_dir": tmp_path}


def test_shortlist_reports_judge_failures_without_a_traceback(ocr_root, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("gst.cli.make_judge",
                        lambda model, work_dir: ScriptedJudge(JudgeError("No API key was provided.")))

    assert _shortlist(ocr_root, tmp_path) == 1
    assert "level 1: No API key was provided." in capsys.readouterr().out
