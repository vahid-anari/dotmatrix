#include "App.h"

#include <WiFi.h>
#include <esp_system.h>
#include <esp_task_wdt.h>

#include "animations/Registry.h"
#include "display/Effects.h"
#include "net/WebServer.h"
#include "storage/Storage.h"

App app;

static const uint32_t PREVIEW_TIMEOUT_MS = 10UL * 60 * 1000;

static const char* resetReasonName(esp_reset_reason_t r) {
  switch (r) {
    case ESP_RST_POWERON: return "power_on";
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "crash";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_BROWNOUT: return "brownout";
    default: return "other";
  }
}

// ------------------------------------------------------------------ Off mode

void OffMode::begin(App& app) { app.display.setPower(false); }
void OffMode::end(App& app) { app.display.setPower(true); }

// --------------------------------------------------------------------- Setup

void App::begin() {
  Serial.begin(115200);
  _resetReason = resetReasonName(esp_reset_reason());
  LOG("dotmatrix %s starting (last reset: %s)", FW_VERSION, _resetReason);

  _led.begin();
  display.begin();

  Storage::begin();
  Storage::loadSettings(settings);
  Storage::loadPlaylist(textMode.items, textMode.playlistName, sizeof(textMode.playlistName));
  display.setBrightness(settings.brightness);

  network.onOnline(&App::onOnline);
  network.begin(settings);
  WebServer::begin();

  Mode* m = findMode(settings.mode);
  setMode(m ? m : &textMode, false);

  // Watchdog: if loop() stalls for 10 s, reboot; state is restored from flash.
  // Armed last, because formatting LittleFS on first boot takes a few seconds.
  esp_task_wdt_config_t wdt = {WATCHDOG_TIMEOUT_MS, 0, true};
  if (esp_task_wdt_reconfigure(&wdt) != ESP_OK) esp_task_wdt_init(&wdt);
  esp_task_wdt_add(nullptr);
}

void App::onOnline() {
  // Show where to find the device, once per connection.
  char msg[64];
  snprintf(msg, sizeof(msg), "%s.local  %s", app.settings.hostname, WiFi.localIP().toString().c_str());
  app.showNotice(msg, true);
  app._stateChanged = true;
}

// ---------------------------------------------------------------------- Loop

void App::loop() {
  esp_task_wdt_reset();

  network.loop();
  handleEvents();
  // Read the clock *after* handling messages: handlers store fresh millis()
  // values, and `now - thatValue` must never go negative (it would wrap).
  uint32_t now = millis();

  if (WebServer::otaInProgress()) {
    // Keep the display quiet while flashing.
  } else if (_noticeActive) {
    updateNotice();
  } else if (needsSetupNotice()) {
    char msg[96];
    snprintf(msg, sizeof(msg), "Setup: join Wi-Fi %s  password %s  then open 192.168.4.1",
             network.apName(), SETUP_AP_PASSWORD);
    showNotice(msg);
  } else if (_mode) {
    _mode->loop(*this, now);
  }

  if (textMode.previewing() && now - _previewStarted >= PREVIEW_TIMEOUT_MS) endPreview();

  checkBrightness(now);
  saveIfDue(now);
  updateLed();

  if (_stateChanged || now - _lastState >= STATE_BROADCAST_MS) {
    _stateChanged = false;
    _lastState = now;
    broadcastState();
  }
  if (now - _lastCleanup >= 1000) {
    _lastCleanup = now;
    WebServer::cleanup();
  }

  if (WebServer::rebootRequested() && !_rebootAt) _rebootAt = now + 800;
  if (_rebootAt && (int32_t)(now - _rebootAt) >= 0) {
    if (_settingsDirty) Storage::saveSettings(settings);
    if (_playlistDirty) Storage::savePlaylist(textMode.items, textMode.playlistName);
    LOG("rebooting");
    delay(100);
    ESP.restart();
  }
}

// --------------------------------------------------------------------- Modes

Mode* App::findMode(const char* id) {
  Mode* modes[] = {&textMode, &clockMode, &offMode};
  for (Mode* m : modes)
    if (strcmp(m->id(), id) == 0) return m;
  return nullptr;
}

