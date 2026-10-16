"""The client reports first-byte and response-complete separately, so a response that arrives
all at once is distinguishable from one that sends bytes early."""
import asyncio
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.voicebox_client import VoiceboxClient

WAV = (Path(__file__).parent.parent / "fixtures" / "tiny.wav").read_bytes()
GAP = 0.4


def build_app() -> FastAPI:
    app = FastAPI()

    @app.post("/generate/stream")
    async def gen(body: dict):
        async def delayed_whole():          # simulated: nothing, then everything
            await asyncio.sleep(GAP)
            yield WAV

        async def incremental():            # real streaming: bytes early, rest later
            yield WAV[:200]
            await asyncio.sleep(GAP)
            yield WAV[200:]

        gen_ = incremental() if body["text"] == "early" else delayed_whole()
        return StreamingResponse(gen_, media_type="audio/wav")

    return app


@pytest.fixture
async def server():
    cfg = uvicorn.Config(build_app(), host="127.0.0.1", port=0, log_level="error")
    srv = uvicorn.Server(cfg)
    task = asyncio.create_task(srv.serve())
    while not srv.started:
        await asyncio.sleep(0.02)
    port = srv.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    await task


def is_incremental(res) -> bool:
    return res.complete_s - res.first_byte_s > GAP / 2


async def test_delayed_whole_body_is_non_incremental(server):
    res = await VoiceboxClient(server).synthesize_chunk("late", "p", "en", "qwen", "0.6B")
    assert res.first_byte_s >= GAP * 0.8
    assert not is_incremental(res)


async def test_early_bytes_classified_incremental(server):
    res = await VoiceboxClient(server).synthesize_chunk("early", "p", "en", "qwen", "0.6B")
    assert res.first_byte_s < GAP / 2
    assert is_incremental(res)
