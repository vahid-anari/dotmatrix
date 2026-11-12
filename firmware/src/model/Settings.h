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
    // Now and then the clock makes way for the date, the weather and the
    // room's temperature, one after the other ("extras").
    uint16_t extrasEvery = 0;   // seconds, 0 = never
    bool showDate = true;
    bool showWeather = true;
    bool showIndoor = true;     // the room's temperature and humidity (with a BME280)
    bool extrasDrop = true;     // true: each drops in from the top, stays, goes back up;
                                // false: each scrolls across from the right
    uint16_t extrasPause = 3000;  // ms each stays (drop only)
  } clock;

  // Outside weather, from Open-Meteo, for the place chosen in the app.
  struct Weather {
    char place[40] = "";  // empty = no place chosen
    int32_t lat = 0;      // 1/10000 degree
    int32_t lon = 0;
    char country[3] = ""; // ISO code, e.g. "CA": picks the weather model (since 0.7)
    bool fahrenheit = false;
  } weather;

  // Brightness from the room's light (with a light sensor): `dark` in a dark
  // room, `bright` with the lights on, in between by daylight (since 0.8).
  struct AutoBrightness {
    bool enabled = false;
    uint8_t dark = 0;
    uint8_t bright = 2;
  } autoBrightness;

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
