"""Offline A/B on John's recorded phrases (from /voice-bench.html): engine x Whisper hint x name correction, on VM 102.

Setup on VM 102 (nothing here is shared or committed: the recordings are a person's voice):
    ~/voice-bench/john/            results.jsonl + the .webm takes copied from StoneSage's data/voice_samples
    ~/voice-bench/vs/              engines.py audio.py vocab.py text_norm.py vocab.txt (server setup/voice-server) +
                                   voice_bench.py voice_client.py (StoneSage/backend)
Run: cd ~/voice-bench && . venv/bin/activate && python john_bench.py
"""

import json
import os
import statistics
import sys
import time

ROOT = os.path.expanduser("~/voice-bench")
sys.path.insert(0, f"{ROOT}/vs")
import audio  # noqa: E402
import voice_bench  # noqa: E402
from engines import SttEngines  # noqa: E402

NAMES = ("kylo", "luna", "savannah", "austin")

latest = {}
for line in open(f"{ROOT}/john/results.jsonl", encoding="utf-8"):
    r = json.loads(line)
    latest[r["phrase"]["id"]] = r
clips = []
for r in latest.values():
    x = audio.decode_to_float32(open(f"{ROOT}/john/{r['file']}", "rb").read())
    clips.append((r["phrase"], x))
print(f"{len(clips)} phrases from John's voice ({sum(len(x) for _, x in clips) / 16000:.0f} s of audio)")


def name_misses(ref, hyp):
    """Names in the reference that the transcript does not contain exactly (the words the shortcuts depend on)."""
    h = set(voice_bench.norm(hyp))
    return [n for n in voice_bench.norm(ref) if n in NAMES and n not in h]


VARIANTS = [
    ("parakeet", "parakeet", False, False),
    ("parakeet + name correction", "parakeet", False, True),
    ("moonshine-base + correction", "moonshine-base", False, True),
    ("whisper-base", "whisper-base", False, False),
    ("whisper-base + hint", "whisper-base", True, False),
    ("whisper-base + correction", "whisper-base", False, True),
    ("whisper-base + hint + corr.", "whisper-base", True, True),
    ("whisper-small + hint + corr.", "whisper-small", True, True),
]
print(f"{'variant':30} {'WER':>6} {'far':>6} {'names missed':>13} {'median':>8}")
detail = {}
for label, engine, prompt, corr in VARIANTS:
    stt = SttEngines(f"{ROOT}/models", engine, 3, f"{ROOT}/vs/vocab.txt", use_prompt=prompt, use_correction=corr)
    stt.transcribe(clips[0][1], engine)                      # load + warm
    errs = words = ferr = fwords = missed = 0
    times, bad = [], []
    for phrase, x in clips:
        text, _e, ms = stt.transcribe(x, engine)
        times.append(ms)
        e = voice_bench.word_errors(phrase["text"], text)
        w = len(voice_bench.norm(phrase["text"]))
        errs += e; words += w
        if phrase["cond"] == "far":
            ferr += e; fwords += w
        m = name_misses(phrase["text"], text)
        missed += len(m)
        if e:
            bad.append((phrase["text"], text))
    detail[label] = bad
    print(f"{label:30} {100 * errs / words:5.1f}% {100 * ferr / max(fwords, 1):5.1f}% {missed:>13} {statistics.median(times):6.0f}ms", flush=True)
print()
for label in ("parakeet + name correction", "whisper-base + hint + corr.", "whisper-small + hint + corr."):
    print(label)
    for ref, hyp in detail[label]:
        print(f"    {ref!r:48} -> {hyp!r}")
