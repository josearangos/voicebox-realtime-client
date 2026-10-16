"""Teleprompter segment model, escaped rendering and active-segment math."""
import html

from .chunking import Chunk

PRECISION = "estimated"   # Voicebox exposes no timestamps


def segment_lengths(chunks: list[Chunk]) -> list[list[int]]:
    return [[s.char_end - s.char_start for s in c.segments] for c in chunks]


def active_segment(lens: list[list[int]], chunk_index: int | None, t: float | None,
                   duration: float | None) -> int | None:
    """Global segment index being spoken, or None when the position is unknown.

    Position inside a chunk is proportional to character count (approximate).
    """
    if chunk_index is None or t is None or duration is None or duration <= 0:
        return None
    if not 0 <= chunk_index < len(lens) or not lens[chunk_index]:
        return None
    base = sum(len(c) for c in lens[:chunk_index])
    seg_lens = lens[chunk_index]
    total = sum(seg_lens)
    frac = min(max(t / duration, 0.0), 1.0)
    pos = frac * total
    acc = 0
    for i, n in enumerate(seg_lens):
        acc += n
        if pos < acc:
            return base + i
    return base + len(seg_lens) - 1


def render_html(text: str, chunks: list[Chunk]) -> str:
    """All user text goes through html.escape; no raw HTML is ever emitted from it."""
    parts = ['<div id="vb-teleprompter" class="vb-tp" aria-label="Teleprompter">']
    prev_end = None
    gi = 0
    for c in chunks:
        parts.append(f'<span class="vb-chunk" data-chunk="{c.index}">')
        for s in c.segments:
            if prev_end is not None:
                gap = text[prev_end:s.char_start]
                parts.append("<br>" if "\n" in gap else " ")
            n = s.char_end - s.char_start
            parts.append(f'<span class="vb-seg upcoming" data-idx="{gi}" data-len="{n}">'
                         f'{html.escape(s.text)}</span>')
            prev_end = s.char_end
            gi += 1
        parts.append("</span>")
    parts.append("</div>")
    return "".join(parts)
