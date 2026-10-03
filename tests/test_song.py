import struct
import wave

import pytest

from utau_lyrics_mcp import plugin, song, ust
from utau_lyrics_mcp.lyrics import english_syllables, romaji_to_kana, syllabify, syllabify_line
from utau_lyrics_mcp.melody import Note
from utau_lyrics_mcp.theory import (TICKS_PER_BEAT, build_timeline, chord_at, note_to_midi,
                                    parse_chord, parse_key, parse_progression, parse_range)

LYRICS = "Morning light on the window pane\nQuiet streets and a little rain\n\nSing it low~"
CHORDS = "C | Am | F G | C"


def test_notes_and_chords():
    assert note_to_midi("C4") == 60
    assert parse_range("A3-C5") == (57, 72)
    assert parse_chord("Am7").pitch_classes == {9, 0, 4, 7}
    assert parse_chord("D/F#").bass == 6
    assert parse_chord("Bbmaj7").root == 10
    with pytest.raises(ValueError):
        parse_chord("Cxyz")
    assert parse_key("Am")[1] == parse_key("C")[1]


def test_progression_timeline():
    bars = parse_progression("C | F G | %")
    assert [len(b) for b in bars] == [1, 2, 2]
    timeline = build_timeline(bars, 4)
    assert sum(s.length for s in timeline) == 4 * 4 * TICKS_PER_BEAT
    assert chord_at(timeline, 4 * TICKS_PER_BEAT + 2 * TICKS_PER_BEAT).symbol == "G"
    assert chord_at(timeline, 3 * 4 * TICKS_PER_BEAT).symbol == "C"  # looped


@pytest.mark.parametrize("word,expected", [
    ("love", ["love"]), ("window", ["win", "dow"]), ("little", ["lit", "tle"]),
    ("melody", ["me", "lo", "dy"]), ("mother", ["mo", "ther"]), ("singing", ["sing", "ing"]),
])
def test_english_syllables(word, expected):
    assert english_syllables(word) == expected


def test_lyric_modes():
    assert [s.text for s in syllabify_line("beau-ti-ful day")] == ["beau", "ti", "ful", "day"]
    held = syllabify_line("low~~")
    assert (held[0].text, held[0].weight) == ("low", 3)
    assert [s.text for s in syllabify_line("きょうは ラーメン")] == ["きょ", "う", "は", "ラ", "メ", "ン"]
    assert [s.text for s in romaji_to_kana("shizuka")] == ["し", "ず", "か"]
    assert [s.text for s in syllabify_line("konnichiwa", "romaji")] == ["こ", "ん", "に", "ち", "わ"]
    assert romaji_to_kana("xyz") is None
    assert syllabify("a\n\n\nb")[1] is None and len(syllabify("a\n\n\nb")) == 3


def test_compose_fits_chords_and_range():
    notes, timeline, total_bars = song.compose(LYRICS, CHORDS, "C")
    bar = 4 * TICKS_PER_BEAT
    assert notes[0].pitch is None and notes[0].length == bar  # intro
    tick = 0
    for n in notes:  # contiguous, as a UST requires
        assert n.start == tick and n.length > 0
        tick += n.length
    assert tick == total_bars * bar
    sung = [n for n in notes if n.pitch is not None]
    assert all(57 <= n.pitch <= 72 for n in sung)
    for n in sung:
        if n.start % TICKS_PER_BEAT == 0:
            assert n.pitch % 12 in chord_at(timeline, n.start).pitch_classes
    ending, _, _ = song.compose("la la la la", "C", "C")
    assert [n.pitch for n in ending if n.pitch is not None][-1] % 12 == 0  # resolves to the tonic
    again, _, _ = song.compose(LYRICS, CHORDS, "C")
    assert [n.pitch for n in again] == [n.pitch for n in notes]
    other, _, _ = song.compose(LYRICS, CHORDS, "C", seed=5)
    assert [n.pitch for n in other] != [n.pitch for n in notes]


