# Data Model

All state is in memory and per browser session. Nothing is persisted. Fields follow the verified
Voicebox schemas where they come from the API.

## Voice (from `GET /profiles`)
- `id` (string), `name` (display label), `language` (string, used as the request `language`),
  `voice_type` (informational).

## ModelOption (from `GET /models/status`, filtered)
- `model_name` (string from API), `display_name` (label), `engine` + `model_size` (derived by the
  documented mapping in research D4), `downloaded` (must be true to be offered), `loaded` (info).
- Validation: only downloaded, mappable TTS entries are offered.

## GenerationSession
- `id` (client-generated), `state`: `idle | loading | generating | streaming | playing | paused |
  completed | stopped | failed`, `mode`: `sentence-chunked | full-response`.
- State meaning: `generating` = waiting for the first chunk; `streaming` = later chunks still
  arriving while earlier ones play; `playing` = all chunks received and playback in progress.
- `text` (as entered), `voice_id`, `model_name`, `chunks[]`, `error` (user message or none),
  `started_at`, `ended_at`.
- Transitions: `idle → loading → generating → playing ⇄ paused → completed`; `generating|playing|
  paused → stopped` (user); any active state → `failed` (error). `completed|stopped|failed → idle`
  on next Generate. Generate is only enabled in `idle`, `completed`, `stopped`, `failed`
  (spec FR-011).

## Chunk
- `index`, `segments[]` (the teleprompter sentences it covers), `char_start`/`char_end` in `text`,
  `status`: `pending | requested | ready | playing | played | failed`, `duration_s` (from WAV
  header, known when ready), `audio` (in-memory bytes; discarded per spec FR-015 on stop/fail).

## TeleprompterSegment
- `index`, `char_start`, `char_end`, `text`, `precision`: `estimated` (always, no timing data from
  Voicebox), `state`: `upcoming | active | done`.

## PerformanceRecord (no full text, no audio)
- `session_id`, `text_length`, `connect_s` (time to reach Voicebox), per chunk: `request_sent`,
  `first_byte`, `response_complete`, `ready_to_play`; session: `first_playable_audio_s` (reported
  by the browser when playback actually starts), `total_generation_s`, `stalls` (count and total
  ms, reported by the browser), `session_duration_s`, `outcome` (`completed|stopped|failed`),
  `error_class`.

## CompletedAudio
- Latest completed session's concatenated audio held for replay/download (spec FR-021); replaced
  on next generation, released at session end.
