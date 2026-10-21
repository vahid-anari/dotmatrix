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
    uint16_t dateEvery = 0;  // seconds, 0 = never
    char dateFormat[24] = "%a %b %d";
  } clock;

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
