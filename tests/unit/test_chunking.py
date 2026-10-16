from app.chunking import make_chunks, split_sentences


def test_offsets_reproduce_text():
    text = "Hello there. How are you?  I'm fine!\nNew line here."
    for s in split_sentences(text):
        assert text[s.char_start:s.char_end] == s.text
    assert [s.text for s in split_sentences(text)] == [
        "Hello there.", "How are you?", "I'm fine!", "New line here."]


def test_abbreviations_and_decimals():
    segs = split_sentences("Dr. Smith paid 3.14 dollars. Then he left.")
    assert [s.text for s in segs] == ["Dr. Smith paid 3.14 dollars.", "Then he left."]


def test_multiline():
    segs = split_sentences("First line.\n\nSecond line.\nThird")
    assert [s.text for s in segs] == ["First line.", "Second line.", "Third"]


def test_empty_and_whitespace():
    assert make_chunks("") == []
    assert make_chunks("   \n\t ") == []


def test_single_sentence_one_chunk():
    chunks = make_chunks("Just one sentence.")
    assert len(chunks) == 1 and len(chunks[0].segments) == 1


def test_short_sentences_grouped_long_ones_separate():
    chunks = make_chunks("Hi. Yo. " + "A longer sentence that goes on for a while, really. " * 3)
    assert len(chunks[0].segments) > 1
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_max_text_5000():
    text = "This is a sentence of moderate length. " * 128
    text = text[:5000]
    chunks = make_chunks(text)
    covered = [text[s.char_start:s.char_end] for c in chunks for s in c.segments]
    assert "".join(covered).replace(" ", "") == "".join(text.split())
    assert chunks[0].char_start == 0
