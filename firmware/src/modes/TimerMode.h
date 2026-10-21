#pragma once
#include "../display/Frame.h"
#include "Mode.h"
#include "TimeFormat.h"

// Countdown timer that runs on the device. When it reaches zero the App brings
// it to the front, and the display blinks "00:00" for a minute.
class TimerMode : public Mode {
 public:
  static constexpr uint32_t MAX_MS = 24UL * 3600 * 1000;
  static constexpr uint32_t BLINK_MS = 60UL * 1000;

  const char* id() const override { return "timer"; }
  void begin(App& app) override;
  void loop(App& app, uint32_t now) override;

  void set(uint32_t totalMs) {
    _total = totalMs > MAX_MS ? MAX_MS : totalMs;
    _clock.reset();
    _done = false;
    _dirty = true;
  }
  void start(uint32_t now) {
    if (_total == 0 || remaining(now) == 0) return;
    _clock.start(now), _done = false, _dirty = true;
  }
  void pause(uint32_t now) { _clock.pause(now), _dirty = true; }
  void reset() { _clock.reset(), _done = false, _dirty = true; }

  uint32_t total() const { return _total; }
  uint32_t remaining(uint32_t now) const {
    uint32_t e = _clock.elapsed(now);
    return e >= _total ? 0 : _total - e;
  }
  bool running() const { return _clock.running; }
  bool done() const { return _done; }

  // Called every loop even when another mode is showing. Returns true once,
  // at the moment the countdown reaches zero.
  bool update(uint32_t now);

 private:
  RunClock _clock;
  uint32_t _total = 5UL * 60 * 1000;
  bool _done = false;
  uint32_t _doneAt = 0;
  Frame _frame;
  uint32_t _lastDraw = 0;
  bool _dirty = true;
};
