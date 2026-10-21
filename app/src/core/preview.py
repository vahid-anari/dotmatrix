"""Render what an item looks like on the 64×8 matrix, as a small PNG of LEDs.

Uses the same font and layout rules as the firmware (DisplayText.cpp), so the
preview in the app matches the real display column for column.
"""
import random
import struct
import zlib
from functools import lru_cache

from .font import CUSTOM, FONT

WIDTH, HEIGHT = 64, 8

# LED look: cell = 6 px, dot = 5 px with clipped corners (reads as round).
CELL = 6
LIT = (255, 72, 48)
UNLIT = (48, 18, 14)
BG = (18, 10, 9)


def glyph(ch: str) -> list[int]:
    if ch in CUSTOM:
        return CUSTOM[ch]
    code = ord(ch)
    return FONT[code] if code < 256 else FONT[ord("?")]


def text_width(text: str) -> int:
    return len(text_columns(text))


def text_columns(text: str) -> list[int]:
    """All the text's columns, as the firmware draws it: byte by byte of the
    UTF-8 text, 1 empty column after each glyph that has width (Parola's rule)."""
    data = text.encode("utf-8")
    cols: list[int] = []
    for i, b in enumerate(data):
        g = glyph(chr(b))
        cols += g
        if g and i + 1 < len(data):
            cols.append(0)
    return cols


def layout(text: str, align: str = "center") -> tuple[list[int], int]:
    """The text's columns and where the first one goes: the same position
    Parola uses (MD_PZone::calcTextLimits) and DisplayText.cpp copies."""
    cols = text_columns(text)
    w = len(cols)
    if w > WIDTH:
        return cols, 0
    if align == "left":
        return cols, 0
    if align == "right":
        return cols, WIDTH - w
    return cols, WIDTH - w - (WIDTH - w) // 2


def draw_text(cols: list[int], text: str, align: str = "center") -> None:
    glyphs, x = layout(text, align)
    for i, c in enumerate(glyphs):
        if 0 <= x + i < WIDTH:
            cols[x + i] = c


def frame_for(item: dict) -> list[int]:
    """64 column bytes (bit 0 = top) showing the item at rest."""
    cols = [0] * WIDTH
    text = item.get("text", "")
    if item.get("type") == "animation":
        # Stable seed (str hash changes per run) so the picture doesn't jump around.
        rng = random.Random(zlib.crc32((item.get("animation", "") + text).encode()))
        if item.get("animation") == "matrix_reveal" and text:
            draw_text(cols, text, item.get("align", "center"))
            # a few drops still falling over the text
            for _ in range(10):
                x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
                for t in range(rng.randrange(1, 3)):
                    if 0 <= y - t < HEIGHT:
                        cols[x] |= 1 << (y - t)
        elif item.get("animation") != "matrix_rain":
            from .player import Player  # (player uses this module)
            cols = Player({**item, "invert": False}).frame(2000)[0]  # inverted below
        else:
            for _ in range(22):
                x, y, n = rng.randrange(WIDTH), rng.randrange(HEIGHT + 3), rng.randrange(2, 5)
                for t in range(n):
                    if 0 <= y - t < HEIGHT and (t == 0 or rng.random() < 0.8 - t * 0.15):
                        cols[x] |= 1 << (y - t)
    else:
        draw_text(cols, text, item.get("align", "center"))
    if item.get("invert"):
        cols = [~c & 0xFF for c in cols]
    return cols


def _png(width: int, height: int, rows: list[bytes], level: int = 6) -> bytes:
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level)) + chunk(b"IEND", b""))


@lru_cache(maxsize=64)
def _cells(lit: tuple[int, int, int]) -> list[tuple[bytes, bytes]]:
    """For each pixel row inside an LED cell: (unlit, lit) cell bytes."""
    bg, off, on = bytes(BG), bytes(UNLIT), bytes(lit)
    rows = []
    for dy in range(CELL):
        pair = []
        for led in (off, on):
            row = bytearray()
            for dx in range(CELL):
                inside = dx < CELL - 1 and dy < CELL - 1
                corner = (dx in (0, CELL - 2)) and (dy in (0, CELL - 2))
                row += led if inside and not corner else bg
            pair.append(bytes(row))
        rows.append(tuple(pair))
    return rows


def _render_uncached(cols: tuple[int, ...], lit: tuple[int, int, int], level: int = 6) -> bytes:
    cells = _cells(lit)
    rows = []
    for y in range(HEIGHT):
        bits = [c >> y & 1 for c in cols]
        for dy in range(CELL):
            pair = cells[dy]
            rows.append(b"".join(pair[b] for b in bits))
    return _png(WIDTH * CELL, HEIGHT * CELL, rows, level)


@lru_cache(maxsize=512)
def _render(cols: tuple[int, ...], lit: tuple[int, int, int]) -> bytes:
    return _render_uncached(cols, lit)


def dimmed(level: float) -> tuple[int, int, int]:
    """The lit colour at a brightness from 0 (dimmest) to 1."""
    level = max(0.0, min(1.0, level))
    return tuple(int(u + (l - u) * (0.25 + 0.75 * level)) for u, l in zip(UNLIT, LIT))


def render_cols(cols: list[int], lit: tuple[int, int, int] = LIT) -> bytes:
    return _render(tuple(cols), lit)


def render_frame(cols: list[int], level: float = 1.0) -> bytes:
    """For animation: not cached (frames rarely repeat), fast compression."""
    return _render_uncached(tuple(cols), dimmed(round(level * 16) / 16), 1)


def render_item(item: dict) -> bytes:
    return render_cols(frame_for(item))


def render_text(text: str, align: str = "center") -> bytes:
    cols = [0] * WIDTH
    draw_text(cols, text, align)
    return render_cols(cols)
