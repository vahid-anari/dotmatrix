#include "TextFx.h"

#include <Arduino.h>

// About how many steps the pixel-by-pixel effects take, whatever the text
// length: at the default 40 ms per step a long text is in after ~3 s, not 20.
static constexpr uint16_t WRITE_STEPS = 64;
static constexpr uint16_t CUT_STEPS = 80;

// Where the laser beam comes from.
static constexpr int BEAM_X = 0, BEAM_Y = DISPLAY_HEIGHT - 1;

void TextFx::begin(const Frame& text, FxKind kind, bool in) {
  _text = text;
  _kind = kind;
  _in = in;
  _step = 0;
  _n = 0;
  switch (kind) {
    case FxKind::LaserWrite: orderColumns(); break;
    case FxKind::LaserCut: orderStrokes(); break;
    default: break;
  }
  if (kind == FxKind::LaserScan) {
    _steps = DISPLAY_WIDTH + 2;  // the beam starts and ends just off the display
  } else {
    uint16_t target = kind == FxKind::LaserCut ? CUT_STEPS : WRITE_STEPS;
    _perStep = _n > target ? (_n + target - 1) / target : 1;
    _steps = (_n + _perStep - 1) / _perStep;
  }
}

// Laser write: left to right, top to bottom within each column.
void TextFx::orderColumns() {
  for (uint8_t x = 0; x < DISPLAY_WIDTH; x++)
    for (uint8_t y = 0; y < DISPLAY_HEIGHT; y++)
      if (_text.get(x, y)) _order[_n++] = x * 8 + y;
}

// Laser cut: follow each stroke like a cutter would. Start at the left-most,
// top-most pixel not yet cut and walk to touching pixels (8 directions),
// backtracking at dead ends; a new piece starts when a letter is done.
void TextFx::orderStrokes() {
  static const int8_t DX[] = {0, 1, 1, 1, 0, -1, -1, -1};
  static const int8_t DY[] = {1, 1, 0, -1, -1, -1, 0, 1};
  Frame seen;
  static uint16_t stack[MAX_PIXELS];  // only one TextFx runs at a time
  for (uint8_t sx = 0; sx < DISPLAY_WIDTH; sx++) {
    for (uint8_t sy = 0; sy < DISPLAY_HEIGHT; sy++) {
      if (!_text.get(sx, sy) || seen.get(sx, sy)) continue;
      uint16_t top = 0;
      stack[top++] = sx * 8 + sy;
      seen.set(sx, sy);
      _order[_n++] = sx * 8 + sy;
      while (top) {
        int x = stack[top - 1] / 8, y = stack[top - 1] % 8;
        bool moved = false;
        for (uint8_t d = 0; d < 8; d++) {
          int nx = x + DX[d], ny = y + DY[d];
          if (_text.get(nx, ny) && !seen.get(nx, ny)) {
            seen.set(nx, ny);
            stack[top++] = nx * 8 + ny;
            _order[_n++] = nx * 8 + ny;
            moved = true;
            break;
          }
        }
        if (!moved) top--;  // dead end: back up along the stroke
      }
    }
  }
}

// The first `count` pixels of the order (when coming in), or all but them
// (when going out, which erases in the same order the text was drawn).
void TextFx::drawPixels(Frame& out, uint16_t count) const {
  if (_in) {
    out.clear();
    for (uint16_t i = 0; i < count && i < _n; i++) out.set(_order[i] / 8, _order[i] % 8);
  } else {
    out = _text;
    for (uint16_t i = 0; i < count && i < _n; i++) out.set(_order[i] / 8, _order[i] % 8, false);
  }
}

void TextFx::line(Frame& f, int x0, int y0, int x1, int y1) {
  int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
  int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;
  while (true) {
    f.set(x0, y0);
    if (x0 == x1 && y0 == y1) break;
    int e2 = 2 * err;
    if (e2 >= dy) err += dy, x0 += sx;
    if (e2 <= dx) err += dx, y0 += sy;
  }
}

bool TextFx::step(Frame& out) {
  if (_step >= _steps) {
    if (_in)
      out = _text;
    else
      out.clear();
    return false;
  }
  uint16_t s = _step++;

  switch (_kind) {
    case FxKind::LaserScan: {
      // Beam at column bx. Coming in, the text is behind it (left);
      // going out, the text is still ahead of it (right).
      int bx = (int)s - 1;
      out.clear();
      for (int x = 0; x < DISPLAY_WIDTH; x++)
        if (_in ? x < bx : x > bx) out.col[x] = _text.col[x];
      if (bx >= 0 && bx < DISPLAY_WIDTH) out.col[bx] = 0xFF;
      // Sparks on the side the beam is working on.
      int sparkX = _in ? bx - 1 : bx + 1;
      if (sparkX >= 0 && sparkX < DISPLAY_WIDTH)
        for (int y = 0; y < DISPLAY_HEIGHT; y++)
          if (random(100) < 30) out.set(sparkX, y, !out.get(sparkX, y));
      break;
    }

    case FxKind::LaserWrite: {
      uint16_t done = (s + 1) * _perStep;
      drawPixels(out, done);
      uint16_t last = (done < _n ? done : _n) - 1;
      line(out, BEAM_X, BEAM_Y, _order[last] / 8, _order[last] % 8);
      break;
    }

    case FxKind::LaserCut: {
      uint16_t done = (s + 1) * _perStep;
      drawPixels(out, done);
      // The cutting point: a bright dot with a spark or two around it.
      uint16_t last = (done < _n ? done : _n) - 1;
      int x = _order[last] / 8, y = _order[last] % 8;
      out.set(x, y, true);
      if (random(100) < 60) out.set(x + random(-1, 2), y + random(-1, 2), true);
      break;
    }

    default:
      _step = _steps;
      return step(out);
  }
  return true;
}
