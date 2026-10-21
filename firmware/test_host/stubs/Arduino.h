// Minimal Arduino API so model/ and animations/ compile on a PC.
#pragma once
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>

#define PROGMEM
#define pgm_read_byte(p) (*(const uint8_t*)(p))

extern uint32_t g_fakeMillis;
inline uint32_t millis() { return g_fakeMillis; }

inline long random(long hi) { return hi > 0 ? std::rand() % hi : 0; }
inline long random(long lo, long hi) { return hi > lo ? lo + std::rand() % (hi - lo) : lo; }

template <class T>
inline T min(T a, T b) { return a < b ? a : b; }
template <class T>
inline T max(T a, T b) { return a > b ? a : b; }

#define constrain(v, lo, hi) ((v) < (lo) ? (lo) : ((v) > (hi) ? (hi) : (v)))

struct FakeSerial {
  template <class... A>
  void printf(const char* f, A... a) { std::printf(f, a...); }
};
extern FakeSerial Serial;
