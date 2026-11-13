#include "EventLog.h"

#include <LittleFS.h>
#include <esp_system.h>

#include "config.h"

namespace EventLog {
namespace {

struct __attribute__((packed)) Event {
  uint32_t time;     // Unix time (UTC)
  uint8_t kind;
  uint8_t reason;    // Restart, or the Wi-Fi's own disconnect reason code
  uint16_t seconds;  // how long the Wi-Fi was gone (capped)
  int8_t rssi;       // the signal just before it was lost, dBm (0 = not known)
};

constexpr const char* PATH = "/events2.bin";  // 0.8.2 kept 8-byte events in /events.bin
constexpr size_t MAX = 100;
constexpr uint32_t NOTE_MAGIC = 0x52535431;  // "RST1"

Event events[MAX];
size_t count = 0;  // oldest first
Restart started = OTHER;

// Survives a software restart (not a power cut): magic in the high bits, the reason below.
RTC_NOINIT_ATTR uint32_t restartNote;

void save() {
  File f = LittleFS.open(PATH, "w");
  if (!f) return;
  f.write((const uint8_t*)events, count * sizeof(Event));
  f.close();
}

}  // namespace

void begin() {
  LittleFS.remove("/events.bin");
  File f = LittleFS.open(PATH, "r");
  if (f) {
    count = min<size_t>(f.size() / sizeof(Event), MAX);
    f.read((uint8_t*)events, count * sizeof(Event));
    f.close();
  }
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: started = POWER_ON; break;
    case ESP_RST_SW:
      started = (restartNote >> 8) == (NOTE_MAGIC >> 8) && (restartNote & 0xFF) ? (Restart)(restartNote & 0xFF) : SOFTWARE;
      break;
    case ESP_RST_PANIC: started = CRASH; break;
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT: started = WATCHDOG; break;
    case ESP_RST_BROWNOUT: started = BROWNOUT; break;
    default: started = OTHER;
  }
  restartNote = 0;
}

void noteRestart(Restart why) { restartNote = (NOTE_MAGIC & ~0xFFu) | why; }

Restart startReason() { return started; }

void add(uint32_t time, Kind kind, uint8_t reason, uint32_t seconds, int8_t rssi) {
  if (count == MAX) {
    memmove(events, events + 1, (MAX - 1) * sizeof(Event));
    count--;
  }
  events[count++] = {time, kind, reason, (uint16_t)min<uint32_t>(seconds, 0xFFFF), rssi};
  save();
}

String csv(uint32_t since) {
  String s = "t,kind,reason,seconds,rssi\n";
  s.reserve(24 + count * 28);
  char line[48];
  for (size_t i = 0; i < count; i++) {
    const Event& e = events[i];
    if (e.time <= since) continue;
    snprintf(line, sizeof(line), "%lu,%s,%u,%u,%d\n", (unsigned long)e.time, e.kind == WIFI_LOST ? "wifi" : "restart",
             e.reason, e.seconds, e.rssi);
    s += line;
  }
  return s;
}

}  // namespace EventLog
