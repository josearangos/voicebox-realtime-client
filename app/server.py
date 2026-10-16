"""Gradio UI plus the local chunk/stop/metrics routes. No HTTP-to-Voicebox code lives here."""
import asyncio
import html
import logging
from pathlib import Path

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config
from .chunking import make_chunks
from .errors import VoiceboxError
from .metrics import PerformanceRecord
from .pipeline import ChunkPipeline, ChunkStopped, mode_for
from .session import GenerationSession, InvalidTransition, SessionRegistry, registry, validate_request
from .teleprompter import render_html
from .voicebox_client import VoiceboxClient

log = logging.getLogger("voicebox_client.server")
STATIC = Path(__file__).parent / "static"
MODE_LABEL = {"sentence-chunked": "sentence-chunked", "full-response": "full response"}


# --------------------------------------------------------------------------- local routes
def create_api(reg: SessionRegistry = registry) -> FastAPI:
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    async def body(req: Request) -> dict:
        try:
            data = await req.json()
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    def lookup(data: dict) -> GenerationSession | None:
        sid = data.get("session")
        return reg.find(sid) if isinstance(sid, str) else None

    @api.post("/api/chunk")
    async def chunk(req: Request):
        data = await body(req)
        s = lookup(data)
        index = data.get("index")
        if s is None or s.pipeline is None:
            return JSONResponse({"error": "Unknown session."}, status_code=404)
        if not isinstance(index, int) or isinstance(index, bool):
            return JSONResponse({"error": "Invalid chunk index."}, status_code=400)
        if s.state == "stopped" or s.stop_event.is_set():
            return JSONResponse({"error": "Session stopped."}, status_code=409)
        try:
            wav, duration = await s.pipeline.get_chunk(index)
        except IndexError:
            return JSONResponse({"error": "Invalid chunk index."}, status_code=400)
        except ChunkStopped:
            return JSONResponse({"error": "Session stopped."}, status_code=409)
        except VoiceboxError as e:
            return JSONResponse({"error": e.message}, status_code=502)
        return Response(wav, media_type="audio/wav",
                        headers={"X-Duration": f"{duration:.4f}", "Cache-Control": "no-store"})

    @api.post("/api/stop")
    async def stop(req: Request):
        s = lookup(await body(req))
        if s is None:
            return JSONResponse({"error": "Unknown session."}, status_code=404)
        await stop_session(s)
        return {"ok": True}

    @api.post("/api/metrics")
    async def metrics(req: Request):
        data = await body(req)
        s = lookup(data)
        event, t = data.get("event"), data.get("t")
        if s is None or s.metrics is None:
            return JSONResponse({"error": "Unknown session."}, status_code=404)
        if not isinstance(event, str) or not isinstance(t, (int, float)) or isinstance(t, bool):
            return JSONResponse({"error": "Invalid event."}, status_code=400)
        if not s.metrics.browser_event(event, float(t)):
            return JSONResponse({"error": "Invalid event."}, status_code=400)
        try:
            if event == "play_start" and s.state == "generating":
                s.transition("playing" if s.received_all else "streaming")
            elif event == "ended" and s.state in ("playing", "streaming", "paused", "generating"):
                s.transition("completed")
                s.metrics.finish("completed")
        except InvalidTransition:
            pass
        return {"ok": True}

    @api.post("/api/state")
    async def state(req: Request):
        data = await body(req)
        s = lookup(data)
        action = data.get("action")
        if s is None:
            return JSONResponse({"error": "Unknown session."}, status_code=404)
        try:
            if action == "pause" and s.active:
                s.transition("paused")
            elif action == "resume" and s.state == "paused":
                s.transition("playing" if s.received_all else "streaming")
            elif action == "replay" and s.state == "completed":
                s.transition("playing")
            elif action not in ("pause", "resume", "replay"):
                return JSONResponse({"error": "Invalid action."}, status_code=400)
        except InvalidTransition:
            pass
        return {"ok": True, "state": s.state}

    @api.get("/api/audio")
    async def audio(session: str = ""):
        s = reg.find(session)
        if s is None or s.completed_audio is None or s.state not in ("completed", "playing"):
            return JSONResponse({"error": "No completed audio."}, status_code=404)
        return Response(s.completed_audio, media_type="audio/wav", headers={
            "Content-Disposition": 'attachment; filename="speech.wav"', "Cache-Control": "no-store"})

    api.mount("/vb-static", StaticFiles(directory=STATIC), name="static")
    return api


