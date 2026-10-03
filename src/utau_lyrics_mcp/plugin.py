"""UTAU plugin entry point.

UTAU calls a plugin with the path of a temporary .ust holding the selected
notes. This re-pitches those notes to fit the chord progression in
settings.ini (lengths and lyrics are kept) and renders a matching backing
track. Chords start at the first selected note.
"""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

from . import song, ust
from .melody import Note, assign_pitches
from .theory import TICKS_PER_BEAT, parse_range

DEFAULTS = {"chords": "C | Am | F | G", "key": "C", "voice_range": "A3-C5", "seed": "0",
            "beats_per_bar": "4", "tempo": "120", "backing": "yes", "instrument": "piano",
            "style": "arpeggio", "bass": "yes", "drums": "no", "guide_volume": "0.35",
            "output_dir": "", "soundfont": ""}


def load_settings(path: Path | None) -> configparser.SectionProxy:
    config = configparser.ConfigParser(defaults=DEFAULTS)
    if path and Path(path).is_file():
        config.read(path, encoding="utf-8")
    if not config.has_section("song"):
        config.add_section("song")
    return config["song"]


def run(ust_path: Path, settings_path: Path | None = None) -> dict:
    cfg = load_settings(settings_path)
    text, encoding = ust.read_text(ust_path)
    sections = ust.parse_ust(text)

    tempo = cfg.getfloat("tempo")
    notes: list[Note] = []
    targets: list[dict] = []
    tick = 0
    for name, items in sections:
        if name == "#SETTING" and items.get("Tempo"):
            tempo = float(items["Tempo"].replace(",", "."))
        if not re.fullmatch(r"#\d+", name):
            continue
        length = int(items.get("Length") or TICKS_PER_BEAT)
        lyric = items.get("Lyric") or ust.REST_LYRIC
        rest = lyric.strip() in ("", "R", "r")
        notes.append(Note(tick, length, lyric, None if rest else 0))
        targets.append(items)
        tick += length
    if not notes:
        return {"notes": 0}

    beats_per_bar = cfg.getint("beats_per_bar")
    total_bars = -(-tick // (beats_per_bar * TICKS_PER_BEAT))
    timeline = song.song_timeline(cfg["chords"], total_bars, beats_per_bar)
    low, high = parse_range(cfg["voice_range"])
    assign_pitches(notes, timeline, cfg["key"], low, high, cfg.getint("seed"))
    for note, items in zip(notes, targets):
        if note.pitch is not None:
            items["NoteNum"] = str(note.pitch)
    Path(ust_path).write_bytes(ust.dump_ust(sections).encode(encoding))

    result: dict = {"notes": len(notes), "bars": total_bars}
    if cfg.getboolean("backing"):
        out = Path(cfg["output_dir"]) if cfg["output_dir"] else song.default_output_dir()
        out.mkdir(parents=True, exist_ok=True)
        result["backing"] = song.write_backing(
            out / "plugin_backing", timeline, total_bars, tempo, beats_per_bar,
            cfg["instrument"], cfg["style"], cfg.getboolean("bass"), cfg.getboolean("drums"),
            notes, cfg.getfloat("guide_volume"), cfg["soundfont"] or None)
    return result


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python -m utau_lyrics_mcp.plugin <temp.ust> [settings.ini]")
    settings = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    print(run(Path(sys.argv[1]), settings))


if __name__ == "__main__":
    main()
