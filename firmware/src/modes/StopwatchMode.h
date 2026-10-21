#pragma once
#include "../display/Frame.h"
#include "Mode.h"
#include "TimeFormat.h"

// Stopwatch that runs on the device, so it keeps going when the phone leaves.
class StopwatchMode : public Mode {
 public:
  const char* id() const override { return "stopwatch"; }
  void begin(App& app) override;
  void loop(App& app, uint32_t now) override;

  void start(uint32_t now) { _clock.start(now), _dirty = true; }
  void pause(uint32_t now) { _clock.pause(now), _dirty = true; }
  void reset() { _clock.reset(), _dirty = true; }
  uint32_t ms(uint32_t now) const { return _clock.elapsed(now); }
  bool running() const { return _clock.running; }

 private:
  RunClock _clock;
  Frame _frame;
  uint32_t _lastDraw = 0;
  bool _dirty = true;
};
