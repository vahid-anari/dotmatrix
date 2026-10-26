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
    // Before 0.5 the date and the weather each had their own interval. Those
    // keys (from an older app, or settings saved by older firmware) still work:
    // a non-zero interval turns that one on and sets the shared interval.
    for (const char* key : {"date_every", "weather_every"}) {
      if (!jsonIsNumber(c[key])) continue;
      int d = jsonNum(c[key], 0);
      if (d < 0 || d > 3600) return err = "date_every/weather_every must be 0-3600", false;
      bool& on = key[0] == 'd' ? n.clock.showDate : n.clock.showWeather;
      on = d > 0;
      if (d > 0) n.clock.extrasEvery = d;
    }
    if (jsonIsNumber(c["extras_every"])) {
      int d = jsonNum(c["extras_every"], 0);
      if (d < 0 || d > 3600) return err = "extras_every must be 0-3600", false;
      n.clock.extrasEvery = d;
    }
    if (c["show_date"].is<bool>()) n.clock.showDate = c["show_date"];
    if (c["show_weather"].is<bool>()) n.clock.showWeather = c["show_weather"];
    if (c["extras_style"].is<const char*>()) {
      const char* st = c["extras_style"];
      if (strcmp(st, "drop") && strcmp(st, "scroll")) return err = "extras_style must be drop or scroll", false;
      n.clock.extrasDrop = strcmp(st, "drop") == 0;
    }
    if (jsonIsNumber(c["extras_pause"])) {
      int p = jsonNum(c["extras_pause"], 3000);
      if (p < 500 || p > 15000) return err = "extras_pause must be 500-15000 ms", false;
      n.clock.extrasPause = p;
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
  c["date_format"] = s.clock.dateFormat;
  c["extras_every"] = s.clock.extrasEvery;
  c["show_date"] = s.clock.showDate;
  c["show_weather"] = s.clock.showWeather;
  c["extras_style"] = s.clock.extrasDrop ? "drop" : "scroll";
  c["extras_pause"] = s.clock.extrasPause;
  // For apps from before 0.5, which still read the two intervals.
  c["date_every"] = s.clock.showDate ? s.clock.extrasEvery : 0;
  c["weather_every"] = s.clock.showWeather ? s.clock.extrasEvery : 0;
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
