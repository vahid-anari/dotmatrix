#include "MatrixRain.h"

void MatrixRain::begin(const Item& item, const Display& display) {
  _density = item.density ? min<uint8_t>(item.density, MAX_DROPS) : 18;
  _duration = item.duration;
  _start = millis();
  _target.clear();
  _shown.clear();
  if (_reveal) display.drawText(_target, item.text, item.align);
  for (auto& d : _drops) d.x = -1;
  // Stagger the first drops above the display so the rain starts gradually.
  for (uint8_t i = 0; i < _density; i++) {
    spawn(_drops[i], false);
    _drops[i].y = -(int8_t)random(0, 16);
  }
}

void MatrixRain::spawn(Drop& d, bool preferHidden) {
  int x = random(DISPLAY_WIDTH);
  if (preferHidden) {
    // Aim new drops at columns that still have text to reveal.
    for (uint8_t tries = 0; tries < 8; tries++) {
      int c = random(DISPLAY_WIDTH);
      if (_target.col[c] & ~_shown.col[c]) {
        x = c;
        break;
      }
    }
  }
  d.x = x;
  d.y = -(int8_t)random(0, 4);
  d.len = random(2, 6);
  d.period = random(1, 4);
  d.tick = 0;
}

bool MatrixRain::fullyRevealed() const {
  for (uint8_t x = 0; x < DISPLAY_WIDTH; x++)
    if (_target.col[x] & ~_shown.col[x]) return false;
  return true;
}

bool MatrixRain::step(Frame& f, uint32_t now) {
  uint32_t elapsed = now - _start;
  // Reveal: stop new rain in the last 25% so the text is left standing.
  bool raining = !_reveal || elapsed < _duration * 3 / 4;
  // Reveal: past 60% of the time, every head that touches text reveals it.
  bool eager = _reveal && elapsed > _duration * 3 / 5;

  f = _shown;  // revealed text stays on screen

  bool anyActive = false;
  for (uint8_t i = 0; i < MAX_DROPS; i++) {
    Drop& d = _drops[i];
    if (d.x < 0) {
      if (raining && i < _density) spawn(d, _reveal);
      continue;
    }
    anyActive = true;

    if (++d.tick >= d.period) {
      d.tick = 0;
      d.y++;
    }
    // Head is solid, tail flickers to fake a fading trail (no per-pixel dimming).
    for (uint8_t t = 0; t <= d.len; t++) {
      int y = d.y - t;
      if (y < 0 || y >= DISPLAY_HEIGHT) continue;
      bool on = (t == 0) || (random(100) < 85 - t * 15);
      if (on) f.set(d.x, y);
    }
    if (_reveal && d.y >= 0 && d.y < DISPLAY_HEIGHT && _target.get(d.x, d.y) &&
        (eager || random(100) < 35)) {
      _shown.set(d.x, d.y);
    }
    if (d.y - d.len >= DISPLAY_HEIGHT) d.x = -1;  // fell off the bottom
  }

  if (_reveal && !raining && !anyActive) {
    _shown = _target;  // make sure nothing is missing at the end
    f = _shown;
  }
  return true;  // runs for the item's full duration
}
