"""Per-browser-session state machine and registry."""
import threading
import uuid
from dataclasses import dataclass, field

from .chunking import Chunk
from .metrics import PerformanceRecord

STATES = {"idle", "loading", "generating", "streaming", "playing", "paused",
          "completed", "stopped", "failed"}
ACTIVE = {"loading", "generating", "streaming", "playing", "paused"}
CAN_GENERATE = {"idle", "completed", "stopped", "failed"}

_ALLOWED: dict[str, set[str]] = {
    "idle": {"loading"},
    "loading": {"generating", "failed", "stopped"},
    "generating": {"streaming", "playing", "paused", "stopped", "failed"},
    "streaming": {"playing", "paused", "stopped", "failed"},
    "playing": {"paused", "completed", "stopped", "failed"},
    "paused": {"playing", "streaming", "generating", "completed", "stopped", "failed"},
    "completed": {"idle", "loading", "playing"},   # playing = replay without new request
    "stopped": {"idle", "loading"},
    "failed": {"idle", "loading"},
}


class InvalidTransition(Exception):
    pass


@dataclass
class GenerationSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = "idle"
    mode: str = "streamed"
    run_id: str = ""
    text: str = ""
    voice_id: str = ""
    language: str = "en"
    engine: str = ""
    model_size: str = ""
    chunks: list[Chunk] = field(default_factory=list)
    audio: dict[int, bytes] = field(default_factory=dict)
    durations: dict[int, float] = field(default_factory=dict)
    completed_audio: bytes | None = None
    received_all: bool = False
    error: str | None = None
    metrics: PerformanceRecord | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    pipeline: object | None = None

    @property
    def can_generate(self) -> bool:
        return self.state in CAN_GENERATE

    @property
    def active(self) -> bool:
        return self.state in ACTIVE

    def transition(self, new: str) -> None:
        if new not in STATES:
            raise InvalidTransition(f"unknown state {new}")
        if new == self.state:
            return
        if new not in _ALLOWED[self.state]:
            raise InvalidTransition(f"{self.state} -> {new}")
        self.state = new
        if new in ("stopped", "failed"):
            self.discard_audio()
        if new == "stopped":
            self.stop_event.set()

    def discard_audio(self) -> None:
        self.audio.clear()
        self.durations.clear()
        self.completed_audio = None

    def reset_for_new_run(self) -> None:
        """Called when Generate starts: releases previous audio and signals."""
        self.audio.clear()
        self.durations.clear()
        self.completed_audio = None
        self.received_all = False
        self.chunks = []
        self.run_id = uuid.uuid4().hex
        self.error = None
        self.stop_event = threading.Event()
        self.transition("loading")


class SessionRegistry:
    def __init__(self):
        self._sessions: dict[str, GenerationSession] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> GenerationSession:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                s = GenerationSession(id=session_id)
                self._sessions[session_id] = s
            return s

    def find(self, session_id: str) -> GenerationSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def drop(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


registry = SessionRegistry()


def validate_request(text: str, voice_id: str, model_name: str,
                     voice_ids: set[str], model_names: set[str], max_chars: int) -> str | None:
    """Return a user-facing message naming the fix, or None when the request is valid."""
    if not text or not text.strip():
        return "Enter some text to speak."
    if len(text) > max_chars:
        return (f"Text is too long: {len(text):,} of {max_chars:,} characters. "
                "Shorten it and try again.")
    if not voice_id or voice_id not in voice_ids:
        return "The selected voice is no longer available. Refresh the list and pick a voice."
    if not model_name or model_name not in model_names:
        return "The selected model is no longer available. Refresh the list and pick a model."
    return None
