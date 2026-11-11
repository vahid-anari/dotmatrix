#include "Sensors.h"

#include <Wire.h>

#include "config.h"

namespace {

constexpr uint32_t LIGHT_EVERY_MS = 1000;
constexpr uint32_t CLIMATE_EVERY_MS = 2000;
constexpr uint32_t PROBE_EVERY_MS = 30000;
constexpr uint32_t LOG_EVERY_MS = 10000;
constexpr uint8_t MAX_FAILS = 5;  // reads in a row before a sensor counts as gone

bool present(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

bool writeReg(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool readRegs(uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t n) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, n) != n) return false;
  for (uint8_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

uint16_t le16(const uint8_t* b) { return b[0] | (b[1] << 8); }

}  // namespace

void Sensors::begin() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 100000);
  Wire.setTimeOut(20);  // a stuck bus must not stall the loop
  probe();
  if (!hasLight() && !hasClimate()) LOG("sensors: none found (SDA %d, SCL %d)", PIN_I2C_SDA, PIN_I2C_SCL);
}

void Sensors::probe() {
  _lastProbe = millis();
  if (!hasLight()) {
    for (uint8_t a : {0x23, 0x5C})
      if (present(a) && startLight(a)) break;
  }
  if (!hasClimate()) {
    for (uint8_t a : {0x76, 0x77})
      if (present(a) && startBme(a)) break;
  }
}

// ------------------------------------------------------------------- BH1750

bool Sensors::startLight(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0x01);  // power on
  if (Wire.endTransmission() != 0) return false;
  Wire.beginTransmission(addr);
  Wire.write(0x10);  // continuous, 1 lx resolution, a new value every 120 ms
  if (Wire.endTransmission() != 0) return false;
  _lightAddr = addr;
  _lightFails = 0;
  _luxValid = false;
  _lastLight = millis();  // first value after one period
  LOG("sensors: BH1750 light sensor at 0x%02X", addr);
  return true;
}

bool Sensors::readLight() {
  if (Wire.requestFrom(_lightAddr, (uint8_t)2) != 2) return false;
  uint16_t raw = (Wire.read() << 8) | Wire.read();
  _lux = raw / 1.2f;
  return true;
}

// ------------------------------------------------------------------- BME280

bool Sensors::startBme(uint8_t addr) {
  uint8_t id;
  if (!readRegs(addr, 0xD0, &id, 1)) return false;
  if (id != 0x60 && id != 0x58) return false;  // 0x60 BME280, 0x58 BMP280
  _isBme = id == 0x60;

  writeReg(addr, 0xE0, 0xB6);  // soft reset
  for (int i = 0; i < 20; i++) {  // wait for the calibration copy
    delay(2);
    uint8_t st;
    if (readRegs(addr, 0xF3, &st, 1) && !(st & 0x01)) break;
  }

  uint8_t c[26];
  if (!readRegs(addr, 0x88, c, 26)) return false;
  _T1 = le16(c + 0);
  _T2 = (int16_t)le16(c + 2);
  _T3 = (int16_t)le16(c + 4);
  _P1 = le16(c + 6);
  _P2 = (int16_t)le16(c + 8);
  _P3 = (int16_t)le16(c + 10);
  _P4 = (int16_t)le16(c + 12);
  _P5 = (int16_t)le16(c + 14);
  _P6 = (int16_t)le16(c + 16);
  _P7 = (int16_t)le16(c + 18);
  _P8 = (int16_t)le16(c + 20);
  _P9 = (int16_t)le16(c + 22);
  _H1 = c[25];
  if (_isBme) {
    uint8_t h[7];
    if (!readRegs(addr, 0xE1, h, 7)) return false;
    _H2 = (int16_t)le16(h + 0);
    _H3 = h[2];
    _H4 = (int16_t)((int8_t)h[3] * 16 | (h[4] & 0x0F));
    _H5 = (int16_t)((int8_t)h[5] * 16 | (h[4] >> 4));
    _H6 = (int8_t)h[6];
    writeReg(addr, 0xF2, 0x01);  // humidity ×1 (takes effect with the next 0xF4 write)
  }
  writeReg(addr, 0xF5, (0b101 << 5) | (0b010 << 2));  // a reading every second, filter ×4
  if (!writeReg(addr, 0xF4, (0b001 << 5) | (0b001 << 2) | 0b11)) return false;  // T ×1, P ×1, running

  _bmeAddr = addr;
  _bmeFails = 0;
  _climateValid = false;
  _lastClimate = millis();
  LOG("sensors: %s at 0x%02X", _isBme ? "BME280" : "BMP280 (no humidity)", addr);
  return true;
}

