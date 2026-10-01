from faster_whisper import WhisperModel

model = WhisperModel("small.en", device="cpu", compute_type="int8")

segments, info = model.transcribe("test_phrase.wav", beam_size=5)

print(f"Detected language: {info.language} (p={info.language_probability:.2f})")
for seg in segments:
    print(f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}")
