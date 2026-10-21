#include "Settings.h"

#include "JsonUtil.h"

// "23:05" → 1385; returns -1 if malformed.
static int parseHHMM(const char* s) {
  if (!s) return -1;
  int h, m;
  if (sscanf(s, "%d:%d", &h, &m) != 2 || h < 0 || h > 23 || m < 0 || m > 59) return -1;
  return h * 60 + m;
}

static void formatHHMM(uint16_t minutes, char* buf, size_t n) {
  snprintf(buf, n, "%02u:%02u", minutes / 60, minutes % 60);
}

static bool validHostname(const char* h) {
  size_t n = strlen(h);
  if (n == 0 || n > 31) return false;
  for (size_t i = 0; i < n; i++) {
    char c = h[i];
    if (!(isalnum((unsigned char)c) || c == '-')) return false;
  }
  return h[0] != '-' && h[n - 1] != '-';
}

bool settingsUpdate(Settings& s, JsonObjectConst o, const char*& err) {
  Settings n = s;  // apply to a copy, commit only if everything is valid

  if (jsonIsNumber(o["brightness"])) {
    int b = jsonNum(o["brightness"], 0);
    if (b < 0 || b > 15) return err = "brightness must be 0-15", false;
    n.brightness = b;
  }
  if (o["mode"].is<const char*>()) strlcpy(n.mode, o["mode"], sizeof(n.mode));
  if (o["hostname"].is<const char*>()) {
    const char* h = o["hostname"];
    if (!validHostname(h)) return err = "hostname: letters, digits and '-' only", false;
    strlcpy(n.hostname, h, sizeof(n.hostname));
  }
  if (o["timezone"].is<const char*>()) {
    const char* tz = o["timezone"];
    if (strlen(tz) == 0 || strlen(tz) >= sizeof(n.timezone)) return err = "bad timezone", false;
    strlcpy(n.timezone, tz, sizeof(n.timezone));
  }

  JsonObjectConst c = o["clock"];
  if (!c.isNull()) {
    if (c["format_24h"].is<bool>()) n.clock.format24h = c["format_24h"];
    if (c["seconds"].is<bool>()) n.clock.seconds = c["seconds"];
    if (jsonIsNumber(c["date_every"])) {
      int d = jsonNum(c["date_every"], 0);
      if (d < 0 || d > 3600) return err = "date_every must be 0-3600", false;
      n.clock.dateEvery = d;
    }
    if (jsonIsNumber(c["weather_every"])) {
      int d = jsonNum(c["weather_every"], 0);
      if (d < 0 || d > 3600) return err = "weather_every must be 0-3600", false;
      n.clock.weatherEvery = d;
    }
    if (c["date_format"].is<const char*>()) {
      const char* f = c["date_format"];
      if (strlen(f) >= sizeof(n.clock.dateFormat)) return err = "date_format too long", false;
      strlcpy(n.clock.dateFormat, f, sizeof(n.clock.dateFormat));
    }
  }

  JsonObjectConst w = o["weather"];
  if (!w.isNull()) {
    if (w["place"].is<const char*>()) {
      const char* p = w["place"];
      if (strlen(p) >= sizeof(n.weather.place)) return err = "weather.place too long", false;
      strlcpy(n.weather.place, p, sizeof(n.weather.place));
    }
    if (jsonIsNumber(w["lat"])) {
      float v = w["lat"].as<float>();
      if (v < -90 || v > 90) return err = "weather.lat must be -90..90", false;
      n.weather.lat = lroundf(v * 10000);
    }
    if (jsonIsNumber(w["lon"])) {
      float v = w["lon"].as<float>();
      if (v < -180 || v > 180) return err = "weather.lon must be -180..180", false;
      n.weather.lon = lroundf(v * 10000);
    }
    if (w["units"].is<const char*>()) {
      const char* u = w["units"];
      if (strcmp(u, "c") && strcmp(u, "f")) return err = "weather.units must be c or f", false;
      n.weather.fahrenheit = strcmp(u, "f") == 0;
    }
  }

  JsonObjectConst nt = o["night"];
  if (!nt.isNull()) {
    if (nt["enabled"].is<bool>()) n.night.enabled = nt["enabled"];
    if (nt["from"].is<const char*>()) {
      int m = parseHHMM(nt["from"]);
      if (m < 0) return err = "night.from must be HH:MM", false;
      n.night.from = m;
    }
    if (nt["to"].is<const char*>()) {
      int m = parseHHMM(nt["to"]);
      if (m < 0) return err = "night.to must be HH:MM", false;
      n.night.to = m;
    }
    if (jsonIsNumber(nt["brightness"])) {
      int b = jsonNum(nt["brightness"], 0);
      if (b < 0 || b > 15) return err = "night.brightness must be 0-15", false;
      n.night.brightness = b;
    }
  }

  s = n;
  return true;
}

void settingsToJson(const Settings& s, JsonObject o) {
  char buf[8];
  o["brightness"] = s.brightness;
  o["mode"] = s.mode;
  o["hostname"] = s.hostname;
  o["timezone"] = s.timezone;
  JsonObject c = o["clock"].to<JsonObject>();
  c["format_24h"] = s.clock.format24h;
  c["seconds"] = s.clock.seconds;
  c["date_every"] = s.clock.dateEvery;
  c["date_format"] = s.clock.dateFormat;
  c["weather_every"] = s.clock.weatherEvery;
  JsonObject w = o["weather"].to<JsonObject>();
  w["place"] = s.weather.place;
  w["lat"] = s.weather.lat / 10000.0;
  w["lon"] = s.weather.lon / 10000.0;
  w["units"] = s.weather.fahrenheit ? "f" : "c";
  JsonObject n = o["night"].to<JsonObject>();
  n["enabled"] = s.night.enabled;
  formatHHMM(s.night.from, buf, sizeof(buf));
  n["from"] = buf;  // ArduinoJson copies char* strings
  formatHHMM(s.night.to, buf, sizeof(buf));
  n["to"] = buf;
  n["brightness"] = s.night.brightness;
}