bool Sensors::readClimate() {
  uint8_t d[8];
  if (!readRegs(_bmeAddr, 0xF7, d, _isBme ? 8 : 6)) return false;
  int32_t adcP = ((uint32_t)d[0] << 12) | ((uint32_t)d[1] << 4) | (d[2] >> 4);
  int32_t adcT = ((uint32_t)d[3] << 12) | ((uint32_t)d[4] << 4) | (d[5] >> 4);
  if (adcT == 0x80000) return false;  // no measurement yet

  // Compensation in floating point, from the Bosch BME280 datasheet (section 8.1).
  double v1 = (adcT / 16384.0 - _T1 / 1024.0) * _T2;
  double v2 = (adcT / 131072.0 - _T1 / 8192.0) * (adcT / 131072.0 - _T1 / 8192.0) * _T3;
  double tFine = v1 + v2;
  _tempC = tFine / 5120.0;

  v1 = tFine / 2.0 - 64000.0;
  v2 = v1 * v1 * _P6 / 32768.0;
  v2 = v2 + v1 * _P5 * 2.0;
  v2 = v2 / 4.0 + _P4 * 65536.0;
  v1 = (_P3 * v1 * v1 / 524288.0 + _P2 * v1) / 524288.0;
  v1 = (1.0 + v1 / 32768.0) * _P1;
  if (v1 != 0) {
    double p = 1048576.0 - adcP;
    p = (p - v2 / 4096.0) * 6250.0 / v1;
    v1 = _P9 * p * p / 2147483648.0;
    v2 = p * _P8 / 32768.0;
    p = p + (v1 + v2 + _P7) / 16.0;
    _hPa = p / 100.0;
  }

  if (_isBme) {
    int32_t adcH = ((uint32_t)d[6] << 8) | d[7];
    if (adcH == 0x8000) return false;
    double h = tFine - 76800.0;
    h = (adcH - (_H4 * 64.0 + _H5 / 16384.0 * h)) *
        (_H2 / 65536.0 * (1.0 + _H6 / 67108864.0 * h * (1.0 + _H3 / 67108864.0 * h)));
    h = h * (1.0 - _H1 * h / 524288.0);
    _hum = constrain(h, 0.0, 100.0);
  }
  return true;
}

// --------------------------------------------------------------------- loop

void Sensors::loop(uint32_t now) {
  if (hasLight() && now - _lastLight >= LIGHT_EVERY_MS) {
    _lastLight = now;
    if (readLight()) {
      _luxValid = true;
      _lightFails = 0;
    } else if (++_lightFails >= MAX_FAILS) {
      LOG("sensors: light sensor stopped answering");
      _lightAddr = 0;
      _luxValid = false;
    }
  }
  if (hasClimate() && now - _lastClimate >= CLIMATE_EVERY_MS) {
    _lastClimate = now;
    if (readClimate()) {
      _climateValid = true;
      _bmeFails = 0;
    } else if (++_bmeFails >= MAX_FAILS) {
      LOG("sensors: %s stopped answering", _isBme ? "BME280" : "BMP280");
      _bmeAddr = 0;
      _climateValid = false;
    }
  }
  if ((!hasLight() || !hasClimate()) && now - _lastProbe >= PROBE_EVERY_MS) probe();

  if (now - _lastLog >= LOG_EVERY_MS && (lightValid() || climateValid())) {
    _lastLog = now;
    char l[24] = "", c[64] = "";
    if (lightValid()) snprintf(l, sizeof(l), "%.0f lx", _lux);
    if (climateValid()) {
      if (_isBme)
        snprintf(c, sizeof(c), "%.1f C, %.0f %%, %.1f hPa", _tempC, _hum, _hPa);
      else
        snprintf(c, sizeof(c), "%.1f C, %.1f hPa", _tempC, _hPa);
    }
    LOG("sensors: %s%s%s", l, (l[0] && c[0]) ? ", " : "", c);
  }
}
