// Text rendering into frames. Shared by the firmware and the host tests;
// only Display::glyph() differs between the two.
#include "Display.h"

uint16_t Display::textWidth(const char* text) const {
  uint8_t buf[16];
  uint16_t w = 0;
  for (const char* p = text; *p; p++) {
    w += glyph(*p, buf, sizeof(buf));
    if (p[1]) w += 1;  // 1 column between characters, like Parola
  }
  return w;
}

uint16_t Display::drawText(Frame& f, const char* text, Align align, int xOffset) const {
  uint16_t w = textWidth(text);
  int x;
  switch (align) {
    case Align::Left: x = 0; break;
    case Align::Right: x = DISPLAY_WIDTH - (int)w; break;
    default: x = ((int)DISPLAY_WIDTH - (int)w) / 2; break;
  }
  x += xOffset;
  uint8_t buf[16];
  for (const char* p = text; *p; p++) {
    uint8_t gw = glyph(*p, buf, sizeof(buf));
    for (uint8_t i = 0; i < gw; i++, x++)
      if (x >= 0 && x < DISPLAY_WIDTH) f.col[x] = buf[i];
    x += 1;
  }
  return w;
}
