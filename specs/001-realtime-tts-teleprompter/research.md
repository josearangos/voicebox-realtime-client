# Research: Realtime TTS Client with Teleprompter

**Date**: 2026-10-15 | **Backend inspected**: Voicebox API v0.5.0 at `http://127.0.0.1:17493`
(OpenAPI fetched from `/openapi.json`; probes run against the live instance, Apple Silicon,
MLX backend, model `qwen-tts-0.6B` loaded).

This satisfies constitution §3.2 (API discovery before planning). Every claim below is either
read from the OpenAPI document or measured; unverified items are marked **UNVERIFIED**.

## 1. Endpoints evaluated

| Need | Endpoint | Verified facts |
|------|----------|----------------|
| Health / reachability | `GET /health` | Returns `status`, `model_loaded`, `model_size`, `gpu_available`, `backend_type`. Live: `healthy`. |
| Voice list | `GET /profiles` | Array of profiles with `id`, `name`, `language`, `voice_type`, `default_engine`. Live: 1 profile. |
| Model list | `GET /models/status` | `model_name`, `display_name`, `downloaded`, `loaded`. Live: 19 entries, including non-TTS (whisper, qwen3 LLM). |
| Generate (saved) | `POST /generate` | Returns a `GenerationResponse` with `id`; writes to the user's history. Not probed (side effects). |
| Generate (stream) | `POST /generate/stream` | "stream the WAV audio directly without saving to disk". Same request body as `/generate`. **Probed.** |
| Cancel | `POST /generate/{id}/cancel` | Needs a generation id. `/generate/stream` does not return one. |
| Status | `GET /generate/{id}/status` | SSE of status updates; no audio. |
| Other | `POST /speak`, `GET /events/speak` | `/speak` mirrors `/generate` (history + polling). `/events/speak` is start/end events. Not suitable. |

Request body (`GenerationRequest`): `profile_id`, `text` (1–50,000 chars), `language`
(22 codes), `engine` (`qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro`),
`model_size` (`1.7B|0.6B|1B|3B`), plus `seed`, `instruct`, `max_chunk_chars` (100–5000,
default 800), `crossfade_ms`, `normalize`, `effects_chain`, `personality`.

## 2. Key finding: `/generate/stream` is NOT incremental

Probe: 3-sentence Spanish text, `qwen` / `0.6B`, read with an unbuffered client.

- Response headers arrived **19.29 s** after the request. No bytes before that.
- Then the entire body (364,844 bytes) was available at the same instant (all chunks at 19.29 s).
- The WAV header already states the final data length (`RIFF` size 0x59124 ≈ the total), so
  the file is fully known before the first byte is sent.
- Transport is `Transfer-Encoding: chunked`, `audio/wav`, 24 kHz, mono, 16-bit PCM
  (`fmt`: 0xC0 0x5D = 24000 Hz, 1 channel, 16 bits).

Conclusion: the endpoint is called "stream" but behaves as **a complete file after full
synthesis**. Per constitution Principle II it MUST NOT be described as real-time streaming.

No endpoint was found that emits audio incrementally, and none exposes word or sentence
timestamps. Alignment data is **unavailable** (spec: sentence-level estimate, labelled approximate).

## 3. Baseline measurements (documented conditions)

Hardware: this development Mac (Apple Silicon, MLX). Voicebox model already loaded.

| Text | Audio length | Time to full response | Real-time factor |
|------|--------------|-----------------------|------------------|
| 1 sentence (~32 chars) | ~2.4 s | 6.54 s | ~2.7× slower than real time |
| 3 sentences (~115 chars) | ~7.6 s | 19.29 s | ~2.5× slower than real time |

Single runs, not a statistical baseline. Playback will therefore stall between sentence chunks
on this hardware. A proper baseline script is part of the quickstart.

## 4. Decisions

### D1. Transport: sentence-chunked requests to `/generate/stream` (client-side pipelining)

- **Decision**: Split the text into sentences/short groups on the client. Request them one at a
  time (in order) from `/generate/stream`; start playing chunk 1 as soon as it is complete while
  chunk 2 is generated.