def test_create_song_files(tmp_path):
    result = song.create_song(LYRICS, CHORDS, tempo=120, name="my song!", output_dir=str(tmp_path),
                              drums=True)
    text, _ = ust.read_text(result["ust"])
    sections = ust.parse_ust(text)
    assert sections[0][0] == "#VERSION" and sections[-1][0] == "#TRACKEND"
    assert sections[1][1]["Tempo"] == "120.00"
    total = sum(int(s["Length"]) for name, s in sections if name[1:].isdigit())
    assert total == result["bars"] * 4 * TICKS_PER_BEAT
    assert ust.dump_ust(sections) == text

    midi_bytes = open(result["backing"]["midi"], "rb").read()
    assert midi_bytes[:4] == b"MThd"
    fmt, ntracks, division = struct.unpack(">HHH", midi_bytes[8:14])
    assert (fmt, ntracks, division) == (1, 5, TICKS_PER_BEAT)
    assert midi_bytes.count(b"MTrk") == 5

    with wave.open(result["backing"]["wav"]) as w:
        seconds = w.getnframes() / w.getframerate()
        assert max(abs(x) for x in struct.unpack(f"<{w.getnframes()}h", w.readframes(w.getnframes()))) > 10000
    assert seconds == pytest.approx(result["seconds"] + 1, abs=0.1)  # 1 s tail
    assert result["backing"]["renderer"] == "built-in synth"


def test_kana_ust_is_shift_jis(tmp_path):
    result = song.create_song("さくら さくら", "Am | Dm", key="Am", output_dir=str(tmp_path), ust_only=True)
    assert result["ust_encoding"] == "shift_jis"
    assert "Lyric=さ" in open(result["ust"], encoding="shift_jis").read()
    assert "backing" not in result


def test_install_and_openutau_temp_file(tmp_path):
    dest = plugin.install(tmp_path)
    assert {p.name for p in dest.iterdir()} == {"plugin.txt", "run.bat", "settings.ini"}
    (dest / "settings.ini").write_text("[song]\nchords = G\nbacking = no\n", encoding="utf-8")
    assert plugin.install(tmp_path) == dest
    assert "chords = G" in (dest / "settings.ini").read_text(encoding="utf-8")  # kept

    # What OpenUtau writes: UTF-8 with BOM, no [#VERSION], plain Tempo.
    body = ("[#SETTING]\r\nTempo=120\r\nTracks=1\r\nMode2=True\r\n"
            "[#0000]\r\nLength=480\r\nLyric=라\r\nNoteNum=60\r\n"
            "[#NEXT]\r\nLength=480\r\nLyric=R\r\nNoteNum=60\r\n")
    path = tmp_path / "temp.ust"
    path.write_bytes(body.encode("utf-8-sig"))
    plugin.run(path, dest / "settings.ini")
    sections = dict(ust.parse_ust(path.read_text(encoding="utf-8")))
    assert sections["#0000"]["Lyric"] == "라"
    assert int(sections["#0000"]["NoteNum"]) % 12 in parse_chord("G").pitch_classes
    assert sections["#NEXT"]["NoteNum"] == "60"


def test_plugin_repitches_selection(tmp_path):
    notes = [Note(0, 480, "ら", 60), Note(480, 480, "R", None), Note(960, 960, "ら", 60)]
    text = ust.build_ust(notes, 90).replace("[#0000]", "[#PREV]\r\nLength=480\r\nLyric=R\r\n[#0000]")
    path = tmp_path / "tmp.ust"
    path.write_bytes(text.encode("cp932"))
    ini = tmp_path / "settings.ini"
    ini.write_text(f"[song]\nchords = F | G\nkey = C\noutput_dir = {tmp_path / 'out'}\n", encoding="utf-8")

    result = plugin.run(path, ini)
    sections = dict(ust.parse_ust(path.read_bytes().decode("cp932")))
    assert sections["#0000"]["NoteNum"] != "60" or sections["#0002"]["NoteNum"] != "60"
    assert int(sections["#0000"]["NoteNum"]) % 12 in parse_chord("F").pitch_classes
    assert sections["#0001"]["Lyric"] == "R" and sections["#0002"]["Length"] == "960"
    assert "NoteNum" not in sections["#PREV"]
    assert (tmp_path / "out" / "plugin_backing.wav").is_file()
    assert result["bars"] == 1
