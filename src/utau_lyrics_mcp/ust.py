"""Read and write UTAU sequence text (.ust) files."""

from __future__ import annotations

from pathlib import Path

from .melody import Note

REST_LYRIC = "R"

# (section name without brackets, {key: value}); a line without '=' is stored
# with value None so files round-trip unchanged.
Section = tuple[str, dict[str, str | None]]


def build_ust(notes: list[Note], tempo: float, project_name: str = "",
              voice_dir: str = "", flags: str = "") -> str:
    lines = ["[#VERSION]", "UST Version1.2", "[#SETTING]", f"Tempo={tempo:.2f}",
             "Tracks=1", f"ProjectName={project_name}", f"VoiceDir={voice_dir}",
             "OutFile=", "CacheDir=", "Tool1=wavtool.exe", "Tool2=resampler.exe",
             f"Flags={flags}", "Mode2=True"]
    merged: list[Note] = []
    for note in notes:
        if note.pitch is None and merged and merged[-1].pitch is None:
            last = merged[-1]
            merged[-1] = Note(last.start, last.length + note.length, REST_LYRIC, None)
        else:
            merged.append(note)
    for i, note in enumerate(merged):
        rest = note.pitch is None
        lines += [f"[#{i:04d}]", f"Length={note.length}",
                  f"Lyric={REST_LYRIC if rest else note.lyric}",
                  f"NoteNum={60 if rest else note.pitch}", "PreUtterance=",
                  "Intensity=100", "Modulation=0"]
    lines.append("[#TRACKEND]")
    return "\r\n".join(lines) + "\r\n"


def write_text(path: Path, text: str, encoding: str = "shift_jis") -> str:
    """Write in the requested encoding, falling back to UTF-8. Returns the one used."""
    try:
        data = text.encode(encoding)
    except UnicodeEncodeError:
        encoding = "utf-8"
        data = text.encode(encoding)
    Path(path).write_bytes(data)
    return encoding


def read_text(path: Path) -> tuple[str, str]:
    """Returns (text, encoding). Classic UTAU writes Shift-JIS, OpenUtau UTF-8."""
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig"), "utf-8"  # OpenUtau writes a BOM
    except UnicodeDecodeError:
        return data.decode("cp932"), "cp932"


def parse_ust(text: str) -> list[Section]:
    sections: list[Section] = []
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            sections.append((line[1:-1], {}))
        elif sections and line:
            key, sep, value = line.partition("=")
            sections[-1][1][key if sep else line] = value if sep else None
    return sections


def dump_ust(sections: list[Section]) -> str:
    lines: list[str] = []
    for name, items in sections:
        lines.append(f"[{name}]")
        lines += [k if v is None else f"{k}={v}" for k, v in items.items()]
    return "\r\n".join(lines) + "\r\n"
