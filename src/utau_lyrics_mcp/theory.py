"""Note names, chord symbols, keys and the chord timeline."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

TICKS_PER_BEAT = 480

_LETTER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_ACCIDENTAL = {"": 0, "#": 1, "b": -1}

QUALITIES: dict[str, tuple[int, ...]] = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "5": (0, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "9": (0, 4, 7, 10, 14),
    "add9": (0, 4, 7, 14),
}
_ALIASES = {"M": "", "maj": "", "min": "m", "-": "m", "sus": "sus4", "M7": "maj7",
            "min7": "m7", "-7": "m7", "+": "aug", "o": "dim", "o7": "dim7"}

MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)


def pitch_class(name: str) -> int:
    m = re.fullmatch(r"([A-Ga-g])([#b]?)", name.strip())
    if not m:
        raise ValueError(f"Not a note name: {name!r}")
    return (_LETTER[m.group(1).upper()] + _ACCIDENTAL[m.group(2)]) % 12


def note_to_midi(name: str) -> int:
    """'C4' -> 60, matching UTAU's NoteNum."""
    m = re.fullmatch(r"([A-Ga-g][#b]?)(-?\d+)", name.strip())
    if not m:
        raise ValueError(f"Not a note with octave: {name!r}")
    return 12 * (int(m.group(2)) + 1) + pitch_class(m.group(1))


def midi_to_note(n: int) -> str:
    return f"{_NAMES[n % 12]}{n // 12 - 1}"


def parse_range(text: str) -> tuple[int, int]:
    """'A3-C5' -> (57, 72)."""
    m = re.fullmatch(r"\s*([A-Ga-g][#b]?-?\d+)\s*-\s*([A-Ga-g][#b]?-?\d+)\s*", text)
    if not m:
        raise ValueError(f"Voice range should look like 'A3-C5', got {text!r}")
    low, high = note_to_midi(m.group(1)), note_to_midi(m.group(2))
    if low > high:
        low, high = high, low
    return low, high


@dataclass(frozen=True)
class Chord:
    symbol: str
    root: int
    intervals: tuple[int, ...]
    bass: int

    @property
    def pitch_classes(self) -> frozenset[int]:
        return frozenset((self.root + i) % 12 for i in self.intervals)


def parse_chord(symbol: str) -> Chord:
    m = re.fullmatch(r"([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?", symbol.strip())
    if not m:
        raise ValueError(f"Cannot read chord {symbol!r}")
    quality = _ALIASES.get(m.group(2), m.group(2))
    if quality not in QUALITIES:
        known = ", ".join(q or "(major)" for q in QUALITIES)
        raise ValueError(f"Unknown chord quality in {symbol!r}. Known: {known}")
    root = pitch_class(m.group(1))
    bass = pitch_class(m.group(3)) if m.group(3) else root
    return Chord(symbol.strip(), root, QUALITIES[quality], bass)


def parse_progression(text: str) -> list[list[Chord]]:
    """'C | Am | F G | %' -> one list of chords per bar.

    Bars are separated by '|' or newlines, chords inside a bar share it
    equally, and '%' repeats the previous bar.
    """
    bars: list[list[Chord]] = []
    for raw in re.split(r"[|\n]", text):
        tokens = raw.split()
        if not tokens:
            continue
        if tokens == ["%"]:
            if not bars:
                raise ValueError("'%' needs a bar before it")
            bars.append(bars[-1])
        else:
            bars.append([parse_chord(t) for t in tokens])
    if not bars:
        raise ValueError("The chord progression is empty")
    return bars


def parse_key(key: str) -> tuple[int, frozenset[int]]:
    """'C' / 'F#m' -> (tonic pitch class, scale pitch classes)."""
    m = re.fullmatch(r"([A-G][#b]?)(m|min|maj|M)?", key.strip())
    if not m:
        raise ValueError(f"Key should look like 'C', 'Bb' or 'F#m', got {key!r}")
    tonic = pitch_class(m.group(1))
    steps = MINOR if m.group(2) in ("m", "min") else MAJOR
    return tonic, frozenset((tonic + s) % 12 for s in steps)


@dataclass(frozen=True)
class ChordSpan:
    start: int
    length: int
    chord: Chord


def build_timeline(bars: list[list[Chord]], total_bars: int, beats_per_bar: int = 4) -> list[ChordSpan]:
    """Loop the progression over total_bars and lay it out in ticks."""
    bar_ticks = beats_per_bar * TICKS_PER_BEAT
    spans: list[ChordSpan] = []
    for b in range(total_bars):
        chords = bars[b % len(bars)]
        step = bar_ticks // len(chords)
        for i, chord in enumerate(chords):
            length = bar_ticks - step * i if i == len(chords) - 1 else step
            spans.append(ChordSpan(b * bar_ticks + step * i, length, chord))
    return spans


def chord_at(timeline: list[ChordSpan], tick: int) -> Chord:
    i = bisect.bisect_right([s.start for s in timeline], tick) - 1
    return timeline[max(i, 0)].chord
