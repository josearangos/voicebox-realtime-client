# Implementation Plan: Realtime TTS Client with Teleprompter

**Branch**: `001-realtime-tts-teleprompter` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-realtime-tts-teleprompter/spec.md`

## Summary

A local Gradio client for the existing Voicebox service. Voices and models are discovered from
Voicebox; text is split into sentence chunks that are synthesized in order through
`POST /generate/stream`; the browser plays each chunk as it arrives and drives a sentence-level
teleprompter from the real audio position.

Verified against the live API (see [research.md](research.md)): Voicebox exposes **no incremental
audio** and **no timestamps**. `/generate/stream` returns the complete WAV only after full
synthesis (19.3 s for a 3-sentence text on this machine). The plan therefore uses client-side
sentence chunking and labels it honestly as "sentence-chunked", with highlight precision
"approximate".

## Technical Context

**Language/Version**: Python 3.10–3.13, using 3.13 (`/opt/homebrew/bin/python3.13`). The latest Gradio on PyPI (6.30.0 when checked) declares support up to 3.13, and the default `python3` here is 3.14, which is not declared supported; do not use it for the project `.venv`.

**Primary Dependencies**: gradio, httpx (Voicebox client), a small ASGI route set inside the Gradio
app for the chunk proxy; browser-side script for playback and teleprompter

**Storage**: None persistent; in-memory per session; latest completed audio held for replay

**Testing**: pytest, respx (HTTP mocks), pytest marker `voicebox` for live-backend tests

**Target Platform**: macOS (Apple Silicon) and other environments with Python 3.10–3.13; no GPU

**Project Type**: Single local web application

**Performance Goals**: Numeric targets are deferred to spec SC-003 and task T022, which records a
baseline first. Initial single-run observations only: 1 sentence 6.5 s, 3 sentences 19.3 s on this
hardware (synthesis ≈ 2.5× slower than the audio). Time to first playable audio is expected to
track the first chunk only; gaps between chunks are expected on this hardware and will be
reported, not hidden. Buffering policy: start playing as soon as chunk 1 is ready, prefetch
one chunk ahead; whether to wait for a second chunk before starting is decided from T022 data.

**Constraints**: Bound to 127.0.0.1; text ≤ 5,000 characters; Generate disabled while a session is
active; no logging of full text or audio; no second TTS model in-process

**Scale/Scope**: Single user, one active session, one page

## Constitution Check

*GATE: passes before Phase 0 and after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I API-First | Pass | Live OpenAPI inspected; table of used operations in contracts/voicebox-api.md; voices and models discovered. Model→engine mapping is not discoverable, so it is documented as a limitation (research D4). |
| II Real-time | Pass with documented limitation | No incremental endpoint exists. Fallback is explicit sentence-chunked playback; full-file mode labelled as such. Needs user confirmation (research D1). |
| III Teleprompter | Pass | Driven by audio element position; estimated precision labelled; degrade when unknown. |
| IV Simplicity | Pass | One page, one flow; no config screens. |
| V Separation | Pass | See structure: client / chunking / session / UI separate. |
| VI Reliability | Pass, one item unverified | Error mapping and timeouts defined; disconnect-cancel unverified, task T-check planned (D3). |
| VII Resources | Pass | No GPU, no model; in-memory audio, released per session. |
| VIII Testability | Pass | Mock-based unit/contract tests plus live integration marker; streaming vs full response test distinguishes timing of first byte. |
| IX Observability | Pass | PerformanceRecord per session without text/audio. |
| X Security | Pass | 127.0.0.1 default; proxy forwards only to configured base URL; text treated as data. |

No violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-realtime-tts-teleprompter/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── voicebox-api.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
app/
├── __main__.py          # entry point, binds 127.0.0.1
├── config.py            # base URL, timeouts, limits (env-driven)
├── errors.py            # typed errors with user-facing messages
├── voicebox_client.py   # HTTP calls, validation, error translation
├── chunking.py          # sentence splitting and grouping, char offsets
├── pipeline.py          # ordered chunk requests with one-chunk prefetch
├── teleprompter.py      # segment model and active-segment math
├── session.py           # session state machine, per-session isolation
├── metrics.py           # performance records (no text/audio)
├── server.py            # Gradio UI + local chunk/stop/metrics routes
└── static/
    ├── player.js        # chunk queue, playback, teleprompter updates, metric events
    └── app.css          # layout (desktop and narrow screens)
scripts/
└── measure.py           # baseline latency measurement
tests/
├── fixtures/            # sanitized samples of Voicebox responses
├── unit/                # chunking, state machine, client parsing, teleprompter math
├── contract/            # client vs recorded Voicebox response fixtures
└── integration/         # live Voicebox, marker `voicebox`
requirements.txt
requirements-dev.txt
README.md
```

**Structure Decision**: Single project. `voicebox_client.py` is the only module that knows
Voicebox URLs and schemas; `server.py` contains no HTTP-to-Voicebox logic.

## Gradio integration mechanism (to be proven by spike T047)

The Gradio `Blocks` app is created in `server.py` and mounted into a FastAPI app with
`gr.mount_gradio_app`. The same FastAPI app defines `POST /api/chunk`, `POST /api/stop` and
`POST /api/metrics`, and serves `app/static/` so `player.js` and `app.css` load into the page
(via Gradio's `head` option or a script tag in the page HTML). The app is run with uvicorn on
`127.0.0.1`. If the spike shows this cannot work with the pinned Gradio version, the fallback is a
plain FastAPI page for the teleprompter and player with Gradio only for the controls; that
decision would be recorded here before continuing.

### Spike result (T047, 2026-10-15)

`scripts/spike_gradio_mount.py` ran against **Gradio 6.30.0** (Python 3.13, uvicorn 0.54.0,
FastAPI 0.143.2): a FastAPI app with `POST /api/ping` and a static directory, with the Gradio
Blocks app mounted at `/` via `gr.mount_gradio_app(..., head=<script tag>)`, served on 127.0.0.1.
(a) `POST /api/ping` returned 200; (b) the static `player.js` was served (200) and the page head
references it. (c) the in-page call was then confirmed in a real Chrome run of the finished app
(Playwright, the player fetched `/api/chunk` and posted `/api/metrics`). The fallback was not
needed. Two integration notes: custom routes must be defined on the FastAPI app before the mount;
and the static mount must not use `/static`, which Gradio uses for its own assets (the app uses
`/vb-static`).

## Decisions

1. Accepted 2026-10-15: sentence-chunked playback as the real-time approach given the API
   (research D1).
2. Accepted 2026-10-15: documented model→engine mapping limitation (research D4).
3. Open: performance targets, set from the T022 baseline (spec SC-003).
