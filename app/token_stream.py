"""Simulated LLM word stream and the incremental chunker that turns it into TTS chunks.

Voicebox only returns audio once a whole request is synthesized, so time-to-first-audio is
the generation time of the *first chunk*. The chunker therefore flushes a tiny first chunk
as soon as a few words (ideally ending at a clause) have arrived, then grows chunk sizes
along RAMP so the fixed per-request overhead is amortized over later, longer chunks.
"""
import asyncio
import re
from collections.abc import AsyncIterator, Callable

from .chunking import _ABBREV

# (min_words, max_words) per chunk index; the last entry repeats.
# A chunk flushes at the first clause/sentence end once min_words is reached, or at max_words.
RAMP = [(3, 6), (8, 16), (14, 28), (20, 40)]

_TOKEN = re.compile(r"\S+\s*")
_CLAUSE_END = re.compile(r"[.!?…;:,][\"'”’)\]]*$")


def limits(chunk_index: int) -> tuple[int, int]:
    return RAMP[min(chunk_index, len(RAMP) - 1)]


async def simulate_llm_stream(
        text: str, words_per_second: float,
        sleep: Callable[[float], object] = asyncio.sleep) -> AsyncIterator[str]:
    """Yield `text` word by word (each token keeps its trailing whitespace) at a steady pace."""
    delay = 1.0 / max(words_per_second, 0.1)
    for m in _TOKEN.finditer(text):
        await sleep(delay)
        yield m.group()


def _is_boundary(token: str) -> bool:
    word = token.strip()
    if "\n" in token[len(token.rstrip()):]:
        return True
    if not _CLAUSE_END.search(word):
        return False
    if word.endswith(".") and word.lower().rstrip(".") in _ABBREV:
        return False
    return True


class StreamChunker:
    """Feed tokens with push(); each call returns the chunks (lists of tokens) now ready."""

    def __init__(self) -> None:
        self._tokens: list[str] = []
        self._emitted = 0

    def push(self, token: str) -> list[list[str]]:
        self._tokens.append(token)
        lo, hi = limits(self._emitted)
        n = len(self._tokens)
        if n >= hi or (n >= lo and _is_boundary(token)):
            return [self._take()]
        return []

    def flush(self) -> list[list[str]]:
        return [self._take()] if self._tokens else []

    def _take(self) -> list[str]:
        out, self._tokens = self._tokens, []
        self._emitted += 1
        return out
