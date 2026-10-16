"""Per-session performance records. Only lengths and timings; never text or audio."""
import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("voicebox_client.metrics")


@dataclass
class ChunkTiming:
    index: int
    request_sent: float | None = None
    first_byte: float | None = None
    response_complete: float | None = None


@dataclass
class PerformanceRecord:
    session_id: str
    text_length: int
    connect_s: float | None = None
    chunks: dict[int, ChunkTiming] = field(default_factory=dict)
    first_playable_audio_s: float | None = None
    total_generation_s: float | None = None
    stall_count: int = 0
    stall_total_s: float = 0.0
    session_duration_s: float | None = None
    outcome: str | None = None
    error_class: str | None = None
    started: float = field(default_factory=time.monotonic)
    _stall_started: float | None = None

    def chunk(self, index: int) -> ChunkTiming:
        return self.chunks.setdefault(index, ChunkTiming(index))

    def request_sent(self, index: int) -> None:
        self.chunk(index).request_sent = time.monotonic() - self.started

    def first_byte(self, index: int, t: float) -> None:
        self.chunk(index).first_byte = t - self.started

    def response_complete(self, index: int) -> None:
        self.chunk(index).response_complete = time.monotonic() - self.started
        self.total_generation_s = self.chunk(index).response_complete

    def browser_event(self, event: str, t: float) -> bool:
        """Apply a browser event; t is seconds in the browser's own clock (relative use only)."""
        if event == "play_start":
            if self.first_playable_audio_s is None:
                self.first_playable_audio_s = time.monotonic() - self.started
        elif event == "stall_start":
            self._stall_started = t
        elif event == "stall_end":
            if self._stall_started is not None:
                self.stall_count += 1
                self.stall_total_s += max(0.0, t - self._stall_started)
                self._stall_started = None
        elif event == "ended":
            pass
        else:
            return False
        return True

    def finish(self, outcome: str, error_class: str | None = None) -> None:
        self.outcome = outcome
        self.error_class = error_class
        self.session_duration_s = time.monotonic() - self.started
        log.info(
            "session=%s outcome=%s text_length=%d first_playable_audio_s=%s "
            "total_generation_s=%s stalls=%d stall_total_s=%.2f error=%s",
            self.session_id, outcome, self.text_length, _fmt(self.first_playable_audio_s),
            _fmt(self.total_generation_s), self.stall_count, self.stall_total_s, error_class,
        )


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
