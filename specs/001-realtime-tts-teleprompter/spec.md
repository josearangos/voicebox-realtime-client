# Feature Specification: Realtime TTS Client with Teleprompter

**Feature Branch**: `001-realtime-tts-teleprompter` (not created; work is on `main`)

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "Gradio client for Voicebox: enter text, pick a voice and model, hear streamed audio as it's generated, and follow along in a teleprompter that highlights the current reading position"

## Clarifications

### Session 2026-10-15

- Q: When Generate is pressed while a generation is running, reject or replace? → A: Reject; Generate is disabled while a session is active and the user must press Stop first.
- Q: Teleprompter highlight granularity? → A: Sentence-level by default; word-level only if Voicebox provides exact word timings.
- Q: Maximum input text length? → A: 5,000 characters, with a clear message when exceeded.
- Q: Keep or discard partial audio after an interrupted stream? → A: Discard it; keep text and selections and show a failed state.
- Q: Replay/download of finished audio? → A: Replay and download the latest completed session only; cleaned up when the next generation starts or the session ends.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate and hear speech as it is produced (Priority: P1)

A user types or pastes text, chooses one of the voices and one of the models offered by their running Voicebox service, and presses Generate. Audio begins playing as soon as the first playable portion is available, without waiting for the whole recording to finish.

**Why this priority**: This is the core value of the product: a fast, usable path from text to heard speech. Everything else builds on it.

**Independent Test**: With Voicebox running, enter a multi-sentence text, select a voice and model, and press Generate. Playback starts before generation of the full text completes, and the user hears the complete text.

**Acceptance Scenarios**:

1. **Given** Voicebox is reachable and the page has loaded, **When** the user opens the page, **Then** the voice and model choices are populated from what Voicebox currently offers, with readable labels.
2. **Given** text, a voice and a model are selected, **When** the user presses Generate, **Then** the status shows generating/streaming, audio starts playing before the full audio is finished, and the status becomes completed when playback ends.
3. **Given** the backend cannot deliver audio incrementally for the selected options, **When** the user presses Generate, **Then** the user is told clearly that the audio is played after full generation, and playback still works.
4. **Given** a generation is in progress, **When** the user presses Generate again, **Then** Generate is disabled (with a visible reason) until the user stops the active session; no second request is ever started in parallel.

---

### User Story 2 - Follow the reading in a teleprompter (Priority: P2)

While audio plays, the user sees the full input text in a teleprompter view in which the current reading position is highlighted and kept in view, including for long texts.

**Why this priority**: It differentiates the client from a plain audio player, but depends on playback working first.

**Independent Test**: Play a long multi-paragraph text and observe that the highlighted position advances in step with the audio and the active segment stays visible without manual scrolling.

**Acceptance Scenarios**:

1. **Given** audio is playing, **When** time passes, **Then** the highlight moves forward consistently with the audio position, not on an unrelated timer.
2. **Given** the highlight is based on estimation rather than exact timing data, **When** the user views the teleprompter, **Then** the interface indicates that the position is approximate.
3. **Given** a text longer than the visible area, **When** playback proceeds, **Then** the active segment is automatically scrolled into view.
4. **Given** the playback position cannot be determined reliably, **When** audio plays, **Then** the teleprompter shows the full text without a misleading highlight.

---

### User Story 3 - Control playback (Priority: P3)

The user can pause, resume, stop and restart playback, and the teleprompter always agrees with what the audio is doing.

**Why this priority**: Useful control over the experience, but the product is already valuable without it.

**Independent Test**: Start playback, then pause, resume, stop and restart, checking after each action that audio and highlight are consistent.

**Acceptance Scenarios**:

1. **Given** audio is playing, **When** the user pauses, **Then** audio and highlight both hold their position; on resume both continue from there.
2. **Given** audio is playing or generating, **When** the user stops, **Then** playback ends, any in-progress generation is cancelled where the backend allows it, and the status shows stopped.
3. **Given** a session completed successfully, **When** the user restarts, **Then** the finished audio replays from the start with the highlight reset, without a new generation.
4. **Given** a session was stopped or failed (its partial audio was discarded), **When** the user restarts, **Then** a new generation begins from the start of the same text.

