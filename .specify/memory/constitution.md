<!--
Sync Impact Report
Version change: (unversioned template) → 1.1.0
Modified principles: none renamed (initial adoption; all placeholders replaced)
Added sections: Project Mission, Principles I–X, Development and Technology Constraints
  (3.1 Required Technology, 3.2 Backend Discovery, 3.3 Scope Boundaries),
  Spec-Driven Development Workflow, Definition of Done, Initial Project Decisions,
  Final Constitutional Principle, Governance
Removed sections: none
Follow-up TODOs: none. Version supplied by the user as 1.1.0 and used as-is.
-->
# Voicebox Realtime Client Constitution

Project Type: Spec-Driven Development (SDD) | Primary Framework: Gradio
Backend: https://github.com/jamiepine/voicebox
Local API Base URL: http://127.0.0.1:17493 | API Documentation: http://127.0.0.1:17493/docs
Target Environment: Local development on macOS and compatible Python environments

## Project Mission

Build a lightweight, responsive Gradio application that acts as a real-time client for an
existing Voicebox text-to-speech (TTS) backend.

Users must be able to enter text, select an available voice and TTS model, generate speech,
listen to audio as it becomes available, and follow the text in a teleprompter that simulates
reading progress during playback.

The application MUST consume the existing Voicebox API rather than reimplementing its TTS engine.

The primary objective is to deliver the lowest practical end-to-end latency while preserving
audio quality, API compatibility, predictable resource consumption, and a useful user experience.

The AI coding agent MUST inspect the existing Voicebox implementation and its live API
documentation before making backend integration decisions. It MUST independently determine which
endpoints and communication mechanisms best satisfy the application's requirements, and MUST NOT
assume that particular endpoints, streaming protocols, or synchronization capabilities exist
without verification.

## Core Principles

### I. API-First Integration

The existing Voicebox backend is the single source of truth for TTS generation, available voices,
supported models, and generation parameters.

- The implementation MUST inspect the live API documentation at http://127.0.0.1:17493/docs
  before selecting endpoints or designing API integrations.
- The implementation MUST use the actual request schemas, response formats, parameter names, and
  streaming capabilities documented by the backend.
- The application MUST retrieve available voices and models dynamically whenever the API supports
  their discovery.
- The application MUST NOT hardcode voice lists, model identifiers, or undocumented request
  parameters when they can be discovered through the API.
- The application MUST NOT assume that an endpoint supports streaming simply because it returns
  audio.
- If the backend does not expose a required capability, the implementation MUST document the
  limitation rather than inventing an endpoint or silently substituting behavior.
- API access MUST be isolated behind a dedicated client or service layer.
- The AI coding agent MUST select endpoints based on verified capabilities and the application's
  functional requirements, not on assumptions or arbitrary preferences.

Acceptance criterion: Every backend operation used by the application maps to a verified Voicebox
API operation or is explicitly documented as an unsupported capability.

### II. Real-Time Audio Is a First-Class Requirement

The system MUST prioritize perceived responsiveness and incremental audio delivery over
unnecessary architectural complexity.

- The application MUST begin audio playback as soon as sufficient valid audio data is available,
  subject to the backend protocol and playback requirements.
- The application MUST prefer genuine incremental streaming over waiting for the complete audio
  file.
- The application MUST NOT describe a complete-file download followed by playback as real-time
  streaming.
- Audio buffering MUST balance low startup latency against interruptions and playback stability.
- Network, synthesis, buffering, and playback delays SHOULD be measured separately whenever the
  architecture allows.
- The implementation MUST avoid unnecessary audio conversions, disk writes, polling, and data
  copies in the critical playback path.
- Audio chunks MUST be processed in their correct order and according to the actual transport and
  audio format.
- If streaming is unsupported by the backend, the application MUST expose that limitation clearly
  and provide an explicitly identified fallback when feasible.
- The implementation MUST use the simplest communication mechanism that satisfies the verified
  real-time requirements.

Acceptance criterion: A test or demonstration can establish whether audio is delivered
incrementally, measure time to first playable audio, and distinguish streaming from full-response
playback.

### III. Teleprompter Progress Must Reflect Playback

