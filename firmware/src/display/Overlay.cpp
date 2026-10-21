#include "Overlay.h"

#include <Arduino.h>

static const char* const IDS[] = {"none", "wave", "sparkle", "pulse", "border"};

uint8_t overlayCount() { return sizeof(IDS) / sizeof(IDS[0]); }
const char* overlayId(uint8_t index) { return index < overlayCount() ? IDS[index] : IDS[0]; }
uint8_t overlayIndex(const char* id) {
  if (!id) return 0;
  for (uint8_t i = 0; i < overlayCount(); i++)
    if (strcmp(IDS[i], id) == 0) return i;
  return 0;
}

// Timing
static constexpr uint16_t WAVE_HOP_MS = 110;   // each letter dips for this long
static constexpr uint16_t WAVE_REST_MS = 700;  // still, before the next wave
static constexpr uint16_t PULSE_MS = 1600;     // one breath, dim → bright → dim
static constexpr uint8_t BORDER_LEN = 6;       // dots in the running line

void Overlay::begin(const Frame& text, OverlayKind kind, uint8_t brightness, uint32_t now) {
  _text = text;
  _kind = kind;
  _brightness = brightness;
  _start = now;
  // Letters are the runs of lit columns, split by empty ones.
  _letters = 0;
  for (uint8_t x = 0; x < DISPLAY_WIDTH && _letters < MAX_LETTERS;) {
    if (!text.col[x]) {
      x++;
      continue;
    }
    _from[_letters] = x;
    while (x < DISPLAY_WIDTH && text.col[x]) x++;
    _to[_letters++] = x;  // exclusive
  }
}

uint16_t Overlay::frameMs() const {
  switch (_kind) {
    case OverlayKind::Sparkle: return 70;
    case OverlayKind::Border: return 15;
    default: return 40;
  }
}

// A position along the edge, clockwise from the top-left corner.
static void edgePoint(int p, int& x, int& y) {
  const int W = DISPLAY_WIDTH, H = DISPLAY_HEIGHT;
  if (p < W) x = p, y = 0;
  else if ((p -= W) < H - 1) x = W - 1, y = p + 1;
  else if ((p -= H - 1) < W - 1) x = W - 2 - p, y = H - 1;
  else p -= W - 1, x = 0, y = H - 2 - p;
}

uint8_t Overlay::step(Frame& out, uint32_t now) {
  uint32_t t = now - _start;
  out = _text;
  switch (_kind) {
    case OverlayKind::Wave: {
      if (!_letters) break;
      uint32_t cycle = (uint32_t)_letters * WAVE_HOP_MS + WAVE_REST_MS;
      uint32_t i = (t % cycle) / WAVE_HOP_MS;
      if (i < _letters)
        for (uint8_t x = _from[i]; x < _to[i]; x++) out.col[x] = _text.col[x] << 1;  // one row down
      break;
    }

    case OverlayKind::Sparkle:
      for (uint8_t i = 0; i < 5; i++) out.set(random(DISPLAY_WIDTH), random(DISPLAY_HEIGHT), true);
      if (random(100) < 25) {
        // now and then a lit pixel blinks off
        uint8_t x = random(DISPLAY_WIDTH);
        if (out.col[x]) out.col[x] &= ~(1 << random(DISPLAY_HEIGHT));
      }
      break;

    case OverlayKind::Pulse: {
      uint32_t p = t % PULSE_MS;
      uint32_t tri = p < PULSE_MS / 2 ? p : PULSE_MS - p;  // 0 .. PULSE_MS/2
      uint8_t lo = _brightness / 4;
      // Starts at full brightness, breathes down and back up.
      return _brightness - (uint8_t)((_brightness - lo) * tri / (PULSE_MS / 2));
    }

    case OverlayKind::Border: {
      const int perimeter = 2 * (DISPLAY_WIDTH + DISPLAY_HEIGHT) - 4;
      int head = (t / frameMs()) % perimeter;
      for (uint8_t i = 0; i < BORDER_LEN; i++) {
        int x, y;
        edgePoint((head - i + perimeter) % perimeter, x, y);
        out.set(x, y, true);
      }
      break;
    }

    default:
      break;
  }
  return _brightness;
}
