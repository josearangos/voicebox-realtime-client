from app.session import SessionRegistry


def test_sessions_are_isolated():
    reg = SessionRegistry()
    a, b = reg.get("tab-a"), reg.get("tab-b")
    assert a is not b and reg.get("tab-a") is a
    a.transition("loading")
    a.audio[0] = b"x"
    a.state = "playing"
    a.transition("stopped")
    assert a.stop_event.is_set() and not b.stop_event.is_set()
    assert b.state == "idle" and b.audio == {}
    b.chunks.append("c")
    assert a.chunks == []
