"""Turn a level's drills into its practice video."""

import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from gst.cards import answer_card, question_card, title_card
from gst.drills import Drill
from gst.timeline import Segment, TimelineConfig, plan_level
from gst.tts import CachedTTS, wav_duration
from gst.video import build_audio, encode_segment, mux


@dataclass(frozen=True)
class Voices:
    question: str
    answer: str


def _card(segment: Segment, drills: list[Drill]) -> Image.Image:
    first = drills[0]
    if segment.kind == "intro":
        return title_card(f"Level {first.level}", f"{first.cefr} · {len(drills)} Sprechübungen")
    if segment.kind == "outro":
        return title_card("Gut gemacht.", f"Level {first.level} geschafft", note="BIS ZUM NÄCHSTEN MAL")
    if segment.kind == "answer":
        return answer_card(segment.drill)
    return question_card(segment.drill, countdown=segment.kind == "speak")


def _encode(image: Image.Image, segment: Segment, folder: Path) -> Path:
    """Encode once per distinct (frame, duration, kind); later renders reuse the file."""
    digest = hashlib.sha256(image.tobytes())
    digest.update(f"{segment.duration:.4f}|{segment.kind}".encode())
    path = folder / f"{digest.hexdigest()[:20]}.mp4"
    if not path.exists():
        with tempfile.TemporaryDirectory() as tmp:
            still = Path(tmp) / "card.png"
            image.save(still)
            partial = path.with_suffix(".partial.mp4")
            encode_segment(still, segment.duration, partial, countdown=segment.kind == "speak")
            partial.rename(path)
    return path


DEFAULT_TIMELINE = TimelineConfig()


def render_level(
    drills: list[Drill],
    tts: CachedTTS,
    voices: Voices,
    work_dir: Path,
    cfg: TimelineConfig = DEFAULT_TIMELINE,
) -> Path:
    items = []
    for drill in drills:
        question = tts.get(drill.question_de, voices.question)
        answer = tts.get(drill.answer_de, voices.answer)
        items.append((drill, question, wav_duration(question), answer, wav_duration(answer)))
    segments, chapters = plan_level(items, cfg)

    work_dir = Path(work_dir)
    for name in ("segments", "audio", "videos"):
        (work_dir / name).mkdir(parents=True, exist_ok=True)
    workers = max(1, (os.cpu_count() or 2) // 2)
    with ThreadPoolExecutor(workers) as pool:
        jobs = [pool.submit(_encode, _card(s, drills), s, work_dir / "segments") for s in segments]
        paths = [job.result() for job in jobs]

    name = f"level-{drills[0].level:02d}"
    audio = work_dir / "audio" / f"{name}.wav"
    build_audio([(s.audio, s.duration) for s in segments], audio)
    video = work_dir / "videos" / f"{name}.mp4"
    mux(paths, audio, chapters, video)
    return video
