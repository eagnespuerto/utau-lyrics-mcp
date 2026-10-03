"""Place syllables in time and pick pitches that fit the chords."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .lyrics import Syllable
from .theory import TICKS_PER_BEAT, ChordSpan, chord_at, parse_key

SLOT = TICKS_PER_BEAT // 2  # eighth note
BREATH_SLOTS = 2  # rest kept at the end of each line


@dataclass
class Note:
    start: int
    length: int
    lyric: str
    pitch: int | None  # None = rest
    line_end: bool = False


def layout_lines(lines: list[list[Syllable] | None], beats_per_bar: int = 4,
                 bars_per_line: int = 2, intro_bars: int = 1,
                 outro_bars: int = 1) -> tuple[list[Note], int]:
    """Give every syllable a start and length. Returns (notes, total_bars).

    Each lyric line gets bars_per_line bars (more if it has too many
    syllables), syllables are spread on an eighth-note grid, the last one
    is held, and the line ends with a breath.
    """
    slots_per_bar = beats_per_bar * 2
    bar_ticks = beats_per_bar * TICKS_PER_BEAT
    notes: list[Note] = []
    tick = 0

    def rest(length: int) -> None:
        nonlocal tick
        if length > 0:
            notes.append(Note(tick, length, "R", None))
            tick += length

    rest(intro_bars * bar_ticks)
    for line in lines:
        if line is None:
            rest(bar_ticks)
            continue
        weight = sum(s.weight for s in line)
        bars = max(1, bars_per_line)
        while weight > bars * slots_per_bar - BREATH_SLOTS:
            bars += 1
        slots = bars * slots_per_bar
        unit = next(k for k in (4, 2, 1) if weight * k <= slots - BREATH_SLOTS)
        line_start = tick
        for i, syl in enumerate(line):
            length = syl.weight * unit
            if i == len(line) - 1:
                free = slots - weight * unit - BREATH_SLOTS
                length += max(0, min(free, slots_per_bar - length))
            notes.append(Note(tick, length * SLOT, syl.text, 0, line_end=i == len(line) - 1))
            tick += length * SLOT
        rest(line_start + slots * SLOT - tick)
    rest(outro_bars * bar_ticks)
    return notes, tick // bar_ticks


def assign_pitches(notes: list[Note], timeline: list[ChordSpan], key: str = "C",
                   low: int = 57, high: int = 72, seed: int = 0) -> None:
    """Fill in Note.pitch in place for every non-rest note.

    Notes on a beat and line endings land on chord tones; off-beat notes may
    use any scale tone. Small steps from the previous note are favoured, and
    the very last note resolves to the tonic when the chord allows it.
    """
    rng = random.Random(seed)
    tonic, scale = parse_key(key)
    center = (low + high) / 2
    sung = [n for n in notes if n.pitch is not None]
    prev: int | None = None
    for i, note in enumerate(sung):
        chord = chord_at(timeline, note.start)
        on_beat = note.start % TICKS_PER_BEAT == 0
        if on_beat or note.line_end or prev is None:
            allowed = chord.pitch_classes
        else:
            allowed = scale | chord.pitch_classes
        if i == len(sung) - 1 and tonic in chord.pitch_classes:
            allowed = frozenset({tonic})
        candidates = [p for p in range(low, high + 1) if p % 12 in allowed]
        if not candidates:
            candidates = list(range(low, high + 1))
        ref = center if prev is None else prev
        weights = [math.exp(-abs(p - ref) / 2.5) * math.exp(-abs(p - center) / 8)
                   * (0.2 if p == prev else 1.0) for p in candidates]
        note.pitch = prev = rng.choices(candidates, weights)[0]
