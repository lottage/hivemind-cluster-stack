"""TTS benchmark on VM 102: synthesis time (= time to first audio when a clip is one sentence) and real-time factor."""
import os, statistics, sys, time
import numpy as np
import soundfile as sf

ROOT = os.path.expanduser("~/voice-bench")
OUT = f"{ROOT}/tts_out"; os.makedirs(OUT, exist_ok=True)
THREADS = int(os.environ.get("THREADS", "4"))
TEXTS = {"12": "Right. Done.", "35": "The living room lights are now off.",
         "70": "The living room lights are now off, and the thermostat is set to 72.",
         "140": "It is currently 72 degrees in the living room, the front door is locked, and nobody has been seen on the driveway camera for about an hour."}
ONLY = set(sys.argv[1:])


def run(label, synth):
    synth("Warm up.")
    row = []
    for k, t in TEXTS.items():
        best = 1e9
        for _ in range(2):
            t0 = time.time(); wav, sr = synth(t); dt = time.time() - t0; best = min(best, dt)
        dur = len(wav) / sr
        sf.write(f"{OUT}/{label.replace(' ', '_')}_{k}.wav", wav, sr)
        row.append(f"{k}ch {best:.2f}s (RTF {best / dur:.2f})")
    print(f"{label:24} " + " | ".join(row), flush=True)


if not ONLY or "kokoro" in ONLY:
    from kokoro_onnx import Kokoro
    import onnxruntime as ort
    for name in ("kokoro-v1.0.int8.onnx", "kokoro-v1.0.onnx"):
        so = ort.SessionOptions(); so.intra_op_num_threads = THREADS
        k = Kokoro(f"{ROOT}/models/tts/{name}", f"{ROOT}/models/tts/voices-v1.0.bin")
        run(f"kokoro-onnx {'int8' if 'int8' in name else 'fp32'} bm_george", lambda t, k=k: (lambda r: (r[0], r[1]))(k.create(t, voice="bm_george", speed=1.06, lang="en-gb")))

if not ONLY or "supertonic" in ONLY:
    from supertonic import TTS
    tts = TTS(intra_op_num_threads=THREADS)
    for v in ("M1", "M3", "F1"):
        try:
            style = tts.get_voice_style(voice_name=v)
        except Exception as e:
            print("supertonic voice", v, "err", e); continue
        def synth(t, style=style):
            r = tts.synthesize(t, voice_style=style, lang="en")
            wav = r[0] if isinstance(r, tuple) else r
            wav = np.asarray(wav).reshape(-1)
            return wav, tts.sample_rate
        run(f"supertonic-3 {v}", synth)
