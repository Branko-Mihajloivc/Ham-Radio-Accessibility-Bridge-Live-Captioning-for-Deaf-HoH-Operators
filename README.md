# Ham Radio Accessibility Bridge — RX / Speech-to-Text Pipeline

Live captioning from radio audio: capture -> denoise -> VAD -> STT, shown
in a large-font scrolling window, plus a parallel grammar-constrained
channel for callsigns/Q-codes. Built so Deaf and hard-of-hearing
operators can follow live ham radio traffic as readable text.

See [`ham-accessibility-bridge-brief.md`](ham-accessibility-bridge-brief.md)
for the overall project scope (this RX/STT pipeline is one half of it; a
TX/text-to-speech path is planned but not yet started), and
[`Ham_Radio_Accessibility_Bridge_Technical_Overview.pdf`](Ham_Radio_Accessibility_Bridge_Technical_Overview.pdf)
for a fuller narrative writeup of the architecture and findings below.

Screenshots of the live audio-filter testing (spectrograms comparing
noise/strong/weak signal before and after the filter chain) are in
[`docs/images/`](docs/images/).

## One-time setup note: antivirus HTTPS interception (Avast and similar)

Some antivirus products (Avast's HTTPS/Mail Shield is the one this was
built against) do TLS interception, which can break `pip` and
`huggingface_hub` downloads with `CERTIFICATE_VERIFY_FAILED` — Python's
bundled certifi list doesn't trust the AV's injected certificate the way
the OS does. If you hit this:

1. Export your AV's root certificate from the Windows certificate store
   (`Cert:\LocalMachine\Root` in PowerShell) as PEM.
2. Append it to a copy of pip's vendored certifi `cacert.pem`.
3. Point these two env vars at the merged file before running `pip
   install` or a script that downloads a model for the first time:

```powershell
$env:SSL_CERT_FILE = "C:\path\to\merged-ca-bundle.pem"
$env:REQUESTS_CA_BUNDLE = "C:\path\to\merged-ca-bundle.pem"
```

If instead you hit `not enough data: cadata does not contain a
certificate` (a different, rarer error — usually a malformed cert
elsewhere in the Windows Root store), that one isn't fixable via the env
vars above since it comes from Python's raw `ssl` module reading the
Windows store directly, not from certifi/requests. `live_caption.py`
already works around this at the top of the file by patching
`ssl.SSLContext.load_default_certs` to skip unparseable certs instead of
crashing — no action needed, it's a standing fix in the script.

## Run it

```powershell
.venv\Scripts\Activate.ps1
python live_caption.py --gui             # large-font window (recommended) -- default: loopback from FlexRemote
python live_caption.py                   # console mode, same default source
python live_caption.py --list-devices    # list device/speaker indices
python live_caption.py --device N        # switch to a physical radio interface's line-in
python live_caption.py --pick            # interactive source picker
```

Default source is loopback from FlexRemote/SmartSDR's "System Default"
output (easiest for testing, no cable). Switching to a physical interface
later is just `--device N` — both paths feed the same pipeline, no
rebuild needed.

## Online mode (`--engine deepgram`) — NOT for off-grid/emergency use

By default this runs fully offline (`--engine local`, the default): local
Whisper + DeepFilterNet3, no internet required once the models are
downloaded. That matters because ham radio's biggest value is often
exactly the situation where internet/cellular infrastructure is down.

`--engine deepgram` is a separate, optional mode that streams audio to
Deepgram's cloud STT instead. It's generally more accurate and lower-
latency than the local "small" Whisper model, especially on fast/unusual
speech (e.g. rapid phonetic callsign spelling), but it **requires internet
and gives up the off-grid capability entirely** — this is a deliberate
trade-off to ship something more usable sooner, not an oversight. State
this plainly to anyone using it: this mode is for normal net operation
with connectivity, not for grid-down/emergency scenarios.

Setup: create a free account at console.deepgram.com, generate an API
key, then set it as an environment variable before running (never commit
it to a file in this repo):

