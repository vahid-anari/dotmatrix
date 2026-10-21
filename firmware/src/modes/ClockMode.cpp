#include "ClockMode.h"

#include <time.h>

#include "../App.h"
#include "../display/Effects.h"

void ClockMode::begin(App& app) {
  _showingDate = false;
  _lastSecond = 0;
  _lastDate = _lastWeather = time(nullptr);
  app.display.clear();
  app.display.setBrightness(app.brightnessFor(-1));
}

void ClockMode::drawTime(App& app, const struct tm& t) {
  const Settings::Clock& c = app.settings.clock;
  char buf[12];
  if (!app.timeValid()) {
    strlcpy(buf, c.seconds ? "--:--:--" : "--:--", sizeof(buf));
  } else {
    int hour = t.tm_hour;
    if (!c.format24h) {
      hour %= 12;
      if (hour == 0) hour = 12;
    }
    if (c.seconds)
      snprintf(buf, sizeof(buf), c.format24h ? "%02d:%02d:%02d" : "%d:%02d:%02d", hour, t.tm_min,
               t.tm_sec);
    else  // without seconds the colon blinks
      snprintf(buf, sizeof(buf), c.format24h ? "%02d%c%02d" : "%d%c%02d", hour,
               (t.tm_sec % 2) ? ' ' : ':', t.tm_min);
  }
  _frame.clear();
  app.display.drawText(_frame, buf, Align::Center);
  app.display.push(_frame);
}

void ClockMode::loop(App& app, uint32_t now) {
  if (_showingDate) {
    if (app.display.animate()) {
      _showingDate = false;
      _lastSecond = 0;  // redraw the time right away
    }
    return;
  }

  time_t t = time(nullptr);
  if (t == _lastSecond) return;
  _lastSecond = t;

  struct tm local;
  localtime_r(&t, &local);

  // When both are due, the date goes first and the weather follows it.
  uint16_t every = app.settings.clock.dateEvery;
  if (every && app.timeValid() && t - _lastDate >= every) {
    _lastDate = t;
    char buf[MAX_TEXT + 1];
    strftime(buf, sizeof(buf), app.settings.clock.dateFormat, &local);
    scroll(app, buf);
    return;
  }
  uint16_t wEvery = app.settings.clock.weatherEvery;
  if (wEvery && t - _lastWeather >= wEvery) {
    _lastWeather = t;
    char buf[48];
    if (app.weather.text(buf, sizeof(buf), app.settings.weather.fahrenheit, now)) {
      scroll(app, buf);
      return;
    }
  }
  drawTime(app, local);
}

void ClockMode::scroll(App& app, const char* text) {
  _dateItem = Item();
  strlcpy(_dateItem.text, text, sizeof(_dateItem.text));
  _dateItem.effectIn = _dateItem.effectOut = effectIndex("scroll_left");
  _dateItem.speedIn = _dateItem.speedOut = 35;
  _dateItem.pause = 1000;
  app.display.playText(_dateItem);
  _showingDate = true;
}
