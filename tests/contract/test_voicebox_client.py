import json
from pathlib import Path

import httpx
import pytest
import respx

from app.errors import (VoiceboxFailed, VoiceboxRejected, VoiceboxTimeout,
                        VoiceboxUnreachable)
from app.voicebox_client import VoiceboxClient, map_model, wav_duration

FX = Path(__file__).parent.parent / "fixtures"
BASE = "http://voicebox.test"
WAV = (FX / "tiny.wav").read_bytes()


@pytest.fixture
def client():
    return VoiceboxClient(BASE)


def synth(client):
    return client.synthesize_chunk("Hello.", "p1", "en", "qwen", "0.6B")


@respx.mock
async def test_list_voices(client):
    respx.get(f"{BASE}/profiles").respond(json=json.loads((FX / "profiles.json").read_text()))
    voices = await client.list_voices()
    assert voices and voices[0].id == "profile-1" and voices[0].name == "Voice 1"


@respx.mock
async def test_list_models_filters_and_maps(client):
    respx.get(f"{BASE}/models/status").respond(json=json.loads((FX / "models_status.json").read_text()))
    models = await client.list_models()
    assert models
    assert all(m.engine == "qwen" for m in models)
    assert {m.model_size for m in models} <= {"0.6B", "1.7B"}
    assert all(m.model_name.startswith("qwen-tts-") for m in models)


def test_map_model():
    assert map_model("qwen-tts-0.6B") == ("qwen", "0.6B")
    assert map_model("qwen-custom-voice-0.6B") == ("qwen_custom_voice", "0.6B")
    assert map_model("kokoro") == ("kokoro", "")
    assert map_model("tada-3b-ml") == ("tada", "3B")
    assert map_model("whisper-base") is None
    assert map_model("qwen3-1.7b") is None
    assert map_model("qwen-tts-") is None


def test_wav_duration():
    assert wav_duration(WAV) == pytest.approx(0.1)


@respx.mock
async def test_synthesize_ok(client):
    respx.post(f"{BASE}/generate/stream").respond(content=WAV, headers={"content-type": "audio/wav"})
    out = await synth(client)
    assert out.duration_s == pytest.approx(0.1) and out.wav == WAV
    assert out.complete_s >= out.first_byte_s >= 0


@respx.mock
async def test_health_retry_once(client):
    route = respx.get(f"{BASE}/health").mock(side_effect=[httpx.ConnectError("x"),
                                                         httpx.Response(200, json={"status": "healthy"})])
    assert (await client.check_health())["status"] == "healthy"
    assert route.call_count == 2


@respx.mock
async def test_refused_connection(client):
    respx.post(f"{BASE}/generate/stream").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(VoiceboxUnreachable) as e:
        await synth(client)
    assert "can't be reached" in e.value.message


@respx.mock
async def test_discovery_unreachable_after_retry(client):
    route = respx.get(f"{BASE}/profiles").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(VoiceboxUnreachable):
        await client.list_voices()
    assert route.call_count == 2


@respx.mock
async def test_timeout_no_retry(client):
    route = respx.post(f"{BASE}/generate/stream").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(VoiceboxTimeout):
        await synth(client)
    assert route.call_count == 1


@respx.mock
async def test_422(client):
    respx.post(f"{BASE}/generate/stream").respond(422, json={"detail": "bad"})
    with pytest.raises(VoiceboxRejected):
        await synth(client)


@respx.mock
async def test_500(client):
    respx.post(f"{BASE}/generate/stream").respond(500, text="boom secret")
    with pytest.raises(VoiceboxFailed) as e:
        await synth(client)
    assert "secret" not in e.value.message


@respx.mock
async def test_truncated_body(client):
    respx.post(f"{BASE}/generate/stream").respond(content=WAV[:100], headers={"content-type": "audio/wav"})
    with pytest.raises(VoiceboxFailed):
        await synth(client)


@respx.mock
async def test_non_wav_body(client):
    respx.post(f"{BASE}/generate/stream").respond(content=b"not audio at all" * 10,
                                                  headers={"content-type": "audio/wav"})
    with pytest.raises(VoiceboxFailed):
        await synth(client)
    respx.post(f"{BASE}/generate/stream").respond(json={"x": 1})
    with pytest.raises(VoiceboxFailed):
        await synth(client)
