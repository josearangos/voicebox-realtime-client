"""Sentence splitting with offsets into the original text, grouped into chunks."""
import re
from dataclasses import dataclass, field

_ABBREV = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "sra", "srta", "st", "vs", "etc",
    "jr", "inc", "ltd", "no", "fig", "e.g", "i.e", "u.s", "a.m", "p.m",
}
_END = re.compile(r"[.!?…]+[\"'”’)\]]*")

MIN_CHUNK_CHARS = 20
MAX_CHUNK_CHARS = 300


@dataclass
class Segment:
    index: int
    char_start: int
    char_end: int
    text: str


@dataclass
class Chunk:
    index: int
    segments: list[Segment] = field(default_factory=list)

    @property
    def char_start(self) -> int:
        return self.segments[0].char_start

    @property
    def char_end(self) -> int:
        return self.segments[-1].char_end


def split_sentences(text: str) -> list[Segment]:
    spans: list[tuple[int, int]] = []
    start = 0
    n = len(text)
    for m in _END.finditer(text):
        end = m.end()
        # needs whitespace (or end of text) after the terminator
        if end < n and not text[end].isspace():
            continue
        # decimals like 3.14 never reach here (no whitespace after '.'); check abbreviations
        word = re.search(r"([\w.]+)\s*$", text[start:m.start()])
        if m.group().startswith(".") and len(m.group().rstrip("\"'”’)]")) == 1 and word:
            if word.group(1).lower().rstrip(".") in _ABBREV:
                continue
        spans.append((start, end))
        start = end
    if start < n:
        spans.append((start, n))

    segments: list[Segment] = []
    for s, e in spans:
        # trim whitespace but keep offsets exact
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if s < e:
            segments.append(Segment(len(segments), s, e, text[s:e]))
    return segments


def make_chunks(text: str) -> list[Chunk]:
    """Group short consecutive sentences into chunks of roughly MIN..MAX chars."""
    chunks: list[Chunk] = []
    current: list[Segment] = []
    size = 0
    for seg in split_sentences(text):
        length = seg.char_end - seg.char_start
        if current and size + length > MAX_CHUNK_CHARS:
            chunks.append(Chunk(len(chunks), current))
            current, size = [], 0
        current.append(seg)
        size += length
        if size >= MIN_CHUNK_CHARS:
            chunks.append(Chunk(len(chunks), current))
            current, size = [], 0
    if current:
        chunks.append(Chunk(len(chunks), current))
    return chunks