The teleprompter MUST provide a clear visual representation of the text being read while audio
plays.

- The complete input text MUST remain available for the duration of the generation session.
- The interface MUST highlight or otherwise distinguish the current reading position.
- Text progression MUST be driven by audio playback timing or reliable alignment metadata, not by
  an unrelated timer.
- If the backend supplies word-level or sentence-level timestamps, the application SHOULD use them
  for accurate synchronization.
- If alignment metadata is unavailable, the application MAY estimate reading progress from
  playback duration and text segments.
- Estimated synchronization MUST NOT be presented as exact word-level alignment.
- The teleprompter MUST remain usable for long texts and automatically keep the active segment
  visible.
- Pausing, resuming, restarting, and stopping playback MUST update teleprompter behavior
  consistently.
- If playback position cannot be determined reliably, the application MUST degrade gracefully
  instead of displaying misleading progress.

Acceptance criterion: During playback, the displayed reading position advances consistently with
the audio, and playback controls do not leave the teleprompter in a contradictory state.

### IV. User Experience Must Remain Simple

The interface MUST focus on the core text-to-speech workflow:

1. Enter or paste text.
2. Select a voice from the available voices.
3. Select a supported TTS model.
4. Generate speech.
5. Listen to the audio while following the teleprompter.
6. Pause, resume, stop, or restart playback as supported.

Additional requirements:

- The text input MUST support multiline content.
- Voice and model selections MUST display meaningful labels when the API provides them.
- The interface MUST clearly indicate loading, generating, streaming, playing, completed,
  stopped, and failed states where applicable.
- The application MUST prevent conflicting generation requests or handle them explicitly.
- Errors MUST be actionable and understandable without requiring the user to inspect server logs.
- The application MUST preserve user input after recoverable errors.
- The layout MUST be usable on desktop screens and adapt reasonably to narrower screens.
- The implementation SHOULD avoid unnecessary controls, dependencies, and configuration screens.

Acceptance criterion: A user can complete the primary workflow without interacting with the command
line or manually calling backend endpoints.

### V. Maintain a Clear Separation of Responsibilities

The application MUST separate interface logic, backend communication, audio handling, and playback
progress.

The logical architecture SHOULD include:

- Presentation layer: Gradio components, text input, voice and model selectors, status indicators,
  and teleprompter.
- Voicebox client: API requests, response validation, timeouts, and error translation.
- Audio streaming layer: Incremental data handling, buffering, and playback integration.
- Session and playback state: Current request, selected configuration, playback status, and
  teleprompter position.
- Testing layer: Unit, integration, and end-to-end tests.

These are logical responsibilities, not mandatory separate packages.

- UI components MUST NOT contain duplicated HTTP request logic.
- API-specific details MUST remain outside the presentation layer.
- Session state MUST be isolated between users or browser sessions where the Gradio deployment
  model requires it.
- Long-running operations MUST NOT unnecessarily block unrelated interface interactions.
- The design MUST favor the simplest architecture that satisfies verified streaming and
  synchronization requirements.
- The architecture MUST NOT duplicate the Voicebox TTS engine or introduce a second synthesis
  backend without explicit approval.

Acceptance criterion: Backend communication and playback behavior can be tested independently of
most UI components.

### VI. Reliability and Explicit Failure Handling

The application MUST handle backend and streaming failures predictably.

- The Voicebox base URL MUST be configurable, with http://127.0.0.1:17493 as the development
  default.
- Connection errors, timeouts, HTTP errors, invalid responses, and interrupted streams MUST be
  handled explicitly.
- Requests MUST have appropriate timeout and cancellation behavior where supported.
- The application MUST validate the selected voice and model before initiating generation when the
  available API information permits validation.
- Stopping a generation MUST cancel the underlying operation when the backend and transport support
  cancellation.
- Partial audio MUST NOT be mistaken for a completed recording.
- Automatic retries MUST NOT duplicate expensive generation requests without a defined policy.
- The application MUST provide a useful message when Voicebox is unavailable.
- Error handling MUST preserve diagnostic information in logs without exposing sensitive
  information to the interface.
- If the backend cannot be reached, the application MUST report the problem and MUST NOT silently
  switch to an unrelated service.

