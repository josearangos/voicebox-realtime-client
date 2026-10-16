import logging
import re
from pathlib import Path

import httpx
import respx

from app import config
from app.server import build_app
from app.voicebox_client import VoiceboxClient

ROOT = Path(__file__).parent.parent.parent


def test_default_host_is_loopback():
    assert config.HOST == "127.0.0.1"
    main_src = (ROOT / "app" / "__main__.py").read_text()
    assert "config.HOST" in main_src and "0.0.0.0" not in main_src
    assert "debug" not in main_src.lower().replace("debug off", "")


def test_no_wildcard_bind_or_debug_anywhere():
    for py in (ROOT / "app").glob("*.py"):
        src = py.read_text()
        assert not re.search(r"host\s*=\s*[\"']0\.0\.0\.0", src), py
        assert "debug=True" not in src, py


@respx.mock
async def test_only_configured_voicebox_host_is_contacted(caplog):
    base = "http://voicebox.test"
    wav = (ROOT / "tests" / "fixtures" / "tiny.wav").read_bytes()
    respx.get(f"{base}/profiles").respond(json=[])
    respx.post(f"{base}/generate/stream").respond(content=wav, headers={"content-type": "audio/wav"})
    c = VoiceboxClient(base)
    secret = "TOP SECRET SENTENCE"
    with caplog.at_level(logging.DEBUG):
        await c.list_voices()
        await c.synthesize_chunk(secret, "p", "en", "qwen", "0.6B")
    hosts = {r.request.url.host for r in respx.calls}
    assert hosts == {"voicebox.test"}
    assert secret not in caplog.text


def test_app_builds_without_loading_models():
    build_app(VoiceboxClient("http://voicebox.test"))
    import sys
    assert not {"torch", "tensorflow", "transformers"} & set(sys.modules)
