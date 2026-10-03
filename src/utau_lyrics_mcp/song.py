"""Lyrics + chords -> UST, backing MIDI and backing WAV."""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import backing, midi, synth, ust
from .lyrics import syllabify
from .melody import Note, assign_pitches, layout_lines
from .theory import (TICKS_PER_BEAT, ChordSpan, build_timeline, midi_to_note,
                     parse_progression, parse_range)


def default_output_dir() -> Path:
    return Path(os.environ.get("UTAU_LYRICS_OUTPUT_DIR") or Path.home() / "utau-lyrics-mcp-output")


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name).strip("_") or "song"


def _out_dir(output_dir: str | None) -> Path:
    path = Path(output_dir) if output_dir else default_output_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def song_timeline(chords: str, total_bars: int, beats_per_bar: int,
                  outro_bars: int = 0) -> list[ChordSpan]:
    """Loop the progression; the outro holds the progression's first chord."""
    bars = parse_progression(chords)
    bar_ticks = beats_per_bar * TICKS_PER_BEAT
    timeline = build_timeline(bars, total_bars - outro_bars, beats_per_bar)
    if outro_bars:
        timeline.append(ChordSpan((total_bars - outro_bars) * bar_ticks,
                                  outro_bars * bar_ticks, bars[0][0]))
    return timeline


def compose(lyrics: str, chords: str, key: str = "C", lyric_mode: str = "auto",
            voice_range: str = "A3-C5", bars_per_line: int = 2, beats_per_bar: int = 4,
            intro_bars: int = 1, seed: int = 0) -> tuple[list[Note], list[ChordSpan], int]:
    """Returns (notes, chord timeline, total bars)."""
    low, high = parse_range(voice_range)
    notes, total_bars = layout_lines(syllabify(lyrics, lyric_mode), beats_per_bar,
                                     bars_per_line, intro_bars, outro_bars=1)
    timeline = song_timeline(chords, total_bars, beats_per_bar, outro_bars=1)
    assign_pitches(notes, timeline, key, low, high, seed)
    return notes, timeline, total_bars


def write_backing(stem: Path, timeline: list[ChordSpan], total_bars: int, tempo: float,
                  beats_per_bar: int = 4, instrument: str = "piano", style: str = "arpeggio",
                  bass: bool = True, drums: bool = False, guide_notes: list[Note] | None = None,
                  guide_volume: float = 0.35, soundfont: str | None = None) -> dict:
    """Write <stem>.mid and <stem>.wav. Returns paths and which renderer was used."""
    tracks = [backing.chord_track(timeline, instrument, style)]
    if bass:
        tracks.append(backing.bass_track(timeline))
    if guide_notes and guide_volume > 0:
        tracks.append(backing.guide_track(guide_notes, guide_volume))
    if drums:
        tracks.append(backing.drum_track(total_bars, beats_per_bar))

    midi_path, wav_path = stem.with_suffix(".mid"), stem.with_suffix(".wav")
    midi.write_midi(midi_path, tracks, tempo, beats_per_bar)
    font = synth.find_soundfont(soundfont)
    if font and synth.render_with_fluidsynth(midi_path, wav_path, font):
        renderer = f"fluidsynth ({Path(font).name})"
    else:
        total_ticks = total_bars * beats_per_bar * TICKS_PER_BEAT
        synth.write_wav(wav_path, synth.render(tracks, tempo, total_ticks))
        renderer = "built-in synth"
    return {"midi": str(midi_path), "wav": str(wav_path), "renderer": renderer}


def create_song(lyrics: str, chords: str, key: str = "C", tempo: float = 100.0,
                name: str = "song", output_dir: str | None = None, lyric_mode: str = "auto",
                voice_range: str = "A3-C5", bars_per_line: int = 2, beats_per_bar: int = 4,
                intro_bars: int = 1, instrument: str = "piano", style: str = "arpeggio",
                bass: bool = True, drums: bool = False, guide_volume: float = 0.35,
                seed: int = 0, soundfont: str | None = None, voice_dir: str = "",
                ust_only: bool = False) -> dict:
    notes, timeline, total_bars = compose(lyrics, chords, key, lyric_mode, voice_range,
                                          bars_per_line, beats_per_bar, intro_bars, seed)
    out = _out_dir(output_dir)
    stem = out / _safe_name(name)
    ust_path = stem.with_suffix(".ust")
    encoding = ust.write_text(ust_path, ust.build_ust(notes, tempo, name, voice_dir))
    sung = [n for n in notes if n.pitch is not None]
    result = {
        "ust": str(ust_path),
        "ust_encoding": encoding,
        "tempo": tempo,
        "key": key,
        "bars": total_bars,
        "seconds": round(total_bars * beats_per_bar * 60 / tempo, 1),
        "syllables": len(sung),
        "melody": " ".join(f"{n.lyric}:{midi_to_note(n.pitch)}" for n in sung),
    }
    if not ust_only:
        result["backing"] = write_backing(
            out / f"{stem.name}_backing", timeline, total_bars, tempo, beats_per_bar,
            instrument, style, bass, drums, notes, guide_volume, soundfont)
    return result


def render_backing(chords: str, bars: int | None = None, tempo: float = 100.0,
                   name: str = "backing", output_dir: str | None = None,
                   beats_per_bar: int = 4, instrument: str = "piano", style: str = "arpeggio",
                   bass: bool = True, drums: bool = False, soundfont: str | None = None) -> dict:
    total_bars = bars or len(parse_progression(chords))
    timeline = song_timeline(chords, total_bars, beats_per_bar)
    result = write_backing(_out_dir(output_dir) / _safe_name(name), timeline, total_bars,
                           tempo, beats_per_bar, instrument, style, bass, drums,
                           soundfont=soundfont)
    result["bars"] = total_bars
    return result
