#include "TimerMode.h"

#include "../App.h"

bool TimerMode::update(uint32_t now) {
  if (!_clock.running || remaining(now) > 0) return false;
  _clock.pause(now);
  _clock.banked = _total;  // pin at exactly zero
  _done = true;
  _doneAt = now;
  _dirty = true;
  return true;
}

void TimerMode::begin(App& app) {
  app.display.clear();
  app.display.setBrightness(app.brightnessFor(-1));
  _dirty = true;
}

void TimerMode::loop(App& app, uint32_t now) {
  bool blinking = _done && now - _doneAt < BLINK_MS;
  uint32_t interval = blinking ? 250 : (running() ? 100 : 1000);
  if (!_dirty && now - _lastDraw < interval) return;
  _dirty = false;
  _lastDraw = now;

  char buf[16];
  formatTimer(remaining(now), buf, sizeof(buf));
  _frame.clear();
  // Blink: on for 500 ms, off for 500 ms.
  if (!blinking || ((now - _doneAt) / 500) % 2 == 0) app.display.drawText(_frame, buf, Align::Center);
  app.display.push(_frame);
}
