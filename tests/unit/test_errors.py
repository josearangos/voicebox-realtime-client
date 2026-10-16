import pytest

from app.errors import (VoiceboxFailed, VoiceboxRejected, VoiceboxTimeout, VoiceboxUnreachable)

EXPECTED = {
    VoiceboxRejected: "Voicebox rejected the request (invalid selection or text).",
    VoiceboxFailed: "Voicebox failed while generating. Try again.",
    VoiceboxTimeout: "Voicebox took too long to respond.",
}


@pytest.mark.parametrize("cls,msg", EXPECTED.items())
def test_messages(cls, msg):
    assert cls().message == msg


def test_unreachable_message_and_no_credentials():
    e = VoiceboxUnreachable("http://user:pass@127.0.0.1:17493/path?token=abc")
    assert e.message == "Voicebox can't be reached at http://127.0.0.1:17493. Check it is running."
    for bad in ("user", "pass", "token", "Authorization", "Traceback"):
        assert bad not in e.message


def test_unreachable_without_url():
    assert "can't be reached" in VoiceboxUnreachable().message
