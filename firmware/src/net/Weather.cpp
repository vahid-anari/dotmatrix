#include "Weather.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>

#include "../config.h"

void Weather::invalidate() {
  portENTER_CRITICAL(&_lock);
  _now.valid = false;
  _generation++;
  portEXIT_CRITICAL(&_lock);
  _tried = false;
}

void Weather::loop(const Settings& s, bool online, uint32_t now) {
  if (_busy || !online || !s.weather.place[0]) return;
  uint32_t wait = _lastOk ? EVERY_MS : RETRY_MS;
  if (_tried && now - _lastTry < wait) return;
  _tried = true;
  _lastTry = now;

  // Plain HTTP: the weather is public, and it saves the TLS handshake's
  // memory and time. Open-Meteo answers on both.
  snprintf(_url, sizeof(_url),
           "http://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
           "&current=temperature_2m,weather_code&temperature_unit=%s",
           s.weather.lat / 10000.0, s.weather.lon / 10000.0, s.weather.fahrenheit ? "fahrenheit" : "celsius");
  _urlGeneration = _generation;
  _busy = true;
  if (xTaskCreate(task, "weather", 6144, this, 1, nullptr) != pdPASS) _busy = false;
}

void Weather::task(void* self) {
  static_cast<Weather*>(self)->fetch();
  vTaskDelete(nullptr);
}

void Weather::fetch() {
  bool ok = false;
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(8000);
  http.setConnectTimeout(5000);
  if (http.begin(client, _url)) {
    int status = http.GET();
    if (status == 200) {
      JsonDocument filter;
      filter["current"]["temperature_2m"] = true;
      filter["current"]["weather_code"] = true;
      JsonDocument doc;
      DeserializationError e = deserializeJson(doc, http.getString(), DeserializationOption::Filter(filter));
      JsonVariantConst cur = doc["current"];
      if (!e && cur["temperature_2m"].is<float>() && cur["weather_code"].is<int>()) {
        Now n;
        n.valid = true;
        n.temp10 = (int16_t)lroundf(cur["temperature_2m"].as<float>() * 10);
        n.code = (uint8_t)cur["weather_code"].as<int>();
        n.at = millis();
        portENTER_CRITICAL(&_lock);
        if (_urlGeneration == _generation) _now = n;  // still the same place and units
        portEXIT_CRITICAL(&_lock);
        ok = true;
      }
    }
    LOG("weather: HTTP %d, %s", status, ok ? "ok" : "no data");
    http.end();
  }
  _lastOk = ok;
  _busy = false;
}

bool Weather::current(Now& out, uint32_t now) const {
  portENTER_CRITICAL(&_lock);
  out = _now;
  portEXIT_CRITICAL(&_lock);
  return out.valid && now - out.at < MAX_AGE_MS;
}

bool Weather::text(char* buf, size_t n, bool fahrenheit, uint32_t now) const {
  Now w;
  if (!current(w, now)) return false;
  int t = w.temp10 >= 0 ? (w.temp10 + 5) / 10 : -((-w.temp10 + 5) / 10);  // whole degrees
  snprintf(buf, n, "%d\xB0%c %s", t, fahrenheit ? 'F' : 'C', describe(w.code));
  return true;
}

// WMO weather interpretation codes, as Open-Meteo uses them.
const char* Weather::describe(uint8_t code) {
  switch (code) {
    case 0: return "Clear";
    case 1: return "Mostly clear";
    case 2: return "Partly cloudy";
    case 3: return "Cloudy";
    case 45: case 48: return "Fog";
    case 51: case 53: case 55: return "Drizzle";
    case 56: case 57: return "Freezing drizzle";
    case 61: case 63: return "Rain";
    case 65: return "Heavy rain";
    case 66: case 67: return "Freezing rain";
    case 71: case 73: return "Snow";
    case 75: return "Heavy snow";
    case 77: return "Snow grains";
    case 80: case 81: return "Showers";
    case 82: return "Heavy showers";
    case 85: case 86: return "Snow showers";
    case 95: return "Thunderstorm";
    case 96: case 99: return "Thunderstorm, hail";
    default: return "";
  }
}
