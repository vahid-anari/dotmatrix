#pragma once
#include <Arduino.h>

// What happened to the display, for the app's History: each time the Wi-Fi
// was lost (and for how long, and the reason the Wi-Fi gave), and each restart
// (and why). The last 100, kept in flash. Served at /api/events.
namespace EventLog {

enum Kind : uint8_t { WIFI_LOST = 1, RESTART = 2 };

// Why the display restarted. Ours (update, app, Wi-Fi settings) are noted in
// memory that survives the restart; the rest come from the chip.
enum Restart : uint8_t {
  POWER_ON = 1, UPDATE = 2, FROM_APP = 3, NEW_WIFI = 4, SOFTWARE = 5, WATCHDOG = 6, CRASH = 7, BROWNOUT = 8, OTHER = 9
};

void begin();                       // load the saved events; work out why we started
void noteRestart(Restart why);      // call just before restarting
Restart startReason();
void add(uint32_t time, Kind kind, uint8_t reason, uint32_t seconds, int8_t rssi = 0);
String csv(uint32_t since);         // "t,kind,reason,seconds,rssi" rows after `since`

}  // namespace EventLog
