---

description: "Task list for Realtime TTS Client with Teleprompter"
---

# Tasks: Realtime TTS Client with Teleprompter

**Input**: Design documents from `/specs/001-realtime-tts-teleprompter/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/voicebox-api.md, quickstart.md

**Tests**: Included. Constitution Principle VIII makes tests mandatory (unit, contract with mocks, live integration marked `voicebox`).

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 = generate and hear, US2 = teleprompter, US3 = playback controls, US4 = failure handling
- Paths are relative to the repository root (single project per plan.md)

## Phase 1: Setup

- [X] T001 Create the project layout from plan.md: `app/`, `app/static/`, `scripts/`, `tests/unit/`, `tests/contract/`, `tests/integration/`, each package with `__init__.py` where needed
- [X] T002 Create `requirements.txt` (gradio, httpx) and `requirements-dev.txt` (pytest, pytest-asyncio, respx); create the `.venv` with Python 3.13 (`/opt/homebrew/bin/python3.13 -m venv .venv`, because the default `python3` here is 3.14 and the pinned Gradio may not support it), pin versions after installing, and record the Python and Gradio versions in README.md
- [X] T003 [P] Create `pyproject.toml` pytest config with the `voicebox` marker (live-backend tests skipped unless `VOICEBOX_URL` is reachable) and `.gitignore` entries for `.venv/`, `__pycache__/`
- [X] T004 [P] Create `README.md` skeleton: install, configure, start, troubleshoot, limitations (filled in Phase 7)

---

## Phase 2: Foundational (blocks all stories)

**⚠️ CRITICAL**: No user story work starts until this phase is complete.

- [X] T005 Implement `app/config.py`: base URL from env `VOICEBOX_URL` defaulting to `http://127.0.0.1:17493`; timeouts connect 3 s, discovery read 10 s, chunk read 120 s; `MAX_TEXT_CHARS = 5000`; host default `127.0.0.1`
- [X] T006 Implement typed errors in `app/errors.py`: `VoiceboxUnreachable`, `VoiceboxRejected` (422), `VoiceboxFailed` (5xx/invalid WAV/truncated), `VoiceboxTimeout`, each with a user-facing message per the error table in contracts/voicebox-api.md; no URLs with credentials or raw bodies in messages
- [X] T007 Implement `app/voicebox_client.py` with `check_health`, `list_voices` (`GET /profiles` → `id`, `name`, `language`), `list_models` (`GET /models/status`, keep only `downloaded` TTS entries and map `qwen-tts-<size>` → engine `qwen`, `model_size` `<size>` per research D4; hide unmappable names), and `synthesize_chunk` (`POST /generate/stream` body `{profile_id, text, language, engine, model_size}`; validate the response is `audio/wav`, parse duration from the WAV header; translate all httpx failures to the typed errors; no automatic retry of synthesis; `GET` discovery calls are retried once after a connection error or timeout; also measure and expose `connect_s`)
- [X] T008 [P] Implement `app/chunking.py`: split text into sentences with `char_start`/`char_end` offsets into the original text, then group short sentences into chunks (each chunk lists its segments); empty/whitespace text yields no chunks
- [X] T009 [P] Implement `app/metrics.py`: `PerformanceRecord` per data-model.md recording connect_s, request_sent, first_byte, response_complete, first_playable_audio_s and stalls (both reported by the browser via `POST /api/metrics`), total_generation_s, session_duration_s, outcome, error_class; logs only lengths and timings, never text or audio
- [X] T010 Implement `app/session.py`: per-browser-session state machine from data-model.md with states `idle | loading | generating | streaming | playing | paused | completed | stopped | failed` and only the allowed transitions (`generating` = waiting for the first chunk, `streaming` = later chunks arriving while earlier ones play, `playing` = all chunks received); `can_generate` true only in `idle|completed|stopped|failed`; holds chunks and discards chunk audio on stop/fail
- [X] T047 Gradio integration spike in `scripts/spike_gradio_mount.py`: prove that a Gradio Blocks app mounted with `gr.mount_gradio_app` in a FastAPI app served by uvicorn on 127.0.0.1 can (a) serve `POST /api/ping`, (b) serve a static `player.js` and load it into the page, and (c) call that route from the page; record the result and the pinned Gradio version in plan.md; if it fails, apply the fallback in plan.md before continuing
- [X] T011 [P] Unit tests for chunking in `tests/unit/test_chunking.py`: offsets reproduce the original text, abbreviations/decimals/multiline text, empty input, text at 5,000 characters, single sentence yields one chunk
- [X] T012 [P] Unit tests for the state machine in `tests/unit/test_session.py`: every allowed and forbidden transition, `can_generate` per state, chunk audio discarded on stop and fail
- [X] T013 [P] Contract tests for the client in `tests/contract/test_voicebox_client.py` using respx and fixtures captured from the live API (store sanitized samples in `tests/fixtures/`: `/profiles` and `/models/status` JSON with profile names and ids replaced by placeholders, and a tiny valid WAV): parsing, model filtering/mapping, WAV validation, and error translation for refused connection, timeout, 422, 500, truncated body, non-WAV body