- **Rationale**: It is the only way, with the verified API, to start audio before the whole text
  is synthesized. Time to first audio drops from "whole text" to "first chunk" (about 6.5 s vs
  19.3 s in the probe above for 1 vs 3 sentences).
- **Honest labelling**: This is **sentence-chunked playback**, not byte-level streaming. The UI
  and docs say so (Principle II). When only one chunk exists the mode is "full response".
- **Alternatives**: (a) one `/generate/stream` call for the whole text: simplest, but the user
  waits for everything and it cannot be called streaming; (b) `/generate` + poll + `/audio/{id}`:
  adds history writes and polling for no latency gain; (c) modify Voicebox to stream: out of scope
  (§3.3).
- **Status**: Accepted by the user on 2026-10-15. This deviates from the "incremental audio"
  ideal; the constitution requires an explicit alternative when the API cannot provide the
  capability, and this is that alternative.

### D2. Playback and teleprompter in the browser, driven by the audio element

- **Decision**: The browser plays each chunk's WAV with a standard audio element/queue and a
  small script updates the teleprompter from the real playback position (`currentTime`).
- **Rationale**: Gradio's server cannot see browser playback position. Principle III requires
  progress driven by audio playback, not by a timer. Pause/resume/stop act on the same element,
  so audio and highlight cannot disagree.
- **Highlight precision**: Each chunk is one or more known sentences with a known audio duration
  (from the WAV header). Within a chunk, position is estimated proportionally to character count.
  Labelled "approximate".
- **Alternatives**: Gradio's built-in streaming audio output: no playback position back to the
  server, so progress would be timer-driven (violates Principle III).

### D3. Cancellation: close the connection (checked 2026-10-15, see "Cancel check" below)

`/generate/{id}/cancel` needs an id that `/generate/stream` does not provide. Stop therefore:
stops playback, drops queued chunks, aborts the in-flight HTTP request. Whether Voicebox stops
synthesizing when the client disconnects is **UNVERIFIED**; a task checks `GET /tasks/active`
after an abort. If it keeps running, this is documented as a limitation (Principle VI).

### D4. Voices and models

- **Voices**: `GET /profiles`; label = `name` (+ language). No hardcoding.
- **Models**: `GET /models/status` lists names (`qwen-tts-0.6B`) but the request needs
  `engine` + `model_size`. The API gives no mapping, so a small, documented mapping
  (`qwen-tts-<size>` → engine `qwen`, size `<size>`; other TTS names → their engine) is the only
  non-discoverable part. Only entries that are `downloaded` and a TTS engine are offered; unknown
  names are hidden rather than guessed. This is a documented limitation. Accepted by the user on
  2026-10-15.
- Voicebox selects the model per request (`model_size`, `engine`), so model choice is supported.

### D5. Stack and structure

- Python 3.14 (present), Gradio for UI, `httpx` for the Voicebox client, `pytest` + `respx` for
  tests. A small proxy route inside the Gradio app's own server lets the browser fetch chunk audio
  without exposing Voicebox directly or fighting CORS; it forwards only to the configured base URL.
- Not yet installed locally (pip list showed none); installation is a setup task.

### D6. Text limit

Client limit 5,000 characters (spec) is below Voicebox's 50,000 maximum, so no conflict.

## 5. Risks

- Slower-than-real-time synthesis on this machine causes audible gaps between chunks. Mitigation:
  pre-generate the next chunk while the current one plays; show a "buffering" state; optionally
  wait for N chunks before starting (tuned from measurements).
- Per-chunk requests may change prosody at boundaries versus one pass. Mitigation: group short
  sentences; measure subjectively in the quickstart.
- Disconnect-cancel behaviour unknown (D3).
- Proportional in-chunk highlighting is approximate (labelled).

## 6. Baseline (T022, measured 2026-10-15)

