#pragma once
#include "../display/Frame.h"
#include "../model/Item.h"
#include "Mode.h"

// Shows the time. Every `extras_every` seconds it makes way for the "extras",
// one after the other: the date, then the weather outside (each if switched on;
// the weather only with a reading).
//
// Drop style: the time slides up and away, each extra drops in from the top,
// stays `extras_pause` ms and goes back up, then the time slides back up from
// below. Scroll style: each extra scrolls across from the right, as before 0.5.
// An extra too wide for the display always scrolls across.
class ClockMode : public Mode {
 public:
  const char* id() const override { return "clock"; }
  void begin(App& app) override;
  void loop(App& app, uint32_t now) override;

 private:
  enum class Phase : uint8_t { Time, TimeOut, Extra, TimeIn };
  Phase _phase = Phase::Time;
  time_t _lastSecond = 0;
  time_t _lastExtras = 0;
  Frame _frame;   // the time as last drawn
  Item _item;     // the extra Parola is showing
  static constexpr uint8_t MAX_EXTRAS = 3;
  char _extras[MAX_EXTRAS][MAX_TEXT + 1];
  uint8_t _count = 0, _next = 0;
  uint8_t _step = 0;  // 0..8, rows moved so far while the time slides
  uint32_t _lastStep = 0;

  void timeText(App& app, const struct tm& t, char* buf, size_t n) const;
  void drawTime(App& app, const struct tm& t);
  bool startExtras(App& app, time_t t, uint32_t now);
  void showExtra(App& app);
  void afterExtras(App& app, uint32_t now);
};
