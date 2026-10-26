#pragma once
#include <Arduino.h>

#include "../model/Settings.h"

// The weather outside, from Open-Meteo (free, no account or key). Fetched in a
// background task every 15 minutes while online, so a slow server never
// stalls the display or the watchdog.
class Weather {
 public:
  struct Now {
    bool valid = false;
    int16_t temp10 = 0;   // tenths of a degree, in the chosen unit
    uint8_t code = 0;     // WMO weather code
    uint32_t at = 0;      // millis() when it was fetched
  };

  void loop(const Settings& s, bool online, uint32_t now);
  // The place or units changed: forget the old reading and fetch again soon.
  void invalidate();
  // The latest reading, if it's less than 2 hours old.
  bool current(Now& out, uint32_t now) const;
  // "8°C Rain" (° is character 0xB0 in the display font), short enough to fit
  // the display even as "-12°C Cloudy".
  bool text(char* buf, size_t n, bool fahrenheit, uint32_t now) const;
  static const char* describe(uint8_t code);  // full: "Partly cloudy" (for the app)
  static const char* shortName(uint8_t code); // one short word: "Clouds"

 private:
  static constexpr uint32_t EVERY_MS = 15UL * 60 * 1000;
  static constexpr uint32_t RETRY_MS = 2UL * 60 * 1000;
  static constexpr uint32_t MAX_AGE_MS = 2UL * 60 * 60 * 1000;

  Now _now;
  mutable portMUX_TYPE _lock = portMUX_INITIALIZER_UNLOCKED;
  volatile bool _busy = false;
  bool _tried = false;
  bool _lastOk = false;
  uint32_t _lastTry = 0;
  uint32_t _generation = 0;  // bumped by invalidate(), so a late answer is dropped
  char _url[200] = "";
  uint32_t _urlGeneration = 0;

  static void task(void* self);
  void fetch();
};