async def stop_session(s: GenerationSession) -> None:
    if s.pipeline is not None:
        await s.pipeline.stop()
    if s.state in ("loading", "generating", "streaming", "playing", "paused"):
        try:
            s.transition("stopped")
        except InvalidTransition:
            pass
        if s.metrics and s.metrics.outcome is None:
            s.metrics.finish("stopped")


# --------------------------------------------------------------------------- UI helpers
def status_html(s: GenerationSession | None, note: str = "", unavailable: bool = False) -> str:
    state = s.state if s else "idle"
    parts = [f'<div class="vb-status" data-state="{html.escape(state)}">']
    if unavailable:
        parts.append('<b>Voicebox unavailable</b>')
    else:
        parts.append(f'State: <b>{html.escape(state)}</b>')
        if s and s.chunks:
            parts.append(f' · Mode: <b>{MODE_LABEL[s.mode]}</b>')
    parts.append(' <span id="vb-buffering"></span>')
    if s and s.error:
        parts.append(f'<div class="vb-error">{html.escape(s.error)}</div>')
    if note:
        parts.append(f'<div class="vb-note">{html.escape(note)}</div>')
    if s and s.active:
        parts.append('<div class="vb-note">Generate is unavailable while a session is active. '
                     'Press Stop to cancel.</div>')
    parts.append("</div>")
    return "".join(parts)


def teleprompter_wrap(s: GenerationSession | None, text: str = "") -> str:
    if s is None or not s.chunks:
        return '<div id="vb-meta" data-run=""></div><div class="vb-tp-empty">The teleprompter appears here.</div>'
    meta = (f'<div id="vb-meta" data-run="{html.escape(s.id)}-{id(s.chunks)}" '
            f'data-session="{html.escape(s.id)}" data-chunks="{len(s.chunks)}" '
            f'data-mode="{html.escape(s.mode)}"></div>')
    return (meta + '<div class="vb-approx">Highlight sync is approximate (sentence level).</div>'
            + render_html(text, s.chunks))


