"""Standalone benchmark for an NLMS Adaptive Line Enhancer (ALE) -- proves
throughput BEFORE wiring into the live pipeline, given today's repeated
lesson that new processing stages need to be verified in isolation first.
"""
import time

import numpy as np


def make_nlms_ale(delay, filter_len, mu, eps=1e-6):
    """Adaptive Line Enhancer via NLMS: predicts x[n] from a delayed copy of
    itself. Stationary/repeating noise (hiss, hum, crackle patterns) is
    predictable from its own recent past, so the filter's weights converge
    onto modeling THAT; speech is comparatively unpredictable over a short
    delay, so it survives in the residual (error) signal, which is the
    output we keep. This adapts continuously in real time -- nothing is
    persisted between calls beyond the running filter state, and it
    naturally re-adapts if the noise characteristics change (e.g. retuning
    to a different frequency).
    """
    history = np.zeros(delay + filter_len, dtype=np.float64)
    w = np.zeros(filter_len, dtype=np.float64)

    def process_block(x):
        nonlocal history, w
        out = np.empty_like(x, dtype=np.float64)
        for n in range(len(x)):
            history[:-1] = history[1:]
            history[-1] = x[n]
            u = history[:filter_len]  # oldest `filter_len` samples = delayed reference
            y = np.dot(w, u)
            e = x[n] - y
            out[n] = e
            norm = np.dot(u, u) + eps
            w += (mu / norm) * e * u
        return out

    return process_block


if __name__ == "__main__":
    RATE = 16000
    DURATION_S = 10
    n_samples = RATE * DURATION_S

    rng = np.random.default_rng(0)
    test_signal = rng.standard_normal(n_samples).astype(np.float64) * 0.1

    for filter_len in (16, 32, 64):
        ale = make_nlms_ale(delay=3, filter_len=filter_len, mu=0.1)
        t0 = time.time()
        ale(test_signal)
        elapsed = time.time() - t0
        realtime_factor = DURATION_S / elapsed
        print(f"filter_len={filter_len}: {elapsed:.2f}s to process {DURATION_S}s of audio "
              f"({realtime_factor:.1f}x real-time, {'OK' if realtime_factor > 3 else 'TOO SLOW'})")
