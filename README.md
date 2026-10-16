# voicebox-realtime-client

Local web client for an existing [Voicebox](http://127.0.0.1:17493) TTS service: type text, pick a
voice and model (both discovered from Voicebox), hear speech as sentence chunks become ready and
follow it in a teleprompter. It runs no speech model itself and never starts or modifies Voicebox.

**Tested with**: Python 3.13.0, Gradio 6.30.0, httpx 0.28.1, uvicorn 0.54.0, Voicebox API v0.5.0.

## Install

Use Python 3.10–3.13. Do **not** use 3.14: the pinned Gradio does not declare support for it.

```text
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # add requirements-dev.txt for tests
```

## Configure

| Variable | Default | Meaning |
|----------|---------|---------|
| `VOICEBOX_URL` | `http://127.0.0.1:17493` | Voicebox base URL (the only host this app contacts) |
| `APP_HOST` | `127.0.0.1` | Bind address. Keep it on loopback. |
| `APP_PORT` | `7860` | Port of this app |

Inside a container, `127.0.0.1` is the container itself: point `VOICEBOX_URL` at the host
(for example `http://host.docker.internal:17493`) and publish the app port explicitly.

## Start

Voicebox must already be running. Then:

```text
python -m app        # http://127.0.0.1:7860
```

## Use

Enter text (max 5,000 characters), choose a voice and model, press **Generate**. The status line
shows the session state and mode (`sentence-chunked` for 2+ chunks, `full response` for one).
Generate and the inputs are locked while a session is active. Pause/Resume, Stop, Restart,
Replay and Download act on the same audio that drives the highlight; Replay and Download appear
after a session completes.

## Test

```text
pytest tests/unit tests/contract          # no backend needed
pytest tests/integration -m voicebox      # needs the running Voicebox (skipped if unreachable)
python scripts/measure.py --runs 5        # baseline latency (fetch-complete times)
python scripts/resource_check.py          # 20 generations, memory stays bounded, no ML packages
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Voicebox can't be reached at …" | Start Voicebox, or set `VOICEBOX_URL`; press Retry. |
| Dropdowns empty | Voicebox needs at least one voice profile and one downloaded Qwen TTS model. |
| "Voicebox took too long to respond" | First use of a model loads it; wait and retry. Chunk timeout is 120 s. |
| Audio does not start | The browser blocked autoplay: press Resume. |
| `pip install` fails on gradio | You are likely on Python 3.14; use 3.13. |

## Limitations (read before relying on it)

- **No incremental audio.** Voicebox's `/generate/stream` returns the complete WAV only after
  synthesis finishes (verified, see `specs/001-realtime-tts-teleprompter/research.md`). The client
  therefore splits text into sentence chunks and plays each as soon as it is ready. This is
  *sentence-chunked playback*, not byte-level real-time streaming. Synthesis can be slower than
  playback on this hardware, so expect pauses between chunks ("buffering").
- **Approximate sync.** Voicebox provides no timestamps. The highlight follows the real audio
  position, but the position inside a chunk is estimated from character counts.
- **Model mapping.** Voicebox does not expose the engine for a model name. Only downloaded
  `qwen-tts-<size>` models are offered (engine `qwen`); other models are hidden, not guessed.
- **Cancel behaviour.** Stop aborts the in-flight request and drops queued chunks. Whether
  Voicebox stops synthesizing after a disconnect: see "Cancel check" below.
- Audio of the last completed session is kept in memory for replay/download and released when the
  next generation starts or the page closes.

## Cancel check

Checked against Voicebox v0.5.0 (see `specs/001-realtime-tts-teleprompter/research.md` section 7).
`GET /tasks/active` does not list `/generate/stream` work, so cancellation cannot be observed
directly. A short request sent right after an aborted long one ran at normal speed (7.5 s vs 7.2 s
idle), which indicates Voicebox stops synthesizing when the client disconnects. This is inferred
from timing, not guaranteed by the API.
