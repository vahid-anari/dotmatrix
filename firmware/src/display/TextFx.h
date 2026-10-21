#pragma once
#include "Frame.h"

// Our own text entry/exit effects, drawn frame by frame (Parola has no laser).
// Each one plays forwards to bring the text in, and backwards to take it out.
enum class FxKind : uint8_t {
  None,
  LaserWrite,  // a beam from the bottom-left corner draws the text, column by column
  LaserScan,   // a vertical beam sweeps across; the text is behind it
  LaserCut,    // a cutting dot traces each letter, stroke by stroke
};

class TextFx {
 public:
  // text: the finished text frame. in: true = bring it in, false = take it out.
  void begin(const Frame& text, FxKind kind, bool in);
  // Draw the next frame into out. Returns false once the effect has finished;
  // out then holds the final frame (the text, or an empty display).
  bool step(Frame& out);
  // Number of steps the effect takes (for tests and timing).
  uint16_t steps() const { return _steps; }

  // Pixels are numbered x * 8 + y.
  static constexpr uint16_t MAX_PIXELS = DISPLAY_WIDTH * DISPLAY_HEIGHT;

 private:
  Frame _text;
  FxKind _kind = FxKind::None;
  bool _in = true;
  uint16_t _order[MAX_PIXELS];  // lit pixels, in drawing order
  uint16_t _n = 0;              // number of lit pixels
  uint16_t _perStep = 1;        // pixels drawn per step
  uint16_t _steps = 0;
  uint16_t _step = 0;

  void orderColumns();
  void orderStrokes();
  void drawPixels(Frame& out, uint16_t count) const;
  static void line(Frame& f, int x0, int y0, int x1, int y1);
};