**Checkpoint**: Client, chunking and session logic work and are tested without the UI.

---

## Phase 3: User Story 1 - Generate and hear speech as it is produced (P1) 🎯 MVP

**Goal**: Choose text, voice and model; hear audio start after the first chunk; Generate disabled while active.

**Independent Test**: With Voicebox running, enter 3+ sentences, press Generate; audio begins after the first chunk's response and plays all chunks in order; quickstart scenarios 1, 2, 3 and 5 pass.

### Tests for User Story 1

- [X] T014 [P] [US1] Unit test for the chunk pipeline in `tests/unit/test_pipeline.py`: chunk N+1 is requested while chunk N is playing, chunks are delivered in order, mode is `sentence-chunked` for 2+ chunks and `full-response` for one chunk
- [X] T015 [P] [US1] Streaming-vs-simulated test in `tests/contract/test_streaming_detection.py`: with a mocked server that delays the whole body versus one that sends bytes early, assert the detector reports first-byte time separately from response-complete time and classifies the first as non-incremental
- [X] T016 [P] [US1] Live integration test in `tests/integration/test_live_generate.py` (marker `voicebox`): discovery returns at least one voice and model, one short chunk returns a valid WAV, records time to first byte versus completion

- [X] T048 [P] [US1] Metrics test in `tests/unit/test_metrics.py`: browser events produce `first_playable_audio_s` and stall totals; records contain no text or audio; `scripts/measure.py` reports fetch-complete times only, labelled as such (browser-measured first playable audio comes from the `POST /api/metrics` events logged during real page runs, quickstart scenario 2)
- [X] T049 [P] [US1] Isolation test in `tests/unit/test_session_isolation.py`: two sessions with different ids keep separate state, chunks and stop signals (multiple tabs)

### Implementation for User Story 1

- [X] T017 [US1] Implement the chunk pipeline in `app/pipeline.py`: for a session, request chunks sequentially with at most one chunk prefetched ahead of playback, record metrics, expose "next chunk ready" to the server routes
- [X] T018 [US1] Implement `app/server.py` using the mechanism proven in T047: Gradio Blocks page with multiline text input (reject over 5,000 characters before any request, message shows limit and current length), voice dropdown, model dropdown (both populated at page load from the client), text and selectors locked while a session is active, Generate button, status line showing the session state and mode label ("sentence-chunked" or "full response"; never "real-time streaming"); Generate disabled with a visible reason while a session is active (spec FR-011); no HTTP-to-Voicebox code in this file
- [X] T019 [US1] Add local routes in `app/server.py`: `POST /api/chunk` (returns the WAV for a chunk from the pipeline, 409 if the session was stopped), `POST /api/stop` and `POST /api/metrics` (accepts `play_start`, `stall_start`, `stall_end`, `ended` events with timestamps, no text or audio, and feeds `app/metrics.py`); both bound to the same host as the app and forwarding only to the configured Voicebox URL
- [X] T020 [US1] Implement `app/static/player.js`: fetch chunks in order, play each with an audio element as soon as its response arrives, start the next chunk without gaps when ready, show "buffering" when waiting, report state changes (`playing`, `completed`) back to the page, and send `play_start`, `stall_start`, `stall_end` and `ended` events to `POST /api/metrics`
- [X] T021 [US1] Implement `app/__main__.py` entry point launching the app on `127.0.0.1` with debug off; add `scripts/measure.py` printing time to first playable audio and total generation per text length for N runs, noting hardware and model
- [X] T022 [US1] Record baseline measurements from `python scripts/measure.py --runs 5` (1, 3 and 8 sentences) into a "Baseline" section of `specs/001-realtime-tts-teleprompter/research.md` before any performance claim; update SC-003 in spec.md with the measured target

