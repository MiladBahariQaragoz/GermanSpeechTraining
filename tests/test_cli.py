import json

import pytest

from gst.cli import main, parse_levels
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
    assert ("Wo ist der Bahnhof?", "de_DE-kerstin-low") in fake.calls


def test_render_refuses_levels_that_fail_the_check(ocr_root, tmp_path, monkeypatch, capsys):
    folder = _drills_dir(tmp_path, [GROCERY_DRILL])
    monkeypatch.setattr("gst.cli.make_tts", lambda name, work_dir: FakeTTS())

    code = _render(ocr_root, folder, tmp_path / "work", *LENIENT)

    assert code == 1
    assert not (tmp_path / "work" / "videos" / "level-01.mp4").exists()
