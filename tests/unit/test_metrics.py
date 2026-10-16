import logging

from app.metrics import PerformanceRecord


def test_browser_events_produce_metrics():
    m = PerformanceRecord("s1", 120)
    assert m.browser_event("play_start", 1.0)
    assert m.first_playable_audio_s is not None
    first = m.first_playable_audio_s
    m.browser_event("play_start", 2.0)               # only the first counts
    assert m.first_playable_audio_s == first
    m.browser_event("stall_start", 10.0)
    m.browser_event("stall_end", 10.75)
    m.browser_event("stall_start", 20.0)
    m.browser_event("stall_end", 20.25)
    assert m.stall_count == 2 and m.stall_total_s == 1.0
    assert not m.browser_event("bogus", 0)


def test_records_contain_no_text_or_audio(caplog):
    secret = "SECRET USER TEXT"
    m = PerformanceRecord("s1", len(secret))
    with caplog.at_level(logging.INFO, logger="voicebox_client.metrics"):
        m.finish("completed")
    assert secret not in caplog.text and "text_length=16" in caplog.text
    assert not any(isinstance(v, (str, bytes)) and secret in str(v) for v in vars(m).values())
