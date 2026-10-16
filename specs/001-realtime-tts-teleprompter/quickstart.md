# Quickstart / Validation Guide

Prerequisites: Voicebox running at `http://127.0.0.1:17493` (started independently, never by this
client), Python 3.13 (the pinned Gradio declares support up to 3.13; the default `python3` here is 3.14), at least one voice profile and one downloaded TTS model in Voicebox.

## Setup (once implemented)
```text
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export VOICEBOX_URL=http://127.0.0.1:17493   # optional, this is the default
python -m app          # serves on 127.0.0.1 only
```

## Validation scenarios

1. **Connection and discovery**: open the page. Expect voice and model dropdowns filled from
   Voicebox (compare with `curl http://127.0.0.1:17493/profiles` and `/models/status`). With
   Voicebox stopped, expect the "can't be reached" message and preserved text.
2. **Primary flow**: three sentences, any voice/model, press Generate. Expect state to go
   generating → playing, audio to start after the first chunk (not the whole text), highlight to
   advance with the audio, state `completed`.
3. **Mode honesty**: a one-sentence text must show "full response"; multi-sentence shows
   "sentence-chunked". Neither is labelled "real-time streaming".
4. **Controls**: pause/resume/stop/restart; highlight and audio agree each time. Restart after
   completion replays without a new request; after stop it regenerates.
5. **Conflicts**: Generate is disabled while a session is active.
6. **Failures**: empty text, text over 5,000 chars, Voicebox stopped mid-session, unsupported
   selection: each gives a clear message, text preserved, no partial audio offered.
7. **Cancel check (D3)**: start a long generation, press Stop, then
   `curl http://127.0.0.1:17493/tasks/active` and record whether synthesis stopped.
8. **Time to first audio (SC-001)**: with a stopwatch, from page load to first audio for a
   3-sentence text; subtract the generation time shown in the status line.
9. **Highlight accuracy (SC-004)**: play a text near 5,000 characters; at 20 random moments
   pause, and note whether the highlighted sentence is the one being spoken or an adjacent one.
   Pass: at least 19 of 20 are within one sentence.
10. **Plain-text display**: enter `<b>bold</b> <script>alert(1)</script>` and confirm it appears
    literally in the teleprompter and nothing runs.
11. **Narrow screen and tabs**: resize the window to about 400 px wide and confirm the controls
    and teleprompter remain usable; open a second tab and confirm sessions do not interfere.
12. **Baseline**: `python scripts/measure.py --runs 5` prints time to first playable audio and
   total generation per text length, with hardware and model noted. Record results in
   `research.md` before claiming any improvement.

## Automated checks
```text
pytest tests/unit tests/contract          # no backend needed (mocks)
pytest tests/integration -m voicebox      # needs the running Voicebox
```