void App::setMode(Mode* m, bool persist) {
  if (_mode == m) return;
  if (_mode) _mode->end(*this);
  _mode = m;
  LOG("mode: %s", m->id());
  _mode->begin(*this);
  if (persist && strcmp(settings.mode, m->id()) != 0) {
    strlcpy(settings.mode, m->id(), sizeof(settings.mode));
    markDirty(true, false);
  }
  _stateChanged = true;
}

void App::showNotice(const char* text, bool fast) {
  _notice = Item();
  strlcpy(_notice.text, text, sizeof(_notice.text));
  _notice.effectIn = _notice.effectOut = effectIndex("scroll_left");
  _notice.speedIn = _notice.speedOut = fast ? 30 : 40;
  _notice.pause = 0;
  display.setPower(true);
  display.setBrightness(brightnessFor(-1));
  display.playText(_notice);
  _noticeActive = true;
}

// Only a device that has never been set up interrupts its mode with setup
// instructions. One with a saved network that is down (e.g. the router is still
// booting after a power cut) keeps showing its playlist while it retries.
bool App::needsSetupNotice() const {
  return network.setupActive() && !network.hasCredentials() && WebServer::clientCount() == 0;
}

void App::updateNotice() {
  if (!display.animate()) return;
  _noticeActive = false;
  if (needsSetupNotice()) return;  // the next setup message follows right away
  // Hand the display back to the current mode from a clean start
  // (this also switches the panel off again in off mode).
  if (_mode) {
    _mode->end(*this);
    _mode->begin(*this);
  }
}

// ---------------------------------------------------------------- Brightness

bool App::timeValid() const { return time(nullptr) > 1700000000; }  // after Nov 2023

bool App::nightActive() const {
  if (!settings.night.enabled || !timeValid()) return false;
  time_t t = time(nullptr);
  struct tm lt;
  localtime_r(&t, &lt);
  uint16_t m = lt.tm_hour * 60 + lt.tm_min;
  uint16_t from = settings.night.from, to = settings.night.to;
  return from <= to ? (m >= from && m < to) : (m >= from || m < to);  // may wrap midnight
}

uint8_t App::brightnessFor(int8_t itemBrightness) const {
  uint8_t b = itemBrightness >= 0 ? itemBrightness : settings.brightness;
  if (nightActive()) b = min<uint8_t>(b, settings.night.brightness);
  return b;
}

void App::checkBrightness(uint32_t now) {
  if (now - _lastBrightnessCheck < 15000 && _appliedBase != 255) return;
  _lastBrightnessCheck = now;
  uint8_t base = brightnessFor(-1);
  if (base != _appliedBase) {
    _appliedBase = base;
    display.setBrightness(base);
    _stateChanged = true;
  }
}

// -------------------------------------------------------------------- Saving

void App::markDirty(bool s, bool p) {
  if (!_settingsDirty && !_playlistDirty) _dirtySince = millis();
  _settingsDirty |= s;
  _playlistDirty |= p;
}

void App::saveIfDue(uint32_t now) {
  if (!(_settingsDirty || _playlistDirty) || now - _dirtySince < SAVE_DEBOUNCE_MS) return;
  if (_settingsDirty) Storage::saveSettings(settings);
  if (_playlistDirty) Storage::savePlaylist(textMode.items, textMode.playlistName);
  _settingsDirty = _playlistDirty = false;
}

void App::updateLed() {
  if (network.setupActive())
    _led.blink(150, 150);
  else if (!network.online())
    _led.blink(80, 1500);
  else if (WebServer::clientCount() > 0)
    _led.on();
  else
    _led.off();
}

// ------------------------------------------------------------------ Protocol

