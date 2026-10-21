#pragma once
#include <ArduinoJson.h>
#include <math.h>

// ArduinoJson's `v | 5L` returns the default for 8.0, because a float is not a
// long. Phones (Python's json, Flet sliders) often send whole numbers as floats,
// so accept any number and round it.
inline bool jsonIsNumber(JsonVariantConst v) { return v.is<float>(); }  // true for ints too

inline long jsonNum(JsonVariantConst v, long def) {
  return jsonIsNumber(v) ? lround(v.as<double>()) : def;
}
