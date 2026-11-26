#include "SensorLog.h"

#include <LittleFS.h>
#include <math.h>
#include <time.h>

#include "config.h"

namespace SensorLog {
namespace {

constexpr const char* PATH = "/sensorlog.bin";    // the minutes
constexpr const char* QPATH = "/sensorlog15.bin";  // the quarters: header, then QUARTERS slots
constexpr uint32_t MAGIC = 0x534C4F32;   // "SLO2" (0.9.0: rows gained chipC)
constexpr uint32_t QMAGIC = 0x534C5132;  // "SLQ2"
constexpr uint32_t MAGIC1 = 0x534C4F31, QMAGIC1 = 0x534C5131;  // before 0.9.0, converted on start
constexpr const char* QTMP = "/sensorlog15.tmp";

// A row as 0.6 to 0.8 wrote it (no chip temperature).
struct __attribute__((packed)) Row1 {
  uint32_t time;
  float lux;
  int16_t temp100;
  uint16_t hum100;
  uint16_t pres10;
  int16_t outdoor10;
  uint8_t brightness;
  uint8_t mode;
};
Row fromRow1(const Row1& o) {
  Row r;
  memcpy(&r, &o, sizeof(Row1));
  r.chipC = INT8_MIN;
  return r;
}
constexpr uint32_t SAVE_EVERY_MS = 10UL * 60 * 1000;
const char* const MODES[] = {"off", "text", "clock", "stopwatch", "timer", "other"};

Row* rows = nullptr;     // the minutes' ring buffer
size_t head = 0, n = 0;  // next slot, rows held
bool dirty = false;
uint32_t lastSave = 0;

uint32_t qHead = 0, qCount = 0;  // the quarters' ring, in the file

// The quarter being collected: sums of what the minutes read.
struct Acc {
  uint32_t start = 0;
  float lux = 0;
  int32_t temp = 0, hum = 0, pres = 0, outdoor = 0, chip = 0;
  uint32_t bright = 0;
  uint16_t nLux = 0, nTemp = 0, nHum = 0, nPres = 0, nOut = 0, nOn = 0, nRows = 0, nChip = 0;
  uint8_t mode = 0;
} acc;

const Row& at(size_t i) { return rows[(head + ROWS - n + i) % ROWS]; }  // 0 = oldest

void save() {
  // Written in place (no copy beside it: flash is short); a power cut while
  // writing loses the minutes, which the length check then throws away.
  File f = LittleFS.open(PATH, "w");
  if (!f) return;
  uint32_t hdr[2] = {MAGIC, (uint32_t)n};
  bool ok = f.write((uint8_t*)hdr, sizeof(hdr)) == sizeof(hdr);
  for (size_t i = 0; ok && i < n; i++) ok = f.write((const uint8_t*)&at(i), sizeof(Row)) == sizeof(Row);
  f.close();
  if (!ok) LOG("sensorlog: save failed");
  dirty = false;
}

// The quarters file from before 0.9.0, rewritten oldest first with the new rows.
// If there's no room for the copy, the display's quarters start again (the phone
// keeps its own copy of everything it fetched).
void qConvert() {
  File f = LittleFS.open(QPATH, "r");
  uint32_t hdr[3];
  if (!f || f.read((uint8_t*)hdr, sizeof(hdr)) != sizeof(hdr) || hdr[0] != QMAGIC1) {
    if (f) f.close();
    return;
  }
  uint32_t oldHead = hdr[1] % QUARTERS, cnt = min<uint32_t>(hdr[2], QUARTERS);
  File o = LittleFS.open(QTMP, "w");
  uint32_t nh[3] = {QMAGIC, cnt % QUARTERS, cnt};
  bool ok = o && o.write((uint8_t*)nh, sizeof(nh)) == sizeof(nh);
  for (uint32_t i = 0; ok && i < cnt; i++) {
    Row1 r1;
    uint32_t slot = (oldHead + QUARTERS - cnt + i) % QUARTERS;
    ok = f.seek(sizeof(hdr) + slot * sizeof(Row1)) && f.read((uint8_t*)&r1, sizeof(Row1)) == sizeof(Row1);
    Row r = fromRow1(r1);
    ok = ok && o.write((const uint8_t*)&r, sizeof(Row)) == sizeof(Row);
  }
  f.close();
  if (o) o.close();
  LittleFS.remove(QPATH);
  if (ok) {
    LittleFS.rename(QTMP, QPATH);
    LOG("sensorlog: %u quarter hours converted", (unsigned)cnt);
  } else {
    LittleFS.remove(QTMP);
    LOG("sensorlog: quarters couldn't be converted; starting again");
  }
}

void qOpen() {
  LittleFS.remove(QTMP);  // a conversion cut short
  qConvert();
  File f = LittleFS.open(QPATH, "r");
  uint32_t hdr[3];
  if (f && f.read((uint8_t*)hdr, sizeof(hdr)) == sizeof(hdr) && hdr[0] == QMAGIC && hdr[1] < QUARTERS &&
      hdr[2] <= QUARTERS) {
    qHead = hdr[1];
    qCount = hdr[2];
    LOG("sensorlog: %u quarter hours", (unsigned)qCount);
  }
  if (f) f.close();
}

void qAppend(const Row& r) {
  File f = LittleFS.open(QPATH, LittleFS.exists(QPATH) ? "r+" : "w+");
  if (!f) return;
  uint32_t hdr[3] = {QMAGIC, (uint32_t)((qHead + 1) % QUARTERS), (uint32_t)min<size_t>(qCount + 1, QUARTERS)};
  bool ok = f.seek(sizeof(hdr) + qHead * sizeof(Row)) && f.write((const uint8_t*)&r, sizeof(Row)) == sizeof(Row) &&
            f.seek(0) && f.write((uint8_t*)hdr, sizeof(hdr)) == sizeof(hdr);
  f.close();
  if (ok) {
    qHead = hdr[1];
    qCount = hdr[2];
  } else {
    LOG("sensorlog: quarter write failed");
  }
}

bool qRead(size_t i, Row& r) {  // 0 = oldest
  File f = LittleFS.open(QPATH, "r");
  if (!f) return false;
  size_t slot = (qHead + QUARTERS - qCount + i) % QUARTERS;
  bool ok = f.seek(3 * sizeof(uint32_t) + slot * sizeof(Row)) && f.read((uint8_t*)&r, sizeof(Row)) == sizeof(Row);
  f.close();
  return ok;
}

void flushQuarter() {
  if (!acc.nRows) return;
  Row q;
  q.time = acc.start;
  q.lux = acc.nLux ? acc.lux / acc.nLux : NAN;
  q.temp100 = acc.nTemp ? (int16_t)(acc.temp / acc.nTemp) : INT16_MIN;
  q.hum100 = acc.nHum ? (uint16_t)(acc.hum / acc.nHum) : 0xFFFF;
  q.pres10 = acc.nPres ? (uint16_t)(acc.pres / acc.nPres) : 0xFFFF;
  q.outdoor10 = acc.nOut ? (int16_t)(acc.outdoor / acc.nOut) : INT16_MIN;
  q.brightness = acc.nOn * 2 >= acc.nRows ? (uint8_t)lroundf((float)acc.bright / acc.nOn) : 0xFF;
  q.mode = acc.mode;
  q.chipC = acc.nChip ? (int8_t)lroundf((float)acc.chip / acc.nChip) : INT8_MIN;
  qAppend(q);
  acc = Acc();
}

void collect(const Row& r) {
  uint32_t start = r.time - r.time % QUARTER_S;
  if (acc.nRows && start != acc.start) flushQuarter();
  acc.start = start;
  acc.nRows++;
  if (!isnan(r.lux)) acc.lux += r.lux, acc.nLux++;
  if (r.temp100 != INT16_MIN) acc.temp += r.temp100, acc.nTemp++;
  if (r.hum100 != 0xFFFF) acc.hum += r.hum100, acc.nHum++;
  if (r.pres10 != 0xFFFF) acc.pres += r.pres10, acc.nPres++;
  if (r.outdoor10 != INT16_MIN) acc.outdoor += r.outdoor10, acc.nOut++;
  if (r.brightness != 0xFF) acc.bright += r.brightness, acc.nOn++;
  if (r.chipC != INT8_MIN) acc.chip += r.chipC, acc.nChip++;
  acc.mode = r.mode;
}

// One CSV line for `r` (or the header when r is null) into buf; returns its length.
size_t formatLine(const Row* r, bool human, char* buf, size_t max) {
  if (!r)
    return snprintf(buf, max, human ? "time,lux,temp_c,humidity,pressure_hpa,outdoor_c,brightness,mode,chip_c\n"
                                    : "t,lux,temp_c,humidity,pressure_hpa,outdoor_c,brightness,mode,chip_c\n");
  char ts[20], lx[12] = "", tc[10] = "", hu[8] = "", pr[10] = "", od[8] = "", br[4] = "", ch[6] = "";
  if (human) {
    time_t t = r->time;
    struct tm lt;
    localtime_r(&t, &lt);
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M", &lt);
  } else {
    snprintf(ts, sizeof(ts), "%lu", (unsigned long)r->time);
  }
  if (!isnan(r->lux)) snprintf(lx, sizeof(lx), r->lux < 10 ? "%.2f" : "%.1f", r->lux);
  if (r->temp100 != INT16_MIN) snprintf(tc, sizeof(tc), "%.2f", r->temp100 / 100.0);
  if (r->hum100 != 0xFFFF) snprintf(hu, sizeof(hu), "%.1f", r->hum100 / 100.0);
  if (r->pres10 != 0xFFFF) snprintf(pr, sizeof(pr), "%.1f", 500 + r->pres10 / 10.0);
  if (r->outdoor10 != INT16_MIN) snprintf(od, sizeof(od), "%.1f", r->outdoor10 / 10.0);
  if (r->brightness != 0xFF) snprintf(br, sizeof(br), "%u", r->brightness);
  if (r->chipC != INT8_MIN) snprintf(ch, sizeof(ch), "%d", r->chipC);
  return snprintf(buf, max, "%s,%s,%s,%s,%s,%s,%s,%s,%s\n", ts, lx, tc, hu, pr, od, br,
                  MODES[r->mode < 6 ? r->mode : 5], ch);
}

}  // namespace

void begin() {
  rows = (Row*)malloc(ROWS * sizeof(Row));
  if (!rows) {
    LOG("sensorlog: no memory");
    return;
  }
  LittleFS.remove("/sensorlog.tmp");  // left by 0.6
  File f = LittleFS.open(PATH, "r");
  if (f) {
    uint32_t hdr[2];
    if (f.read((uint8_t*)hdr, sizeof(hdr)) == sizeof(hdr) && hdr[0] == MAGIC && hdr[1] <= ROWS) {
      size_t got = f.read((uint8_t*)rows, hdr[1] * sizeof(Row)) / sizeof(Row);
      n = got;
      head = got % ROWS;
      LOG("sensorlog: %u rows loaded", (unsigned)n);
    } else if (hdr[0] == MAGIC1 && hdr[1] <= ROWS) {  // before 0.9.0: convert as it loads
      Row1 r1;
      while (n < hdr[1] && f.read((uint8_t*)&r1, sizeof(Row1)) == sizeof(Row1)) rows[n++] = fromRow1(r1);
      head = n % ROWS;
      dirty = true;  // saved in the new form at the next save
      LOG("sensorlog: %u rows converted", (unsigned)n);
    }
    f.close();
  }
  qOpen();
  // Pick up the quarter that was being collected when the display stopped.
  if (n) {
    uint32_t start = at(n - 1).time - at(n - 1).time % QUARTER_S;
    Row last;
    bool done = qCount && qRead(qCount - 1, last) && last.time >= start;
    if (!done)
      for (size_t i = 0; i < n; i++)
        if (at(i).time >= start) collect(at(i));
  }
}

void add(const Row& r) {
  if (!rows) return;
  rows[head] = r;
  head = (head + 1) % ROWS;
  if (n < ROWS) n++;
  dirty = true;
  collect(r);
}

void loop(uint32_t now) {
  if (dirty && now - lastSave >= SAVE_EVERY_MS) {
    lastSave = now;
    save();
  }
}

size_t count() { return n; }
size_t quarterCount() { return qCount; }

std::shared_ptr<Cursor> csv(bool quarters, bool human, uint32_t since) {
  auto c = std::make_shared<Cursor>();
  c->quarters = quarters;
  c->human = human;
  c->since = since;
  return c;
}

// Rows are read as they're sent (2880 rows are ~150 KB of CSV, too much to
// build at once). If a row is added during the download, one row may come
// twice or be missed; the app keeps rows by time, so that does no harm.
size_t Cursor::next(uint8_t* buf, size_t max) {
  if (!rows) return 0;
  size_t out = 0;
  while (out < max) {
    if (sent >= len) {  // make the next line
      size_t total = quarters ? qCount : n;
      if (row < 0) {
        len = formatLine(nullptr, human, text, sizeof(text));
      } else {
        Row r;
        bool have = false;
        while (row < (long)total) {
          if (quarters ? qRead(row, r) : (r = at(row), true)) {
            if (r.time > since) {
              have = true;
              break;
            }
          }
          row++;
        }
        if (!have) break;
        len = formatLine(&r, human, text, sizeof(text));
      }
      row++;
      sent = 0;
    }
    size_t take = min(len - sent, max - out);
    memcpy(buf + out, text + sent, take);
    out += take;
    sent += take;
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
