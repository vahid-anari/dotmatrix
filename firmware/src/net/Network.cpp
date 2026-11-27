#include "Network.h"

#include <ArduinoOTA.h>

#include "OtaProgress.h"
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_mac.h>
#include <esp_sntp.h>
#include <esp_task_wdt.h>

#include "../model/EventLog.h"
#include "../storage/Storage.h"

// The reason the Wi-Fi gave for the last disconnect (from its event task).
static volatile uint8_t lastDisconnect = 0;

static DNSServer dns;

void Network::begin(const Settings& settings) {
  strlcpy(_hostname, settings.hostname, sizeof(_hostname));
  strlcpy(_timezone, settings.timezone, sizeof(_timezone));
  _txQ = settings.radio.txQ;
  _sleep = settings.radio.sleep;
  // Not the defaults: on trial until the Wi-Fi joins once with them.
  _bootTrial = _txQ != WIFI_TX_POWER || _sleep;
  _prevTxQ = WIFI_TX_POWER;
  _prevSleep = false;

  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);  // works before Wi-Fi is started
  snprintf(_apName, sizeof(_apName), SETUP_AP_PREFIX "%02X%02X", mac[4], mac[5]);

  WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) { lastDisconnect = info.wifi_sta_disconnected.reason; },
               ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.persistent(false);  // we keep credentials ourselves (NVS "wifi")
  WiFi.setAutoReconnect(true);
  WiFi.setHostname(_hostname);

  _haveCredentials = Storage::loadWifi(_ssid, _pass);
  if (_haveCredentials) {
    WiFi.mode(WIFI_STA);
    // Awake by default: with the display's leftover noise, dozing between the
    // router's beacons made it miss them and drop (tested in 0.8.4).
    setRadio();
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
  WiFi.setSleep(false);  // an access point can't doze
  WiFi.setTxPower((wifi_power_t)_txQ);
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
  _apActive = false;
  setRadio();
  WiFi.setAutoReconnect(true);
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
  // The display shows how far it has got (drawn from here: the loop is held up).
  ArduinoOTA.onStart([]() {
    LOG("ota: network upload started");
    OtaProgress::failed = false;
    OtaProgress::percent = 0;
    if (OtaProgress::draw) OtaProgress::draw(0);
  });
  ArduinoOTA.onProgress([](unsigned int done, unsigned int total) {
    esp_task_wdt_reset();
    int8_t p = total ? (int8_t)min<unsigned>(99, done * 100ull / total) : 0;
    if (p != OtaProgress::percent) {
      OtaProgress::percent = p;
      if (OtaProgress::draw) OtaProgress::draw(p);
    }
  });
  ArduinoOTA.onEnd([]() {
    EventLog::noteRestart(EventLog::UPDATE);
    OtaProgress::percent = 100;
    if (OtaProgress::draw) OtaProgress::draw(100);
  });
  ArduinoOTA.onError([](ota_error_t e) {
    LOG("ota: error %d", (int)e);
    OtaProgress::percent = -1;
    OtaProgress::failed = true;
  });
  ArduinoOTA.begin();
}

