"""Render backing tracks to WAV.

Two paths: FluidSynth with an open-source SoundFont (real sampled
instruments), or the built-in additive synth below, which needs nothing
but numpy and is the fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from .backing import HAT, KICK, SNARE, Track
from .theory import TICKS_PER_BEAT

SR = 44100
TAU = 2 * np.pi


def _shape(dur: float, attack: float, release: float) -> tuple[np.ndarray, np.ndarray]:
    """Time axis and an attack/release envelope for a note held for dur seconds."""
    t = np.arange(int((dur + release) * SR)) / SR
    env = np.minimum(1.0, t / attack) * np.clip((dur + release - t) / release, 0.0, 1.0)
    return t, env


def _harmonics(f: float, t: np.ndarray, amps: dict[int, float], decay: float = 0.0,
               detune: float = 0.0) -> np.ndarray:
    """Sum of sine partials; decay makes higher partials die faster."""
    out = np.zeros_like(t)
    for h, amp in amps.items():
        if f * h >= SR / 2:
            continue
        partial = np.sin(TAU * f * h * t)
        if detune:
            partial = (partial + np.sin(TAU * f * h * (1 + detune) * t)
                       + np.sin(TAU * f * h * (1 - detune) * t)) / 3
        out += amp * partial * (np.exp(-t * decay * h) if decay else 1.0)
    return out


def _piano(f, dur):
    t, env = _shape(dur, 0.004, 0.25)
    return env * np.exp(-t * 0.9) * _harmonics(f, t, {h: h ** -1.3 for h in range(1, 7)}, 0.5)


def _guitar(f, dur):
    t, env = _shape(dur, 0.002, 0.15)
    return env * np.exp(-t * 2.0) * _harmonics(f, t, {h: 1 / h for h in range(1, 9)}, 1.2)


def _epiano(f, dur):
    t, env = _shape(dur, 0.004, 0.2)
    return env * np.exp(-t * 1.5) * np.sin(TAU * f * t + 1.2 * np.exp(-t * 4) * np.sin(TAU * f * t))


def _organ(f, dur):
    t, env = _shape(dur, 0.01, 0.05)
    return env * 0.5 * _harmonics(f, t, {1: 1.0, 2: 0.6, 3: 0.4, 4: 0.25, 6: 0.15})


def _strings(f, dur):
    t, env = _shape(dur, 0.18, 0.3)
    return env * 0.6 * _harmonics(f, t, {h: 1 / h for h in range(1, 8)}, detune=0.003)


def _pad(f, dur):
    t, env = _shape(dur, 0.4, 0.6)
    return env * _harmonics(f, t, {h: h ** -2.0 for h in range(1, 5)}, detune=0.004)


def _bass(f, dur):
    t, env = _shape(dur, 0.005, 0.08)
    return env * np.exp(-t * 2.2) * _harmonics(f, t, {1: 1.0, 2: 0.4, 3: 0.15})


def _flute(f, dur):
    t, env = _shape(dur, 0.05, 0.1)
    vibrato = (f * 0.004 / 5.0) * np.sin(TAU * 5.0 * t) * np.minimum(1.0, t / 0.3)
    phase = TAU * f * t + vibrato
    return env * (np.sin(phase) + 0.12 * np.sin(2 * phase))


TIMBRES = {"piano": _piano, "guitar": _guitar, "epiano": _epiano, "organ": _organ,
           "strings": _strings, "pad": _pad, "bass": _bass, "flute": _flute}


def _drum(pitch: int, rng: np.random.Generator) -> np.ndarray:
    if pitch == KICK:
        t = np.arange(int(0.3 * SR)) / SR
        return np.sin(TAU * (50 * t + 3 * (1 - np.exp(-30 * t)))) * np.exp(-t * 9)
    if pitch == SNARE:
        t = np.arange(int(0.2 * SR)) / SR
        return (0.7 * rng.uniform(-1, 1, t.size) * np.exp(-t * 22)
                + 0.4 * np.sin(TAU * 190 * t) * np.exp(-t * 18))
    t = np.arange(int(0.08 * SR)) / SR
    return 0.5 * np.diff(rng.uniform(-1, 1, t.size + 1)) * np.exp(-t * 60)


def render(tracks: list[Track], tempo: float, total_ticks: int) -> np.ndarray:
    """Mix all tracks to a mono float array, normalised to just under full scale."""
    sec_per_tick = 60.0 / (tempo * TICKS_PER_BEAT)
    out = np.zeros(int(total_ticks * sec_per_tick * SR) + SR)
    rng = np.random.default_rng(0)
    for track in tracks:
        for e in track.events:
            if track.instrument == "drums":
                sound = _drum(e.pitch, rng)
            else:
                freq = 440.0 * 2 ** ((e.pitch - 69) / 12)
                sound = TIMBRES[track.instrument](freq, e.length * sec_per_tick)
            at = int(e.start * sec_per_tick * SR)
            sound = sound[:out.size - at]
            out[at:at + sound.size] += sound * (e.velocity / 127) * track.gain
    peak = np.abs(out).max()
    return out * (0.89 / peak) if peak > 0 else out


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def find_soundfont(soundfont: str | None = None) -> str | None:
    """Explicit path, else $UTAU_LYRICS_SOUNDFONT. None if unset or missing."""
    path = soundfont or os.environ.get("UTAU_LYRICS_SOUNDFONT")
    return path if path and Path(path).is_file() else None


def render_with_fluidsynth(midi_path: Path, wav_path: Path, soundfont: str) -> bool:
    """Render the MIDI through a SoundFont. False if FluidSynth is unavailable or fails."""
    exe = shutil.which("fluidsynth")
    if not exe:
        return False
    result = subprocess.run([exe, "-ni", "-F", str(wav_path), "-r", str(SR), soundfont,
                             str(midi_path)], capture_output=True, timeout=300)
    return result.returncode == 0 and Path(wav_path).is_file()
