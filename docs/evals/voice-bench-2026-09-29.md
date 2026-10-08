# Voice stack benchmark, 2026-09-29

Question: where does conversation-mode delay come from, and which STT/TTS models and which host fix it?
Scripts: `tests/live/voice_bench/stt_bench.py`, `tts_bench.py` (run on VM 102 in an isolated `~/voice-bench` venv; nothing
production was touched). Models fetched with SHA-256 recorded in `~/voice-bench/models/SHA256SUMS` and `models/tts/SHA256SUMS`.

## Host matters more than model
| | Voice LXC 121 (bigserv) | VM 102 (pve) |
| --- | --- | --- |
| CPU | Xeon Silver 4110 (2017), 4 cores, idles at 43 % clock, no VNNI | i7-12700K, 10 vCPUs |
| Single-thread loop (12 M iterations) | 1.54 s | 0.36 s (4.3x) |
| Free RAM / disk / internet | ~1.4 GB / 3 GB / none | ~4 GB / 84 GB / yes |
| Whisper base.en, 5-8 s clip | 2.9-3.8 s (cold 12.9 s) | 0.26 s at 4 threads |

## STT on VM 102 (4 threads, 40 synthetic command clips of 1.1-3.6 s + 2 real human clips)
| Engine | Median | RTF | WER cmd | WER real (2 clips, small sample) |
| --- | --- | --- | --- | --- |
| whisper tiny.en | 0.17 s | 0.08 | 0.4 % | 4.5 % |
| whisper base.en (current model) | 0.26 s | 0.12 | 1.3 % | 3.0 % |
| whisper small.en | 0.72 s | 0.34 | 0.9 % | 1.5 % |
| moonshine tiny | 0.03 s | 0.02 | 0.0 % | 3.0 % |
| moonshine base | 0.08 s | 0.04 | 0.4 % | 3.0 % |
| parakeet-tdt-0.6b-v2 (int8) | 0.10 s | 0.06 | 0.9 % | 1.5 % |

Thread scaling (short clips are latency-bound, so more cores are SLOWER): parakeet 0.14 s at 2 threads, 0.10 s at 4, 0.30 s at
6, 0.60 s at 10; whisper base.en 0.42 / 0.26 / 0.30 / 0.31 s. Use 2-4 threads.
Caveats: the command clips are clean synthetic speech (Kokoro), so WER differences of a word or two are noise; the real-speech set is
two clips. The test that matters is John's real voice and mic, with names (Kylo, Luna, Savannah, Austin). Parakeet writes "TV" as
"T V", which would break the reflex matcher unless normalised.

## TTS on VM 102 (4 threads, synthesis time for the whole clip = time to first audio for a one-sentence clip)
| Engine | 12 chars | 35 | 70 | 140 |
| --- | --- | --- | --- | --- |
| Kokoro in the LXC today (bm_george, PyTorch CPU) | 0.9-1.6 s | 1.4 s | 2.6 s | 5.3 s |
| kokoro-onnx fp32 bm_george | 0.37 s | 0.53 s | 1.21 s | 1.85 s |
| kokoro-onnx int8 bm_george | 1.16 s | 3.53 s | 3.93 s | 6.89 s (slower: int8 does not pay here) |
| supertonic-3 M1 / M3 / F1 | 0.31-0.45 s | 0.43-0.53 s | 0.77-0.85 s | 1.32-1.42 s |

Supertonic has no British male voice and is not clearly faster than Kokoro fp32 on this CPU. Pocket-TTS (PyTorch, streaming) was not
measured. Kokoro fp32 keeps the persona voice (bm_george) at 3-4x the current speed.

## Not fixable by cores
Adding 2 cores to the LXC gives at most +50 % on a slow CPU, and short-utterance inference does not use extra threads. Moving the
voice services to VM 102 gives ~4x per thread and lets a model use a GPU if wanted.

## Side finding
The HA "Courage" pipeline's TTS is Piper `en_GB-alan-medium`, but the Piper container only has `en_US-lessac-medium` on disk: every
synthesis request crashes ("# channels not specified"), so HA voice replies are probably silent.
