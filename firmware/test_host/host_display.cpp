// Host version of Display: only the text-rendering half (Parola parts are no-ops).
#include "../src/display/Display.h"

#include "stubs/host_font.h"

uint32_t g_fakeMillis = 0;
FakeSerial Serial;

static const uint8_t GLYPH_ONE[] = {5, 0x00, 0x04, 0x02, 0x7F, 0x00};
static const uint8_t GLYPH_SEVEN[] = {5, 0x01, 0x01, 0x71, 0x09, 0x07};

Display::Display() : _parola(MD_MAX72XX::FC16_HW, 0, 8) {}
void Display::begin() {}
void Display::playText(const Item&) {}
void Display::setText(const char*) {}
bool Display::animate() { return true; }
void Display::push(const Frame&) {}
void Display::clear() {}
void Display::setBrightness(uint8_t b) { _brightness = b; }
void Display::setPower(bool on) { _power = on; }

uint8_t Display::glyph(char c, uint8_t* buf, uint8_t size) const {
  const uint8_t* g = c == '1' ? GLYPH_ONE : (c == '7' ? GLYPH_SEVEN : HOST_FONT[(uint8_t)c]);
  uint8_t w = std::min<uint8_t>(g[0], size);
  memcpy(buf, g + 1, w);
  return w;
}
