#pragma once
#include <Arduino.h>

// The optional sensors on the I2C bus (SDA/SCL in config.h): a BH1750 light
// sensor (GY-302) and a BME280 for temperature, humidity and air pressure
// (a BMP280 gives the same without humidity). Each one is found at start and
// looked for again every half minute while it is missing; the readings are
// kept here and reported in the state message.
class Sensors {
 public:
  void begin();
  void loop(uint32_t now);

  bool hasLight() const { return _lightAddr != 0; }
  bool hasClimate() const { return _bmeAddr != 0; }
  bool hasHumidity() const { return _bmeAddr != 0 && _isBme; }
  // Readings are valid once the sensor has answered at least once.
  bool lightValid() const { return hasLight() && _luxValid; }
  bool climateValid() const { return hasClimate() && _climateValid; }
  float lux() const { return _lux; }
  float tempC() const { return _tempC; }
  float humidity() const { return _hum; }
  float pressureHPa() const { return _hPa; }

 private:
  uint8_t _lightAddr = 0, _bmeAddr = 0;
  bool _isBme = false;
  bool _luxValid = false, _climateValid = false;
  float _lux = 0, _tempC = 0, _hum = 0, _hPa = 0;
  uint32_t _lastLight = 0, _lastClimate = 0, _lastProbe = 0, _lastLog = 0;
  uint8_t _lightFails = 0, _bmeFails = 0;
  uint8_t _mt = 254;        // BH1750 measuring time (31..254): longer = more sensitive
  bool _skipLight = false;  // the first value after a change of _mt is mixed; drop it

  // BME280 calibration
  uint16_t _T1, _P1;
  int16_t _T2, _T3, _P2, _P3, _P4, _P5, _P6, _P7, _P8, _P9, _H2, _H4, _H5;
  uint8_t _H1, _H3;
  int8_t _H6;

  void probe();
  bool startLight(uint8_t addr);
  bool startBme(uint8_t addr);
  bool readLight();
  bool setMeasuringTime(uint8_t mt);
  bool readClimate();
};
