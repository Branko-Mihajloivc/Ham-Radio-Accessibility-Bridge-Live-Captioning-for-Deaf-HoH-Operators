import json
import time
import wave

from vosk import KaldiRecognizer, Model

from ham_grammar import build_grammar_words

MODEL_PATH = "vosk-model-small-en-us-0.15"

t0 = time.time()
model = Model(MODEL_PATH)
print(f"Model loaded in {time.time() - t0:.1f}s")
words = build_grammar_words()
grammar = json.dumps(words + ["[unk]"])
print(f"Grammar has {len(words)} words")

rec = KaldiRecognizer(model, 16000, grammar)
rec.SetWords(True)

wf = wave.open("test_phrase.wav", "rb")
print(f"Test file: {wf.getframerate()}Hz, {wf.getnchannels()}ch, {wf.getsampwidth()} bytes/sample")

while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    if rec.AcceptWaveform(data):
        print("FINAL:", rec.Result())
    else:
        print("partial:", rec.PartialResult())

print("FINAL (flush):", rec.FinalResult())
