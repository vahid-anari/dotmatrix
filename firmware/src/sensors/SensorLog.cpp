#include "SensorLog.h"

#include <LittleFS.h>
#include <math.h>
#include <time.h>

#include "config.h"

namespace SensorLog {
namespace {

constexpr const char* PATH = "/sensorlog.bin";
constexpr uint32_t MAGIC = 0x534C4F31;  // "SLO1"
constexpr uint32_t SAVE_EVERY_MS = 10UL * 60 * 1000;
const char* const MODES[] = {"off", "text", "clock", "stopwatch", "timer", "other"};

Row* rows = nullptr;     // ring buffer
size_t head = 0, n = 0;  // next slot, rows held
bool dirty = false;
uint32_t lastSave = 0;

const Row& at(size_t i) { return rows[(head + ROWS - n + i) % ROWS]; }  // 0 = oldest

void save() {
  File f = LittleFS.open("/sensorlog.tmp", "w");
  if (!f) return;
  uint32_t hdr[2] = {MAGIC, (uint32_t)n};
  bool ok = f.write((uint8_t*)hdr, sizeof(hdr)) == sizeof(hdr);
  for (size_t i = 0; ok && i < n; i++) ok = f.write((const uint8_t*)&at(i), sizeof(Row)) == sizeof(Row);
  f.close();
  if (ok) {
    LittleFS.remove(PATH);
    ok = LittleFS.rename("/sensorlog.tmp", PATH);
  }
  if (!ok) {
    LittleFS.remove("/sensorlog.tmp");
    LOG("sensorlog: save failed");
  }
  dirty = false;
}

// One CSV line for row i (i = -1: the header) into buf; returns its length.
size_t line(long i, char* buf, size_t max) {
  if (i < 0)
    return snprintf(buf, max, "time,lux,temp_c,humidity,pressure_hpa,outdoor_c,brightness,mode\n");
  const Row& r = at(i);
  time_t t = r.time;
  struct tm lt;
  localtime_r(&t, &lt);
  char ts[20], lx[12] = "", tc[10] = "", hu[8] = "", pr[10] = "", od[8] = "", br[4] = "";
  strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M", &lt);
  if (!isnan(r.lux)) snprintf(lx, sizeof(lx), r.lux < 10 ? "%.2f" : "%.1f", r.lux);
  if (r.temp100 != INT16_MIN) snprintf(tc, sizeof(tc), "%.2f", r.temp100 / 100.0);
  if (r.hum100 != 0xFFFF) snprintf(hu, sizeof(hu), "%.1f", r.hum100 / 100.0);
  if (r.pres10 != 0xFFFF) snprintf(pr, sizeof(pr), "%.1f", 500 + r.pres10 / 10.0);
  if (r.outdoor10 != INT16_MIN) snprintf(od, sizeof(od), "%.1f", r.outdoor10 / 10.0);
  if (r.brightness != 0xFF) snprintf(br, sizeof(br), "%u", r.brightness);
  return snprintf(buf, max, "%s,%s,%s,%s,%s,%s,%s,%s\n", ts, lx, tc, hu, pr, od, br,
                  MODES[r.mode < 6 ? r.mode : 5]);
}

}  // namespace

void begin() {
  rows = (Row*)malloc(ROWS * sizeof(Row));
  if (!rows) {
    LOG("sensorlog: no memory");
    return;
  }
  File f = LittleFS.open(PATH, "r");
  if (!f) return;
  uint32_t hdr[2];
  if (f.read((uint8_t*)hdr, sizeof(hdr)) == sizeof(hdr) && hdr[0] == MAGIC && hdr[1] <= ROWS) {
    size_t got = f.read((uint8_t*)rows, hdr[1] * sizeof(Row)) / sizeof(Row);
    n = got;
    head = got % ROWS;
    LOG("sensorlog: %u rows loaded", (unsigned)n);
  }
  f.close();
}

void add(const Row& r) {
  if (!rows) return;
  rows[head] = r;
  head = (head + 1) % ROWS;
  if (n < ROWS) n++;
  dirty = true;
}

void loop(uint32_t now) {
  if (dirty && now - lastSave >= SAVE_EVERY_MS) {
    lastSave = now;
    save();
  }
}

size_t count() { return n; }

// The CSV is never built whole (2880 rows are ~150 KB): each chunk is made
// from the rows on demand. The server asks for the chunks in order, so where
// the last one ended is remembered and the next one starts from there.
size_t csvChunk(uint8_t* buf, size_t max, size_t index) {
  if (!rows) return 0;
  static long nextRow = -1;   // first line not yet fully sent (-1 = header)
  static size_t nextPos = 0;  // byte offset where that line starts
  if (index < nextPos) nextRow = -1, nextPos = 0;  // a new download
  char tmp[128];
  size_t out = 0;
  while (nextRow < (long)n && out < max) {
    size_t len = line(nextRow, tmp, sizeof(tmp));
    if (nextPos + len <= index) {  // wholly before this chunk
      nextPos += len;
      nextRow++;
      continue;
    }
    size_t from = index - nextPos;
    size_t take = min(len - from, max - out);
    memcpy(buf + out, tmp + from, take);
    out += take;
    index += take;
    if (from + take < len) break;  // the buffer is full mid-line
    nextPos += len;
    nextRow++;
  }
  return out;
}

const char* const* modeNames() { return MODES; }

uint8_t modeIndex(const char* id) {
  for (uint8_t i = 0; i < 5; i++)
    if (strcmp(MODES[i], id) == 0) return i;
  return 5;
}

}  // namespace SensorLog
