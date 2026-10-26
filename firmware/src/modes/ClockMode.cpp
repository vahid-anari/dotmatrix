#include "ClockMode.h"

#include <time.h>

#include "../App.h"
#include "../display/Effects.h"

static constexpr uint16_t SLIDE_MS = 35;  // per row while the time slides

void ClockMode::begin(App& app) {
  _phase = Phase::Time;
  _lastSecond = 0;
  _lastExtras = time(nullptr);
  app.display.clear();
  app.display.setBrightness(app.brightnessFor(-1));
}

void ClockMode::timeText(App& app, const struct tm& t, char* buf, size_t n) const {
  const Settings::Clock& c = app.settings.clock;
  if (!app.timeValid()) {
    strlcpy(buf, c.seconds ? "--:--:--" : "--:--", n);
    return;
  }
  int hour = t.tm_hour;
  if (!c.format24h) {
    hour %= 12;
    if (hour == 0) hour = 12;
  }
  if (c.seconds)
    snprintf(buf, n, c.format24h ? "%02d:%02d:%02d" : "%d:%02d:%02d", hour, t.tm_min, t.tm_sec);
  else  // without seconds the colon blinks
    snprintf(buf, n, c.format24h ? "%02d%c%02d" : "%d%c%02d", hour, (t.tm_sec % 2) ? ' ' : ':', t.tm_min);
}

void ClockMode::drawTime(App& app, const struct tm& t) {
  char buf[12];
  timeText(app, t, buf, sizeof(buf));
  _frame.clear();
  app.display.drawText(_frame, buf, Align::Center);
  app.display.push(_frame);
}

// Collects the extras that are switched on and available. Returns false if
// there's nothing to show this time.
bool ClockMode::startExtras(App& app, time_t t, uint32_t now) {
  const Settings::Clock& c = app.settings.clock;
  _count = _next = 0;
  if (c.showDate && app.timeValid()) {
    struct tm local;
    localtime_r(&t, &local);
    strftime(_extras[_count], sizeof(_extras[0]), c.dateFormat, &local);
    if (_extras[_count][0]) _count++;
  }
  if (c.showWeather && app.weather.text(_extras[_count], sizeof(_extras[0]), app.settings.weather.fahrenheit, now))
    _count++;
  if (!_count) return false;
  if (c.extrasDrop) {
    _phase = Phase::TimeOut;  // the time slides up and away first
    _step = 0;
    _lastStep = now - SLIDE_MS;
  } else {
    showExtra(app);
  }
  return true;
}

void ClockMode::showExtra(App& app) {
  const Settings::Clock& c = app.settings.clock;
  _item = Item();
  strlcpy(_item.text, _extras[_next++], sizeof(_item.text));
  bool drop = c.extrasDrop && app.display.textWidth(_item.text) <= DISPLAY_WIDTH;
  _item.effectIn = effectIndex(drop ? "scroll_down" : "scroll_left");  // down from the top
  _item.effectOut = effectIndex(drop ? "scroll_up" : "scroll_left");   // back up
  _item.speedIn = _item.speedOut = drop ? 40 : 35;
  _item.pause = drop ? c.extrasPause : 1000;
  app.display.playText(_item);
  _phase = Phase::Extra;
}

void ClockMode::afterExtras(App& app, uint32_t now) {
  if (app.settings.clock.extrasDrop) {
    // The time comes back up from below, drawn for the current second.
    time_t t = time(nullptr);
    struct tm local;
    localtime_r(&t, &local);
    char buf[12];
    timeText(app, local, buf, sizeof(buf));
    _frame.clear();
    app.display.drawText(_frame, buf, Align::Center);
    _phase = Phase::TimeIn;
    _step = 0;
    _lastStep = now - SLIDE_MS;
  } else {
    _phase = Phase::Time;
    _lastSecond = 0;  // redraw the time right away
  }
}

void ClockMode::loop(App& app, uint32_t now) {
  switch (_phase) {
    case Phase::TimeOut:
    case Phase::TimeIn:
      if (now - _lastStep < SLIDE_MS) return;
      _lastStep = now;
      if (++_step > DISPLAY_HEIGHT) {
        if (_phase == Phase::TimeOut) {
          showExtra(app);
        } else {
          _phase = Phase::Time;
          _lastSecond = 0;
        }
        return;
      }
      {
        // Out: rows move up (towards bit 0) until gone. In: from below, up into place.
        Frame f;
        for (uint8_t x = 0; x < DISPLAY_WIDTH; x++)
          f.col[x] = _phase == Phase::TimeOut ? _frame.col[x] >> _step
                                             : (uint8_t)(_frame.col[x] << (DISPLAY_HEIGHT - _step));
        app.display.push(f);
      }
      return;

    case Phase::Extra:
      if (!app.display.animate()) return;
      if (_next < _count)
        showExtra(app);
      else
        afterExtras(app, now);
      return;

    case Phase::Time:
      break;
  }

  time_t t = time(nullptr);
  if (t == _lastSecond) return;
  _lastSecond = t;

  uint16_t every = app.settings.clock.extrasEvery;
  if (every && t - _lastExtras >= every) {
    _lastExtras = t;
    if (startExtras(app, t, now)) return;
  }
  struct tm local;
  localtime_r(&t, &local);
  drawTime(app, local);
}
