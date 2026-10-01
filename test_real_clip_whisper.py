import sys
import time

from faster_whisper import WhisperModel

clip_path = sys.argv[1]

t0 = time.time()
model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
print(f"Whisper loaded in {time.time() - t0:.1f}s")

t0 = time.time()
segments, info = model.transcribe(clip_path, beam_size=5, vad_filter=True, language="en")
segments = list(segments)
print(f"Transcribed in {time.time() - t0:.1f}s, language={info.language}")
for seg in segments:
    print(f"  [{seg.start:.1f}-{seg.end:.1f}] no_speech={seg.no_speech_prob:.2f} avg_logprob={seg.avg_logprob:.2f} comp_ratio={seg.compression_ratio:.2f}")
    print(f"    {seg.text}")
print("WHISPER FULL TEXT:", " ".join(s.text.strip() for s in segments))
