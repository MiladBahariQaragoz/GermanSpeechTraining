---
title: German speaking drills from course transcripts
date: 2026-10-10
domain: content
type: enhancement
priority: high
breaking: false
db-migration: false
rls-affecting: false
output-quality-required: true
slice: null
parent-spec: none
touched-files: [src/gst/**, tests/**, data/drills/**, docs/**, pyproject.toml, README.md, CLAUDE.md, .gitignore]
trigger-tasks-touched: []
shared-modules-touched: []
---

# German Speaking Drills — Implementation Plan

> **For agentic workers:** Execute task-by-task with TDD (red → green → refactor → commit → push). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the OCR'd transcripts of *Master German with 800 Real-Life Conversations* into at least 40 speaking drills per course level, and render each level as a practice video: the video asks a question, shows hint words, waits for you to answer out loud, then plays the correct answer.

**Architecture:** `load transcripts → digest per level → drills authored by Claude (frontier LLM, in-session) → validate → TTS → render video`. Python code does everything mechanical: it turns transcripts into a compact numbered digest, validates the authored drill files against the success criteria, synthesises speech and renders the videos. The creative step — picking the most relevant parts of each conversation and writing the questions, hints and model answers — is done by Claude directly into `data/drills/level-NN.json`, grounded in numbered source lines. TTS backends (Piper / ElevenLabs) sit behind one interface, and audio is cached on disk so re-runs are free and incremental.

**Tech Stack:** Python 3.12 (uv), pytest, ruff, Piper TTS (local, offline), httpx (optional ElevenLabs backend), Pillow (cards), ffmpeg (video).

**Issue:** GitHub issue gate skipped — `gh` token is invalid on this machine. Create the tracking issue once `gh auth login` is done.

---

## 1. Context — what the input data looks like

- Input root: `<course>/_slide_ocr/output/<level folder>/<conversation folder>/slides.json`
  (`<course>` = `/run/media/sudo/Vesno & Graphic/shadow/Udemy - Master German with 800 Real-Life Conversations 2025-5`).
- Level folder: `1 - Level 1 - A1 - Beginner` → course level `1`, CEFR `A1`.
  Conversation folder: `1 -Im Lebensmittelgeschäft` → number `1`, topic `Im Lebensmittelgeschäft`.
- `slides.json` = `{"video": str, "slides": [{index, start, end, image, flag, german, english}]}`.
- Every video has the same shape (verified on all 200 A1 files):
  1. EN-only intro slide ("First, you will listen to the dialogue naturally…").
  2. Title slide: `german == topic`, `english == topic translation`.
  3. **Pass 1:** the dialogue, one DE/EN sentence per slide.
  4. EN-only marker slide containing *"listen and repeat"*.
  5. **Pass 2:** the identical dialogue again (pass 1 == pass 2 in 200/200 files).
- Speakers are **not** labelled; one utterance can span several slides.
- A1 stats (levels 1–10, 200 conversations): 53–111 lines per conversation (median 83),
  8–28 lines ending in `?` per conversation (median 16), 3,276 question lines total.
- Only A1 (levels 1–10) is OCR'd. Levels 11–40 need `slide_ocr.py` first (out of scope for now —
  the pipeline must pick them up later with no code change).

## 2. Decisions

| Topic | Decision | Why |
|---|---|---|
| Level unit | **Course levels 1–40**, ≥40 drills each (A1 = levels 1–10 now) | User choice. 20 conversations/level → ~2 drills per conversation. |
| Scope now | A1 only (levels 1–10, 200 conversations) | User choice. |
| Question writing | **Claude writes the drills in-session** (no Jev, no local LLM) | User decision 2026-10-10: question writing needs a frontier LLM anyway, so the separate "decision maker" stage is dropped. Claude reads each level's digest, picks the most topic-relevant exchanges and writes ≥40 drills per level. |
| Grounding | Every drill cites `source_lines` (line numbers in its conversation); the model answer reuses the course's own sentences wherever they fit | Practice stays tied to what the course taught; the validator checks the citation and the word overlap. |
| TTS | **Piper** (local, offline, unlimited) default; **ElevenLabs** optional backend | Tested 2026-10-10: Piper `de_DE-thorsten-high` works. edge-tts returns HTTP 403. ElevenLabs free tier = 10k chars/month ≈ 1–2 levels/month — too small as default. |
| Video unit | One MP4 per course level, one chapter per drill | One practice session = one level (~12 min). |
| Repo | `github.com/MiladBahariQaragoz/GermanSpeechTraining`, cloned to `~/Github/GermanSpeechTraining` | User choice. Code + drill JSON in git; MP4/WAV/cache on the external drive, gitignored. |
| Docs | `CLAUDE.md` and `docs/` committed | User choice. |

## 3. Definition of Success

The project is done for a set of levels when **all** of these hold. Items marked *(auto)* are
enforced by tests or by `gst check`; items marked *(human)* are judged by the user.

**Content**
1. *(auto)* For every processed course level `N`, `data/drills/level-NN.json` exists and holds **≥ 40 drills**.
2. *(auto)* Each drill has `conversation`, `question_de`, `question_en`, `answer_de`, `answer_en`,
   `hints` (2–5 words) and `source_lines` (≥ 1 valid line number of that conversation).
3. *(auto)* **Grounded:** every hint word occurs in `answer_de`, and at least half of the content words of
   `answer_de` occur in the cited source lines.
4. *(auto)* **Spread:** no conversation contributes more than 4 drills to its level; at least 15 of the
   level's 20 conversations are represented; no duplicate questions within a level.
5. *(human)* **Relevance:** in a random sample of 20 drills from a level, at least 18 are a natural
   question you could be asked in that situation, answerable without seeing the dialogue, on the
   conversation's topic, with a correct, level-appropriate model answer.

**Video**
6. *(auto)* `level-NN.mp4` exists for every processed level, has one video and one audio stream, and its
   duration matches the planned timeline within ±1 s.
7. *(auto)* One chapter per drill (plus intro), so you can skip to any question.
8. *(human)* Per drill you **hear** the question and **see** the German question, its English
   translation and the hint words; then a visible countdown gives you time to speak
   (≥ 1.5 × answer length + 2 s, at least 5 s); then you **hear and see** the correct answer.
9. *(human)* German pronunciation is clear and understandable at normal playback speed.

**Engineering**
10. *(auto)* `uv run pytest` and `uv run ruff check .` pass on every commit.
11. *(auto)* Rendering costs **$0** by default (local Piper TTS) and needs no API key.
12. *(auto)* Re-rendering is incremental: a second run with unchanged drills makes **zero** TTS calls.
13. *(auto)* Adding levels 11–40 later needs only `slide_ocr.py`, a Claude authoring session per level,
    and `gst render --levels 11-40` — no code change.
14. Every commit is pushed to GitHub on a feature branch; work reaches `main` via pull request.

## 4. Drill and video format

**Drill** = a question you could be asked in the conversation's situation, the hint words you need, and a
model answer built from the course's own sentences. Example (level 1, *Im Lebensmittelgeschäft*):

```json
{
  "conversation": 1,
  "question_de": "Was möchtest du heute Abend kochen?",
  "question_en": "What would you like to cook tonight?",
  "answer_de": "Ich möchte Pasta machen.",
  "answer_en": "I want to make pasta.",
  "hints": ["möchte", "Pasta", "machen"],
  "source_lines": [9, 10]
}
```

`level`, `cefr`, `id` (`L01-D07`), `topic_de` and `topic_en` are filled in by the loader from the folder
names, so they cannot drift from the source.

**Per-drill timeline** (all durations configurable in `gst.timeline.TimelineConfig`):

| Segment | Screen | Audio | Duration |
|---|---|---|---|
| `question` | topic, German question (large), English translation (small), hint chips | question TTS (voice A) | `q_audio + 0.6 s` |
| `speak` | same card + shrinking countdown bar | silence | `max(5.0, 1.5 × a_audio + 2.0)` |
| `answer` | question (small), German answer (large), English answer | answer TTS (voice B) | `a_audio + 1.2 s` |

**Per-level video** = intro card (`Level 1 · A1 — 40 speaking drills`, 3 s) + drills in conversation order
+ outro card (2 s). 1280×720, 30 fps, H.264 + AAC. Expected length ≈ 40 × 17 s ≈ 11–12 min.

## 5. File structure

```
GermanSpeechTraining/
├── pyproject.toml            # uv project, deps, ruff + pytest config, `gst` entry point
├── README.md                 # setup + usage
├── CLAUDE.md                 # guidance for Claude Code (incl. how to author a level)
├── docs/plan.md              # this file
├── data/drills/              # committed: level-NN.json (authored) + level-NN.md (generated view)
├── src/gst/
│   ├── transcript.py         # folder-name parsing, slides.json → Conversation
│   ├── digest.py             # compact numbered per-level transcript for authoring
│   ├── text.py               # tokenising, stop words, content words
│   ├── drills.py             # Drill model, load/save, Markdown view
│   ├── check.py              # success-criteria validator (1–4)
│   ├── tts.py                # TTS protocol, PiperTTS, ElevenLabsTTS, audio cache
│   ├── timeline.py           # pure segment/chapter planning
│   ├── cards.py              # Pillow card rendering
│   ├── video.py              # ffmpeg segment encode + concat + chapters
│   └── cli.py                # `gst digest|check|render`
└── tests/
    ├── fixtures/ocr/…        # tiny fake OCR tree (2 levels × 2 conversations)
    └── test_<module>.py      # one test file per module
```

Runtime paths (env var → default):
- `GST_OCR_ROOT` → `<course>/_slide_ocr/output`
- `GST_WORK_DIR` → `<course>/_speaking_drills` (TTS cache, cards, segments, final MP4s)

## 6. Tasks

Each code task: write the failing tests listed → run (`uv run pytest tests/test_<module>.py -v`, expect FAIL)
→ minimal implementation → run (expect PASS) → `uv run ruff check . && uv run pytest` → commit → push.

Order puts a **level-1 video in front of the user early** (Task 11) before authoring levels 2–10, so format
feedback lands before the bulk of the writing.

### Task 0: Scaffold
**Files:** `pyproject.toml`, `.gitignore`, `README.md`, `CLAUDE.md`, `src/gst/__init__.py`, `tests/__init__.py`
- [ ] `uv init --package --python 3.12`; deps `pillow`, `piper-tts`; optional extra `elevenlabs = ["httpx"]`; dev deps `pytest`, `ruff`.
- [ ] `.gitignore`: `node_modules/`, `.env`, `.env.local`, `.env.*.local`, `dist/`, `build/`, `.next/`, `.DS_Store`, `.venv/`, `__pycache__/`, `*.wav`, `*.mp4`, `.cache/`.
- [ ] `uv run pytest` and `uv run ruff check .` run clean. Commit `chore: scaffold uv project`.

### Task 1: Transcript loader — `src/gst/transcript.py`
Types: `Line(number:int, de:str, en:str)` (1-based), `Conversation(level, cefr, number, topic_de, topic_en, lines, path)`.
Functions: `parse_level_dir(name)`, `parse_conversation_dir(name)`, `load_conversation(dir)`, `iter_conversations(root, levels)`.

Tests (`tests/test_transcript.py`):
- [ ] `parse_level_dir("1 - Level 1 - A1 - Beginner") == (1, "A1")`; `"29 - Level 29 - B2 - Intermediate"` → `(29, "B2")`; garbage → `ValueError`.
- [ ] `parse_conversation_dir("1 -Im Lebensmittelgeschäft") == (1, "Im Lebensmittelgeschäft")`; `"12 - Kleidung einkaufen"` → `(12, "Kleidung einkaufen")`.
- [ ] Fixture with intro, title, 6 dialogue lines, marker, pass 2 → exactly the 6 pass-1 lines, numbered 1..6.
- [ ] `topic_en` comes from the title slide; the title slide is not in `lines`.
- [ ] No marker slide → all DE lines after the title are kept.
- [ ] `iter_conversations(root, levels=[2])` yields only level 2, natural-sorted (2 before 10).

### Task 2: Text helpers — `src/gst/text.py`
Functions: `normalise(text)`, `words(text)`, `content_words(text)` (drops German stop words + punctuation).
Tests (`tests/test_text.py`):
- [ ] `words("Ich möchte Pasta machen.") == ["ich", "möchte", "pasta", "machen"]`; handles `geht's`, `z. B.`, `–`.
- [ ] `content_words("Ich möchte Pasta machen.") == ["möchte", "pasta", "machen"]`.
- [ ] `normalise("Was wirst du kochen?") == normalise("was wirst du kochen")`.

### Task 3: Digest — `src/gst/digest.py`
`level_digest(conversations) -> str`: per conversation a header `## C01 · Im Lebensmittelgeschäft — At the grocery store`,
then one line per sentence: `09 ? Was wirst du kochen? | What will you cook?` (`?` marks question lines).
Tests (`tests/test_digest.py`):
- [ ] Header and numbering match the fixture; question lines carry the `?` marker; EN after `|`.
- [ ] Line numbers in the digest equal `Line.number` (so `source_lines` can be checked).

### Task 4: Drill model — `src/gst/drills.py`
`Drill` dataclass (authored fields from §4 + derived `id`, `level`, `cefr`, `topic_de`, `topic_en`).
`load_level(path, conversations) -> list[Drill]`, `write_markdown(path, drills)`.
Tests (`tests/test_drills.py`):
- [ ] Loading fills `id` (`L01-D01`…), `level`, `cefr`, `topic_de`, `topic_en` from the conversation.
- [ ] Unknown conversation number → `DrillError` naming the drill.
- [ ] Missing required field → `DrillError` naming the field.
- [ ] Markdown view lists every question, answer and hint line; UTF-8 umlauts preserved.

### Task 5: Validator — `src/gst/check.py`
`check_level(drills, conversations, min_drills=40, cap=4, min_conversations=15) -> list[str]` (empty = pass).
Tests (`tests/test_check.py`), one failing case per rule of success criteria 1–4:
- [ ] fewer than `min_drills`; hint not in answer; 1 or 6 hints; `source_lines` empty or out of range;
      answer content words < 50 % in source lines; > `cap` drills from one conversation;
      < `min_conversations` represented; duplicate normalised question.
- [ ] A valid level returns `[]`.

### Task 6: Author level 1 (Claude, in-session)
- [ ] `uv run gst digest --level 1 > .cache/digest-01.txt`; read it in full.
- [ ] Write `data/drills/level-01.json` (≥ 40 drills, ~2 per conversation, most topic-relevant exchanges,
      questions phrased to the learner and answerable without the dialogue, level-appropriate German).
- [ ] `uv run gst check --levels 1` passes; commit `feat: add level 1 speaking drills`.

### Task 7: TTS — `src/gst/tts.py`
`TTS` protocol: `synthesize(text, voice, out) -> None` (WAV). `PiperTTS(models_dir)`, `ElevenLabsTTS(api_key, post)`,
`CachedTTS(inner, cache_dir).get(text, voice) -> Path` (file name = sha256(backend, voice, text)). `wav_duration(path)`.
Voices: question = `de_DE-thorsten-high`, answer = a female Piper voice (pick after a listening test).
Tests (`tests/test_tts.py`):
- [ ] `wav_duration` of a generated 1.5 s silent WAV == 1.5.
- [ ] `CachedTTS` returns the same path twice and calls the inner backend once.
- [ ] `ElevenLabsTTS` sends `xi-api-key` and the text to `/v1/text-to-speech/{voice}` (fake `post`); missing key → clear error.
- [ ] `@pytest.mark.slow` — real Piper gives a WAV > 0.5 s for `"Hallo, wie geht's?"` (skipped when the model is absent).

### Task 8: Timeline — `src/gst/timeline.py` (pure, no I/O)
`TimelineConfig`, `Segment(kind, drill_id, duration, audio)`, `Chapter(title, start)`,
`plan_drill(drill, q_audio, q_dur, a_audio, a_dur, cfg)`, `plan_level(level_label, items, cfg) -> (segments, chapters)`.
Tests (`tests/test_timeline.py`):
- [ ] q=2.0, a=3.0 → durations `[2.6, 6.5, 4.2]`; a=1.0 → speak uses the 5.0 s floor.
- [ ] 3 drills → intro + 9 + outro segments; chapter starts are cumulative sums.

### Task 9: Cards — `src/gst/cards.py`
*Run `/taste-skill` first.* `wrap(text, font, max_width)`, `question_card(drill, label)`, `answer_card(drill, label)`, `title_card(title, subtitle)`.
Font via `fc-match` (Noto Sans → DejaVu Sans fallback).
Tests (`tests/test_cards.py`):
- [ ] Every card is 1280×720 RGB; `wrap` never exceeds `max_width` nor drops words.
- [ ] 200-character answer renders without overflow (font steps down); `ÄÖÜäöüß` have non-empty bboxes.

### Task 10: Video — `src/gst/video.py`
`encode_segment(image, audio, duration, out, countdown=False)`, `concat(paths, chapters, out)`, `probe(path)`.
Shared codec params (1280×720, 30 fps, yuv420p, H.264, AAC 44.1 kHz mono) so concat is `-c copy`.
Tests (`tests/test_video.py`, real ffmpeg, tiny inputs):
- [ ] 1.0 s still + 0.5 s audio → 1.0 s ± 0.05, one video + one audio stream; silent segment still has audio.
- [ ] Concat of 3 segments → duration = sum ± 0.1 s; chapters present with the given titles.

### Task 11: CLI + first video — `src/gst/cli.py`
`gst digest --level N`, `gst check --levels 1-10`, `gst render --levels 1-10 [--tts piper|elevenlabs]`; `parse_levels("1-3,7") == [1,2,3,7]`.
Tests (`tests/test_cli.py`):
- [ ] `parse_levels` valid + invalid cases.
- [ ] `render` end-to-end on `tests/fixtures/ocr` with a fake TTS and a 2-drill fixture → MP4 that `probe` accepts.
- [ ] Second `render` → 0 TTS calls.
- [ ] Render level 1 for real; **user watches it** and gives format feedback (criteria 8–9) before Task 12.

### Task 12: Author + render levels 2–10
- [ ] Per level: digest → write `level-NN.json` → `gst check` → commit + push (one commit per level).
- [ ] `gst render --levels 1-10`; user spot-checks criterion 5 on two levels.

## 7. Output Validation Recipe
- **PRODUCE:** `uv run gst check --levels 1-10 && uv run gst render --levels 1-10`, then open
  `$GST_WORK_DIR/videos/level-01.mp4` in mpv/VLC.
- **JUDGE:** the voice asks a real, situation-appropriate German question; the card shows the German
  question, English translation and 2–5 hint words that appear in the answer; the countdown leaves enough
  time to say the answer; the correct answer is spoken and shown; 18 of 20 sampled drills are on-topic and
  answerable without the dialogue; pronunciation is clear.

## 8. Git workflow
- `main` gets one empty root commit (bootstrap of the empty repo); after that, nothing lands on `main` except via PR.
- Branches: `docs/project-plan` (this plan, CLAUDE.md, README) → `feat/drill-pipeline` (Tasks 0–11, atomic commits)
  → `feat/a1-drills` (Task 12). Push after every commit.
- Blocker: `gh` token invalid and SSH key not registered — run `gh auth login` (then `gh auth setup-git`) to push and open PRs.

## 9. Risks
| Risk | Mitigation |
|---|---|
| OCR typos in transcript lines | Claude reads the digest and fixes obvious OCR errors in the authored answer; grounding check uses word overlap, not exact match. |
| Piper German sounds robotic | Listening test in Task 7; ElevenLabs backend for the final render if needed (~10k chars/month free). |
| 4 GB GPU / CPU-only rendering is slow | Still images + `-tune stillimage`, segment cache, one level at a time. |
| Authoring 400+ drills is long | One level per commit; validator catches structural errors immediately. |
