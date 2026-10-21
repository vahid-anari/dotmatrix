#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

// Pure formatting helpers for the stopwatch and timer (host-tested).

// Stopwatch: "MM:SS.cc" under an hour, then "H:MM:SS".
inline void formatStopwatch(uint32_t ms, char* buf, size_t n) {
  uint32_t s = ms / 1000;
  if (s < 3600)
    snprintf(buf, n, "%02u:%02u.%02u", (unsigned)(s / 60), (unsigned)(s % 60), (unsigned)(ms % 1000 / 10));
  else
    snprintf(buf, n, "%u:%02u:%02u", (unsigned)(s / 3600), (unsigned)(s / 60 % 60), (unsigned)(s % 60));
}

// Timer: whole seconds rounded up, so "00:01" shows until it really reaches zero.
// "MM:SS" under an hour, then "H:MM:SS".
inline void formatTimer(uint32_t ms, char* buf, size_t n) {
  uint32_t s = (ms + 999) / 1000;
  if (s < 3600)
    snprintf(buf, n, "%02u:%02u", (unsigned)(s / 60), (unsigned)(s % 60));
  else
    snprintf(buf, n, "%u:%02u:%02u", (unsigned)(s / 3600), (unsigned)(s / 60 % 60), (unsigned)(s % 60));
}

// Elapsed-time bookkeeping shared by both: overflow-safe with millis().
struct RunClock {
  bool running = false;
  uint32_t since = 0;     // millis() when last started
  uint32_t banked = 0;    // ms accumulated before the last start

  uint32_t elapsed(uint32_t now) const { return banked + (running ? now - since : 0); }
  void start(uint32_t now) {
    if (running) return;
    since = now;
    running = true;
  }
  void pause(uint32_t now) {
    if (!running) return;
    banked += now - since;
    running = false;
  }
  void reset() { running = false, banked = 0; }
};
