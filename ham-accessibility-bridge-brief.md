# Ham Radio Accessibility Bridge — Project Brief

**One-liner:** A free, open-source tool that lets a Deaf, hard-of-hearing, or non-verbal amateur radio operator work ordinary voice nets (SSB/FM) — live captioning on receive, typed-text-to-speech on transmit — by sitting between a radio's AF-out/mic-in and a computer.

Author: Branko Mihajlović (YU1FWX), President, Ham Radio Club Knjazevac
Status: pre-build — this document is the seed brief for the Claude Code build phase.

---

## 1. Problem statement

Voice modes (SSB, FM) dominate ham radio and are inaccessible to Deaf/HoH operators (can't hear the other station) and non-verbal/mute operators (can't key voice themselves). Existing digital text modes (RTTY, PSK31, FT8, JS8Call) are already 100% accessible, but only when *both* stations run compatible digital software — they don't help a Deaf/mute operator join an ordinary voice net or repeater where everyone else is talking. This project bridges that gap: convert speech to text on receive, and typed text to speech on transmit, so a Deaf/mute operator can participate in voice nets they otherwise couldn't.

Confirmed via research: no existing project does this specific combination (see §5). It's a real gap, not a reinvention.

## 2. Scope for v1

- **In scope:** English only. Two independent one-way pipelines (receive-captioning, transmit-speech). Push-to-talk style turn-taking (not full duplex) — the operator types a full thought, sends it, the software keys PTT via CAT control, speaks it, releases PTT.
- **Explicitly decided:** PTT keying is via CAT/Hamlib control (or another hardware line), **not VOX** — already ruled out because a Deaf/mute operator can't audibly confirm the radio actually keyed up.
- **Out of scope for v1:** multi-language support, full-duplex/barge-in conversation, mobile/portable hardware target (laptop/shack PC first).

## 3. Architecture

```
RECEIVE (radio → captions):
  Radio AF/speaker out
    → USB audio interface (SignaLink USB / DigiRig Mobile / RigBlaster)
    → Denoiser (DeepFilterNet3, RNNoise fallback)
    → Streaming STT engine (NVIDIA Parakeet/NeMo, primary)
    → Large-font live caption display

TRANSMIT (typed text → radio):
  Operator types text
    → TTS engine (Piper, primary)
    → USB audio interface → radio mic in
    → PTT asserted via Hamlib/rigctld (CAT control) before playback,
      released after playback ends
```

The two pipelines are independent and can be built/tested separately.

## 4. Component choices and licensing

All licenses below were confirmed free for commercial *and* non-commercial redistribution, which matters since the finished tool will be given away free.

| Stage | Primary choice | License | Notes |
|---|---|---|---|
| Radio↔PC interface | SignaLink USB / DigiRig Mobile | (hardware, not licensed) | Same interface already used by fldigi/WSJT-X; provides AF-in, AF-out, PTT line |
| PTT keying | Hamlib / rigctld (CAT) | LGPL (library) | No VOX — see §2 |
| Denoise (pre-STT) | DeepFilterNet3 | Dual MIT/Apache-2.0 | Fallback: RNNoise (BSD, Xiph.Org) — lighter weight, lower quality |
| Speech-to-text (RX) | NVIDIA NeMo toolkit + Parakeet-TDT-0.6B-v2 weights | NeMo: Apache-2.0. Parakeet weights: **CC-BY-4.0** (attribution required) | Fully local, no account/API key needed; runs CPU-only via int8 quantized weights. Supports native word-boosting/context-biasing — important for callsigns, Q-codes, phonetic alphabet, RST reports. Fallback/faster-to-prototype: WhisperLiveKit + faster-whisper (MIT-family licenses), weaker vocabulary biasing (soft `initial_prompt`/`hotwords` only) |
| Text-to-speech (TX) | Piper | MIT (software) | **Voice models have separate, per-voice licenses** — see §6 caveat, must pick a voice explicitly cleared for redistribution (CC-BY-4.0 or public domain), never a "Blizzard"-licensed voice (explicitly excludes commercialization of TTS products). Fallback: eSpeak-NG (GPL) |

## 5. Related prior art (checked — none is a direct competitor)

No existing project combines STT+TTS+PTT specifically as a Deaf/mute accessibility bridge for voice nets. Useful adjacent/reusable work found:

- **[RFWhisper](https://github.com/jakenherman/rfwhisper)** — GPLv3, active alpha. Already builds exactly the denoise front-end described above: SDR → GNU Radio → SoapySDR → DeepFilterNet3/RNNoise (ONNX Runtime) → virtual audio cable, purpose-built for amateur bands. Worth studying or forking for the denoise stage. **Caveat:** GPLv3 is copyleft — if we fork/incorporate its code directly, the combined project needs to be GPLv3 too (see §7).
- **[HamBot](https://github.com/w2sz/HamBot)** — MIT license, rough prototype (5 commits, author calls it concept-verification only). Wires Vosk STT to live ham radio audio for transcription→Mastodon posting. Proves the "radio audio → STT" plumbing works; not production-grade.
- **RadioTranscriber / RadioTransciptor / radio-capture-to-ai-speech2txt** — Whisper-over-SDR tools aimed at public-safety scanner monitoring, not ham accessibility. Same technique, different audience.
- **[AI Ham Radio Responder](https://hackaday.io/project/193997-ai-ham-radio-responder)** (Hackaday.io) — closest in spirit (STT in, TTS out, radio-integrated), but it's an autonomous auto-answering bot for when the operator is *away*, not a live tool for a present Deaf/mute operator.
- **HamPod** — discontinued (2022) accessibility device for *blind* operators; TTS-only over serial/CAT status readback, not audio-based, not STT. Different problem, same motivating community.
- General consumer apps (DeafChat, Speak2Text, Be My Voice) solve the same human problem for phone calls, not radio audio — validates the need, not reusable code.

## 6. Open questions / risks to resolve during build

1. **Vocabulary biasing list** — need to compile the actual boost list for NeMo/Parakeet: phonetic alphabet (Alpha/Bravo/Charlie…), common Q-codes (QRM, QSB, QTH, QRZ, QSY…), RST report format, and standard net phrases ("over," "roger," "break," "this is," callsign format itself).
2. **HF/SSB noise floor** — denoiser helps but HF fading (QSB) and weak-signal conditions will still hurt STT accuracy more than clean FM/repeater audio; may need separate expectations/testing for HF vs VHF/UHF.
3. **Piper voice selection** — must explicitly verify the chosen voice's MODEL_CARD license before shipping (CC-BY-4.0 or public domain only; avoid Blizzard-licensed voices entirely; note eSpeak-ng phonemizer dependency is GPL, which has its own linking implications).
4. **Project license for the finished tool** — if the denoise stage forks/reuses RFWhisper's GPLv3 code, the whole project effectively needs to ship under GPLv3 (which is fine and common for ham software, and doesn't conflict with giving it away free — just means source must stay open). If a more permissive license (MIT/Apache) is preferred, denoise should be built directly against the DeepFilterNet library (dual MIT/Apache) rather than forking RFWhisper's GPL wrapper.
5. **Regulatory check** — computer-generated voice keyed onto a phone (voice) segment from typed text is very likely fine under amateur rules, but worth a quick confirmation with RATEL (Serbia's regulator) / IARU on classification, since this isn't standard legal advice.
6. **UI for the Deaf/HoH side** — large, legible live-caption display is a hard requirement, not a nice-to-have.

## 7. Suggested build order (v1)

1. Bench-test hardware path: interface + Hamlib PTT keying only (no AI yet) — confirm CAT keying works reliably before adding software complexity.
2. TX pipeline: text box → Piper → audio out → PTT-keyed transmission. Simpler pipeline, good first milestone.
3. RX pipeline: radio audio → DeepFilterNet3 → NeMo/Parakeet → caption display. Start with WhisperLiveKit/faster-whisper if NeMo setup friction is too high initially; swap in Parakeet once the pipeline shape is proven.
4. Add ham-vocabulary word-boosting once base STT pipeline works.
5. Field test on club repeater traffic (clean FM) before HF/SSB.
6. Pick final license (leaning GPLv3 per §6.4) and publish.

## 8. Sources

- [nvidia/parakeet-tdt-0.6b-v2 (Hugging Face)](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2)
- [Nvidia launches fully open source Parakeet-TDT-0.6B-V2 (VentureBeat)](https://venturebeat.com/ai/nvidia-launches-fully-open-source-transcription-ai-model-parakeet-tdt-0-6b-v2-on-hugging-face)
- [NVIDIA-NeMo/Speech license (Apache 2.0)](https://github.com/NVIDIA-NeMo/Speech)
- [Parakeet vs Whisper vs Nemotron comparison](https://openwhispr.com/blog/parakeet-vs-whisper-vs-nemotron)
- [NVIDIA NeMo Word Boosting docs](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/asr_customization/word_boosting.html)
- [WhisperLiveKit (GitHub)](https://github.com/QuentinFuxa/WhisperLiveKit)
- [Piper LICENSE.md (MIT)](https://github.com/rhasspy/piper/blob/master/LICENSE.md)
- [Piper voice licensing discussion](https://github.com/rhasspy/piper/discussions/271)
- [DeepFilterNet LICENSE (dual MIT/Apache-2.0)](https://github.com/Rikorose/DeepFilterNet/blob/main/LICENSE)
- [RFWhisper (GitHub)](https://github.com/jakenherman/rfwhisper)
- [HamBot (GitHub)](https://github.com/w2sz/HamBot)
- [AI Ham Radio Responder (Hackaday.io)](https://hackaday.io/project/193997-ai-ham-radio-responder)
- [DigiRig vs SignaLink interfaces](https://n0luv.com/radio-reviews/2026/03/digirig-vs-signalink-which-sound-card-interface-is-right-for-you/)
- [Hamlib CAT control](https://www.hamradiobase.com/ham-tools-hamlib-rigctld-linux/)
