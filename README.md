# utau-lyrics-mcp

Test version. Give it lyrics and a chord progression, and it writes:

- a `.ust` file for UTAU or OpenUtau, one note per syllable, with pitches chosen to fit the chords
- a backing track of the same length as `.mid` and `.wav`, so the two line up at 0:00

It runs as an MCP server (for Claude or any other MCP client), as a UTAU plugin, or from the command line.

It does not render the voice. You still open the `.ust` in UTAU or OpenUtau with a voicebank and import the backing `.wav` next to it.

## Install

Python 3.10 or newer.

```bash
pip install -e .
```

## Try it without an MCP client

```bash
python -m utau_lyrics_mcp song examples/lyrics_en.txt --chords "C | Am | F G | C" --output-dir output
```

That writes `output/lyrics_en.ust`, `output/lyrics_en_backing.mid` and `output/lyrics_en_backing.wav`, and prints the melody it picked.

A Japanese voicebank needs kana lyrics. Write romaji and pass `--lyric-mode romaji`:

```bash
python -m utau_lyrics_mcp song examples/lyrics_romaji.txt --chords "Am | F | C | G" --key Am --lyric-mode romaji --instrument guitar --style strum --drums --output-dir output
```

## Use it as an MCP server

Claude Code:

```bash
claude mcp add utau-lyrics -- python -m utau_lyrics_mcp
```

Claude Desktop, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "utau-lyrics": { "command": "python", "args": ["-m", "utau_lyrics_mcp"] }
  }
}
```

Files go to `utau-lyrics-mcp-output` in your user folder unless you pass `output_dir` or set `UTAU_LYRICS_OUTPUT_DIR`.

| Tool | What it does |
| --- | --- |
| `create_song` | Lyrics and chords in, `.ust` plus backing `.mid` and `.wav` out |
| `lyrics_to_ust` | The `.ust` only |
| `render_backing` | A backing track from chords alone |
| `preview_syllables` | Shows how each line will be split into notes |
| `list_options` | Instruments, styles, lyric modes, chord qualities |

## Writing lyrics and chords

Each line of text is one sung line and gets two bars by default. A line with too many syllables takes more bars. A blank line is one bar of rest. The song starts with a one-bar intro and ends with one bar on the first chord of the progression.

The English syllable splitter is a rough guess based on vowel groups. It gets "window" and "little" right and treats "quiet" as one syllable. Fix a word by hyphenating it yourself: `qui-et`, `beau-ti-ful`. Add `~` to hold a syllable longer: `slow~`. Run `preview_syllables` first to see the split.

Kana is split by mora. `ー` and `っ` lengthen the note before them.

Chords are bars separated by `|`. Chords inside one bar share it equally, and `%` repeats the previous bar:

```
C | Am | F G | %
```

The progression loops until the lyrics run out. Supported qualities: major, `m`, `5`, `dim`, `aug`, `sus2`, `sus4`, `6`, `m6`, `7`, `maj7`, `m7`, `m7b5`, `dim7`, `9`, `add9`, plus slash bass like `D/F#`.

## How the melody is chosen

Notes that start on a beat, and the last note of every line, use a tone from the chord playing at that moment. Notes between beats can use any note of the key. The picker prefers small steps from the previous note and stays inside `voice_range` (default `A3-C5`). The last note of the song lands on the tonic when the final chord contains it.

The same input always gives the same melody. Change `seed` for a different one.

## The backing track and the voice

The backing has a chord part (`block`, `strum` or `arpeggio`), a bass, optional drums, and a flute that doubles the vocal melody quietly. The flute is there as a pitch reference while you tune the voice. Set `guide_volume` to `0` for a backing without it.

Instruments: `piano`, `epiano`, `organ`, `guitar`, `strings`, `pad`.

There are two renderers.

**Built-in synth.** Used by default. It builds each instrument from sine partials in numpy, so it needs no downloads and sounds like a synth.

**FluidSynth with a SoundFont.** For sampled instruments, install [FluidSynth](https://www.fluidsynth.org/) and get a free SoundFont such as FluidR3_GM (MIT), MuseScore_General (MIT) or GeneralUser GS (its own permissive licence). Then pass `soundfont` or set `UTAU_LYRICS_SOUNDFONT` to the `.sf2` path. The instrument names map to General MIDI programs. If FluidSynth or the file is missing, the built-in synth takes over.

The `.mid` is always written, so you can also load it into any DAW and pick your own instruments.

## UTAU plugin

Copy the `utau_plugin` folder into UTAU's `plugins` folder. `run.bat` calls `python`, so the package must be installed for the Python on your PATH.

Select notes in UTAU and run "Fit notes to chords + backing track". The plugin keeps your lyrics and note lengths, changes the pitches to fit the chords in `settings.ini`, and writes `plugin_backing.wav` and `.mid` for the selection. Chords start at the first selected note.

## Not tested yet

- The plugin has only been run against UST files written by the tests, not inside UTAU itself.
- The FluidSynth path has not been run on a real install.
- Rhythm is an even eighth-note grid. There is no syncopation and no melisma.
- 4/4 is the only time signature that has been tried, though `beats_per_bar` exists.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Licence

MIT
