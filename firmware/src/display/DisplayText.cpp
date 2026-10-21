// Text rendering into frames. Shared by the firmware and the host tests;
// only Display::glyph() differs between the two.
#include "Display.h"

uint16_t Display::textWidth(const char* text) const {
  uint8_t buf[16];
  uint16_t w = 0;
  for (const char* p = text; *p; p++) {
    uint8_t gw = glyph(*p, buf, sizeof(buf));
    w += gw;
    // 1 column between characters, like Parola: only after one with width
    // (the second byte of some UTF-8 letters is an empty glyph).
    if (gw && p[1]) w += 1;
  }
  return w;
}

uint16_t Display::drawText(Frame& f, const char* text, Align align, int xOffset) const {
  uint16_t w = textWidth(text);
  // Same positions as Parola (MD_PZone::calcTextLimits), so a text drawn here
  // lines up exactly with one Parola drew: centred text leans right by half a
  // column when it can't sit exactly in the middle, and text wider than the
  // display starts at the left edge whatever the alignment.
  int x;
  if (w > DISPLAY_WIDTH) {
    x = 0;
  } else {
    switch (align) {
      case Align::Left: x = 0; break;
      case Align::Right: x = DISPLAY_WIDTH - (int)w; break;
      default: x = (int)DISPLAY_WIDTH - (int)w - ((int)DISPLAY_WIDTH - (int)w) / 2; break;
    }
  }
  x += xOffset;
  uint8_t buf[16];
  for (const char* p = text; *p; p++) {
    uint8_t gw = glyph(*p, buf, sizeof(buf));
    for (uint8_t i = 0; i < gw; i++, x++)
      if (x >= 0 && x < DISPLAY_WIDTH) f.col[x] = buf[i];
    if (gw) x += 1;
  }
  return w;
}