**Checkpoint**: MVP works end to end: text in, audio out as chunks, Generate lock.

---

## Phase 4: User Story 2 - Follow the reading in a teleprompter (P2)

**Goal**: Full text shown; current sentence highlighted from the real audio position and kept in view.

**Independent Test**: Play a long text; highlight advances with audio, stays visible, and shows "approximate"; quickstart scenario 2 highlight checks.

### Tests for User Story 2

- [X] T023 [P] [US2] Unit tests for position math in `tests/unit/test_teleprompter.py`: given chunk durations and segment character lengths, the active segment index at time t is correct at boundaries, at 0, at the end, and with a single segment; precision flag is always `estimated`
- [X] T050 [P] [US2] Escape test in `tests/unit/test_teleprompter_escape.py`: text containing `<b>x</b>`, `<script>alert(1)</script>` and `&amp;` is rendered as literal text segments (no HTML in the generated markup), spec FR-022
- [X] T024 [P] [US2] Unit test for the "unknown position" path in `tests/unit/test_teleprompter.py`: when no position is available, no segment is marked active

### Implementation for User Story 2

- [X] T025 [US2] Implement `app/teleprompter.py`: build `TeleprompterSegment` list from chunking offsets and compute the active segment from (chunk index, time within chunk, chunk duration) with in-chunk position proportional to character count; expose the same math as data for the browser
- [X] T026 [US2] Extend `app/server.py` with a teleprompter panel that inserts the user's text as plain text only (escape or use text nodes, never raw HTML) showing the full text split into segments, states `upcoming | active | done`, and a visible "approximate sync" label
- [X] T027 [US2] Extend `app/static/player.js` to update the active segment from the audio element's `currentTime` (not a timer), auto-scroll the active segment into view, and clear highlighting when playback position is unavailable
- [X] T028 [US2] Add layout CSS in `app/static/app.css` so the teleprompter is usable at narrow widths (about 400 px) and for texts of 5,000 characters; verify with quickstart scenario 11

**Checkpoint**: US1 and US2 both work; highlight follows real playback.

---

## Phase 5: User Story 3 - Control playback (P3)

**Goal**: Pause, resume, stop, restart with audio and highlight always consistent.

**Independent Test**: Quickstart scenario 4 and cancel check (scenario 7).

### Tests for User Story 3

- [X] T029 [P] [US3] Extend `tests/unit/test_session.py`: pause/resume/stop/restart transitions; restart after `completed` replays without a new request; restart after `stopped|failed` triggers a new generation
- [X] T030 [P] [US3] Contract test in `tests/contract/test_stop.py`: stop aborts the in-flight request and `/api/chunk` returns 409 afterwards

### Implementation for User Story 3

- [X] T031 [US3] Add Pause/Resume, Stop, Restart, Replay and Download controls in `app/server.py` (Replay and Download only after a completed session, spec FR-021) with enabled/disabled states following the session state
- [X] T032 [US3] Implement pause/resume/stop/restart in `app/static/player.js` acting on the same audio element that drives the highlight; stop drops queued chunks and aborts the in-flight fetch
- [X] T033 [US3] Implement stop in `app/pipeline.py` and `app/server.py`: cancel the in-flight `synthesize_chunk`, discard chunk audio (spec FR-015), keep text and selections
- [X] T034 [US3] Keep the concatenated audio of the latest completed session for replay and download (spec FR-021); release it when the next generation starts or the session ends; Restart after completion replays it
- [X] T035 [US3] Verify disconnect-cancel (research D3): add a live test in `tests/integration/test_live_cancel.py` (marker `voicebox`) that starts a long chunk, aborts the request, polls `GET /tasks/active`, and records whether Voicebox stopped; write the result and any limitation into research.md and README.md

