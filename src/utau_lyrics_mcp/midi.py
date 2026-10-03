"""Minimal Standard MIDI File (format 1) writer."""

from __future__ import annotations

import struct
from pathlib import Path

from .backing import DRUM_CHANNEL, INSTRUMENTS, Track
from .theory import TICKS_PER_BEAT


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def _chunk(body: bytes) -> bytes:
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _meta(kind: int, data: bytes) -> bytes:
    return b"\x00\xff" + bytes([kind]) + _vlq(len(data)) + data


_END = b"\x00\xff\x2f\x00"


def write_midi(path: Path, tracks: list[Track], tempo: float, beats_per_bar: int = 4) -> None:
    micros = round(60_000_000 / tempo)
    conductor = (_meta(0x51, micros.to_bytes(3, "big"))
                 + _meta(0x58, bytes([beats_per_bar, 2, 24, 8])) + _END)
    chunks = [_chunk(conductor)]
    for track in tracks:
        body = _meta(0x03, track.name.encode("ascii", "replace"))
        if track.channel != DRUM_CHANNEL:
            body += bytes([0x00, 0xC0 | track.channel, INSTRUMENTS[track.instrument]])
        messages = []
        for e in track.events:
            messages.append((e.start, 1, bytes([0x90 | track.channel, e.pitch, e.velocity])))
            messages.append((e.start + e.length, 0, bytes([0x80 | track.channel, e.pitch, 0])))
        messages.sort(key=lambda m: (m[0], m[1]))  # note-offs before note-ons
        now = 0
        for tick, _, data in messages:
            body += _vlq(tick - now) + data
            now = tick
        chunks.append(_chunk(body + _END))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), TICKS_PER_BEAT)
    Path(path).write_bytes(header + b"".join(chunks))