Acceptance criterion: Expected failure scenarios produce controlled UI states and actionable
messages rather than unhandled exceptions.

### VII. Cross-Platform and Resource Efficiency

The client MUST run in a standard supported Python environment and MUST NOT require a GPU.

- The client MUST NOT introduce an independent TTS model or GPU requirement.
- The application MUST reuse the existing Voicebox backend.
- Dependencies MUST be limited to those justified by API communication, Gradio, streaming, audio
  playback, or testing.
- The implementation SHOULD support Apple Silicon macOS and other environments supported by its
  dependencies.
- Audio data SHOULD be streamed or buffered in memory where practical.
- Temporary audio files MUST be managed explicitly and cleaned up when no longer needed.
- Resource consumption SHOULD remain bounded during long sessions and repeated generations.
- The application MUST NOT launch a duplicate Voicebox instance as part of its normal startup
  workflow.

Acceptance criterion: The client can run without GPU-specific dependencies and without loading a
second TTS model into its own process.

### VIII. Testability and Verifiable Quality

Every critical behavior MUST have a defined verification strategy.

- Unit tests MUST cover API client behavior, response parsing, state transitions, and teleprompter
  progress calculations.
- Integration tests MUST validate the client against the real Voicebox API when the backend is
  available.
- Tests MUST cover backend unavailability, malformed responses, interrupted streams, empty input,
  and unsupported selections.
- Streaming behavior MUST be tested independently from the correctness of the generated speech.
- Tests MUST distinguish between actual streaming and simulated streaming.
- External API tests SHOULD be complemented by deterministic mocks or fixtures so that development
  does not always require a running backend.
- Test results MUST NOT depend on access to a GPU or external paid TTS services.
- Changes MUST NOT be considered complete solely because the application starts successfully.
- API endpoint selection and request/response handling MUST be validated against the actual backend
  whenever possible.

Acceptance criterion: Critical requirements have reproducible tests or documented manual
verification procedures.

### IX. Observability and Measurable Performance

The system MUST make latency and operational problems observable.

Where technically measurable, the application SHOULD record:

- Time to establish a backend connection.
- Time from generation request to first audio data.
- Time to first playable audio.
- Total generation duration.
- Audio playback interruptions or buffer underruns.
- Request failures and cancellations.
- Total session duration.

Further rules:

- Performance measurements MUST use consistent definitions and distinguish backend synthesis
  latency from client-side processing and playback latency.
- Logs MUST avoid recording the complete user text or generated audio by default.
- Performance optimizations MUST be based on measurements rather than assumptions.
- The project MUST establish baseline measurements before claiming that a change improves
  real-time performance.
- Performance targets MUST be defined and validated during specification and planning against the
  capabilities of the actual Voicebox backend and development hardware.

Acceptance criterion: A repeatable test can measure time to first playable audio and total
playback behavior under documented conditions.

### X. Security and Local-First Defaults

The initial application is a local client for a local backend.

- The default backend address MUST remain 127.0.0.1:17493.
- The application MUST NOT expose Voicebox or Gradio to external networks by default.
- Debug mode MUST NOT be enabled by default in a production deployment.
- User-provided text MUST be treated as untrusted input.
- The application MUST NOT execute pasted text as code or shell commands.
- Error messages and logs MUST NOT expose credentials, authorization headers, or other secrets.
- Any future remote deployment MUST explicitly review authentication, access control, network
  exposure, and data retention.
- The application MUST NOT transmit user text or audio to unrelated external services.
- The application MUST NOT assume that a localhost address is reachable from a container or remote
  coding agent.

Acceptance criterion: A default local installation operates without intentionally exposing the
backend or sending text to an unrelated third-party service.

## Development and Technology Constraints

### Required Technology

- Language: Python.
- Frontend: Gradio.
- TTS backend: Existing Voicebox instance.
- API contract: Live Voicebox OpenAPI specification and verified endpoint behavior.
- Development methodology: Spec-Driven Development using GitHub Spec Kit.
- Version control: Git.
- Primary execution environment: Developer's local machine.

### Local Voicebox Backend Discovery and Endpoint Selection

