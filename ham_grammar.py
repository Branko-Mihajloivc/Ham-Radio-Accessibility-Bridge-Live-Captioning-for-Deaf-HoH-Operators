"""
Vosk grammar word list for the constrained callsign/Q-code/RST channel.

This is NOT a list of sentences -- Vosk's grammar mode restricts the active
VOCABULARY to these words and freely recognizes any sequence of them, which
is exactly what's needed for callsigns (arbitrary-length phonetic letter
sequences) without enumerating every possible callsign.

IMPORTANT: this list is scoped to what vosk-model-small-en-us-0.15's own
vocabulary actually contains -- that's the model that supports runtime
grammar constraint at all (the larger vosk-model-en-us-0.22 ships a
monolithic graph that silently ignores the grammar entirely, per its own
"Runtime graphs are not supported by this model" warning). Vosk's grammar
mode can only restrict to a SUBSET of words the model already knows; it
can't teach it new words on the fly.

Verified gaps as of 2026-09-07 (confirmed by feeding a full candidate list
and checking Vosk's "Ignoring word missing in vocabulary" warnings):
  - The letter X ("x-ray"/"xray") is missing entirely -- callsigns containing
    X currently can't be spelled correctly through this channel.
  - Almost the entire Q-code table is missing except qrs, qsb, qtr.
Both are real, known limitations, not bugs -- fixing them for real needs
extending the small model's pronunciation lexicon with the missing words
(no audio data required, just correct phonetics), not just editing this
list. Revisit that when this initial version has been tested enough to
justify the effort.
"""

NATO_PHONETIC = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliet", "kilo", "lima", "mike", "november", "oscar",
    "papa", "quebec", "romeo", "sierra", "tango", "uniform", "victor",
    "whiskey", "yankee", "zulu",
    # NOTE: "x-ray"/"xray" deliberately omitted -- both rejected by the
    # small model's vocabulary. Letter X is unrecognizable until the
    # lexicon is extended.
]

DIGITS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "niner", "fife",  # aviation/military-style alternates
]

# Only these three Q-codes exist in the small model's vocabulary at all.
# The rest of the standard Q-code table (qrz, qsy, qrx, qth, qsl, ...) is
# missing and needs the lexicon-extension work noted above.
Q_CODES = ["qrs", "qsb", "qtr"]

RST_AND_NET_WORDS = [
    "cq", "dx", "de", "over", "roger", "wilco", "break", "this", "is",
    "calling", "receiving", "copy", "copied", "report", "signal", "readability",
    "strength", "tone", "loud", "clear", "solid", "weak", "seven", "three",
    "seventy", "and", "with", "you", "are", "the",
]


def build_grammar_words():
    words = set()
    for group in (NATO_PHONETIC, DIGITS, Q_CODES, RST_AND_NET_WORDS):
        words.update(w.lower() for w in group)
    return sorted(words)


if __name__ == "__main__":
    words = build_grammar_words()
    print(f"{len(words)} grammar words:")
    print(" ".join(words))
