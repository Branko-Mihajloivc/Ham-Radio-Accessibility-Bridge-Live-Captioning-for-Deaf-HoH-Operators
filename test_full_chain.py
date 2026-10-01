"""Offline test of the full new processing chain (bandpass -> DeepFilterNet3
-> NLMS ALE) against known-hard clips with confirmed ground truth, before
wiring any of this into the live pipeline. Resampling matches live_caption.py
exactly (audioop.ratecv), not a different method, so this is a fair test of
what the live pipeline would actually produce.
"""
import audioop
import sys

import numpy as np
import soundfile as sf
import torch
from df.enhance import enhance, init_df
from faster_whisper import WhisperModel
from scipy.signal import butter, sosfilt, sosfilt_zi

from bench_nlms import make_nlms_ale

BANDPASS_LOW_HZ = 300
BANDPASS_HIGH_HZ = 3000
BANDPASS_ORDER = 6
RATE_48K = 48000
RATE_16K = 16000

clip_path = sys.argv[1]

audio_48k_f32, sr = sf.read(clip_path, dtype="float32")
assert sr == RATE_48K, f"expected {RATE_48K}Hz, got {sr}"
print(f"Loaded {len(audio_48k_f32)/sr:.1f}s of audio at {sr}Hz")

int16_48k = np.clip(audio_48k_f32 * 32767.0, -32768, 32767).astype(np.int16)


def resample(int16_bytes, rate_in, rate_out):
    out, _ = audioop.ratecv(int16_bytes, 2, 1, rate_in, rate_out, None)
    return np.frombuffer(out, dtype=np.int16)


# Stage 1: bandpass (300-3000Hz), applied on float32 like the live pipeline
sos = butter(BANDPASS_ORDER, [BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ], btype="bandpass", fs=RATE_48K, output="sos")
zi = sosfilt_zi(sos)
bandpassed_f32, _ = sosfilt(sos, audio_48k_f32, zi=zi)
bandpassed_f32 = bandpassed_f32.astype(np.float32)

# Stage 2: DeepFilterNet3
print("Loading DeepFilterNet3...")
df_model, df_state, _ = init_df()
tensor = torch.from_numpy(bandpassed_f32).unsqueeze(0)
with torch.no_grad():
    enhanced = enhance(df_model, df_state, tensor, atten_lim_db=15.0)
denoised_48k_f32 = enhanced.squeeze(0).numpy()
denoised_int16_48k = np.clip(denoised_48k_f32 * 32767.0, -32768, 32767).astype(np.int16)

# Resample 48k -> 16k via audioop, same as live_caption.py
raw_16k = resample(int16_48k.tobytes(), RATE_48K, RATE_16K)
denoised_16k = resample(denoised_int16_48k.tobytes(), RATE_48K, RATE_16K)

# Stage 3: NLMS ALE at 16kHz
print("Running NLMS ALE...")
ale = make_nlms_ale(delay=3, filter_len=32, mu=0.1)
ale_out_f64 = ale(denoised_16k.astype(np.float64) / 32768.0)
ale_out_int16 = np.clip(ale_out_f64 * 32767.0, -32768, 32767).astype(np.int16)

print("Loading Whisper...")
model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)


def transcribe(label, int16_audio):
    f32 = int16_audio.astype(np.float32) / 32768.0
    segments, info = model.transcribe(f32, beam_size=5, vad_filter=True, language="en", condition_on_previous_text=False)
    segments = list(segments)
    text = " ".join(s.text.strip() for s in segments)
    print(f"\n=== {label} ===")
    for seg in segments:
        print(f"  no_speech={seg.no_speech_prob:.2f} avg_logprob={seg.avg_logprob:.2f}  {seg.text}")
    print(f"FULL TEXT: {text}")


transcribe("RAW (no processing)", raw_16k)
transcribe("BANDPASS + DEEPFILTERNET3 (no ALE)", denoised_16k)
transcribe("BANDPASS + DEEPFILTERNET3 + NLMS ALE", ale_out_int16)
