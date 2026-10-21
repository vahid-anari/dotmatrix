#include "Network.h"

#include <ArduinoOTA.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <esp_mac.h>
#include <esp_sntp.h>
#include <esp_task_wdt.h>

#include "../storage/Storage.h"

static DNSServer dns;

void Network::begin(const Settings& settings) {
  strlcpy(_hostname, settings.hostname, sizeof(_hostname));
  strlcpy(_timezone, settings.timezone, sizeof(_timezone));

  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);  // works before Wi-Fi is started
  snprintf(_apName, sizeof(_apName), SETUP_AP_PREFIX "%02X%02X", mac[4], mac[5]);

  WiFi.persistent(false);  // we keep credentials ourselves (NVS "wifi")
  WiFi.setAutoReconnect(true);
  WiFi.setHostname(_hostname);

  _haveCredentials = Storage::loadWifi(_ssid, _pass);
  if (_haveCredentials) {
    WiFi.mode(WIFI_STA);
    WiFi.setTxPower((wifi_power_t)WIFI_TX_POWER);
    WiFi.begin(_ssid.c_str(), _pass.c_str());
    _state = State::Connecting;
    _connectStart = millis();
    LOG("wifi: connecting to '%s'", _ssid.c_str());
  } else {
    LOG("wifi: no saved network");
    startAP();
  }

  // Time zone applies even before the first sync.
  setenv("TZ", _timezone, 1);
  tzset();
}

void Network::startAP() {
  if (_apActive) return;
  if (_haveCredentials) {
    // Stop the station's own retries: while it is connecting, scans fail and
    // its channel hopping disturbs the phone on the setup network. We retry
    // ourselves in loop(), only while nobody is using the setup network.
    WiFi.setAutoReconnect(false);
    WiFi.disconnect(false);
  }
  WiFi.mode(_haveCredentials ? WIFI_AP_STA : WIFI_AP);
  WiFi.setTxPower((wifi_power_t)WIFI_TX_POWER);
  WiFi.softAP(_apName, SETUP_AP_PASSWORD);
  dns.start(53, "*", WiFi.softAPIP());  // captive portal: every name → us
  _apActive = true;
  _state = State::Setup;
  LOG("wifi: setup AP '%s' at %s", _apName, WiFi.softAPIP().toString().c_str());
}

void Network::stopAP() {
  if (!_apActive) return;
  dns.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  _apActive = false;
  LOG("wifi: setup AP stopped");
}

static void startMdns(const char* hostname) {
  if (!MDNS.begin(hostname)) {
    LOG("mdns: failed to start");
    return;
  }
  MDNS.addService("http", "tcp", 80);
  MDNS.addService("dotmatrix", "tcp", 80);
  MDNS.addServiceTxt("dotmatrix", "tcp", "fw", FW_VERSION);
  MDNS.addServiceTxt("dotmatrix", "tcp", "proto", String(PROTO_VERSION));
}

void Network::startServices() {
  if (_servicesUp) return;
  _servicesUp = true;

  startMdns(_hostname);

  sntp_set_sync_interval(NTP_SYNC_INTERVAL_MS);
  configTzTime(_timezone, "pool.ntp.org", "time.google.com", "time.cloudflare.com");

  // Development uploads from PlatformIO: pio run -t upload --upload-port dotmatrix.local
  ArduinoOTA.setHostname(_hostname);
  ArduinoOTA.setMdnsEnabled(false);  // already announced above
  // handle() blocks the loop for the whole upload; keep the watchdog fed.
  ArduinoOTA.onStart([]() { LOG("ota: network upload started"); });
  ArduinoOTA.onProgress([](unsigned int, unsigned int) { esp_task_wdt_reset(); });
  ArduinoOTA.onError([](ota_error_t e) { LOG("ota: error %d", (int)e); });
  ArduinoOTA.begin();
}

void Network::loop() {
  uint32_t now = millis();
  if (_apActive) dns.processNextRequest();
  if (_servicesUp) ArduinoOTA.handle();

  bool connected = WiFi.status() == WL_CONNECTED;

  switch (_state) {
    case State::Connecting:
      if (connected) {
        _state = State::Online;
        LOG("wifi: online, %s (%s.local), rssi %d", WiFi.localIP().toString().c_str(), _hostname,
            WiFi.RSSI());
        startServices();
        if (_onOnline) _onOnline();
      } else if (now - _connectStart >= WIFI_CONNECT_TIMEOUT_MS) {
        LOG("wifi: could not join, opening setup AP");
        startAP();
        _lastRetry = now;
      }
      break;

    case State::Online:
      if (!connected) {
        // Auto-reconnect is on; fall back to setup only if it stays down.
        _state = State::Connecting;
        _connectStart = now;
        LOG("wifi: connection lost");
      }
      break;

    case State::Setup:
      if (connected) {
        stopAP();
        _state = State::Connecting;  // promotes to Online on the next loop
      } else if (_haveCredentials && now - _lastRetry >= 60000 && WiFi.softAPgetStationNum() == 0) {
        _lastRetry = now;
        LOG("wifi: retrying '%s'", _ssid.c_str());
        WiFi.begin(_ssid.c_str(), _pass.c_str());
      }
      break;
  }
}

String Network::ip() const {
  if (_state == State::Online) return WiFi.localIP().toString();
  if (_apActive) return WiFi.softAPIP().toString();
  return "";
}

int Network::rssi() const { return _state == State::Online ? WiFi.RSSI() : 0; }

void Network::applyTimezone(const char* tz) {
  strlcpy(_timezone, tz, sizeof(_timezone));
  setenv("TZ", _timezone, 1);
  tzset();
}

void Network::applyHostname(const char* hostname) {
  strlcpy(_hostname, hostname, sizeof(_hostname));
  WiFi.setHostname(_hostname);
  if (_servicesUp) {
    MDNS.end();
    startMdns(_hostname);  // ArduinoOTA keeps the old name until reboot
  }
}
