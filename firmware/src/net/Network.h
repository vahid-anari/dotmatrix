#pragma once
#include <Arduino.h>

#include "../model/Settings.h"

// Wi-Fi life cycle:
//   no saved network  → Setup (own access point + captive portal)
//   saved network     → Connecting → Online
//   connect timeout   → Setup, while still retrying the saved network
class Network {
 public:
  enum class State : uint8_t { Setup, Connecting, Online };

  void begin(const Settings& settings);
  void loop();

  State state() const { return _state; }
  bool online() const { return _state == State::Online; }
  bool setupActive() const { return _apActive; }
  // True once a home network has been saved (setup page or app).
  bool hasCredentials() const { return _haveCredentials; }
  const char* apName() const { return _apName; }
  String ip() const;
  int rssi() const;

  // Called once each time the device joins the home network.
  void onOnline(void (*cb)()) { _onOnline = cb; }

  void applyTimezone(const char* tz);
  void applyHostname(const char* hostname);
  // Transmit power (1/4 dBm) and modem sleep, applied now. If the Wi-Fi is lost
  // and doesn't come back within a minute, the previous ones come back and
  // radioReverted() says so once (the app then saves them).
  void applyRadio(uint8_t txQ, bool sleep);
  bool radioReverted(uint8_t& txQ, bool& sleep);

 private:
  State _state = State::Setup;
  bool _apActive = false;
  bool _servicesUp = false;
  char _apName[24] = "";
  char _hostname[32] = DEFAULT_HOSTNAME;
  char _timezone[64] = DEFAULT_TIMEZONE;
  uint32_t _connectStart = 0;
  uint32_t _lastRetry = 0;
  uint32_t _lostAt = 0;       // millis() when the Wi-Fi was lost (0 = not lost)
  uint8_t _lostReason = 0;
  int8_t _lostRssi = 0, _lastRssi = 0;  // dBm
  uint32_t _lastRssiAt = 0;
  bool _haveCredentials = false;
  uint8_t _txQ = WIFI_TX_POWER, _prevTxQ = WIFI_TX_POWER;
  bool _sleep = false, _prevSleep = false;
  uint32_t _radioTrialAt = 0;  // millis() of a change on trial, 0 = none
  bool _bootTrial = false;     // non-default radio at start, not yet proven
  bool _reverted = false;
  void setRadio();
  void checkRadio(uint32_t now, bool connected);
  String _ssid, _pass;
  void (*_onOnline)() = nullptr;

  void startAP();
  void stopAP();
  void startServices();
};