The Voicebox API is already running locally on the developer's machine at
http://127.0.0.1:17493, with documentation at http://127.0.0.1:17493/docs. The API documentation
MUST be inspected before implementation begins. The AI coding agent MUST explore the available
endpoints and independently select the most appropriate ones for the application.

The agent MUST:

1. Access and inspect the live API documentation.
2. Explore available endpoints, HTTP methods, request schemas, response schemas, and supported
   parameters.
3. Identify the endpoints responsible for listing available voices, listing or selecting TTS
   models, and generating speech.
4. Investigate whether the API supports HTTP streaming, WebSockets, server-sent events, or another
   documented transport mechanism.
5. Determine whether generation responses contain raw audio, encoded audio, file URLs, incremental
   chunks, or another representation.
6. Investigate whether the API exposes word-level timestamps, sentence alignment, playback
   metadata, or generation cancellation.
7. Identify supported audio codecs, sample rates, channel formats, and other relevant audio
   parameters.
8. Evaluate the available endpoints against the application's requirements for real-time playback,
   voice selection, model selection, and teleprompter synchronization.
9. Select the most appropriate endpoints and communication mechanisms based on verified
   capabilities.
10. Validate the selected endpoints against the running local backend before finalizing the
    implementation plan.
11. Document the endpoint selection, request and response formats, streaming capabilities,
    limitations, and architectural rationale.
12. Implement the integration using the verified API contract.
13. Revalidate the integration when the selected API behavior changes or an implementation
    assumption is found to be incorrect.

The agent MUST prefer existing documented endpoints over creating new endpoints, modifying
Voicebox, or implementing unnecessary workarounds.

The agent MUST NOT:

- Invent endpoints, methods, parameters, request fields, or response formats.
- Assume that an endpoint supports streaming without verification.
- Hardcode available voices or models when the backend provides a discovery mechanism.
- Assume that audio chunks contain timing or alignment information unless documented or verified.
- Begin the main integration implementation based solely on the repository description or
  assumptions about common TTS APIs.

If the documentation or backend is inaccessible, the agent MUST report the blocker and request the
information needed to proceed. It MAY continue with backend-independent scaffolding and mocked
tests, but MUST NOT claim that the integration has been verified.

If the API cannot provide a required capability, the limitation MUST be documented in the
specification. An explicit alternative MUST be evaluated before implementation proceeds.

Acceptance criterion: Before main integration implementation begins, the agent has inspected the
local API documentation, identified the appropriate endpoints, verified their capabilities, and
documented the integration strategy.

#### Development Environment and Localhost Constraint

The address 127.0.0.1 refers to the loopback interface of the machine or execution environment
making the request.

- The agent MUST verify that the environment running the Gradio client can reach the developer's
  Voicebox instance.
- If both applications run directly on the same machine, the configured local address SHOULD work
  without additional network configuration.
- If the client runs inside a container, the agent MUST determine the correct host-access
  configuration.
- If the agent runs in a remote environment, it MUST NOT assume that the developer's localhost is
  accessible remotely.
- Any networking workaround MUST be documented and MUST avoid unnecessarily exposing the Voicebox
  API to external networks.
- The application MUST allow the backend base URL to be configured through an appropriate
  environment variable or configuration setting.
- The development setup MUST NOT automatically start another Voicebox instance because one is
  already running on the developer's machine.

### Scope Boundaries

The initial version MUST focus on a single-user local workflow. The following are outside the
initial scope unless explicitly approved through a new specification:

- Reimplementing Voicebox's synthesis engine.
- Training or fine-tuning TTS models.
- Requiring cloud infrastructure or GPU acceleration.
- Adding authentication systems for a local-only application.
- Integrating telephony providers or SIP infrastructure.
- Building a multi-user production service.
- Implementing speech-to-text or voice cloning workflows independently of Voicebox.
- Replacing Voicebox with an unrelated TTS provider.
- Modifying the Voicebox backend to compensate for an unverified client-side assumption.

## Development Workflow and Definition of Done

All substantial features MUST follow the Spec Kit workflow:

1. Constitution: Establish project principles and non-negotiable constraints.
2. Specify: Define user stories, functional requirements, acceptance criteria, and scope.
3. Clarify: Resolve ambiguous requirements, particularly the meaning of real-time streaming and
   teleprompter synchronization.