```powershell
$env:DEEPGRAM_API_KEY = "your-key-here"
python live_caption.py --gui --engine deepgram
```

The parallel Vosk callsign/Q-code channel and the waterfall/audio monitor
work the same in both modes; only the main transcript's source changes.
The tuning sliders (bandpass, DF3 atten, spectral gate) have no effect in
this mode since neither DeepFilterNet3 nor local bandpass filtering runs
in the Deepgram path — audio goes to Deepgram largely as captured.

## Architecture

```
capture (mic or loopback, 48kHz)
  -> Noise Blanker       [off by default -- confirmed unusable live, see limitations]
  -> Bandpass 300-3000Hz [off by default -- confirmed net-negative live]
  -> Spectral Subtraction [off by default -- VALIDATED: net positive live.
     over_subtract=2.0, floor=30% is the live-tested-good setting]
  -> Noise Gate          [off by default -- VALIDATED alongside Subtraction.
     threshold_db must stay 1-2, higher cuts real weak signal]
  -> Spectral Gate       [off by default -- confirmed no improvement, even
     after a harmonic-aware rebuild]
  -> DeepFilterNet3 (denoise, atten_lim_db=4 -- LOWER than you'd expect:
     higher values made its own per-block state-reset artifact more
     audible, not less, on real HF interference)
  -> resample to 16kHz
  -> fan out to:
       - webrtcvad + pitch-detector-gated VAD/turn segmentation ->
         faster-whisper ("small", multilingual model, language forced to
         English by default, ham-vocabulary hotwords) -> main transcript
         (word-by-word ticker)
       - Vosk (small model, grammar-constrained to phonetic alphabet /
         digits / a few Q-codes / net procedure words) -> parallel
         callsign/Q-code channel, true streaming, independent of Whisper's
         utterance boundaries
       - raw + processed audio taps -> waterfall display + audio monitor
```

Every filter-chain stage is independently toggleable live via GUI
checkboxes/sliders — none of it is hardcoded on or off. See
`Ham_Radio_Accessibility_Bridge_Technical_Overview.pdf` in this repo for
the full validated-vs-negative-result writeup and the reasoning behind
each stage, including a confirmed real bug (Spectral Subtraction's own
"musical noise" residue was measured to fool the Noise Gate's pitch
detector into false-opening on pure noise 17% of the time) and how it
was fixed. The filter chain itself has also been extracted as a
standalone, speech-recognition-independent library (separate repo,
link to follow) if you just want the denoising, not the STT.

Three engines run concurrently (Whisper, DeepFilterNet3, Vosk) plus the
GUI and audio I/O threads. `OMP_NUM_THREADS=2` is set at the top of
`live_caption.py` and each engine's own thread count is capped (3 each)
-- **do this before adding any new concurrent processing stage**; every
"freeze/slowdown/garbled output" bug hit this session traced back to CPU
oversubscription across these engines, not VAD or model logic.

## GUI features

- **Scrolling transcript** with permanent history — nothing is ever
  overwritten. A Deaf/HoH operator can't ask "what did you just say?",
  so anything shown must stay visible.
