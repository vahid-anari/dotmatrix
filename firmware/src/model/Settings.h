#pragma once
#include <ArduinoJson.h>

#include "../config.h"

struct Settings {
  uint8_t brightness = 6;  // 0..15
  char mode[12] = "text";  // mode restored on boot
  char hostname[32] = DEFAULT_HOSTNAME;
  char timezone[64] = DEFAULT_TIMEZONE;

  struct Clock {
    bool format24h = true;
    bool seconds = true;
    char dateFormat[24] = "%a %b %d";
    // Now and then the clock makes way for the date and the weather, one
    // after the other ("extras").
    uint16_t extrasEvery = 0;   // seconds, 0 = never
    bool showDate = true;
    bool showWeather = true;
    bool extrasDrop = true;     // true: each drops in from the top, stays, goes back up;
                                // false: each scrolls across from the right
    uint16_t extrasPause = 3000;  // ms each stays (drop only)
  } clock;

  // Outside weather, from Open-Meteo, for the place chosen in the app.
  struct Weather {
    char place[40] = "";  // empty = no place chosen
    int32_t lat = 0;      // 1/10000 degree
    int32_t lon = 0;
    bool fahrenheit = false;
  } weather;

  struct Night {
    bool enabled = false;
    uint16_t from = 23 * 60;  // minutes after midnight
    uint16_t to = 7 * 60;
    uint8_t brightness = 1;
  } night;
};

// Apply a partial update. Unknown keys are ignored. Returns false on bad values.
bool settingsUpdate(Settings& s, JsonObjectConst o, const char*& err);
void settingsToJson(const Settings& s, JsonObject o);