void App::handleEvents() {
  WebServer::Event ev;
  // A few per loop, so a burst of messages can't starve the display.
  for (int i = 0; i < 4 && WebServer::poll(ev); i++) {
    switch (ev.kind) {
      case WebServer::EventKind::Connected:
        LOG("ws: client %u connected", (unsigned)ev.client);
        sendHello(ev.client);
        _stateChanged = true;
        break;
      case WebServer::EventKind::Disconnected:
        LOG("ws: client %u disconnected", (unsigned)ev.client);
        if (textMode.previewing() && ev.client == _previewClient) endPreview();
        break;
      case WebServer::EventKind::Message:
        handleMessage(ev.client, ev.data, ev.len);
        free(ev.data);
        break;
    }
  }
}

void App::ack(uint32_t client, int id, bool ok, const char* error) {
  JsonDocument doc;
  doc["evt"] = "ack";
  doc["id"] = id;
  doc["ok"] = ok;
  if (error) doc["error"] = error;
  WebServer::send(client, doc);
}

void App::sendHello(uint32_t client) {
  JsonDocument doc;
  doc["evt"] = "hello";
  doc["proto"] = PROTO_VERSION;
  doc["fw"] = FW_VERSION;
  doc["name"] = settings.hostname;
  doc["max_items"] = MAX_ITEMS;
  doc["max_text"] = MAX_TEXT;
  JsonArray fx = doc["effects"].to<JsonArray>();
  for (uint8_t i = 0; i < effectCount(); i++) fx.add(effectAt(i).id);
  JsonArray an = doc["animations"].to<JsonArray>();
  for (uint8_t i = 0; i < animationCount(); i++) an.add(animationId(i));
  JsonArray md = doc["modes"].to<JsonArray>();
  md.add("text");
  md.add("clock");
  md.add("off");
  WebServer::send(client, doc);
  sendSettings(client);
}

void App::fillState(JsonDocument& doc) {
  doc["evt"] = "state";
  doc["mode"] = _mode ? _mode->id() : "";
  doc["playlist"] = textMode.playlistName;
  doc["items"] = textMode.items.size();
  doc["index"] = textMode.index();
  doc["previewing"] = textMode.previewing();
  char tbuf[24] = "";
  if (timeValid()) {
    time_t t = time(nullptr);
    struct tm lt;
    localtime_r(&t, &lt);
    strftime(tbuf, sizeof(tbuf), "%Y-%m-%d %H:%M:%S", &lt);
  }
  if (tbuf[0])
    doc["time"] = tbuf;
  else
    doc["time"] = nullptr;
  doc["brightness"] = display.brightness();
  doc["night"] = nightActive();
  doc["wifi"] = network.online() ? "online" : (network.setupActive() ? "setup" : "connecting");
  doc["ip"] = network.ip();
  doc["rssi"] = network.rssi();
  doc["uptime"] = millis() / 1000;
  doc["free_heap"] = ESP.getFreeHeap();
  doc["min_free_heap"] = ESP.getMinFreeHeap();
  doc["last_reset"] = _resetReason;
}

void App::broadcastState() {
  JsonDocument doc;
  fillState(doc);
  WebServer::broadcast(doc);

  // Small status for the setup page.
  JsonDocument s;
  s["name"] = settings.hostname;
  s["fw"] = FW_VERSION;
  s["wifi"] = doc["wifi"];
  s["ip"] = doc["ip"];
  String out;
  serializeJson(s, out);
  WebServer::setStatus(out);
}

void App::sendSettings(uint32_t client) {
  JsonDocument doc;
  doc["evt"] = "settings";
  settingsToJson(settings, doc["settings"].to<JsonObject>());
  if (client)
    WebServer::send(client, doc);
  else
    WebServer::broadcast(doc);
}

void App::endPreview() {
  textMode.stopPreview(*this);
  _previewClient = 0;
  if (_modeBeforePreview) {
    setMode(_modeBeforePreview, false);
    _modeBeforePreview = nullptr;
  }
  _stateChanged = true;
}

