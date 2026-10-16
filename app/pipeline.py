"""Ordered chunk synthesis with one chunk prefetched ahead of playback."""
import asyncio
import io
import logging
import struct
import time

from .chunking import Chunk
from .errors import VoiceboxError, VoiceboxFailed
from .session import GenerationSession, InvalidTransition

log = logging.getLogger("voicebox_client.pipeline")


class ChunkStopped(Exception):
    """The session was stopped while waiting for a chunk."""


def mode_for(n_chunks: int) -> str:
    return "sentence-chunked" if n_chunks >= 2 else "full-response"


def concat_wavs(wavs: list[bytes]) -> bytes:
    """Join PCM WAVs of identical format into one WAV."""
    if len(wavs) == 1:
        return wavs[0]
    pcm = bytearray()
    fmt = None
    for w in wavs:
        pos = 12
        while pos + 8 <= len(w):
            cid, size = w[pos:pos + 4], struct.unpack("<I", w[pos + 4:pos + 8])[0]
            if cid == b"fmt ":
                fmt = fmt or w[pos + 8:pos + 8 + size]
            elif cid == b"data":
                pcm.extend(w[pos + 8:pos + 8 + size])
                break
            pos += 8 + size + (size & 1)
    out = io.BytesIO()
    out.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<I", len(fmt)))
    out.write(fmt)
    out.write(b"data" + struct.pack("<I", len(pcm)))
    out.write(bytes(pcm))
    return out.getvalue()


class ChunkPipeline:
    def __init__(self, session: GenerationSession, client, chunks: list[Chunk], text: str):
        self.session = session
        self.client = client
        self.chunks = chunks
        self.texts = [text[c.char_start:c.char_end] for c in chunks]
        self.failure: VoiceboxError | None = None
        self.stopped = False
        self.task: asyncio.Task | None = None
        self._max_requested = -1
        self._cv = asyncio.Condition()
        self._ready = [asyncio.Event() for _ in chunks]
        self.requested_log: list[int] = []     # order in which synthesis was requested

    def start(self) -> None:
        self.task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        s = self.session
        try:
            for k, text in enumerate(self.texts):
                async with self._cv:
                    await self._cv.wait_for(lambda: k <= self._max_requested + 1 or self.stopped)
                if self.stopped:
                    return
                self.requested_log.append(k)
                if s.metrics:
                    s.metrics.request_sent(k)
                res = await self.client.synthesize_chunk(
                    text, s.voice_id, s.language, s.engine, s.model_size)
                if self.stopped:
                    return
                s.audio[k] = res.wav
                s.durations[k] = res.duration_s
                if s.metrics:
                    if k == 0:
                        s.metrics.connect_s = res.connect_s
                    s.metrics.first_byte(k, time.monotonic() - res.complete_s + res.first_byte_s)
                    s.metrics.response_complete(k)
                self._ready[k].set()
            s.received_all = True
            s.completed_audio = concat_wavs([s.audio[i] for i in range(len(self.texts))])
            if s.state == "streaming":
                s.transition("playing")
        except asyncio.CancelledError:
            raise
        except Exception as e:                       # never leak a traceback to the UI
            err = e if isinstance(e, VoiceboxError) else VoiceboxFailed()
            if not isinstance(e, VoiceboxError):
                log.warning("pipeline error class=%s", type(e).__name__)
            self.failure = err
            s.error = err.message
            if s.metrics:
                s.metrics.finish("failed", err.error_class)
            try:
                s.transition("failed")
            except InvalidTransition:
                pass
        finally:
            for ev in self._ready:                   # wake any waiting get_chunk
                if self.failure or self.stopped:
                    ev.set()

    async def get_chunk(self, index: int) -> tuple[bytes, float]:
        """Wait for chunk `index`; requesting it lets the pipeline prefetch index+1."""
        if not 0 <= index < len(self._ready):
            raise IndexError(index)
        async with self._cv:
            self._max_requested = max(self._max_requested, index)
            self._cv.notify_all()
        await self._ready[index].wait()
        if self.stopped:
            raise ChunkStopped()
        if self.failure:
            raise self.failure
        return self.session.audio[index], self.session.durations[index]

    async def stop(self) -> None:
        self.stopped = True
        if self.task and not self.task.done():
            self.task.cancel()                       # closes the in-flight HTTP request
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        for ev in self._ready:
            ev.set()
        async with self._cv:
            self._cv.notify_all()
