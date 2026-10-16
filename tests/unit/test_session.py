import pytest

from app.session import (ACTIVE, CAN_GENERATE, GenerationSession, InvalidTransition,
                         STATES)


def walk(s, *states):
    for st in states:
        s.transition(st)


def test_can_generate_per_state():
    for st in STATES:
        s = GenerationSession()
        s.state = st
        assert s.can_generate == (st in {"idle", "completed", "stopped", "failed"})
    assert ACTIVE.isdisjoint(CAN_GENERATE)


def test_happy_path():
    s = GenerationSession()
    walk(s, "loading", "generating", "streaming", "playing", "paused", "playing", "completed")
    assert s.state == "completed" and s.can_generate


@pytest.mark.parametrize("bad", [("idle", "playing"), ("idle", "completed"),
                                 ("completed", "paused"), ("stopped", "playing"),
                                 ("failed", "completed"), ("loading", "playing")])
def test_forbidden(bad):
    s = GenerationSession()
    s.state = bad[0]
    with pytest.raises(InvalidTransition):
        s.transition(bad[1])


@pytest.mark.parametrize("active", ["generating", "streaming", "playing", "paused"])
def test_stop_and_fail_discard_audio(active):
    for end in ("stopped", "failed"):
        s = GenerationSession()
        s.state = active
        s.audio[0] = b"x"
        s.durations[0] = 1.0
        s.transition(end)
        assert s.audio == {} and s.durations == {}
    assert s.state == "failed"


def test_stop_sets_signal():
    s = GenerationSession()
    s.state = "playing"
    s.transition("stopped")
    assert s.stop_event.is_set()


def test_pause_resume_stop_restart():
    s = GenerationSession()
    walk(s, "loading", "generating", "playing", "paused", "playing", "stopped")
    assert s.can_generate
    s.reset_for_new_run()
    assert s.state == "loading" and not s.stop_event.is_set()


def test_restart_after_completed_replays_without_request():
    s = GenerationSession()
    walk(s, "loading", "generating", "playing", "completed")
    s.transition("playing")             # replay: no new loading/generating
    assert s.state == "playing"


def test_restart_after_stopped_or_failed_regenerates():
    for end in ("stopped", "failed"):
        s = GenerationSession()
        walk(s, "loading", "generating", end)
        with pytest.raises(InvalidTransition):
            s.transition("playing")
        s.reset_for_new_run()
        assert s.state == "loading"
