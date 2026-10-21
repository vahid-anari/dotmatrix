#pragma once
#include <ArduinoJson.h>

#include "display/Display.h"
#include "model/Settings.h"
#include "modes/ClockMode.h"
#include "modes/Mode.h"
#include "modes/TextMode.h"
#include "net/Network.h"
#include "util/Led.h"

class OffMode : public Mode {
 public:
  const char* id() const override { return "off"; }
  void begin(App& app) override;
  void loop(App&, uint32_t) override {}
  void end(App& app) override;
};

class App {
 public:
  Display display;
  Settings settings;
  Network network;
  TextMode textMode;
  ClockMode clockMode;
  OffMode offMode;

  void begin();
  void loop();

  // Brightness for an item (-1 = no override), with night dimming applied.
  uint8_t brightnessFor(int8_t itemBrightness) const;
  bool timeValid() const;
  bool nightActive() const;

 private:
  Led _led{PIN_STATUS_LED, STATUS_LED_INVERTED};
  Mode* _mode = nullptr;
  Mode* _modeBeforePreview = nullptr;
  uint32_t _previewClient = 0;
  uint32_t _previewStarted = 0;

  // One-off scrolling messages (setup instructions, IP address).
  bool _noticeActive = false;
  Item _notice;

  bool _settingsDirty = false;
  bool _playlistDirty = false;
  uint32_t _dirtySince = 0;
  uint32_t _lastState = 0;
  uint32_t _lastCleanup = 0;
  uint32_t _lastBrightnessCheck = 0;
  uint8_t _appliedBase = 255;
  uint32_t _rebootAt = 0;
  bool _stateChanged = false;
  const char* _resetReason = "";

  Mode* findMode(const char* id);
  void setMode(Mode* m, bool persist);
  void showNotice(const char* text, bool fast = false);
  void updateNotice();
  bool needsSetupNotice() const;
  void markDirty(bool settings, bool playlist);
  void saveIfDue(uint32_t now);
  void checkBrightness(uint32_t now);
  void updateLed();

  // Protocol
  void handleEvents();
  void handleMessage(uint32_t client, const char* data, size_t len);
  void sendHello(uint32_t client);
  void fillState(JsonDocument& doc);
  void broadcastState();
  void sendSettings(uint32_t client);
  void ack(uint32_t client, int id, bool ok, const char* error = nullptr);
  void endPreview();

  static void onOnline();
};

extern App app;
