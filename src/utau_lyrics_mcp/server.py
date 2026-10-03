"""MCP server: lyrics + chords -> UTAU project and backing track."""

from __future__ import annotations

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from . import song
from .backing import INSTRUMENTS, STYLES
from .lyrics import MODES, syllabify
from .theory import QUALITIES

mcp = MCPServer("utau-lyrics")


@mcp.tool()
def create_song(lyrics: str, chords: str, key: str = "C", tempo: float = 100.0,
                name: str = "song", output_dir: str | None = None, lyric_mode: str = "auto",
                voice_range: str = "A3-C5", bars_per_line: int = 2, beats_per_bar: int = 4,
                intro_bars: int = 1, instrument: str = "piano", style: str = "arpeggio",
                bass: bool = True, drums: bool = False, guide_volume: float = 0.35,
                seed: int = 0, soundfont: str | None = None, voice_dir: str = "") -> dict:
    """Turn lyrics and a chord progression into a song: a UTAU .ust file plus a
    backing track (.mid and .wav) of the same length, so both line up at 0:00.

    The vocal itself is not rendered here: open the .ust in UTAU or OpenUtau
    with a voicebank, and import the backing .wav alongside it.

    lyrics: one sung line per text line; a blank line is a bar of rest. Write
        'syl-la-ble' to force syllable breaks and 'la~' to hold a syllable.
    chords: bars separated by '|', e.g. 'C | Am | F G | C'. Chords in one bar
        share it equally, '%' repeats the previous bar. The progression loops.
    key: e.g. 'C', 'Bb', 'F#m'. Off-beat notes use this scale.
    lyric_mode: 'auto' (kana by mora; other words keep the whole word on
        their first note and '+' on the rest, which is what OpenUtau's English
        phonemizers expect), 'syllables' (word fragments like 'win' 'dow'),
        'romaji' (convert romaji to hiragana for Japanese voicebanks), 'raw'.
    voice_range: lowest-highest note for the melody, e.g. 'A3-C5'.
    guide_volume: 0-1 level of a flute doubling the melody in the backing,
        as a pitch reference for the voice; 0 leaves it out.
    seed: change it to get a different melody over the same chords.
    soundfont: path to an .sf2 file; used if FluidSynth is installed,
        otherwise the built-in synth renders the backing.
    """
    return song.create_song(lyrics, chords, key, tempo, name, output_dir, lyric_mode,
                            voice_range, bars_per_line, beats_per_bar, intro_bars,
                            instrument, style, bass, drums, guide_volume, seed,
                            soundfont, voice_dir)


@mcp.tool()
def lyrics_to_ust(lyrics: str, chords: str, key: str = "C", tempo: float = 100.0,
                  name: str = "song", output_dir: str | None = None, lyric_mode: str = "auto",
                  voice_range: str = "A3-C5", bars_per_line: int = 2, beats_per_bar: int = 4,
                  intro_bars: int = 1, seed: int = 0, voice_dir: str = "") -> dict:
    """Write only the UTAU .ust file (melody fitted to the chords), no backing.
    Arguments are the same as create_song."""
    return song.create_song(lyrics, chords, key, tempo, name, output_dir, lyric_mode,
                            voice_range, bars_per_line, beats_per_bar, intro_bars,
                            seed=seed, voice_dir=voice_dir, ust_only=True)


@mcp.tool()
def render_backing(chords: str, bars: int | None = None, tempo: float = 100.0,
                   name: str = "backing", output_dir: str | None = None,
                   beats_per_bar: int = 4, instrument: str = "piano", style: str = "arpeggio",
                   bass: bool = True, drums: bool = False, soundfont: str | None = None) -> dict:
    """Render only a backing track (.mid and .wav) from a chord progression.
    bars defaults to one pass through the progression."""
    return song.render_backing(chords, bars, tempo, name, output_dir, beats_per_bar,
                               instrument, style, bass, drums, soundfont)


@mcp.tool()
def preview_syllables(lyrics: str, lyric_mode: str = "auto") -> list[str]:
    """Show how each lyric line will be split into notes, before making a song.
    Notes are separated by spaces; '+' continues the word before it and
    '(xN)' marks a held note."""
    return [" ".join(s.text + (f"(x{s.weight})" if s.weight > 1 else "") for s in line)
            if line else "(rest)" for line in syllabify(lyrics, lyric_mode)]


@mcp.tool()
def list_options() -> dict:
    """Instruments, accompaniment styles, lyric modes and chord qualities accepted."""
    return {"instruments": [i for i in INSTRUMENTS if i not in ("bass", "flute")],
            "styles": list(STYLES), "lyric_modes": list(MODES),
            "chord_qualities": [q or "(major)" for q in QUALITIES],
            "default_output_dir": str(song.default_output_dir())}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