4. Plan: Inspect the actual local API contract and choose the simplest architecture that meets the
   requirements.
5. Tasks: Produce small, testable implementation tasks with explicit dependencies.
6. Analyze: Verify consistency between the specification, plan, tasks, and constitution.
7. Implement: Implement in small increments, validating each critical capability.
8. Converge: Evaluate implementation completeness and document remaining gaps.

- The API discovery and endpoint selection process MUST be completed before the implementation
  plan is finalized.
- Optional checklist generation SHOULD be used for critical streaming, reliability, and
  synchronization requirements.
- Each feature specification MUST define observable acceptance criteria. Implementation tasks MUST
  map back to those criteria.
- The AI coding agent MUST inspect existing project files and preserve established conventions
  before making changes. It MUST NOT overwrite unrelated files or invent existing project
  structure.
- The agent SHOULD use the actual API documentation as the primary integration reference and the
  Voicebox source code as supporting evidence when additional implementation details are needed.

### Definition of Done

A release candidate is complete only when all applicable requirements below are satisfied:

- [x] The Gradio application starts using documented instructions.
- [x] The application connects to the configured Voicebox instance.
- [x] The local API documentation has been inspected.
- [x] The selected endpoints and their request/response formats have been documented.
- [x] Endpoint selection is based on verified API capabilities.
- [x] Available voices and models are populated from verified API capabilities.
- [x] Users can submit text and generate speech using valid selections.
- [x] Audio playback works with the actual backend response format.
- [ ] Incremental audio delivery is demonstrated when the backend supports it.
- [x] The teleprompter progresses during playback and handles pause, resume, stop, and restart
  appropriately.
- [x] Unsupported synchronization precision is documented honestly.
- [x] Backend errors and interrupted streams produce controlled UI states.
- [x] Unit and applicable integration tests pass.
- [x] No GPU or duplicate TTS model is required by the client.
- [x] The client can reach Voicebox from its actual execution environment.
- [x] Performance is measured using reproducible conditions.
- [x] Installation, configuration, startup, troubleshooting, and limitations are documented.
- [ ] No unresolved critical security or data-handling issue remains.

A feature MUST NOT be marked complete merely because its interface exists. Its underlying behavior
must be verified.

### Initial Project Decisions

- Backend ownership: Reuse the existing Voicebox service.
- API discovery: Inspect the live documentation and verify endpoint behavior.
- Endpoint selection: Determined by the AI coding agent after API inspection.
- Voice and model selection: Dynamic when supported by the API.
- Audio behavior: Incremental streaming whenever supported.
- Teleprompter: Playback-driven progress with honest synchronization precision.
- GPU requirement: None for the client.
- Backend startup: Managed independently of the client.
- Deployment scope: Local-first, single-user application.

### Final Principle

Build the smallest reliable client that demonstrates genuine real-time Voicebox audio playback and
a useful synchronized teleprompter without duplicating backend responsibilities. Verified behavior
MUST take precedence over assumptions. If a required capability is unavailable, the limitation and
proposed alternative MUST be documented explicitly.

## Governance

This constitution is the highest-level source of project principles and MUST guide all
specifications, implementation plans, tasks, and code reviews.

- Amendments MUST be made through the Spec Kit constitution workflow.
- Constitution changes MUST include a version update, a rationale for the change, identification
  of affected principles and requirements, an assessment of compatibility with existing
  specifications and implementation, and a record of any required follow-up work.
- Versioning follows semantic principles: MAJOR for incompatible changes to established principles
  or project governance; MINOR for new principles or materially expanded requirements; PATCH for
  clarifications and corrections that do not change the intended obligations.
- When a specification or implementation conflicts with this constitution, the conflict MUST be
  resolved explicitly rather than silently ignoring the governing principle.
- All plans and reviews MUST verify compliance with the principles above.
- The project MUST prefer verified facts, simple designs, measurable outcomes, and transparent
  limitations over speculative implementation choices.

**Version**: 1.1.0 | **Ratified**: 2026-10-15 | **Last Amended**: 2026-10-15
