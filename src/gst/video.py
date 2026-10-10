"""ffmpeg plumbing: silent still-image segments, one sample-exact audio track, final mux.

Audio is assembled separately from the video segments so that ~180 concatenated segments
cannot drift out of sync (per-segment AAC priming would add up to seconds).
"""

import json
import subprocess
import tempfile
import wave
from pathlib import Path

from gst.cards import BAR, BAR_FILL, RULE
from gst.timeline import Chapter

RATE = 44100


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _hex(colour: str) -> str:
    return "0x" + colour.lstrip("#")


def encode_segment(image: Path, duration: float, out: Path, countdown: bool = False, fps: int = 30) -> None:
    """A silent H.264 clip of `image`; with `countdown`, the bar empties over the clip.

    `fps` must match the timeline's, which rounds every segment to whole frames.
    """
    frames = round(duration * fps)
    if countdown:
        x, y, width, height = BAR
        graph = (
            f"color=c={_hex(RULE)}:s={width}x{height}:r={fps}[track];"
            f"color=c={_hex(BAR_FILL)}:s={width}x{height}:r={fps}[fill];"
            f"[track][fill]overlay=x='-{width}*t/{frames / fps}':y=0[bar];"
            f"[0:v][bar]overlay=x={x}:y={y},format=yuv420p[v]"
        )
        video = ["-filter_complex", graph, "-map", "[v]"]
    else:
        video = ["-vf", "format=yuv420p"]
    _ffmpeg(
        "-loop", "1", "-framerate", str(fps), "-i", str(image), *video,
        "-frames:v", str(frames), "-r", str(fps),
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "20", "-an", str(out),
    )


def _pcm(clip: Path) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
        capture_output=True, check=True,
    )
    return result.stdout


def build_audio(parts: list[tuple[Path | None, float]], out: Path) -> None:
    """One mono track: each (clip or silence, slot length) fills exactly its slot."""
    with wave.open(str(out), "wb") as track:
        track.setnchannels(1)
        track.setsampwidth(2)
        track.setframerate(RATE)
        for clip, seconds in parts:
            size = round(seconds * RATE) * 2
            data = _pcm(clip)[:size] if clip else b""
            track.writeframes(data + b"\x00" * (size - len(data)))


def _escape(text: str) -> str:
    for char in "\\=;#\n":
        text = text.replace(char, "\\" + char)
    return text


def _chapters_metadata(chapters: list[Chapter], total: float) -> str:
    lines = [";FFMETADATA1"]
    ends = [c.start for c in chapters[1:]] + [total]
    for chapter, end in zip(chapters, ends, strict=True):
        lines += [
            "[CHAPTER]", "TIMEBASE=1/1000",
            f"START={round(chapter.start * 1000)}", f"END={round(end * 1000)}",
            f"title={_escape(chapter.title)}",
        ]
    return "\n".join(lines) + "\n"


def mux(segments: list[Path], audio: Path, chapters: list[Chapter], out: Path) -> None:
    with wave.open(str(audio), "rb") as wav:
        total = wav.getnframes() / wav.getframerate()
    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp) / "segments.txt"
        quoted = (str(Path(s).resolve()).replace("'", "'\\''") for s in segments)
        listing.write_text("".join(f"file '{q}'\n" for q in quoted), encoding="utf-8")
        metadata = Path(tmp) / "chapters.txt"
        metadata.write_text(_chapters_metadata(chapters, total), encoding="utf-8")
        _ffmpeg(
            "-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(audio), "-i", str(metadata),
            "-map", "0:v", "-map", "1:a", "-map_metadata", "2", "-map_chapters", "2",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
        )


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,r_frame_rate:chapter_tags=title",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    video = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)
    num, _, den = video["r_frame_rate"].partition("/") if video else ("0", "", "1")
    return {
        "fps": int(num) / int(den or 1),
        "duration": float(info["format"]["duration"]),
        "streams": [s["codec_type"] for s in info.get("streams", [])],
        "chapters": [c.get("tags", {}).get("title") for c in info.get("chapters", [])],
    }
