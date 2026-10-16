"""Baseline latency measurement against a running Voicebox.

Reports FETCH-COMPLETE times only: time until the first chunk's response is fully received, and
time until all chunks have been received (sequential requests). Browser-measured first playable
audio comes from the POST /api/metrics events logged during real page runs (quickstart scenario 2).
"""
import argparse
import asyncio
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config                                   # noqa: E402
from app.chunking import make_chunks                      # noqa: E402
from app.errors import VoiceboxError                      # noqa: E402
from app.voicebox_client import VoiceboxClient            # noqa: E402

SENTENCE = "The quick brown fox jumps over the lazy dog near the river bank. "


async def run_once(client, text, voice, model):
    chunks = make_chunks(text)
    t0 = time.monotonic()
    first = audio = 0.0
    for i, c in enumerate(chunks):
        res = await client.synthesize_chunk(text[c.char_start:c.char_end], voice.id, voice.language,
                                            model.engine, model.model_size)
        if i == 0:
            first = time.monotonic() - t0
        audio += res.duration_s
    return len(chunks), first, time.monotonic() - t0, audio


async def main(runs, sizes):
    client = VoiceboxClient()
    voices, models = await client.list_voices(), await client.list_models()
    voice = voices[0]
    model = next((m for m in models if m.loaded), models[0])
    print(f"Hardware: {platform.platform()} / {platform.machine()}  Python {platform.python_version()}")
    print(f"Voicebox: {config.VOICEBOX_URL}  model: {model.model_name}  voice: {voice.language}  runs: {runs}")
    print("Times are fetch-complete (not browser playback).")
    print(f"{'sentences':>9} {'chunks':>6} {'chars':>6} {'audio_s':>8} {'first_chunk_s':>14} {'all_chunks_s':>13}")
    for n in sizes:
        text = (SENTENCE * n).strip()
        rows, failed = [], 0
        for _ in range(runs):
            try:
                rows.append(await run_once(client, text, voice, model))
            except VoiceboxError as e:        # report, do not hide, failed runs
                failed += 1
                print(f"  run failed: {e.message}", flush=True)
        if not rows:
            continue
        f = [r[1] for r in rows]; t = [r[2] for r in rows]
        print(f"{n:>9} {rows[0][0]:>6} {len(text):>6} {statistics.mean(r[3] for r in rows):>8.1f} "
              f"{statistics.mean(f):>8.1f}±{statistics.pstdev(f):<4.1f} "
              f"{statistics.mean(t):>7.1f}±{statistics.pstdev(t):<4.1f}  ok={len(rows)}/{runs}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--sizes", type=int, nargs="+", default=[1, 3, 8])
    a = ap.parse_args()
    asyncio.run(main(a.runs, a.sizes))