**Checkpoint**: All controls consistent; cancel behaviour documented.

---

## Phase 6: User Story 4 - Understand and recover from problems (P3)

**Goal**: Clear messages, preserved input, no unhandled errors.

**Independent Test**: Quickstart scenario 6.

### Tests for User Story 4

- [X] T036 [P] [US4] Unit tests in `tests/unit/test_errors.py`: each error class yields its specified message and none contain credentials, headers or raw response bodies
- [X] T037 [P] [US4] Tests in `tests/unit/test_validation.py`: empty text, whitespace-only text, 5,001 characters, a voice or model no longer offered after refresh are all rejected before any request

### Implementation for User Story 4

- [X] T038 [US4] Implement pre-generation validation in `app/session.py` or `app/server.py` (empty, over limit, voice/model still offered via a fresh discovery check) with messages that name the fix
- [X] T039 [US4] Surface typed errors as UI status plus message in `app/server.py`; set state `failed`, preserve text and selections, discard partial audio, never show a traceback
- [X] T040 [US4] Handle interrupted or slow chunk responses in `app/pipeline.py` and `app/static/player.js`: timeout message, failed state, no partial audio offered; verify with a mocked mid-session failure test in `tests/unit/test_pipeline.py`
- [X] T041 [US4] Add a "Voicebox unavailable" state on page load with a Retry control that re-runs discovery without clearing input

**Checkpoint**: All failure scenarios give controlled states.

---

## Phase 7: Polish & Cross-Cutting

- [X] T042 [P] Complete `README.md`: install, configuration (`VOICEBOX_URL`), start, troubleshooting, limitations (no incremental audio, approximate sync, model mapping, cancel behaviour), localhost note for containers
- [X] T043 [P] Verify security items: app binds `127.0.0.1` only, debug off, logs contain no full text/audio, route inputs validated; add a test in `tests/unit/test_security.py` for the default host and log content, and a mocked-network assertion that the only outbound host contacted is the configured Voicebox URL (spec FR-017)
- [X] T044 Add a resource check: repeat 20 generations and confirm memory stays bounded and temporary audio is released (script or test noted in README); also confirm `pip list` in the `.venv` has no torch, tensorflow or speech-model packages and the app process loads no model (spec SC-008, FR-017)
- [ ] T045 Run all quickstart.md scenarios (1 to 12, including the manual SC-001 and SC-004 procedures) against the live Voicebox, record results, and tick the Definition of Done items in the constitution that now hold
- [X] T046 Run `pytest tests/unit tests/contract` (no backend) and `pytest tests/integration -m voicebox` (live) and fix failures

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → user stories → Phase 7.
- Task IDs are unique, not strictly in execution order: T047–T050 were added after analysis and sit where their dependencies require (T047 before T018).
- **US1** needs Phase 2 only (including the T047 spike). **US2** extends US1's page and player (T026–T027 modify files from T018/T020), so start it after US1. **US3** and **US4** also extend US1 files; each can follow US1 in either order, but T031–T033 and T039–T040 touch the same files, so do not run them concurrently.
- Within a story: tests first (confirm they fail), then pipeline/server/player.
- Same-file tasks are never marked [P]: `app/server.py` (T018, T019, T026, T031, T039), `app/static/player.js` (T020, T027, T032, T040), `app/pipeline.py` (T017, T033, T040).

## Parallel Opportunities

- Phase 1: T003, T004.
- Phase 2: T008, T009 together; then T011, T012, T013 together. T047 can run alongside T005–T007.
- US1: T014, T015, T016, T048, T049 together.
- US2: T023, T024, T050 together. US3: T029, T030. US4: T036, T037.
- Phase 7: T042, T043.

## Implementation Strategy

1. MVP: Phases 1–3. Stop and validate with quickstart scenarios 1, 2, 3, 5 and record the baseline (T022).
2. Add US2 (teleprompter), validate, then US3, then US4.
3. Finish with Phase 7 and the Definition of Done review.

## Notes

- Voicebox must already be running; no task starts it.
- No task modifies Voicebox. If a task finds a capability missing, document the limitation instead.
- Revalidate against the live API if endpoint behaviour differs from research.md.
