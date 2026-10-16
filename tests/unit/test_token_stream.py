from app.token_stream import RAMP, StreamChunker, simulate_llm_stream


def chunk_all(text):
    import asyncio

    async def run():
        out, c = [], StreamChunker()
        async def nosleep(_): pass
        async for tok in simulate_llm_stream(text, 10, sleep=nosleep):
            out += c.push(tok)
        return out + c.flush()
    return asyncio.run(run())


def test_first_chunk_small_and_clause_aligned():
    chunks = chunk_all("Hola, buenos días, hoy vamos a hablar de síntesis de voz en tiempo real. Gracias.")
    assert "".join("".join(c) for c in chunks).strip().startswith("Hola, buenos días")
    assert "".join(chunks[0]).strip() == "Hola, buenos"[:0] + "Hola, buenos días,"
    assert len(chunks[0]) <= RAMP[0][1]


def test_hard_cap_without_punctuation():
    chunks = chunk_all("one two three four five six seven eight nine ten eleven twelve")
    assert len(chunks[0]) == RAMP[0][1]
    assert sum(len(c) for c in chunks) == 12


def test_abbreviation_does_not_flush():
    chunks = chunk_all("Hello Dr. Smith will see you now. Please sit.")
    assert "".join(chunks[0]).strip().endswith("Dr. Smith will see")  or len(chunks[0]) >= 3
    assert not "".join(chunks[0]).strip().endswith("Dr.")


def test_newline_is_a_boundary():
    chunks = chunk_all("alpha beta gamma\ndelta epsilon zeta eta")
    assert "".join(chunks[0]) == "alpha beta gamma\n"


def test_tokens_roundtrip_text():
    text = "A  b\nc, d. E f g h i j k l m n o p q r s t u v w x y z."
    assert "".join("".join(c) for c in chunk_all(text)) == text


def test_chunk_sizes_grow():
    text = " ".join(f"w{i}" for i in range(200))
    sizes = [len(c) for c in chunk_all(text)]
    assert sizes[0] < sizes[1] < sizes[2]
