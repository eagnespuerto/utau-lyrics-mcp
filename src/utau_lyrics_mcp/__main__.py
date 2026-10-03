"""`python -m utau_lyrics_mcp` runs the MCP server; `... song` makes a song from the shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import song


def main() -> None:
    parser = argparse.ArgumentParser(prog="utau_lyrics_mcp")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    p = sub.add_parser("song", help="make a .ust and backing track without an MCP client")
    p.add_argument("lyrics_file", type=Path)
    p.add_argument("--chords", required=True, help="e.g. 'C | Am | F G | C'")
    p.add_argument("--key", default="C")
    p.add_argument("--tempo", type=float, default=100.0)
    p.add_argument("--name")
    p.add_argument("--output-dir")
    p.add_argument("--lyric-mode", default="auto")
    p.add_argument("--voice-range", default="A3-C5")
    p.add_argument("--instrument", default="piano")
    p.add_argument("--style", default="arpeggio")
    p.add_argument("--drums", action="store_true")
    p.add_argument("--guide-volume", type=float, default=0.35)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--soundfont")
    args = parser.parse_args()

    if args.command == "song":
        result = song.create_song(
            args.lyrics_file.read_text(encoding="utf-8"), args.chords, args.key, args.tempo,
            args.name or args.lyrics_file.stem, args.output_dir, args.lyric_mode,
            args.voice_range, instrument=args.instrument, style=args.style, drums=args.drums,
            guide_volume=args.guide_volume, seed=args.seed, soundfont=args.soundfont)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        from .server import main as serve
        serve()


if __name__ == "__main__":
    main()
