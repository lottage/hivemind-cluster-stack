"""Speech-to-text bench with John's own voice: he records a fixed list of phrases on the phone, every engine transcribes each
recording, and the summary says which engine hears him best (word error rate) and how fast. Recordings stay in the
gitignored data dir: they are a person's voice.
"""

import json
import os
import re
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from voice_client import settings, transcribe_with

# (id, text, condition). Real device and pet names from this house; numbers, yes/no replies and three far/noisy repeats.
PHRASES: List[Dict[str, str]] = [
    {"id": "tv_on", "text": "Turn on the living room TV lights.", "cond": "near"},
    {"id": "tv_off", "text": "Turn off the living room TV lights.", "cond": "near"},
    {"id": "flood_off", "text": "Turn off the driveway floodlight.", "cond": "near"},
    {"id": "porch_on", "text": "Turn on the porch light.", "cond": "near"},
    {"id": "kylo", "text": "Where's Kylo?", "cond": "near"},
    {"id": "luna", "text": "Is Luna in the kitchen?", "cond": "near"},
    {"id": "savannah", "text": "Is Savannah home?", "cond": "near"},
    {"id": "austin", "text": "Is Austin home?", "cond": "near"},
    {"id": "temp", "text": "What's the temperature inside?", "cond": "near"},
    {"id": "thermo", "text": "Set the thermostat to seventy two.", "cond": "near"},
    {"id": "lock", "text": "Is the front door locked?", "cond": "near"},
    {"id": "sister", "text": "What did I tell you about my sister?", "cond": "near"},
    {"id": "joke", "text": "Tell me a joke about toasters.", "cond": "near"},
    {"id": "driveway", "text": "Computer, what's on the driveway camera?", "cond": "near"},
    {"id": "backyard", "text": "Show me the back yard camera.", "cond": "near"},
    {"id": "text", "text": "Text Savannah that I'm running late.", "cond": "near"},
    {"id": "cold", "text": "Why is the living room so cold?", "cond": "near"},
    {"id": "hello", "text": "Hello? Are you there?", "cond": "near"},
    {"id": "yes", "text": "Yes.", "cond": "near"},
    {"id": "no", "text": "No, don't do that.", "cond": "near"},
    {"id": "tv_on_far", "text": "Turn on the living room TV lights.", "cond": "far"},
    {"id": "kylo_far", "text": "Where's Kylo?", "cond": "far"},
    {"id": "thermo_far", "text": "Set the thermostat to seventy two.", "cond": "far"},
]
# moonshine-tiny and whisper-small are left out: the voice server holds every engine it has used in RAM (~3 GB with all five),
# and they are the least likely winners (tiny is less accurate, small is 7x slower for no accuracy gain)
ENGINES = ["parakeet", "moonshine-base", "whisper-base"]
LXC = "lxc-old (whisper base.en)"

_lock = threading.Lock()


def norm(text: str) -> List[str]:
    t = (text or "").lower().replace("seventy two", "72").replace("seventy-two", "72")
    return re.sub(r"[^a-z0-9' ]", " ", t).replace("where's", "where is").replace("what's", "what is").split()


def word_errors(ref: str, hyp: str) -> int:
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)]


def data_dir(base: str) -> str:
    p = os.path.join(base, "voice_samples")
    os.makedirs(p, exist_ok=True)
    return p


def save_and_score(config: Dict[str, Any], base_dir: str, phrase_id: str, audio: bytes, mime: str) -> Dict[str, Any]:
    phrase = next((p for p in PHRASES if p["id"] == phrase_id), None)
    if not phrase:
        raise ValueError(f"unknown phrase '{phrase_id}'")
    s = settings(config)
    ext = "webm" if "webm" in mime else "mp4" if "mp4" in mime else "ogg" if "ogg" in mime else "wav"
    d = data_dir(base_dir)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    fname = f"{stamp}_{phrase_id}.{ext}"
    with open(os.path.join(d, fname), "wb") as f:
        f.write(audio)

    def run(label: str, base: str, engine: str) -> Dict[str, Any]:
        try:
            r = transcribe_with(base, audio, mime, engine)
            text = r.get("text", "")
            return {"engine": label, "text": text, "ms": r.get("ms"), "errors": word_errors(phrase["text"], text),
                    "words": len(norm(phrase["text"]))}
        except Exception as e:
            return {"engine": label, "text": "", "error": f"{type(e).__name__}: {str(e)[:80]}"}

    jobs = [(e, s["stt_url"], e) for e in ENGINES]
    if s["stt_fallback_url"]:
        jobs.append((LXC, s["stt_fallback_url"], "base.en"))
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        results = list(ex.map(lambda j: run(*j), jobs))
    rec = {"file": fname, "phrase": phrase, "at": time.time(), "results": results}
    with _lock, open(os.path.join(d, "results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def load_records(base_dir: str) -> List[Dict[str, Any]]:
    path = os.path.join(data_dir(base_dir), "results.jsonl")
    if not os.path.exists(path):
        return []
    latest: Dict[str, Dict[str, Any]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                latest[r["phrase"]["id"]] = r          # a re-recorded phrase replaces the earlier take
            except (ValueError, KeyError):
                continue
    return list(latest.values())


def summary(base_dir: str) -> Dict[str, Any]:
    recs = load_records(base_dir)
    rows: Dict[str, Dict[str, Any]] = {}
    for rec in recs:
        far = rec["phrase"]["cond"] == "far"
        for r in rec["results"]:
            row = rows.setdefault(r["engine"], {"engine": r["engine"], "errors": 0, "words": 0, "far_errors": 0, "far_words": 0,
                                                "ms": [], "failed": 0, "exact": 0, "n": 0})
            if "error" in r:
                row["failed"] += 1
                continue
            row["n"] += 1
            row["errors"] += r["errors"]; row["words"] += r["words"]
            if far:
                row["far_errors"] += r["errors"]; row["far_words"] += r["words"]
            row["exact"] += r["errors"] == 0
            if r.get("ms") is not None:
                row["ms"].append(r["ms"])
    out = []
    for row in rows.values():
        ms = row.pop("ms")
        row["median_ms"] = round(statistics.median(ms)) if ms else None
        row["wer_pct"] = round(100 * row["errors"] / row["words"], 1) if row["words"] else None
        row["far_wer_pct"] = round(100 * row["far_errors"] / row["far_words"], 1) if row["far_words"] else None
        out.append(row)
    out.sort(key=lambda r: (r["wer_pct"] is None, r["wer_pct"] or 0, r["median_ms"] or 0))
    return {"recorded": len(recs), "of": len(PHRASES), "engines": out}
