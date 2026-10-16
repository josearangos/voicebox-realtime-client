import asyncio
import re

import pytest

from app.errors import VoiceboxFailed
from app.pipeline import ChunkPipeline, ChunkStopped, EndOfStream, concat_wavs
from app.session import GenerationSession
from app.voicebox_client import ChunkAudio, wav_duration

from pathlib import Path

WAV = (Path(__file__).parent.parent / "fixtures" / "tiny.wav").read_bytes()
TEXT = ("This is the first sentence of the test. This is the second sentence of the test. "
        "And here is the third sentence of the test. Finally the fourth sentence arrives.")


async def words(text, gate: asyncio.Event | None = None):
    for m in re.finditer(r"\S+\s*", text):
        if gate is not None:
            await gate.wait()
        yield m.group()
        await asyncio.sleep(0)


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


def make(client, gate=None):
    s = GenerationSession()
    s.state = "generating"
    s.text = TEXT
    return s, ChunkPipeline(s, client, words(TEXT, gate))


async def settle():
    for _ in range(100):
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
    i = 2
    while True:
        try:
            await p.get_chunk(i)
        except EndOfStream:
            break
        i += 1
    await p.task
    assert len(p.chunks) >= 3 and i == len(p.chunks)
    assert p.requested_log == list(range(len(p.chunks)))
    assert " ".join(p.texts) == TEXT
    assert s.received_all and s.completed_audio


async def test_first_chunk_is_requested_before_stream_ends():
    gate = asyncio.Event()
    fake = FakeClient()
    s, p = make(fake, gate)
    p.start()
    await settle()
    assert fake.calls == []                       # no words yet, nothing to speak
    gate.set()
    await p.get_chunk(0)
    assert fake.calls[0] == "This is the first sentence of"   # hard cap: 6 words
    assert TEXT[p.chunks[0].char_start:p.chunks[0].char_end] == "This is the first sentence of"
    assert p.chunks[0].segments[0].text == "This"
    await p.stop()


def test_is_last_only_after_stream_ends():
    s, p = make(FakeClient())
    p.texts = ["a", "b"]
    assert not p.is_last(1)
    p.feed_done = True
    assert p.is_last(1) and not p.is_last(0)


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
