#pragma once
#include <Arduino.h>

// A record of the sensors over the last two days, one row a minute: what the
// sensors read, with what the display was doing (it warms the case) and the
// weather outside, to compare. Kept in RAM and saved to flash every ten
// minutes, so a restart loses at most ten minutes. Served as /log.csv.
namespace SensorLog {

struct __attribute__((packed)) Row {
  uint32_t time;      // Unix time (UTC)
  float lux;          // NAN = no reading
  int16_t temp100;    // 1/100 °C; INT16_MIN = no reading
  uint16_t hum100;    // 1/100 %; 0xFFFF = no reading
  uint16_t pres10;    // 1/10 hPa above 500 hPa; 0xFFFF = no reading
  int16_t outdoor10;  // 1/10 °C outside; INT16_MIN = none
  uint8_t brightness; // 0..15 as shown; 0xFF = display off
  uint8_t mode;       // index into modeNames()
};

constexpr uint32_t EVERY_S = 60;
constexpr size_t ROWS = 48 * 60;  // two days

void begin();                              // load what was saved
void add(const Row& r);
void loop(uint32_t now);                   // saves when due
size_t count();
// Writes up to `max` bytes of CSV starting at byte `index` of the whole text;
// returns how many (0 at the end). For a chunked HTTP response.
size_t csvChunk(uint8_t* buf, size_t max, size_t index);
const char* const* modeNames();
uint8_t modeIndex(const char* id);

}  // namespace SensorLog