---

### User Story 4 - Understand and recover from problems (Priority: P3)

When Voicebox is unavailable, a request fails, or a stream is interrupted, the user sees a clear, actionable message, keeps their text and selections, and can try again.

**Why this priority**: Required for a trustworthy tool, but secondary to the happy path.

**Independent Test**: Stop Voicebox (or point the client at a wrong address), then try to load choices and generate; verify the messages and that the text remains.

**Acceptance Scenarios**:

1. **Given** Voicebox is not reachable, **When** the page loads or the user presses Generate, **Then** a message says Voicebox cannot be reached and how to check it, and no other service is used instead.
2. **Given** the stream is interrupted mid-playback, **When** the failure occurs, **Then** the status shows failed, the partial audio is not presented as a completed recording, and the text is preserved.
3. **Given** the text field is empty, **When** the user presses Generate, **Then** no request is made and the user is told text is required.

---

### Edge Cases

- Text at the 5,000-character limit: generation, playback and teleprompter remain usable and memory use stays bounded over repeated generations; text over the limit is rejected with a clear message.
- Text containing unusual characters, markup or code-like content: it is spoken or displayed as plain text and never interpreted.
- The previously selected voice or model is no longer offered after choices are refreshed: the user is prompted to choose again before generating.
- The user changes selections or text while a session is active: the text and selectors are locked until the session ends, so the running session cannot be altered; changes apply to the next generation.
- Multiple browser tabs: each has its own independent session state.
- Voicebox responds slowly: a visible loading state is shown and a timeout produces an understandable message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a multiline text input for the text to be spoken, accepting up to 5,000 characters; longer input MUST be rejected before any request is made, with a message stating the limit and the current length.
- **FR-002**: The system MUST obtain the list of voices and the list of models from the Voicebox service at runtime and present them with meaningful labels; it MUST NOT rely on fixed lists.
- **FR-003**: The system MUST let the user choose one voice and one model and MUST verify the choices are currently offered before starting generation.
- **FR-004**: The system MUST begin audio playback as soon as enough audio is available. When the text has more than one sentence group, it MUST request the text in ordered chunks and start playing the first chunk as soon as it is complete, while later chunks are still being produced; it MUST NOT wait for the whole text. If Voicebox later offers incremental audio, that MUST be preferred.
- **FR-005**: The system MUST label the delivery mode ("sentence-chunked" for several chunks, "full response" for one) and MUST NOT describe either mode as real-time streaming, since Voicebox returns each chunk only after it is fully produced.
- **FR-006**: The system MUST display the full input text in a teleprompter view for the whole session and highlight the current reading position.
- **FR-007**: The teleprompter position MUST be derived from actual audio playback position or from alignment data supplied by Voicebox, and MUST be labelled as approximate when estimated.
- **FR-008**: The teleprompter MUST keep the active segment visible automatically for long texts.
- **FR-009**: The system MUST support pause, resume, stop and restart, and the teleprompter MUST stay consistent with each action. Restart replays the finished audio after a completed session, and starts a new generation after a stopped or failed one.
- **FR-010**: The system MUST show the current state: loading, generating (waiting for the first chunk), streaming (later chunks still arriving while earlier ones play), playing (all chunks received), paused, completed, stopped or failed.
- **FR-011**: The system MUST disable Generate while a session is active (generating, streaming, playing or paused) and MUST re-enable it once the session is completed, stopped or failed.
- **FR-012**: Stopping MUST cancel the in-progress generation where the backend supports cancellation, and otherwise MUST stop playback and discard further audio.
- **FR-013**: The system MUST handle unreachable backend, timeouts, error responses, invalid responses and interrupted streams with actionable messages and without unhandled errors.
- **FR-014**: The system MUST preserve the user's text and selections after recoverable errors.
- **FR-015**: Partial audio from a failed or stopped session MUST be discarded and MUST NOT be offered for replay or download; the text and selections remain so the user can generate again.
- **FR-016**: The Voicebox address MUST be configurable, defaulting to the local address `http://127.0.0.1:17493`.
- **FR-017**: The system MUST NOT start its own Voicebox, load its own speech model, or send text or audio to any service other than the configured Voicebox.
- **FR-018**: The system MUST record, per generation and without storing the full text, the time to connect to Voicebox, time to first audio, time to first playable audio (measured when the browser actually starts playing), total generation time, playback interruptions, failures, cancellations and total session duration.
- **FR-019**: The system MUST by default be reachable only from the local machine.
- **FR-020**: The layout MUST remain usable on desktop and narrower screens.
- **FR-021**: The system MUST let the user replay and download the audio of the latest successfully completed session only; that audio and any temporary audio data MUST be cleaned up when the next generation starts or the session ends. Replay and download controls MUST NOT be offered for stopped or failed sessions.
- **FR-022**: The teleprompter MUST show the user's text as plain text only; markup or script-like content in the input MUST be displayed literally and never interpreted.

