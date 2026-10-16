import asyncio

import pytest

from app.chunking import make_chunks
from app.errors import VoiceboxFailed
from app.pipeline import ChunkPipeline, ChunkStopped, concat_wavs, mode_for
from app.session import GenerationSession
from app.voicebox_client import ChunkAudio, wav_duration

from pathlib import Path

WAV = (Path(__file__).parent.parent / "fixtures" / "tiny.wav").read_bytes()
TEXT = ("This is the first sentence of the test. This is the second sentence of the test. "
        "And here is the third sentence of the test. Finally the fourth sentence arrives.")


class FakeClient:
    def __init__(self, fail_at=None, delay=0.0):
        self.calls, self.fail_at, self.delay = [], fail_at, delay

    async def synthesize_chunk(self, text, voice, lang, engine, size):
        idx = len(self.calls)
        self.calls.append(text)
        await asyncio.sleep(self.delay)
        if self.fail_at == idx:
            raise VoiceboxFailed()
        return ChunkAudio(WAV, 0.1, 0.0, 0.0, 0.0)


def make(client):
    s = GenerationSession()
    s.state = "generating"
    chunks = make_chunks(TEXT)
    assert len(chunks) >= 3
    return s, ChunkPipeline(s, client, chunks, TEXT)


async def settle():
    for _ in range(10):
        await asyncio.sleep(0)


async def test_prefetch_one_ahead_and_order():
    fake = FakeClient()
    s, p = make(fake)
    p.start()
    await settle()
    assert p.requested_log == [0]                 # chunk 0 starts at once; chunk 1 waits
    await p.get_chunk(0)
    await settle()
    assert p.requested_log == [0, 1]              # chunk 1 requested while chunk 0 plays
    await p.get_chunk(1)
    await settle()
    assert p.requested_log == [0, 1, 2]
    for i in range(2, len(p.chunks)):
        await p.get_chunk(i)
    await p.task
    assert p.requested_log == list(range(len(p.chunks)))
    assert s.received_all and s.completed_audio


def test_mode_labels():
    assert mode_for(1) == "full-response"
    assert mode_for(2) == "sentence-chunked"
    assert mode_for(5) == "sentence-chunked"


async def test_mid_session_failure():
    s, p = make(FakeClient(fail_at=1))
    p.start()
    await p.get_chunk(0)
    with pytest.raises(VoiceboxFailed):
        await p.get_chunk(1)
    assert s.state == "failed" and s.audio == {} and s.completed_audio is None
    assert s.error == "Voicebox failed while generating. Try again."


async def test_stop_cancels_in_flight():
    fake = FakeClient(delay=5)
    s, p = make(fake)
    p.start()
    waiter = asyncio.create_task(p.get_chunk(0))
    await settle()
    await p.stop()
    with pytest.raises(ChunkStopped):
        await waiter
    assert p.task.done()


def test_concat_wavs():
    joined = concat_wavs([WAV, WAV])
    assert wav_duration(joined) == pytest.approx(0.2)
