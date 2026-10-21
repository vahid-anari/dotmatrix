#pragma once
#include "../display/Frame.h"
#include "../model/Item.h"
#include "Mode.h"

// Shows the time; every `date_every` seconds the date scrolls past once, and
// every `weather_every` seconds the weather outside (when there's a reading).
class ClockMode : public Mode {
 public:
  const char* id() const override { return "clock"; }
  void begin(App& app) override;
  void loop(App& app, uint32_t now) override;

 private:
  bool _showingDate = false;  // the date or the weather is scrolling past
  time_t _lastSecond = 0;
  time_t _lastDate = 0;
  time_t _lastWeather = 0;
  Frame _frame;
  Item _dateItem;

  void drawTime(App& app, const struct tm& t);
  void scroll(App& app, const char* text);
};
