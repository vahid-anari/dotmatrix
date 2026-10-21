"""Copy the sprite data from the firmware into the app, for its previews.

    python tools/gen_sprites.py      (from the repository root)

Run it after changing firmware/src/display/Sprites.cpp.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "firmware/src/display/Sprites.cpp").read_text()

arrays = {m[1]: [int(v, 16) for v in re.findall(r"0x[0-9a-fA-F]+", m[2])]
          for m in re.finditer(r"PROGMEM (\w+)\[[^]]*\]\s*=[^{]*\{(.*?)\};", src, re.S)}
consts = {m[1]: int(m[2]) for m in re.finditer(r"static const uint8_t (\w+) = (\d+);", src)}
table = re.findall(r'\{"(\w+)", (\w+), (\w+), (\w+)\}', src)

out = ['"""Sprite data, generated from firmware/src/display/Sprites.cpp by tools/gen_sprites.py.',
       "", "Data from the MD_Parola examples (LGPL-2.1, MajicDesigns). Each sprite is",
       "(width, frames, columns): frames × width column bytes, bit 0 = top row,",
       'column 0 = the front edge."""', "", "SPRITES = {"]
for name, data, w, f in table:
    width, frames, cols = consts[w], consts[f], arrays[data]
    assert len(cols) == width * frames, name
    out.append(f'    "{name}": ({width}, {frames}, bytes.fromhex("{bytes(cols).hex()}")),')
out.append("}")
dest = ROOT / "app/src/core/sprites.py"
dest.write_text("\n".join(out) + "\n")
print(f"{len(table)} sprites → {dest.relative_to(ROOT)}")
