#include "Storage.h"

#include <LittleFS.h>
#include <Preferences.h>

static const char* SETTINGS_PATH = "/settings.json";
static const char* PLAYLIST_PATH = "/playlist.json";

// Write to path.tmp, then rename over path. The rename replaces the old file in
// one step, so after a power cut there is always a complete old or new file.
static bool writeAtomic(const char* path, const JsonDocument& doc) {
  String tmp = String(path) + ".tmp";
  File f = LittleFS.open(tmp, "w");
  if (!f) return false;
  size_t expected = measureJson(doc);
  size_t n = serializeJson(doc, f);
  f.close();
  if (n != expected) {  // e.g. filesystem full: never promote a partial file
    LittleFS.remove(tmp);
    return false;
  }
  if (LittleFS.rename(tmp, path)) return true;
  // Fallback if this filesystem refuses to rename over an existing file.
  LittleFS.remove(path);
  return LittleFS.rename(tmp, path);
}

// After a power cut: keep a finished .tmp if the main file is missing.
static void recover(const char* path) {
  String tmp = String(path) + ".tmp";
  if (!LittleFS.exists(tmp)) return;
  if (LittleFS.exists(path)) {
    LittleFS.remove(tmp);  // main file is intact; the .tmp may be partial
  } else {
    LittleFS.rename(tmp, path);
    LOG("storage: recovered %s", path);
  }
}

static bool readJson(const char* path, JsonDocument& doc) {
  File f = LittleFS.open(path, "r");
  if (!f) return false;
  DeserializationError e = deserializeJson(doc, f);
  f.close();
  if (e) LOG("storage: %s is corrupt (%s), using defaults", path, e.c_str());
  return !e;
}

bool Storage::begin() {
  if (!LittleFS.begin(true)) {  // format on first use
    LOG("storage: LittleFS mount failed");
    return false;
  }
  recover(SETTINGS_PATH);
  recover(PLAYLIST_PATH);
  return true;
}

bool Storage::loadSettings(Settings& s) {
  JsonDocument doc;
  if (!readJson(SETTINGS_PATH, doc)) return false;
  const char* err = nullptr;
  Settings loaded;
  if (!settingsUpdate(loaded, doc.as<JsonObjectConst>(), err)) return false;
  s = loaded;
  return true;
}

bool Storage::saveSettings(const Settings& s) {
  JsonDocument doc;
  settingsToJson(s, doc.to<JsonObject>());
  bool ok = writeAtomic(SETTINGS_PATH, doc);
  LOG("storage: settings saved (%s)", ok ? "ok" : "FAILED");
  return ok;
}

bool Storage::loadPlaylist(std::vector<Item>& items, char* name, size_t nameLen) {
  JsonDocument doc;
  if (!readJson(PLAYLIST_PATH, doc)) return false;
  strlcpy(name, doc["name"] | "", nameLen);
  items.clear();
  for (JsonObjectConst o : doc["items"].as<JsonArrayConst>()) {
    if (items.size() >= MAX_ITEMS) break;
    Item it;
    const char* err = nullptr;
    if (itemFromJson(o, it, err)) items.push_back(it);
  }
  LOG("storage: playlist '%s' loaded, %u items", name, (unsigned)items.size());
  return true;
}

bool Storage::savePlaylist(const std::vector<Item>& items, const char* name) {
  JsonDocument doc;
  doc["name"] = name;
  JsonArray arr = doc["items"].to<JsonArray>();
  for (const Item& it : items) itemToJson(it, arr.add<JsonObject>());
  bool ok = writeAtomic(PLAYLIST_PATH, doc);
  LOG("storage: playlist saved, %u items (%s)", (unsigned)items.size(), ok ? "ok" : "FAILED");
  return ok;
}

bool Storage::loadWifi(String& ssid, String& password) {
  Preferences p;
  p.begin("wifi", true);
  ssid = p.getString("ssid", "");
  password = p.getString("pass", "");
  p.end();
  return ssid.length() > 0;
}

void Storage::saveWifi(const char* ssid, const char* password) {
  Preferences p;
  p.begin("wifi", false);
  p.putString("ssid", ssid);
  p.putString("pass", password);
  p.end();
}

void Storage::clearWifi() {
  Preferences p;
  p.begin("wifi", false);
  p.clear();
  p.end();
}
