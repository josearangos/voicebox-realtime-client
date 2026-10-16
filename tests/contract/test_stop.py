import asyncio

import httpx

from app.chunking import make_chunks
from app.pipeline import ChunkPipeline
from app.server import create_api
from app.session import SessionRegistry

TEXT = "First sentence is here. Second sentence is here. Third sentence is here."


class SlowClient:
    def __init__(self):
        self.cancelled = False
        self.started = asyncio.Event()

    async def synthesize_chunk(self, *a):
        self.started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled = True        # the in-flight request was aborted
            raise


async def test_stop_aborts_in_flight_and_chunk_returns_409():
    reg = SessionRegistry()
    s = reg.get("sess")
    s.transition("loading"); s.transition("generating")
    client = SlowClient()
    s.chunks = make_chunks(TEXT)
    s.pipeline = ChunkPipeline(s, client, s.chunks, TEXT)
    s.pipeline.start()
    api = create_api(reg)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://t") as http:
        waiting = asyncio.create_task(http.post("/api/chunk", json={"session": "sess", "index": 0}))
        await client.started.wait()
        r = await http.post("/api/stop", json={"session": "sess"})
        assert r.status_code == 200
        assert (await waiting).status_code == 409
        assert client.cancelled and s.state == "stopped"
        r = await http.post("/api/chunk", json={"session": "sess", "index": 0})
        assert r.status_code == 409
        assert s.audio == {}                       # chunk audio discarded


async def test_routes_validate_input():
    reg = SessionRegistry()
    api = create_api(reg)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://t") as http:
        assert (await http.post("/api/chunk", json={"session": "nope", "index": 0})).status_code == 404
        assert (await http.post("/api/chunk", content=b"not json")).status_code == 404
        assert (await http.post("/api/metrics", json={"session": "nope", "event": "x", "t": 1})).status_code == 404
        assert (await http.get("/api/audio?session=nope")).status_code == 404
