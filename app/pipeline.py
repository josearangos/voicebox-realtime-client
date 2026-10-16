"""Streams words into chunks and synthesizes them in order, one chunk ahead of playback."""
import asyncio
import io
import logging
import struct
import time
from collections.abc import AsyncIterator

from .chunking import Chunk, Segment
from .errors import VoiceboxError, VoiceboxFailed
from .session import GenerationSession, InvalidTransition
from .token_stream import StreamChunker

log = logging.getLogger("voicebox_client.pipeline")


class ChunkStopped(Exception):
    """The session was stopped while waiting for a chunk."""


class EndOfStream(Exception):
    """The word stream finished and there is no chunk at the requested index."""


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
    """Consumes a word stream, cuts it into chunks as words arrive and synthesizes each at once.

    Synthesis of chunk k starts only after playback has requested chunk k-1 (one chunk ahead).
    `session.chunks` grows as the stream progresses.
    """

    def __init__(self, session: GenerationSession, client, tokens: AsyncIterator[str]):
        self.session = session
        self.client = client
        self.tokens = tokens
        self.chunks: list[Chunk] = session.chunks
        self.texts: list[str] = []
        self.breaks: list[bool] = []               # newline before this chunk
        self.failure: VoiceboxError | None = None
        self.stopped = False
        self.feed_done = False
        self.task: asyncio.Task | None = None
        self.feeder: asyncio.Task | None = None
        self.requested_log: list[int] = []         # order in which synthesis was requested
        self._max_requested = -1
        self._cv = asyncio.Condition()
        self._ready: list[asyncio.Event] = []

    def start(self) -> None:
        self.feeder = asyncio.create_task(self._guard(self._feed()))
        self.task = asyncio.create_task(self._guard(self._run()))

    def is_last(self, index: int) -> bool:
        return self.feed_done and index == len(self.texts) - 1

    async def _guard(self, coro) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:                       # never leak a traceback to the UI
            await self._fail(e)

    async def _fail(self, e: Exception) -> None:
        s = self.session
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
        for t in (self.feeder, self.task):
            if t and t is not asyncio.current_task() and not t.done():
                t.cancel()
        await self._wake_all()

    async def _wake_all(self) -> None:
        for ev in self._ready:
            ev.set()
        async with self._cv:
            self._cv.notify_all()

    async def _feed(self) -> None:
        prev_newline = False
        text = self.session.text
        pos = len(text) - len(text.lstrip())

        async def emit(tokens: list[str]) -> None:
            nonlocal pos, prev_newline
            segs = []
            for t in tokens:
                word = t.rstrip()
                segs.append(Segment(len(segs), pos, pos + len(word), word))
                pos += len(t)
            chunk = Chunk(len(self.chunks), segs)
            async with self._cv:
                self.breaks.append(prev_newline)
                self.texts.append("".join(tokens).strip())
                self._ready.append(asyncio.Event())
                self.chunks.append(chunk)
                self._cv.notify_all()
            prev_newline = "\n" in tokens[-1][len(tokens[-1].rstrip()):]

        chunker = StreamChunker()
        async for tok in self.tokens:
            for ready in chunker.push(tok):
                await emit(ready)
        for ready in chunker.flush():
            await emit(ready)
        async with self._cv:
            self.feed_done = True
            self._cv.notify_all()

    async def _run(self) -> None:
        s = self.session
        k = 0
        while True:
            async with self._cv:
                await self._cv.wait_for(lambda: self.stopped or (
                    k <= self._max_requested + 1 and (k < len(self.texts) or self.feed_done)))
            if self.stopped:
                return
            if k >= len(self.texts):
                break
            self.requested_log.append(k)
            if s.metrics:
                s.metrics.request_sent(k)
            res = await self.client.synthesize_chunk(
                self.texts[k], s.voice_id, s.language, s.engine, s.model_size)
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
            k += 1
        s.received_all = True
        s.completed_audio = concat_wavs([s.audio[i] for i in range(len(self.texts))]) if self.texts else None
        if s.state == "streaming":
            s.transition("playing")

    async def get_chunk(self, index: int) -> tuple[bytes, float]:
        """Wait for chunk `index`; requesting it lets the pipeline prefetch index+1.

        Raises EndOfStream when the word stream ended before reaching `index`.
        """
        if index < 0:
            raise IndexError(index)
        async with self._cv:
            self._max_requested = max(self._max_requested, index)
            self._cv.notify_all()
            await self._cv.wait_for(lambda: index < len(self.texts) or self.feed_done
                                    or self.stopped or self.failure)
        if not self.stopped and not self.failure and index >= len(self.texts):
            raise EndOfStream()
        if not self.stopped and not self.failure:
            await self._ready[index].wait()
        if self.stopped:
            raise ChunkStopped()
        if self.failure:
            raise self.failure
        return self.session.audio[index], self.session.durations[index]

    async def stop(self) -> None:
        self.stopped = True
        for t in (self.feeder, self.task):
            if t and not t.done():
                t.cancel()                           # closes the in-flight HTTP request
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        await self._wake_all()