void App::handleMessage(uint32_t client, const char* data, size_t len) {
  JsonDocument doc;
  DeserializationError e = deserializeJson(doc, data, len);
  if (e) {
    ack(client, -1, false, "invalid JSON");
    return;
  }
  int id = doc["id"] | -1;
  const char* cmd = doc["cmd"] | "";
  const char* err = nullptr;

  if (strcmp(cmd, "get_state") == 0) {
    ack(client, id, true);
    JsonDocument st;
    fillState(st);
    WebServer::send(client, st);

  } else if (strcmp(cmd, "set_mode") == 0) {
    Mode* m = findMode(doc["mode"] | "");
    if (!m) return ack(client, id, false, "unknown mode");
    if (textMode.previewing()) endPreview();
    setMode(m, true);
    ack(client, id, true);

  } else if (strcmp(cmd, "set_playlist") == 0) {
    if (!doc["items"].is<JsonArrayConst>()) return ack(client, id, false, "missing items");
    JsonArrayConst arr = doc["items"];
    if (arr.size() > MAX_ITEMS) return ack(client, id, false, "too many items");
    std::vector<Item> items;
    items.reserve(arr.size());
    int i = 0;
    for (JsonObjectConst o : arr) {
      Item it;
      if (!itemFromJson(o, it, err)) {
        static char msg[48];
        snprintf(msg, sizeof(msg), "item %d: %s", i, err);
        return ack(client, id, false, msg);
      }
      items.push_back(it);
      i++;
    }
    textMode.items = std::move(items);
    strlcpy(textMode.playlistName, doc["name"] | "", sizeof(textMode.playlistName));
    markDirty(false, true);
    if (_mode == &textMode && !textMode.previewing()) textMode.restart(*this);
    _stateChanged = true;
    ack(client, id, true);

  } else if (strcmp(cmd, "get_playlist") == 0) {
    JsonDocument out;
    out["evt"] = "playlist";
    out["id"] = id;
    out["name"] = textMode.playlistName;
    JsonArray arr = out["items"].to<JsonArray>();
    for (const Item& it : textMode.items) itemToJson(it, arr.add<JsonObject>());
    WebServer::send(client, out);

  } else if (strcmp(cmd, "preview") == 0) {
    Item it;
    if (!itemFromJson(doc["item"], it, err)) return ack(client, id, false, err);
    if (_mode != &textMode) {
      if (!_modeBeforePreview) _modeBeforePreview = _mode;
      setMode(&textMode, false);
    }
    textMode.startPreview(*this, it);
    _previewClient = client;
    _previewStarted = millis();
    _stateChanged = true;
    ack(client, id, true);

  } else if (strcmp(cmd, "preview_end") == 0) {
    endPreview();
    ack(client, id, true);

  } else if (strcmp(cmd, "get_settings") == 0) {
    ack(client, id, true);
    sendSettings(client);

  } else if (strcmp(cmd, "set_settings") == 0) {
    Settings before = settings;
    JsonObjectConst s = doc["settings"];
    if (s.isNull()) return ack(client, id, false, "missing settings");
    if (!settingsUpdate(settings, s, err)) return ack(client, id, false, err);
    strlcpy(settings.mode, before.mode, sizeof(settings.mode));  // use set_mode for that
    if (strcmp(before.timezone, settings.timezone) != 0) network.applyTimezone(settings.timezone);
    if (strcmp(before.hostname, settings.hostname) != 0) network.applyHostname(settings.hostname);
    _appliedBase = 255;  // re-apply brightness now
    markDirty(true, false);
    ack(client, id, true);
    sendSettings(0);
    _stateChanged = true;

  } else if (strcmp(cmd, "set_wifi") == 0) {
    const char* ssid = doc["ssid"] | "";
    const char* pass = doc["password"] | "";
    if (!*ssid || strlen(ssid) > 32 || strlen(pass) > 64) return ack(client, id, false, "invalid ssid or password");
    Storage::saveWifi(ssid, pass);
    ack(client, id, true);
    _rebootAt = millis() + 800;

  } else if (strcmp(cmd, "reboot") == 0) {
    ack(client, id, true);
    _rebootAt = millis() + 500;

  } else if (strcmp(cmd, "stopwatch") == 0 || strcmp(cmd, "timer") == 0) {
    ack(client, id, false, "not available in this firmware yet");

  } else {
    ack(client, id, false, "unknown command");
  }
}
