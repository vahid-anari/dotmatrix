#pragma once
#include <Arduino.h>

class App;

// A mode owns the display while it is active (text playlist, clock, ...).
// To add one: subclass this and register it in App.cpp.
class Mode {
 public:
  virtual ~Mode() = default;
  virtual const char* id() const = 0;
  virtual void begin(App& app) = 0;
  virtual void loop(App& app, uint32_t now) = 0;
  virtual void end(App& app) {}
};
