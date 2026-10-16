"""T044: repeat 20 generations through the session/pipeline code and confirm memory is bounded.

Uses an in-process fake Voicebox client returning ~1 MB WAVs so it needs no backend and never
loads a model. Also reports whether heavy ML packages are installed in this environment.
"""
import asyncio
import gc
import importlib.metadata as md
import struct
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import ChunkPipeline, EndOfStream                      # noqa: E402
from app.session import GenerationSession                     # noqa: E402
from app.token_stream import simulate_llm_stream              # noqa: E402
from app.voicebox_client import ChunkAudio                    # noqa: E402

pcm = b"\x00\x01" * 250_000                                   # ~1 s... 0.5 MB per chunk
WAV = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 24000, 48000, 2, 16)
       + b"data" + struct.pack("<I", len(pcm)) + pcm)
TEXT = ("A sentence that is long enough to be its own chunk. " * 10).strip()


class Fake:
    async def synthesize_chunk(self, *a):
        return ChunkAudio(WAV, 5.0, 0, 0, 0)


async def one_generation(s):
    s.reset_for_new_run()
    s.text = TEXT
    p = ChunkPipeline(s, Fake(), simulate_llm_stream(TEXT, 100_000))
    s.pipeline = p
    s.transition("generating")
    p.start()
    for i in range(1000):
        try:
            await p.get_chunk(i)
        except EndOfStream:
            break
    await p.task
    s.transition("playing"); s.transition("completed")


async def main():
    s = GenerationSession()
    tracemalloc.start()
    sizes = []
    for n in range(20):
        await one_generation(s)
        gc.collect()
        sizes.append(tracemalloc.get_traced_memory()[0] / 1e6)
    print("traced MB after generations 1, 5, 10, 15, 20:",
          [f"{sizes[i]:.1f}" for i in (0, 4, 9, 14, 19)])
    growth = sizes[-1] - sizes[4]
    print(f"growth between run 5 and run 20: {growth:.2f} MB ->", "BOUNDED" if growth < 2 else "LEAK?")
    heavy = [n for n in ("torch", "tensorflow", "transformers", "whisper", "onnxruntime")
             if any(d.metadata["Name"].lower().startswith(n) for d in md.distributions())]
    print("heavy ML packages installed:", heavy or "none")
    print("ML modules loaded by this process:", [m for m in ("torch", "tensorflow") if m in sys.modules] or "none")
    sys.exit(0 if growth < 2 and not heavy else 1)


asyncio.run(main())
