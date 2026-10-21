#pragma once
#include <Arduino.h>

#include "../config.h"

// A 64×8 off-screen frame. Column bytes, bit 0 = top row, x = 0 is the left edge.
struct Frame {
  uint8_t col[DISPLAY_WIDTH] = {0};

  void clear() { memset(col, 0, sizeof(col)); }
  void fill() { memset(col, 0xFF, sizeof(col)); }

  bool get(int x, int y) const {
    if (x < 0 || x >= DISPLAY_WIDTH || y < 0 || y >= DISPLAY_HEIGHT) return false;
    return col[x] & (1 << y);
  }
  void set(int x, int y, bool on = true) {
    if (x < 0 || x >= DISPLAY_WIDTH || y < 0 || y >= DISPLAY_HEIGHT) return;
    if (on)
      col[x] |= (1 << y);
    else
      col[x] &= ~(1 << y);
  }
  void invert() {
    for (auto& c : col) c = ~c;
  }
};
