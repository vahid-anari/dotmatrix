#pragma once
#include "Frame.h"

// Effects drawn over a text while it stays on the display (its "pause").
enum class OverlayKind : uint8_t { None, Wave, Sparkle, Pulse, Border };

uint8_t overlayCount();                // including "none" at index 0
const char* overlayId(uint8_t index);  // "none", "wave", ...
uint8_t overlayIndex(const char* id);  // 0 (none) if unknown

class Overlay {
 public:
  // text: the text frame the overlay decorates. brightness: the item's level.
  void begin(const Frame& text, OverlayKind kind, uint8_t brightness, uint32_t now);
  // Draw the frame for time `now` into out. Returns the brightness to use.
  uint8_t step(Frame& out, uint32_t now);
  // How often step() needs calling.
  uint16_t frameMs() const;

 private:
  Frame _text;
  OverlayKind _kind = OverlayKind::None;
  uint8_t _brightness = 6;
  uint32_t _start = 0;
  // Wave: the letters, as column ranges.
  static constexpr uint8_t MAX_LETTERS = 32;
  uint8_t _from[MAX_LETTERS], _to[MAX_LETTERS];
  uint8_t _letters = 0;
};