def build_ui(client: VoiceboxClient, reg: SessionRegistry = registry) -> gr.Blocks:
    def lock(s: GenerationSession | None, note: str = "", unavailable: bool = False):
        free = s is None or s.can_generate
        return (gr.update(interactive=free and not unavailable), gr.update(interactive=free),
                gr.update(interactive=free), gr.update(interactive=free),
                status_html(s, note, unavailable))

    async def discover(request: gr.Request):
        s = reg.find(request.session_hash)
        try:
            voices, models = await asyncio.gather(client.list_voices(), client.list_models())
        except VoiceboxError as e:
            return (gr.update(choices=[]), gr.update(choices=[]),
                    status_html(s, e.message, unavailable=True), gr.update(visible=True),
                    gr.update(interactive=False))
        note = "" if voices and models else "Voicebox has no voices or no downloaded TTS models."
        return (gr.update(choices=[(v.label, v.id) for v in voices],
                          value=voices[0].id if voices else None),
                gr.update(choices=[(m.display_name, m.model_name) for m in models],
                          value=(next((m for m in models if m.loaded), models[0]).model_name
                                 if models else None)),
                status_html(s, note), gr.update(visible=False),
                gr.update(interactive=bool(voices and models)))

    async def generate(text: str, voice_id: str, model_name: str, request: gr.Request):
        s = reg.get(request.session_hash)
        tp = teleprompter_wrap(s, text)
        if not s.can_generate:
            return (*lock(s, "A session is already active."), tp)
        try:
            voices, models = await asyncio.gather(client.list_voices(), client.list_models())
        except VoiceboxError as e:
            s.error = e.message
            return (*lock(s, e.message, unavailable=True), tp)
        msg = validate_request(text or "", voice_id, model_name, {v.id for v in voices},
                               {m.model_name for m in models}, config.MAX_TEXT_CHARS)
        if msg:
            s.error = None
            return (*lock(s, msg), tp)
        if s.pipeline is not None:
            await s.pipeline.stop()
        voice = next(v for v in voices if v.id == voice_id)
        model = next(m for m in models if m.model_name == model_name)
        s.reset_for_new_run()
        s.text, s.voice_id, s.language = text, voice.id, voice.language
        s.engine, s.model_size = model.engine, model.model_size
        s.chunks = make_chunks(text)
        s.mode = mode_for(len(s.chunks))
        s.metrics = PerformanceRecord(s.id, len(text))
        s.pipeline = ChunkPipeline(s, client, s.chunks, text)
        s.transition("generating")
        s.pipeline.start()
        return (*lock(s), teleprompter_wrap(s, text))

    async def sync(request: gr.Request):
        return lock(reg.find(request.session_hash))

    async def on_unload(request: gr.Request):
        s = reg.find(request.session_hash)
        if s is not None:
            await stop_session(s)
            reg.drop(s.id)

    with gr.Blocks(title="Voicebox Realtime Client") as demo:
        gr.Markdown("# Voicebox Realtime Client\nSentence-chunked speech with a teleprompter. "
                    "Audio for each chunk starts as soon as that chunk is ready.")
        status = gr.HTML(status_html(None), elem_id="vb-status")
        with gr.Row():
            voice_dd = gr.Dropdown(label="Voice", choices=[], interactive=True, elem_id="vb-voice")
            model_dd = gr.Dropdown(label="Model", choices=[], interactive=True, elem_id="vb-model")
            retry = gr.Button("Retry", visible=False, elem_id="vb-retry")
        text = gr.Textbox(label=f"Text (max {config.MAX_TEXT_CHARS:,} characters)", lines=6,
                          elem_id="vb-text")
        generate_btn = gr.Button("Generate", variant="primary", interactive=False, elem_id="vb-generate")
        with gr.Row(elem_id="vb-controls"):
            gr.Button("Pause", interactive=False, elem_id="vb-pause")
            gr.Button("Stop", interactive=False, elem_id="vb-stop")
            gr.Button("Restart", interactive=False, elem_id="vb-restart")
            gr.Button("Replay", interactive=False, elem_id="vb-replay")
            gr.Button("Download", interactive=False, elem_id="vb-download")
        tp = gr.HTML(teleprompter_wrap(None), elem_id="vb-tp-wrap")
        with gr.Row(elem_id="vb-hidden"):
            sync_btn = gr.Button("sync", elem_id="vb-sync")

        lock_out = [generate_btn, text, voice_dd, model_dd, status]
        disc_out = [voice_dd, model_dd, status, retry, generate_btn]
        demo.load(discover, None, disc_out, show_progress="hidden")
        retry.click(discover, None, disc_out, show_progress="hidden")
        generate_btn.click(generate, [text, voice_dd, model_dd], lock_out + [tp], show_progress="hidden")
        sync_btn.click(sync, None, lock_out, show_progress="hidden", api_name=False)
        demo.unload(on_unload)
    return demo


def build_app(client: VoiceboxClient | None = None) -> FastAPI:
    client = client or VoiceboxClient()
    api = create_api()
    demo = build_ui(client)
    return gr.mount_gradio_app(
        api, demo, path="/", server_name=config.HOST, server_port=config.PORT,
        css_paths=STATIC / "app.css", head='<script src="/vb-static/player.js?v=1" defer></script>')
