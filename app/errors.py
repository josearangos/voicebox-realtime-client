"""Typed errors. Messages are user-facing: no credentials, headers or raw bodies."""


class VoiceboxError(Exception):
    error_class = "error"
    default_message = "Something went wrong."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class VoiceboxUnreachable(VoiceboxError):
    error_class = "unreachable"

    def __init__(self, url: str = ""):
        host = _safe_url(url)
        where = f" at {host}" if host else ""
        super().__init__(f"Voicebox can't be reached{where}. Check it is running.")


class VoiceboxRejected(VoiceboxError):
    error_class = "rejected"
    default_message = "Voicebox rejected the request (invalid selection or text)."


class VoiceboxFailed(VoiceboxError):
    error_class = "failed"
    default_message = "Voicebox failed while generating. Try again."


class VoiceboxTimeout(VoiceboxError):
    error_class = "timeout"
    default_message = "Voicebox took too long to respond."


def _safe_url(url: str) -> str:
    """Scheme://host:port only; strips userinfo, path and query."""
    from urllib.parse import urlsplit

    if not url:
        return ""
    p = urlsplit(url)
    host = p.hostname or ""
    port = f":{p.port}" if p.port else ""
    return f"{p.scheme}://{host}{port}" if p.scheme else host
