# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

Speaking drills built from the OCR'd transcripts of the Udemy course *Master German with 800 Real-Life
Conversations*. For every course level (1–40) there are at least 40 drills; each level is rendered as a
practice video that asks a question, shows hint words, waits for the learner to answer out loud and then
plays the correct answer. The full plan and the definition of success live in `docs/plan.md`.

## Repository decisions

- `CLAUDE.md` and `docs/` are committed to this repo (decided 2026-10-10).
- Drills are **written by Claude in-session**, not by a pipeline LLM. Code does everything mechanical:
  transcript loading, the authoring digest, validation, TTS and video rendering.
- Default TTS is local Piper (free, offline). ElevenLabs is an optional backend.
- Only A1 (levels 1–10) is OCR'd so far. Other levels need `_slide_ocr/slide_ocr.py` first.

## Paths

- `GST_OCR_ROOT` — OCR output, default
  `/run/media/sudo/Vesno & Graphic/shadow/Udemy - Master German with 800 Real-Life Conversations 2025-5/_slide_ocr/output`
- `GST_WORK_DIR` — TTS cache, cards, segments and final MP4s, default `<course>/_speaking_drills`.
  Never commit audio or video.
- `data/drills/level-NN.json` — authored drills (source of truth, committed).

## Commands

```bash
uv run pytest                 # tests
uv run ruff check .           # lint
uv run gst digest --level 1   # numbered transcript digest for authoring
uv run gst check --levels 1-10
uv run gst render --levels 1-10
```

Run `uv run ruff check . && uv run pytest` before every commit.

## Authoring a level

1. `uv run gst digest --level N` and read the whole digest.
2. Write `data/drills/level-NN.json` with at least 40 drills, about 2 per conversation and at most 4.
   Pick the exchanges most relevant to each conversation's topic. Phrase questions to the learner so
   they can be answered without seeing the dialogue. Build the model answer from the cited
   `source_lines`, fixing obvious OCR errors. Hints are 2–5 words taken from the answer.
3. `uv run gst check --levels N` must pass, then commit the level on its own.
