"""Runs a recorded clip through the EXACT same processing chain as the live
pipeline's feed_denoised() (bandpass currently disabled + DeepFilterNet3 +
resample to 16kHz), and saves the result to a WAV file to listen to
directly -- isolates whether "high pitch and garbled" is a bug in the core
processing chain (would affect real transcription) or just in the live
monitor's playback/upsampling path (cosmetic, monitor-only).
"""
import sys

import numpy as np
import soundfile as sf
import torch
from df.enhance import enhance, init_df

from live_caption import (
    BANDPASS_ENABLED, DENOISE_ATTEN_LIM_DB, DENOISE_BLOCK_S, LOOPBACK_RATE, TARGET_RATE,
)
import audioop

clip_path = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else "processed_output.wav"

audio_48k_f32, sr = sf.read(clip_path, dtype="float32")
assert sr == LOOPBACK_RATE, f"expected {LOOPBACK_RATE}Hz, got {sr}"
print(f"Loaded {len(audio_48k_f32)/sr:.1f}s at {sr}Hz. BANDPASS_ENABLED={BANDPASS_ENABLED}")

print("Loading DeepFilterNet3...")
df_model, df_state, _ = init_df()

block_samples = int(DENOISE_BLOCK_S * LOOPBACK_RATE)
resample_state = None
out_chunks_16k = []

for start in range(0, len(audio_48k_f32), block_samples):
    block = audio_48k_f32[start:start + block_samples]
    if len(block) == 0:
        continue
    tensor = torch.from_numpy(block.copy()).unsqueeze(0)
    with torch.no_grad():
        enhanced = enhance(df_model, df_state, tensor, atten_lim_db=DENOISE_ATTEN_LIM_DB)
    denoised = enhanced.squeeze(0).numpy()
    denoised_int16 = np.clip(denoised * 32767.0, -32768, 32767).astype(np.int16)
    mono16k, resample_state = audioop.ratecv(denoised_int16.tobytes(), 2, 1, LOOPBACK_RATE, TARGET_RATE, resample_state)
    out_chunks_16k.append(np.frombuffer(mono16k, dtype=np.int16))

full_16k = np.concatenate(out_chunks_16k)
sf.write(out_path, full_16k, TARGET_RATE, subtype="PCM_16")
print(f"Wrote {out_path}: {len(full_16k)/TARGET_RATE:.1f}s at {TARGET_RATE}Hz")
print("This is EXACTLY the audio Whisper/Vosk receive in the live pipeline right now.")
