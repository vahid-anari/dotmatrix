#pragma once
#include <MD_MAX72xx.h>
#include <MD_Parola.h>

#include "../model/Item.h"
#include "Frame.h"

// Owns the LED matrix. Two ways to draw:
//  1. Parola text with in/out effects:  playText(item) + animate()
//  2. Direct frames for animations and the clock:  push(frame)
//
// The text shown by Parola always lives in this class's own buffer, so Parola
// never holds a pointer into memory that can be freed or moved (the v8 freeze).
class Display {
 public:
  Display();
  void begin();

  // ---- Parola text ----
  void playText(const Item& item);
  // Replace the text of the item that is playing, keeping its animation state.
  void setText(const char* text);
  // Advance the animation. Returns true once the item has finished (in → pause → out).
  bool animate();

  // ---- Direct drawing ----
  void push(const Frame& f);
  // Render text into a frame (no effects). Returns the text width in columns.
  uint16_t drawText(Frame& f, const char* text, Align align, int xOffset = 0) const;
  uint16_t textWidth(const char* text) const;

  void clear();
  void setBrightness(uint8_t level);  // 0..15, applied immediately
  uint8_t brightness() const { return _brightness; }
  void setPower(bool on);             // shutdown mode keeps the content
  bool power() const { return _power; }

 private:
  MD_Parola _parola;
  MD_MAX72XX* _mx;
  char _text[MAX_TEXT + 1] = "";
  uint8_t _brightness = 6;
  bool _power = true;

  void applySprites(const Item& item);
  uint8_t glyph(char c, uint8_t* buf, uint8_t size) const;
};
