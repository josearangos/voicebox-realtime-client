"""T047 spike: Gradio Blocks mounted in FastAPI on 127.0.0.1 with custom routes + static JS.

Checks (over real HTTP against a uvicorn server): (a) POST /api/ping works, (b) /static/player.js is
served and the page HTML loads it, (c) the page script can call /api/ping (needs a browser; this
script verifies (a)+(b) and that the page head contains the script tag; the in-page call is
confirmed during quickstart scenario 2/11).
"""
import threading
import time
from pathlib import Path

import gradio as gr
import httpx
import uvicorn
from fastapi import FastAPI

STATIC = Path(__file__).parent / "_spike_static"


def build() -> FastAPI:
    STATIC.mkdir(exist_ok=True)
    (STATIC / "player.js").write_text(
        "fetch('/api/ping',{method:'POST'}).then(r=>r.json()).then(j=>{window.__ping=j});")
    from fastapi.staticfiles import StaticFiles
    api = FastAPI()

    @api.post("/api/ping")
    async def ping():
        return {"ok": True}

    api.mount("/static", StaticFiles(directory=STATIC), name="static")
    with gr.Blocks() as demo:
        gr.Markdown("spike")
    return gr.mount_gradio_app(api, demo, path="/",
                               head='<script src="/static/player.js" defer></script>')


if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(build(), host="127.0.0.1", port=7899, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.2)
    base = "http://127.0.0.1:7899"
    ping = httpx.post(f"{base}/api/ping")
    js = httpx.get(f"{base}/static/player.js")
    page = httpx.get(f"{base}/")
    print("gradio", gr.__version__)
    print("(a) POST /api/ping:", ping.status_code, ping.json())
    print("(b) static player.js:", js.status_code, "| page loads it:", "/static/player.js" in page.text)
    server.should_exit = True
