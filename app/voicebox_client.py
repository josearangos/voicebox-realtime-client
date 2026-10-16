"""The only module that knows Voicebox URLs and schemas."""
import struct
import time
from dataclasses import dataclass

import httpx

from . import config
from .errors import (VoiceboxFailed, VoiceboxRejected, VoiceboxTimeout,
                     VoiceboxUnreachable)


@dataclass
class Voice:
    id: str
    name: str
    language: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.language})" if self.language else self.name


@dataclass
class ModelOption:
    model_name: str
    display_name: str
    engine: str
    model_size: str
    loaded: bool = False


@dataclass
class ChunkAudio:
    wav: bytes
    duration_s: float
    connect_s: float
    first_byte_s: float
    complete_s: float


def _timeout(read: float) -> httpx.Timeout:
    return httpx.Timeout(read, connect=config.CONNECT_TIMEOUT_S)


def map_model(model_name: str) -> tuple[str, str] | None:
    """qwen-tts-<size> -> (qwen, <size>); anything else is hidden (research D4)."""
    prefix = "qwen-tts-"
    if model_name.startswith(prefix) and model_name[len(prefix):]:
        return "qwen", model_name[len(prefix):]
    return None


def wav_duration(wav: bytes) -> float:
    """Validate a PCM WAV and return its duration in seconds."""
    if len(wav) < 44 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise VoiceboxFailed()
    pos, rate, channels, bits, data_len = 12, 0, 0, 0, None
    while pos + 8 <= len(wav):
        cid = wav[pos:pos + 4]
        size = struct.unpack("<I", wav[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            _, channels, rate, _, _, bits = struct.unpack("<HHIIHH", wav[pos + 8:pos + 24])
        elif cid == b"data":
            data_len = min(size, len(wav) - pos - 8)
            if size > len(wav) - pos - 8:      # header promises more than we received
                raise VoiceboxFailed()
            break
        pos += 8 + size + (size & 1)
    if not rate or not channels or not bits or data_len is None or data_len <= 0:
        raise VoiceboxFailed()
    return data_len / (rate * channels * bits // 8)


def _translate(exc: Exception) -> Exception:
    if isinstance(exc, httpx.ConnectTimeout):
        return VoiceboxUnreachable(config.VOICEBOX_URL)
    if isinstance(exc, httpx.TimeoutException):
        return VoiceboxTimeout()
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return VoiceboxUnreachable(config.VOICEBOX_URL)
    return VoiceboxFailed()


class VoiceboxClient:
    def __init__(self, base_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = (base_url or config.VOICEBOX_URL).rstrip("/")
        self._transport = transport

    def _http(self, read: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=_timeout(read),
                                 transport=self._transport)

    async def _get_json(self, path: str):
        last: Exception | None = None
        for _ in range(2):                    # discovery GETs: one retry (contract)
            try:
                async with self._http(config.DISCOVERY_READ_TIMEOUT_S) as c:
                    r = await c.get(path)
                if r.status_code >= 400:
                    raise VoiceboxFailed()
                return r.json()
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last = e
            except ValueError:
                raise VoiceboxFailed()
        raise _translate(last)

    async def check_health(self) -> dict:
        data = await self._get_json("/health")
        return {"status": data.get("status"), "model_loaded": data.get("model_loaded")}

    async def list_voices(self) -> list[Voice]:
        data = await self._get_json("/profiles")
        return [Voice(id=p["id"], name=p.get("name", p["id"]), language=p.get("language", "en"))
                for p in data if isinstance(p, dict) and "id" in p]

    async def list_models(self) -> list[ModelOption]:
        data = await self._get_json("/models/status")
        items = data.get("models", data) if isinstance(data, dict) else data
        out = []
        for m in items:
            if not isinstance(m, dict) or not m.get("downloaded"):
                continue
            mapped = map_model(m.get("model_name", ""))
            if mapped:
                out.append(ModelOption(m["model_name"], m.get("display_name", m["model_name"]),
                                       mapped[0], mapped[1], bool(m.get("loaded"))))
        return out

    async def synthesize_chunk(self, text: str, voice_id: str, language: str,
                               engine: str, model_size: str) -> ChunkAudio:
        """One synthesis request. No automatic retry (Principle VI)."""
        body = {"profile_id": voice_id, "text": text, "language": language,
                "engine": engine, "model_size": model_size}
        t0 = time.monotonic()
        try:
            async with self._http(config.CHUNK_READ_TIMEOUT_S) as c:
                async with c.stream("POST", "/generate/stream", json=body) as r:
                    connect_s = time.monotonic() - t0
                    if r.status_code == 422:
                        raise VoiceboxRejected()
                    if r.status_code >= 400:
                        raise VoiceboxFailed()
                    if "audio/wav" not in r.headers.get("content-type", ""):
                        raise VoiceboxFailed()
                    buf = bytearray()
                    first = None
                    async for part in r.aiter_bytes():
                        if first is None and part:
                            first = time.monotonic() - t0
                        buf.extend(part)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError,
                httpx.DecodingError) as e:
            raise _translate(e)
        complete = time.monotonic() - t0
        wav = bytes(buf)
        return ChunkAudio(wav, wav_duration(wav), connect_s,
                          first if first is not None else complete, complete)
