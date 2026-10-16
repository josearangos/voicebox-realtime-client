"""Research D3: does Voicebox stop synthesizing when the client disconnects?

Records the observation; it does not assert either outcome, because the finding is documented
as a limitation if synthesis continues.
"""
import asyncio
import time

import httpx
import pytest

from app import config
from app.voicebox_client import VoiceboxClient

pytestmark = pytest.mark.voicebox

LONG = ("The history of the lighthouse is a story of patience and stubborn light. " * 6).strip()


async def active_tasks(http) -> object:
    return (await http.get("/tasks/active")).json()


async def test_disconnect_cancel_behaviour():
    c = VoiceboxClient()
    voices, models = await c.list_voices(), await c.list_models()
    model = next((m for m in models if m.loaded), models[0])
    body = {"profile_id": voices[0].id, "text": LONG, "language": voices[0].language,
            "engine": model.engine, "model_size": model.model_size}
    async with httpx.AsyncClient(base_url=config.VOICEBOX_URL, timeout=30) as http:
        before = await active_tasks(http)
        req = asyncio.create_task(http.post("/generate/stream", json=body, timeout=60))
        await asyncio.sleep(4)
        during = await active_tasks(http)
        req.cancel()                              # abort the in-flight request
        await asyncio.gather(req, return_exceptions=True)
        # /tasks/active did not list the /generate/stream synthesis, so use timing as evidence: a
        # short request right after the abort is slow if Voicebox is still busy with the long one.
        short = dict(body, text="Short check sentence.")
        async def timed() -> float:
            t = time.monotonic()
            r = await http.post("/generate/stream", json=short, timeout=300)
            assert r.status_code == 200
            return time.monotonic() - t
        after_abort = await timed()
        baseline = await timed()
    print(f"\nactive before={before}\nactive during={during}")
    print(f"short request after abort: {after_abort:.1f}s; same request on idle server: {baseline:.1f}s")
