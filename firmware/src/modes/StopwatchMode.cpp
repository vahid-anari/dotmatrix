#include "StopwatchMode.h"

#include "../App.h"

void StopwatchMode::begin(App& app) {
  app.display.clear();
  app.display.setBrightness(app.brightnessFor(-1));
  _dirty = true;
}

void StopwatchMode::loop(App& app, uint32_t now) {
  // ~33 frames/s while running is enough for the hundredths to look smooth.
  if (!_dirty && !(running() && now - _lastDraw >= 30)) return;
  _dirty = false;
  _lastDraw = now;
  char buf[16];
  formatStopwatch(ms(now), buf, sizeof(buf));
  _frame.clear();
  app.display.drawText(_frame, buf, Align::Center);
  app.display.push(_frame);
}
