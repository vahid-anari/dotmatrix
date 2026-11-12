#pragma once
#include <Arduino.h>

#include <memory>

// A record of the sensors, in two series:
//   - minutes: a row a minute for the last two days, kept in RAM and saved to
//     flash every ten minutes (a restart loses at most ten minutes);
//   - quarters: 15-minute averages for the last 30 days, written to flash as
//     each quarter hour ends.
// Each row has what the sensors read, what the display was doing (it warms
// the case) and the weather outside, to compare. Served as CSV: /log.csv (the
// minutes, for people) and /api/log (either series, for the app).
namespace SensorLog {

struct __attribute__((packed)) Row {
  uint32_t time;      // Unix time (UTC) of the minute, or of the quarter's start
  float lux;          // NAN = no reading
  int16_t temp100;    // 1/100 °C; INT16_MIN = no reading
  uint16_t hum100;    // 1/100 %; 0xFFFF = no reading
  uint16_t pres10;    // 1/10 hPa above 500 hPa; 0xFFFF = no reading
  int16_t outdoor10;  // 1/10 °C outside; INT16_MIN = none
  uint8_t brightness; // 0..15 as shown (a quarter: the average); 0xFF = display off
  uint8_t mode;       // index into modeNames()
};

constexpr uint32_t EVERY_S = 60;
constexpr uint32_t QUARTER_S = 15 * 60;
constexpr size_t ROWS = 48 * 60;          // two days of minutes
constexpr size_t QUARTERS = 30 * 24 * 4;  // 30 days of quarters

void begin();                              // load what was saved
void add(const Row& r);                    // a minute's row; also feeds the quarters
void loop(uint32_t now);                   // saves when due
size_t count();
size_t quarterCount();

// CSV, made in pieces for a chunked HTTP response: each download gets its own
// Cursor; next() fills up to `max` bytes and returns how many (0 at the end).
struct Cursor {
  bool quarters = false;  // which series
  bool human = false;     // local time "2026-11-12 18:05" (else Unix time "t")
  uint32_t since = 0;     // only rows after this time
  long row = -1;          // next row (-1 = the header line)
  char text[128];         // the line being sent, and how much of it is out
  size_t len = 0, sent = 0;
  size_t next(uint8_t* buf, size_t max);
};
std::shared_ptr<Cursor> csv(bool quarters, bool human, uint32_t since);

const char* const* modeNames();
uint8_t modeIndex(const char* id);

}  // namespace SensorLog
