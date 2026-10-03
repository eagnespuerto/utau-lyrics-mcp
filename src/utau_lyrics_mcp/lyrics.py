"""Split lyrics into singable syllables (one UTAU note each)."""

from __future__ import annotations

import re
from dataclasses import dataclass

MODES = ("auto", "syllables", "romaji", "raw")
CONTINUE = "+"

_PUNCT = str.maketrans({**dict.fromkeys(".,!?;:\"()[]{}…、。！？「」『』・“”"), "’": "'", "‘": "'"})
_SMALL_KANA = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")
_HOLD = set("ー〜~っッ")
_DIGRAPH_STAY = ("ng", "ck")
_DIGRAPH_MOVE = ("th", "sh", "ch", "ph", "wh")


@dataclass
class Syllable:
    text: str
    weight: int = 1  # relative duration; '~' and 'ー' add to it


def _is_kana(ch: str) -> bool:
    return "぀" <= ch <= "ヿ"


def kana_morae(text: str) -> list[Syllable]:
    out: list[Syllable] = []
    for ch in text:
        if ch in _HOLD:
            if out:
                out[-1].weight += 1
        elif ch in _SMALL_KANA and out:
            out[-1].text += ch
        else:
            out.append(Syllable(ch))
    return out


def english_syllables(word: str) -> list[str]:
    """Rough vowel-group syllabifier. Use hyphens in the lyrics to override it."""
    w = word.lower()
    groups = [(m.start(), m.end()) for m in re.finditer(r"[aeiouy]+", w)]
    # silent final e ("love"), but not consonant + "le" ("little")
    if len(groups) > 1 and w.endswith("e") and groups[-1] == (len(w) - 1, len(w)):
        if not (w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy"):
            groups.pop()
    if len(groups) <= 1:
        return [word]
    cuts = []
    for (_, a_end), (b_start, _) in zip(groups, groups[1:]):
        cluster = w[a_end:b_start]
        if len(cluster) <= 1 or cluster in _DIGRAPH_MOVE:
            cuts.append(a_end)
        elif cluster[:2] in _DIGRAPH_STAY:
            cuts.append(a_end + 2)
        else:
            cuts.append(a_end + 1)
    bounds = [0, *cuts, len(word)]
    return [word[a:b] for a, b in zip(bounds, bounds[1:]) if word[a:b]]


def _build_romaji_table() -> dict[str, str]:
    rows = {"": "あいうえお", "k": "かきくけこ", "s": "さしすせそ", "t": "たちつてと",
            "n": "なにぬねの", "h": "はひふへほ", "m": "まみむめも", "r": "らりるれろ",
            "g": "がぎぐげご", "z": "ざじずぜぞ", "d": "だぢづでど", "b": "ばびぶべぼ",
            "p": "ぱぴぷぺぽ"}
    table = {c + v: k for c, kana in rows.items() for v, k in zip("aiueo", kana)}
    table.update(ya="や", yu="ゆ", yo="よ", wa="わ", wo="を",
                 shi="し", chi="ち", tsu="つ", fu="ふ", ji="じ")
    glides = {"k": "き", "s": "し", "t": "ち", "n": "に", "h": "ひ", "m": "み", "r": "り",
              "g": "ぎ", "z": "じ", "b": "び", "p": "ぴ", "sh": "し", "ch": "ち", "j": "じ"}
    for c, k in glides.items():
        for v, small in zip("auo", "ゃゅょ"):
            table[c + v if len(c) == 2 or c == "j" else c + "y" + v] = k + small
    return table


_ROMAJI = _build_romaji_table()


def romaji_to_kana(word: str) -> list[Syllable] | None:
    """'sakura' -> さ く ら. Returns None if the word is not valid romaji."""
    w = word.lower().replace("'", "")
    out: list[Syllable] = []
    i = 0
    while i < len(w):
        for size in (3, 2, 1):
            if w[i:i + size] in _ROMAJI:
                out.append(Syllable(_ROMAJI[w[i:i + size]]))
                i += size
                break
        else:
            if w[i] == "n":
                out.append(Syllable("ん"))
            elif i + 1 < len(w) and w[i] == w[i + 1] and out:
                out[-1].weight += 1  # doubled consonant = small tsu
            else:
                return None
            i += 1
    return out


def _split_token(token: str, mode: str) -> list[Syllable]:
    if any(_is_kana(ch) for ch in token):
        return kana_morae(token)
    parts = [p for p in token.split("-") if p.rstrip("~")]
    out: list[Syllable] = []
    for part in parts:
        holds = len(part) - len(part.rstrip("~"))
        part = part.rstrip("~")
        if mode == "romaji":
            pieces = romaji_to_kana(part) or [Syllable(part)]
        elif mode == "raw" or len(parts) > 1:
            pieces = [Syllable(part)]
        else:
            pieces = [Syllable(s) for s in english_syllables(part)]
        pieces[-1].weight += holds
        out.extend(pieces)
    if mode == "auto" and out:
        # OpenUtau's dictionary phonemizers need the whole word on the first
        # note and "+" on each note that continues it.
        out[0].text = "".join(p.rstrip("~") for p in parts)
        for syllable in out[1:]:
            syllable.text = CONTINUE
    return out


def syllabify_line(line: str, mode: str = "auto") -> list[Syllable]:
    if mode not in MODES:
        raise ValueError(f"lyric_mode must be one of {MODES}, got {mode!r}")
    out: list[Syllable] = []
    for token in line.translate(_PUNCT).split():
        out.extend(_split_token(token, mode))
    return out


def syllabify(lyrics: str, mode: str = "auto") -> list[list[Syllable] | None]:
    """One entry per lyric line; None marks a blank line (a bar of rest)."""
    lines: list[list[Syllable] | None] = []
    for raw in lyrics.strip().splitlines():
        syllables = syllabify_line(raw, mode)
        if syllables:
            lines.append(syllables)
        elif lines and lines[-1] is not None:
            lines.append(None)
    if not any(lines):
        raise ValueError("No singable syllables found in the lyrics")
    return lines
