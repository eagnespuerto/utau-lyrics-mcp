"""Turn the chord timeline into accompaniment tracks."""

from __future__ import annotations

from dataclasses import dataclass, field

from .melody import Note
from .theory import TICKS_PER_BEAT, Chord, ChordSpan

# name -> General MIDI program (0-based). The same names select a timbre in
# the built-in synth, and the GM program is what a SoundFont will play.
INSTRUMENTS = {"piano": 0, "epiano": 4, "organ": 19, "guitar": 24,
               "strings": 48, "pad": 89, "bass": 32, "flute": 73}
STYLES = ("block", "strum", "arpeggio")
DRUM_CHANNEL = 9
KICK, SNARE, HAT = 36, 38, 42


@dataclass
class Event:
    start: int
    length: int
    pitch: int
    velocity: int


@dataclass
class Track:
    name: str
    instrument: str  # key of INSTRUMENTS, or "drums"
    channel: int
    gain: float = 1.0
    events: list[Event] = field(default_factory=list)


def voice_chord(chord: Chord) -> list[int]:
    """Close voicing with the root between G#2 and G3."""
    root = 48 + chord.root
    if root > 55:
        root -= 12
    return [root + i for i in chord.intervals]


def chord_track(timeline: list[ChordSpan], instrument: str = "piano",
                style: str = "arpeggio") -> Track:
    if instrument not in INSTRUMENTS:
        raise ValueError(f"instrument must be one of {sorted(INSTRUMENTS)}, got {instrument!r}")
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}, got {style!r}")
    track = Track("Chords", instrument, 0, gain=0.5)
    for span in timeline:
        pitches = voice_chord(span.chord)
        if style == "block":
            track.events += [Event(span.start, span.length, p, 70) for p in pitches]
        elif style == "strum":
            for offset in range(0, span.length, TICKS_PER_BEAT):
                length = min(TICKS_PER_BEAT, span.length - offset) * 9 // 10
                velocity = 78 if offset == 0 else 62
                track.events += [Event(span.start + offset, length, p, velocity) for p in pitches]
        else:
            step = TICKS_PER_BEAT // 2
            order = [*range(len(pitches)), *range(len(pitches) - 2, 0, -1)] or [0]
            for i, offset in enumerate(range(0, span.length, step)):
                length = min(TICKS_PER_BEAT, span.length - offset)
                track.events.append(Event(span.start + offset, length,
                                          pitches[order[i % len(order)]], 74 if i == 0 else 64))
    return track


def bass_track(timeline: list[ChordSpan]) -> Track:
    track = Track("Bass", "bass", 1, gain=0.7)
    for span in timeline:
        root = 36 + span.chord.bass
        if root > 45:
            root -= 12
        half = 2 * TICKS_PER_BEAT
        track.events.append(Event(span.start, min(span.length, half) * 19 // 20, root, 88))
        if span.length >= 2 * half:
            fifth = 7 if 7 in span.chord.intervals and span.chord.bass == span.chord.root else 0
            track.events.append(Event(span.start + half, half * 19 // 20, root + fifth, 76))
    return track


def drum_track(total_bars: int, beats_per_bar: int = 4) -> Track:
    track = Track("Drums", "drums", DRUM_CHANNEL, gain=0.5)
    for bar in range(total_bars):
        for beat in range(beats_per_bar):
            tick = (bar * beats_per_bar + beat) * TICKS_PER_BEAT
            track.events.append(Event(tick, 120, SNARE if beat % 2 else KICK, 90))
            track.events.append(Event(tick, 60, HAT, 60))
            track.events.append(Event(tick + TICKS_PER_BEAT // 2, 60, HAT, 45))
    return track


def guide_track(notes: list[Note], volume: float = 0.35) -> Track:
    """The vocal melody on a flute, so the singer's pitch has a reference."""
    track = Track("Guide melody", "flute", 2, gain=0.8)
    velocity = max(1, min(127, round(127 * volume)))
    track.events = [Event(n.start, n.length, n.pitch, velocity)
                    for n in notes if n.pitch is not None]
    return track