Command: `python scripts/measure.py --runs 5` (3 and 1 sentence sizes) and
`--runs 5 --sizes 8` (the first invocation's 8-sentence stage hit a Voicebox 500 and was re-run
separately). Repeated sentence "The quick brown fox jumps over the lazy dog near the river bank."
(~64 chars), one chunk per sentence. Hardware: macOS 26.2 arm64 (Apple Silicon, MLX backend),
Python 3.13.0, model `qwen-tts-1.7B` (loaded), one Spanish voice, Voicebox v0.5.0 on localhost.
Times are **fetch-complete** (the whole chunk response received), not browser playback; the
browser-measured first playable audio is logged from `/api/metrics` events during page runs.
Mean ± population std dev over 5 runs.

| Sentences | Chunks | Chars | Audio (s) | First chunk fetched (s) | All chunks fetched (s) |
|-----------|--------|-------|-----------|--------------------------|------------------------|
| 1 | 1 | 64 | 4.1 | 10.4 ± 0.8 | 10.4 ± 0.8 |
| 3 | 3 | 194 | 13.0 | 14.8 ± 2.6 | 45.5 ± 7.6 |
| 8 | 8 | 519 | 33.4 | 15.9 ± 1.4 | 140.7 ± 28.7 |

Reading: time to first audio stays about 10 to 16 s regardless of text length (the chunking
benefit); total synthesis is roughly 3.5 to 4.2 times the audio duration, so playback cannot keep
up and stalls between chunks are expected on this hardware. The model is the 1.7B one, because
the loaded model changed during earlier live tests; the 0.6B model was faster in the early single
probes (section 3). Run-to-run spread is large (up to about 20 %).

## 7. Cancel check (T035, D3)

`tests/integration/test_live_cancel.py` (marker `voicebox`): start a 6-sentence request, abort
the HTTP request after 4 s, then time a short request.

- `GET /tasks/active` did **not** show the `/generate/stream` synthesis (`generations` stayed
  empty during the run; `downloads` listed a recurring model entry unrelated to the test), so it
  cannot be used to observe cancellation.
- Timing evidence instead: a short request sent right after the abort took 7.5 s versus 7.2 s on
  an idle server. If Voicebox had kept synthesizing the remaining ~5 sentences (tens of seconds),
  the short request would have been much slower.

Conclusion: disconnecting appears to stop synthesis on this Voicebox version (v0.5.0, MLX), but
this is inferred from timing, not reported by the API. Documented as a limitation.

## 8. Quickstart run log (T045, 2026-10-15)

Run in real Chrome (Playwright, headless, autoplay allowed) against the live Voicebox and the
app on 127.0.0.1:7860, plus the automated suites (69 tests passing).

| # | Scenario | Result |
|---|----------|--------|
| 1 | Connection and discovery | Pass. Dropdowns filled from `/profiles` and `/models/status`. With Voicebox unreachable: "can't be reached" message, Retry shown, typed text kept. |
| 2 | Primary flow | Pass. generating, then streaming/playing, then completed; audio starts after chunk 1; active segment advanced 0, 1, 2, 3 with playback. |
| 3 | Mode honesty | Pass. Multi-sentence text shows "sentence-chunked"; a single chunk shows "full response". The phrase "real-time streaming" appears nowhere in the UI. |
| 4 | Controls | Pass. Pause, Resume, Stop verified; Replay after completion restarted playback with no new request; Restart after stop goes through Generate. |
| 5 | Conflicts | Pass. Generate and inputs disabled during a session, with a visible reason. |
| 6 | Failures | Pass for empty text, 5,001 characters, Voicebox unreachable. Mid-session failure is covered by `tests/unit/test_pipeline.py` (mocked), not by killing the live Voicebox. |
| 7 | Cancel check | Done: section 7. |
| 8 | SC-001 stopwatch | **Not performed.** |
| 9 | SC-004 highlight accuracy (20 pauses on ~5,000 characters) | **Not performed** (would take over 30 minutes of synthesis at the measured speed). Highlight advancement was checked only on short texts. |
| 10 | Plain-text display | Pass. `<b>` and `<script>` shown literally; `window.__x` stayed undefined. |
| 11 | Narrow screen and tabs | Pass at 400 px (no horizontal scroll, controls usable); a second tab stayed idle and independent. |
| 12 | Baseline | Done: section 6. |

T045 stays open until scenarios 8 and 9 are run by hand.