void Network::loop() {
  uint32_t now = millis();
  if (_apActive) dns.processNextRequest();
  if (_servicesUp) ArduinoOTA.handle();

  bool connected = WiFi.status() == WL_CONNECTED;
  checkRadio(now, connected);

  switch (_state) {
    case State::Connecting:
      if (connected) {
        _state = State::Online;
        LOG("wifi: online, %s (%s.local), rssi %d", WiFi.localIP().toString().c_str(), _hostname,
            WiFi.RSSI());
        startServices();
        if (_lostAt) {  // back after losing it: log how long it was gone
          uint32_t secs = (now - _lostAt) / 1000;
          time_t t = time(nullptr);
          if (t > 1700000000) EventLog::add(t - secs, EventLog::WIFI_LOST, _lostReason, secs, _lostRssi);
          _lostAt = 0;
        }
        if (_onOnline) _onOnline();
      } else if (_lostAt && now - _connectStart < WIFI_RECONNECT_MS) {
        // Lost while running: keep at it for a few minutes before the setup
        // network (which made a few seconds' drop last 81 s: 20 s, then a try a minute).
        // Each try starts over with a full scan: WiFi.reconnect() kept trying the
        // old channel and access point and failed for minutes.
        if (now - _lastRetry >= 15000) {
          _lastRetry = now;
          WiFi.disconnect(false);
          WiFi.begin(_ssid.c_str(), _pass.c_str());
        }
      } else if (now - _connectStart >= (_lostAt ? WIFI_RECONNECT_MS : WIFI_CONNECT_TIMEOUT_MS)) {
        LOG("wifi: could not join, opening setup AP");
        startAP();
        _lastRetry = now;
      }
      break;

    case State::Online:
      if (now - _lastRssiAt >= 5000) {  // the signal just before a drop goes in the event
        _lastRssiAt = now;
        _lastRssi = (int8_t)WiFi.RSSI();
      }
      if (!connected) {
        // Auto-reconnect is on; fall back to setup only if it stays down.
        _state = State::Connecting;
        _connectStart = now;
        _lostAt = now ? now : 1;
        _lostReason = lastDisconnect;
        _lostRssi = _lastRssi;
        _lastRetry = now;
        LOG("wifi: connection lost (reason %u)", _lostReason);
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

void Network::setRadio() {
  WiFi.setTxPower((wifi_power_t)_txQ);
  bool doze = _apActive ? false : _sleep;
  WiFi.setSleep(doze);
  // The router's signals ("beacons") the radio may miss before it calls the
  // Wi-Fi lost: 6 s by default. Dozing sometimes misses several in a row, and
  // that ended the connection (reason 200) though the router was right there;
  // so 20 s while dozing (0.9.1), the default when awake.
  esp_wifi_set_inactive_time(WIFI_IF_STA, doze ? WIFI_DOZE_BEACON_TIMEOUT_S : 6);
}

void Network::applyRadio(uint8_t txQ, bool sleep) {
  if (txQ == _txQ && sleep == _sleep) return;
  if (!_radioTrialAt && !_bootTrial) {  // the last proven ones, to go back to
    _prevTxQ = _txQ;
    _prevSleep = _sleep;
  }
  _txQ = txQ;
  _sleep = sleep;
  setRadio();
  _radioTrialAt = millis() ? millis() : 1;
  LOG("wifi: radio %.2f dBm, sleep %s (on trial)", txQ / 4.0, sleep ? "on" : "off");
}

// A new radio setting stays if the Wi-Fi is up a minute after it; if the Wi-Fi
// is down for a whole minute meanwhile (or never joins after a start with it),
// the last good one comes back.
void Network::checkRadio(uint32_t now, bool connected) {
  if (!_radioTrialAt && !_bootTrial) return;
  static uint32_t downSince = 0;
  if (connected) {
    downSince = 0;
    if (_bootTrial || now - _radioTrialAt >= 60000) {
      _bootTrial = false;
      _radioTrialAt = 0;
      LOG("wifi: radio setting kept");
    }
    return;
  }
  if (!downSince) downSince = now ? now : 1;
  if (now - downSince < 60000 || !_haveCredentials) return;
  LOG("wifi: no connection with the new radio setting; back to %.2f dBm, sleep %s", _prevTxQ / 4.0,
      _prevSleep ? "on" : "off");
  _txQ = _prevTxQ;
  _sleep = _prevSleep;
  _radioTrialAt = 0;
  _bootTrial = false;
  _reverted = true;
  downSince = 0;
  setRadio();
  WiFi.disconnect(false);
  WiFi.begin(_ssid.c_str(), _pass.c_str());
}

bool Network::radioReverted(uint8_t& txQ, bool& sleep) {
  if (!_reverted) return false;
  _reverted = false;
  txQ = _txQ;
  sleep = _sleep;
  return true;
}

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
