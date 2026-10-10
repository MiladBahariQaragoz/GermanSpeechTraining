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
uv run --env-file .env gst shortlist --level 13   # Jev-ranked lines most worth practising
uv run gst check --levels 1-10     # validate data/drills/level-NN.json
uv run gst render --levels 1-10    # synthesize speech and render one MP4 per level
```

Videos are written to `$GST_WORK_DIR/videos/level-NN.mp4`.

`gst shortlist` needs the optional TypeSafe SDK and an API key: `uv sync --extra jev`, then put
`TYPESAFE_API_KEY=...` in a git-ignored `.env` (keys: https://console.typesafe.ai/).

### Voices

The default backend is **edge-tts** (Microsoft's neural voices): free and needs no key. Questions use
`de-DE-FlorianMultilingualNeural`, answers use `de-DE-KillianNeural` (slower and clearer, since the
answers are what you imitate). The service refuses about half of all requests with HTTP 403 at random;
`gst` retries them, and every sentence is cached, so it is only ever downloaded once.

Other backends:

- `--tts piper`: fully offline ([Piper](https://github.com/OHF-Voice/piper1-gpl)), but the German
  pronunciation is noticeably weaker.
- `--tts elevenlabs`: needs `uv sync --extra elevenlabs` and `ELEVENLABS_API_KEY`; the free tier covers
  roughly one or two levels per month.

Pick other voices with `--question-voice` / `--answer-voice`.
