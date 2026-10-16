from app.chunking import make_chunks
from app.teleprompter import PRECISION, active_segment, segment_lengths

LENS = [[10, 30], [20]]       # chunk 0: two segments (25% / 75% of its duration), chunk 1: one


def test_active_segment_boundaries():
    d = 4.0
    assert active_segment(LENS, 0, 0.0, d) == 0
    assert active_segment(LENS, 0, 0.99, d) == 0          # 24.75 % < 25 %
    assert active_segment(LENS, 0, 1.0, d) == 1           # exactly the boundary
    assert active_segment(LENS, 0, 3.99, d) == 1
    assert active_segment(LENS, 0, 4.0, d) == 1           # end clamps to last segment
    assert active_segment(LENS, 0, 99, d) == 1


def test_second_chunk_offsets_and_single_segment():
    assert active_segment(LENS, 1, 0.0, 2.0) == 2
    assert active_segment(LENS, 1, 2.0, 2.0) == 2


def test_precision_always_estimated():
    assert PRECISION == "estimated"


def test_segment_lengths_from_chunks():
    chunks = make_chunks("One short one. Another short one. " * 4)
    lens = segment_lengths(chunks)
    assert sum(len(c) for c in lens) == sum(len(c.segments) for c in chunks)


def test_unknown_position_marks_nothing():
    assert active_segment(LENS, None, 1.0, 4.0) is None
    assert active_segment(LENS, 0, None, 4.0) is None
    assert active_segment(LENS, 0, 1.0, None) is None
    assert active_segment(LENS, 0, 1.0, 0) is None
    assert active_segment(LENS, 5, 1.0, 4.0) is None
