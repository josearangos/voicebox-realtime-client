from app.config import MAX_TEXT_CHARS
from app.session import validate_request

V, M = {"v1"}, {"qwen-tts-0.6B"}


def check(text="Hello.", voice="v1", model="qwen-tts-0.6B"):
    return validate_request(text, voice, model, V, M, MAX_TEXT_CHARS)


def test_valid():
    assert check() is None
    assert check("a" * 5000) is None


def test_empty_and_whitespace():
    assert "Enter some text" in check("")
    assert "Enter some text" in check("  \n\t ")


def test_over_limit_message_shows_limit_and_length():
    msg = check("a" * 5001)
    assert "5,001" in msg and "5,000" in msg


def test_stale_voice_or_model():
    assert "voice" in check(voice="gone")
    assert "voice" in check(voice="")
    assert "model" in check(model="gone")
