# Contract: Voicebox operations used by the client

Source of truth: `http://127.0.0.1:17493/openapi.json` (v0.5.0). Base URL comes from
configuration (default above). Every operation here exists in that document.

| Client operation | Request | Used response fields | Notes |
|------------------|---------|----------------------|-------|
| `check_health` | `GET /health` | `status`, `model_loaded` | Used for the connection check and the unreachable message. |
| `list_voices` | `GET /profiles` | `id`, `name`, `language` | Called on page load and on refresh. |
| `list_models` | `GET /models/status` | `model_name`, `display_name`, `downloaded`, `loaded` | Filtered per research D4. |
| `synthesize_chunk` | `POST /generate/stream` JSON `{profile_id, text, language, engine, model_size}` | Body: `audio/wav`, 24 kHz mono 16-bit | Not incremental (research §2). One call per chunk. `normalize`/`crossfade_ms` left at defaults. |
| `active_tasks` (diagnostic) | `GET /tasks/active` | list | Only to verify disconnect-cancel (D3). |

Error mapping (client layer translates; UI never sees raw HTTP):

| Condition | User message class |
|-----------|--------------------|
| Connection refused / DNS / timeout on `/health` | "Voicebox can't be reached at <url>. Check it is running." |
| 422 from `/generate/stream` | "Voicebox rejected the request (invalid selection or text)." |
| 5xx / body not valid WAV / truncated body | "Voicebox failed while generating. Try again." |
| Read timeout during a chunk | "Voicebox took too long to respond." |

No automatic retry of generation (Principle VI). Only `GET` discovery calls (`/health`,
`/profiles`, `/models/status`) are retried, once, after a connection error or timeout.

Timeouts (initial, to be tuned from measurements): connect 3 s, discovery read 10 s,
chunk read 120 s (observed 6.5–19 s).

# Contract: Client-local HTTP surface (browser ↔ Gradio server)

The browser never talks to Voicebox directly.

| Route | Purpose |
|-------|---------|
| Gradio UI | Page, controls, status. |
| `POST /api/chunk` (JSON `{session, index}`) | Returns the WAV for a chunk (proxied from Voicebox); 409 if the session was stopped. |
| `POST /api/stop` (JSON `{session}`) | Aborts the in-flight request and discards chunks. |
| `POST /api/metrics` (JSON `{session, event, t}`) | Browser reports `play_start`, `stall_start`, `stall_end`, `ended`; contains no text or audio. |

Bound to `127.0.0.1` by default (Principle X).
