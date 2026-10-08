"""STT benchmark on VM 102: latency, real-time factor and WER on short command clips. Isolated in ~/voice-bench."""
import glob, os, re, statistics, sys, time
import numpy as np
import soundfile as sf

ROOT = os.path.expanduser("~/voice-bench")
M = f"{ROOT}/models"
THREADS = int(os.environ.get("THREADS", "4"))
ONLY = set(sys.argv[1:])


def norm(t):
    t = t.lower().replace("seventy two", "72").replace("seventy-two", "72")
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    return t.split()


def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)], len(r)


clips = []
for f in sorted(glob.glob(f"{ROOT}/clips/*.wav")):
    x, sr = sf.read(f, dtype="float32")
    clips.append((f, x, sr, open(f.replace(".wav", ".txt")).read().strip()))
real = []
tr = {l.split(" ", 1)[0]: l.split(" ", 1)[1].strip() for l in open(f"{M}/sherpa-onnx-moonshine-tiny-en-int8/test_wavs/trans.txt") if " " in l}
for name in ("0.wav", "1.wav"):
    x, sr = sf.read(f"{M}/sherpa-onnx-moonshine-tiny-en-int8/test_wavs/{name}", dtype="float32")
    real.append((name, x if x.ndim == 1 else x[:, 0], sr, tr.get(name, "")))


def engines():
    import sherpa_onnx as so
    from faster_whisper import WhisperModel
    for name in ("tiny.en", "base.en", "small.en"):
        for beam in ((1, 5) if name == "base.en" else (1,)):
            yield f"whisper-{name} beam{beam}", (lambda n=name: WhisperModel(n, device="cpu", compute_type="int8", cpu_threads=THREADS, download_root=f"{M}/whisper")), \
                (lambda m, x, sr, b=beam: " ".join(s.text for s in m.transcribe(x, language="en", beam_size=b, vad_filter=False, condition_on_previous_text=False)[0]))
    for size in ("tiny", "base"):
        d = f"{M}/sherpa-onnx-moonshine-{size}-en-int8"
        yield f"moonshine-{size}", (lambda d=d: so.OfflineRecognizer.from_moonshine(
            preprocessor=f"{d}/preprocess.onnx", encoder=f"{d}/encode.int8.onnx", uncached_decoder=f"{d}/uncached_decode.int8.onnx",
            cached_decoder=f"{d}/cached_decode.int8.onnx", tokens=f"{d}/tokens.txt", num_threads=THREADS)), \
            (lambda m, x, sr: _sherpa(m, x, sr))
    d = f"{M}/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
    yield "parakeet-tdt-0.6b-v2", (lambda: so.OfflineRecognizer.from_transducer(
        encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx", joiner=f"{d}/joiner.int8.onnx", tokens=f"{d}/tokens.txt",
        num_threads=THREADS, model_type="nemo_transducer")), (lambda m, x, sr: _sherpa(m, x, sr))


def _sherpa(rec, x, sr):
    s = rec.create_stream()
    s.accept_waveform(sr, x)
    rec.decode_stream(s)
    return s.result.text


print(f"threads={THREADS}, {len(clips)} command clips (median {statistics.median(len(c[1]) / c[2] for c in clips):.1f}s), {len(real)} real-speech clips")
print(f"{'engine':26} {'load':>5} {'median':>7} {'p95':>6} {'RTF':>6} {'WER cmd':>8} {'WER real':>9}")
for name, load, run in engines():
    if ONLY and not any(o in name for o in ONLY):
        continue
    t = time.time(); m = load(); lt = time.time() - t
    run(m, clips[0][1], clips[0][2])              # warm-up
    lat, err, tot, dur = [], 0, 0, 0.0
    bad = []
    for f, x, sr, ref in clips:
        t = time.time(); hyp = run(m, x, sr); dt = time.time() - t
        lat.append(dt); dur += len(x) / sr
        e, n = wer(ref, hyp); err += e; tot += n
        if e and len(bad) < 3: bad.append((ref, hyp.strip()))
    rerr = rtot = 0
    for f, x, sr, ref in real:
        e, n = wer(ref, run(m, x, sr)); rerr += e; rtot += n
    lat.sort()
    print(f"{name:26} {lt:5.1f} {statistics.median(lat):6.2f}s {lat[int(.95 * (len(lat) - 1))]:5.2f}s {sum(lat) / dur:6.2f} {100 * err / tot:7.1f}% {100 * rerr / max(rtot, 1):8.1f}%")
    for ref, hyp in bad:
        print(f"      e.g. {ref!r} -> {hyp!r}")