### Key Entities *(include if feature involves data)*

- **Voice**: A selectable speaker offered by Voicebox, with an identifier and a display label.
- **Model**: A selectable speech model offered by Voicebox, with an identifier and a display label.
- **Generation Session**: One request to speak a text with a chosen voice and model; has a state, a start time, collected timing measurements and an outcome.
- **Playback State**: Current status (playing, paused, stopped, completed, failed) and audio position for a session.
- **Teleprompter Segment**: A portion of the input text (such as a sentence) with its position, used to show the current reading location; carries whether its timing is exact or estimated.
- **Performance Record**: Timing and outcome measurements for one session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user completes the full flow (enter text, choose voice and model, hear speech) without using the command line, in under 1 minute from page load to first audio, excluding the backend's own generation time; checked by the manual procedure in quickstart.md.
- **SC-002**: For a text of at least 3 sentences, playback starts after the first chunk is ready and before the remaining chunks have finished generating; a demonstration shows start time against total generation time.
- **SC-003**: Time to first playable audio is measured for every generation and a performance target is set against the actual Voicebox and development hardware during planning, with a baseline recorded before any optimization claim. **Target (set from the 2026-10-15 baseline in research.md, qwen-tts-1.7B, Apple Silicon/MLX):** time to first playable audio is at most 20 s for a text whose first chunk is one sentence (baseline mean 10.4 s for 1 sentence, 14.8 s and 15.9 s for the first chunk of 3 and 8 sentence texts), and does not grow with total text length. Total generation time is not targeted: synthesis runs about 3 to 4 times slower than playback on this hardware, so gaps between chunks are expected and are reported as stalls.
- **SC-004**: During playback of a text near the 5,000-character limit, the highlight stays within one sentence of the spoken position in at least 95% of 20 spot checks taken at random moments (procedure in quickstart.md), and the active segment is always visible.
- **SC-005**: After each of pause, resume, stop and restart, audio and teleprompter agree in 100% of tested sequences.
- **SC-006**: For each tested failure (backend down, timeout, error response, interrupted stream, empty text), the user sees an understandable message, the text is preserved, and no unhandled error appears.
- **SC-007**: Voice and model choices shown match what Voicebox reports at the time of page load in 100% of checks.
- **SC-008**: The client runs on a standard laptop with no GPU and loads no speech model of its own.

## Assumptions

- The user already runs Voicebox locally and manages its lifecycle; this client never starts it.
- Single user on one machine; multi-user deployment, authentication and cloud hosting are out of scope.
- Voicebox capabilities were verified during planning (see research.md): it returns each chunk only after full synthesis (no incremental audio), supplies no alignment timestamps, supports cancellation only by generation id (not on the stream endpoint), and selects the model per request. The requirements above rely on the labelled sentence-chunked fallback and approximate sync for that reason.
- Input is plain text; speech-to-text, voice cloning and other Voicebox features are out of scope.
- Teleprompter segments are sentence-level by default; word-level highlighting is used only if Voicebox provides exact word timings (confirmed in clarification).
- Performance numeric targets are deferred to planning, once a baseline can be measured.
- Governing rules are in `.specify/memory/constitution.md` (v1.1.0).
