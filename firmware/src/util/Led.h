#pragma once
#include <Arduino.h>

// Status LED with non-blocking blink (from Vahid's LED library).
class Led {
 public:
  Led(uint8_t pin, bool inverted) : _pin(pin), _inverted(inverted) {}
  void begin() {
    pinMode(_pin, OUTPUT);
    off();
  }
  void on() { write(true); }
  void off() { write(false); }
  void blink(uint32_t onMs, uint32_t offMs) {
    uint32_t now = millis();
    if (now - _last >= (_state ? onMs : offMs)) {  // overflow-safe
      _last = now;
      write(!_state);
    }
  }

 private:
  uint8_t _pin;
  bool _inverted;
  bool _state = false;
  uint32_t _last = 0;
  void write(bool on) {
    _state = on;
    digitalWrite(_pin, (on ^ _inverted) ? HIGH : LOW);
  }
};