- **Word-by-word ticker**: each word commits permanently as soon as a
  newer word follows it (streaming/redecode ASR essentially never
  revises words it's already moved past). Only the last word or two is
  shown dim/live. A `----- HH:MM:SS -----` marker separates transmissions
  since utterance boundaries otherwise disappear into one continuous flow.
- **Level meter**: raw per-frame RMS + webrtcvad speech/noise flag
  (flickers frame-to-frame by design — watch the caption text turning
  green for the actual debounced speech-detected state, not the bar).
- **Waterfall** (`WATERFALL_*` constants): shows the RAW pre-filter signal
  spectrum, same purpose as an SDR panadapter — visually confirm what's
  on the air. 300-3000Hz-ish range, ~6s of scrolling history.
- **Audio monitor** (🔊 button, cycles Off/Raw/Processed): plays back
  either the raw incoming audio or the fully-processed (denoised)
  audio, so filtering can be judged by ear, not just by transcription
  quality — useful for telling whether noise reduction is cutting too
  much or too little.
- **Vosk channel** (blue box): parallel grammar-constrained callsign/Q-code
  recognition, separate history from the main transcript.

## Known limitations / open items

1. **Bandpass filter, Noise Blanker, and Spectral Gate are all DISABLED
   by default — each confirmed NOT to help on real HF audio.** Bandpass
   (300-3000Hz, built on sound-seeming DSP reasoning) measurably *hurt*
   transcription in real A/B testing, even on a clip Whisper already
   transcribed perfectly unfiltered. The Noise Blanker (a hardware-style
   impulse/click suppressor) was confirmed unusable live even after
   widening its settings. The Spectral Gate (a per-bin frequency gate,
   later rebuilt to be harmonic-aware) showed no measurable improvement
   either version. Don't re-enable any of these without new A/B evidence
   from real audio — see the technical overview PDF for the full story
   on each.
2. **Spectral Subtraction + Noise Gate are the validated, working
   combination — also off by default pending more live tuning.**
   Spectral Subtraction (over_subtract=2.0, floor=30%) does most of the
   actual noise reduction; the Noise Gate (threshold_db kept very low,
   1-2) works well alongside it. Still open: whether Subtraction's
   residual "musical noise" artifact measurably confuses Whisper (not
   yet tested with real transcript comparisons), and further live tuning
   of the Gate's release time.
3. **NLMS Adaptive Line Enhancer — built and benchmarked, NOT integrated.**
   `bench_nlms.py` has a working, fast (~26x real-time) NLMS filter
   implementing the "learn and cancel the predictable/stationary noise"
   idea. `test_full_chain.py` showed it made transcription *dramatically*
   worse (introduced outright hallucinated content on a previously-perfect
   clip) with the tested parameters (delay=3, filter_len=32, mu=0.1).
   The underlying technique is sound and worth revisiting with different
   tuning, but don't wire it into the live pipeline without new A/B
   evidence it helps.
4. **Vosk's grammar vocabulary is incomplete.** Only `qrs`/`qsb`/`qtr`
   survive from the full Q-code table, and the letter X ("x-ray") is
   missing entirely — the small model's base vocabulary doesn't contain
   the rest. Fixing this needs extending the model's pronunciation
   lexicon (no audio data needed, just correct phonetics), not just
   editing `ham_grammar.py`. See its docstring for the confirmed gaps.
5. **NVIDIA Parakeet-TDT-0.6b-v2 evaluated as an alternative engine**
   (separate venv, kept isolated since NeMo wants a different torch
   version than DeepFilterNet3). Result: no decisive accuracy win over
   Whisper across 4 test clips. Its real advantages are structural
   (fails silently instead of hallucinating fluent nonsense; correctly
   handles rare vocabulary like "QRZ" via native word-boosting
   potential), not raw content-recovery on weak signal. Not integrated.
6. **Weak/marginal HF signal remains a hard, likely unsolvable-by-software
   limit** — on signals close to the noise floor, content can be
   genuinely unrecoverable to both engines and sometimes to the human
   ear too (confirmed by the user's own self-corrections while providing
   ground truth on one test clip). Don't chase this as a "bug."
7. VU meter / RX-TX volume sliders (nice-to-have, not yet built).
8. TX pipeline (typed text -> TTS -> PTT) not started.

## Key files

- `live_caption.py` — the live pipeline + GUI.
- `ham_grammar.py` — Vosk grammar vocabulary (see docstring for coverage gaps).
- `bench_nlms.py` — standalone NLMS filter, benchmarked but not integrated (see limitation #2).
- `test_full_chain.py` — offline A/B test harness (bandpass/DF3/NLMS vs. raw) against real recorded clips.
- `test_transcribe.py`, `test_real_clip_whisper.py`, `test_vosk_grammar.py` — smaller standalone smoke tests.
