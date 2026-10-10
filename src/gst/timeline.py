"""Plan a level video as a list of timed segments, before any rendering happens."""

from dataclasses import dataclass
from pathlib import Path

from gst.drills import Drill


@dataclass(frozen=True)
class TimelineConfig:
    intro: float = 3.0
    outro: float = 2.0
    question_pad: float = 0.6  # silence after the question is read
    answer_pad: float = 1.2  # silence after the answer, before the next question
    speak_factor: float = 1.5  # speaking time relative to the model answer's length
    speak_extra: float = 2.0  # thinking time on top
    speak_min: float = 5.0


@dataclass(frozen=True)
class Segment:
    kind: str  # intro | question | speak | answer | outro
    drill: Drill | None
    duration: float
    audio: Path | None


@dataclass(frozen=True)
class Chapter:
    title: str
    start: float


def plan_drill(
    drill: Drill, q_audio: Path, q_duration: float, a_audio: Path, a_duration: float, cfg: TimelineConfig
) -> list[Segment]:
    speak = max(cfg.speak_min, cfg.speak_factor * a_duration + cfg.speak_extra)
    return [
        Segment("question", drill, q_duration + cfg.question_pad, q_audio),
        Segment("speak", drill, speak, None),
        Segment("answer", drill, a_duration + cfg.answer_pad, a_audio),
    ]


def plan_level(
    items: list[tuple[Drill, Path, float, Path, float]], cfg: TimelineConfig
) -> tuple[list[Segment], list[Chapter]]:
    """`items` holds (drill, question audio, its duration, answer audio, its duration) per drill."""
    segments = [Segment("intro", None, cfg.intro, None)]
    chapters = [Chapter("Intro", 0.0)]
    start = cfg.intro
    for drill, q_audio, q_duration, a_audio, a_duration in items:
        chapters.append(Chapter(f"{drill.id} · {drill.question_de}", start))
        drill_segments = plan_drill(drill, q_audio, q_duration, a_audio, a_duration, cfg)
        segments += drill_segments
        start += sum(s.duration for s in drill_segments)
    segments.append(Segment("outro", None, cfg.outro, None))
    return segments, chapters
