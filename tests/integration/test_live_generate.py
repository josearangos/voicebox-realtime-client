import pytest

from app.voicebox_client import VoiceboxClient

pytestmark = pytest.mark.voicebox


async def test_discovery_and_one_chunk():
    c = VoiceboxClient()
    voices, models = await c.list_voices(), await c.list_models()
    assert voices and models
    res = await c.synthesize_chunk("Hello there.", voices[0].id, voices[0].language,
                                   models[0].engine, models[0].model_size)
    assert res.duration_s > 0 and res.wav[:4] == b"RIFF"
    print(f"\nfirst_byte={res.first_byte_s:.2f}s complete={res.complete_s:.2f}s "
          f"audio={res.duration_s:.2f}s")
