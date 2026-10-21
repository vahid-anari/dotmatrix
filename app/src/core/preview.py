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
    if not text:
        return 0
    return sum(len(glyph(c)) for c in text) + len(text) - 1


def draw_text(cols: list[int], text: str, align: str = "center") -> None:
    w = text_width(text)
    if align == "left":
        x = 0
    elif align == "right":
        x = WIDTH - w
    else:
        x = (WIDTH - w) // 2  # C++ integer division of a possibly negative number
        if WIDTH - w < 0 and (WIDTH - w) % 2:
            x += 1  # truncate toward zero like C++
    for ch in text:
        for b in glyph(ch):
            if 0 <= x < WIDTH:
                cols[x] = b
            x += 1
        x += 1


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


def _png(width: int, height: int, rows: list[bytes]) -> bytes:
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


@lru_cache(maxsize=512)
def _render(cols: tuple[int, ...], lit: tuple[int, int, int]) -> bytes:
    w, h = WIDTH * CELL, HEIGHT * CELL
    bg, off, on = bytes(BG), bytes(UNLIT), bytes(lit)
    rows = []
    for py in range(h):
        y, dy = divmod(py, CELL)
        row = bytearray()
        for x in range(WIDTH):
            led = on if cols[x] >> y & 1 else off
            for dx in range(CELL):
                inside = dx < CELL - 1 and dy < CELL - 1
                corner = (dx in (0, CELL - 2)) and (dy in (0, CELL - 2))
                row += led if inside and not corner else bg
        rows.append(bytes(row))
    return _png(w, h, rows)


def render_cols(cols: list[int], lit: tuple[int, int, int] = LIT) -> bytes:
    return _render(tuple(cols), lit)


def render_item(item: dict) -> bytes:
    return render_cols(frame_for(item))


def render_text(text: str, align: str = "center") -> bytes:
    cols = [0] * WIDTH
    draw_text(cols, text, align)
    return render_cols(cols)
