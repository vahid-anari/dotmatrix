#pragma once
#include "../display/Frame.h"
#include "../model/Item.h"
#include "Mode.h"

// Shows the time; every `date_every` seconds the date scrolls past once.
class ClockMode : public Mode {
 public:
  const char* id() const override { return "clock"; }
  void begin(App& app) override;
  void loop(App& app, uint32_t now) override;

 private:
  bool _showingDate = false;
  time_t _lastSecond = 0;
  time_t _lastDate = 0;
  Frame _frame;
  Item _dateItem;

  void drawTime(App& app, const struct tm& t);
};
