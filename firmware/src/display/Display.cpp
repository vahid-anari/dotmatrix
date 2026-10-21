#include "Display.h"

#include "Effects.h"
#include "Sprites.h"

// Narrow digits so "12:17:11" fits nicely (from v8). Format: width, columns...
static const uint8_t GLYPH_ONE[] = {5, 0x00, 0x04, 0x02, 0x7F, 0x00};
static const uint8_t GLYPH_SEVEN[] = {5, 0x01, 0x01, 0x71, 0x09, 0x07};

static textPosition_t toParola(Align a) {
  switch (a) {
    case Align::Left: return PA_LEFT;
    case Align::Right: return PA_RIGHT;
    default: return PA_CENTER;
  }
}

Display::Display() : _parola(MD_MAX72XX::FC16_HW, PIN_DISPLAY_CS, DISPLAY_MODULES) {}

void Display::begin() {
  _parola.begin();
  _mx = _parola.getGraphicObject();
  _parola.addChar('1', GLYPH_ONE);
  _parola.addChar('7', GLYPH_SEVEN);
  _parola.setTextBuffer(_text);  // the only buffer Parola ever sees
  setBrightness(_brightness);
  clear();
}

// ---------------------------------------------------------------- Parola text

void Display::applySprites(const Item& item) {
  const char* inName = effectSpriteName(item.effectIn);
  const char* outName = effectSpriteName(item.effectOut);
  if (!inName && !outName) return;
  // Parola needs data for both sides; reuse one if only one side is a sprite.
  const Sprite* in = findSprite(inName ? inName : outName);
  const Sprite* out = findSprite(outName ? outName : inName);
  if (!in || !out) return;
  _parola.setSpriteData(in->data, in->width, in->frames, out->data, out->width, out->frames);
}

void Display::start(const Item& item, textEffect_t in, textEffect_t out, uint16_t speedIn,
                    uint16_t pause) {
  strlcpy(_text, item.text, sizeof(_text));
  // Invert first: displayClear() fills with the *current* invert state, and
  // scroll/sprite effects don't clear again, so the old state would show through.
  _parola.setInvert(item.invert);
  _parola.displayClear();
  _parola.setTextAlignment(toParola(item.align));
  _parola.setSpeedInOut(speedIn, item.speedOut);
  _parola.setPause(pause);
  applySprites(item);
  _parola.setTextEffect(in, out);
  _parola.displayReset();
}

// "None" coming in means the text is simply there: Parola's PA_NO_EFFECT would
// skip the whole item instead, so it's shown with PA_PRINT.
static textEffect_t entry(const Item& item) {
  textEffect_t e = effectAt(item.effectIn).effect;
  return e == PA_NO_EFFECT ? PA_PRINT : e;
}

void Display::playText(const Item& item) {
  start(item, entry(item), effectAt(item.effectOut).effect, item.speedIn, item.pause);
}

// PA_NO_EFFECT on the way out ends the animation and leaves the text up.
void Display::playTextIn(const Item& item) {
  start(item, entry(item), PA_NO_EFFECT, item.speedIn, 0);
}

// PA_PRINT shows the whole text in one step; with no pause the exit follows.
void Display::playTextOut(const Item& item) {
  start(item, PA_PRINT, effectAt(item.effectOut).effect, 1, 0);
}

void Display::setText(const char* text) {
  // Same buffer, new content: Parola's pointer stays valid.
  strlcpy(_text, text, sizeof(_text));
}

bool Display::animate() { return _parola.displayAnimate(); }

// -------------------------------------------------------------- Direct frames

void Display::push(const Frame& f) {
  _mx->control(MD_MAX72XX::UPDATE, MD_MAX72XX::OFF);  // batch, then one refresh
  for (uint8_t x = 0; x < DISPLAY_WIDTH; x++) {
    // MD_MAX72XX numbers columns from the right-hand end of the chain.
    uint8_t c = DISPLAY_FLIP_X ? x : (DISPLAY_WIDTH - 1 - x);
    _mx->setColumn(c, f.col[x]);
  }
  _mx->control(MD_MAX72XX::UPDATE, MD_MAX72XX::ON);
}

uint8_t Display::glyph(char c, uint8_t* buf, uint8_t size) const {
  const uint8_t* custom = c == '1' ? GLYPH_ONE : (c == '7' ? GLYPH_SEVEN : nullptr);
  if (custom) {
    uint8_t w = min<uint8_t>(custom[0], size);
    memcpy(buf, custom + 1, w);
    return w;
  }
  return _mx->getChar((uint8_t)c, size, buf);
}

// -------------------------------------------------------------------- Common

void Display::clear() {
  _parola.displayClear();
  _mx->clear();
}

void Display::setBrightness(uint8_t level) {
  _brightness = min<uint8_t>(level, 15);
  _parola.setIntensity(_brightness);
}

void Display::setPower(bool on) {
  _power = on;
  _parola.displayShutdown(!on);
}
