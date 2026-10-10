# German Speech Training

Speaking practice videos built from the transcripts of *Master German with 800 Real-Life Conversations*.

Each course level gets at least 40 speaking drills. The video for a level asks you a question in German,
shows the English translation and a few hint words, gives you time to answer out loud, and then plays the
correct answer.

See [`docs/plan.md`](docs/plan.md) for the plan and the definition of success.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed automatically)
- `ffmpeg` and `ffprobe` on `PATH`
- The OCR output of the course (`_slide_ocr/output`)

## Usage

```bash
export GST_OCR_ROOT="/path/to/course/_slide_ocr/output"
export GST_WORK_DIR="/path/to/course/_speaking_drills"

uv run gst digest --level 1        # numbered transcript used to write drills
uv run gst check --levels 1-10     # validate data/drills/level-NN.json
uv run gst render --levels 1-10    # synthesize speech and render one MP4 per level
```

Videos are written to `$GST_WORK_DIR/videos/level-NN.mp4`.

### Voices

The default backend is [Piper](https://github.com/OHF-Voice/piper1-gpl): free, offline, downloaded on
first use. Questions use `de_DE-kerstin-low`, answers use `de_DE-thorsten-high` (the answers are what you
imitate, so they get the clearer voice). Pick others with `--question-voice` / `--answer-voice`, e.g.
`de_DE-ramona-low`, `de_DE-eva_k-x_low`.

To use ElevenLabs instead (its free tier covers roughly one or two levels per month):

```bash
uv sync --extra elevenlabs
export ELEVENLABS_API_KEY=...
uv run gst render --levels 1 --tts elevenlabs --question-voice <voice id> --answer-voice <voice id>
```
