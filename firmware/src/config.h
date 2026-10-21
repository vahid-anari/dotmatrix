#pragma once
#include <Arduino.h>

// ---- Version -------------------------------------------------------------
// Release builds set this from the git tag (see .github/workflows/build.yml).
#ifndef FW_VERSION
#define FW_VERSION "0.4.0-dev"
#endif
#define PROTO_VERSION 1

// ---- Hardware ------------------------------------------------------------
constexpr uint8_t PIN_DISPLAY_CS = 7;   // MAX7219 CS (SPI: SCK=4, MOSI=6)
constexpr uint8_t PIN_STATUS_LED = 8;   // on-board LED, active low
constexpr bool STATUS_LED_INVERTED = true;
constexpr uint8_t DISPLAY_MODULES = 8;  // 8 × 8×8 = 64×8
constexpr uint8_t DISPLAY_WIDTH = DISPLAY_MODULES * 8;
constexpr uint8_t DISPLAY_HEIGHT = 8;
// Set to true if animations come out mirrored on your modules.
constexpr bool DISPLAY_FLIP_X = false;

// ---- Limits --------------------------------------------------------------
constexpr size_t MAX_ITEMS = 100;
constexpr size_t MAX_TEXT = 128;            // characters per text item
constexpr size_t MAX_WS_MESSAGE = 48 * 1024;  // largest JSON message accepted
constexpr uint8_t MAX_WS_CLIENTS = 4;

// ---- Network defaults ----------------------------------------------------
#define DEFAULT_HOSTNAME "dotmatrix"
#define SETUP_AP_PREFIX "DotMatrix-"
#define SETUP_AP_PASSWORD "dotmatrix"      // shown on the display in setup mode
#define DEFAULT_TIMEZONE "EST5EDT,M3.2.0,M11.1.0"  // America/Toronto
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;
constexpr uint32_t NTP_SYNC_INTERVAL_MS = 3600UL * 1000;  // hourly
constexpr int8_t WIFI_TX_POWER = 34;  // ×0.25 dBm → 8.5 dBm (C3 Super Mini antenna)

// ---- Timing --------------------------------------------------------------
constexpr uint32_t STATE_BROADCAST_MS = 5000;
constexpr uint32_t WATCHDOG_TIMEOUT_MS = 10000;
constexpr uint32_t SAVE_DEBOUNCE_MS = 2000;  // batch flash writes

// ---- Logging -------------------------------------------------------------
#ifndef LOG_ENABLED
#define LOG_ENABLED 1
#endif
#if LOG_ENABLED
#define LOG(fmt, ...) Serial.printf("[%7lu] " fmt "\n", (unsigned long)millis(), ##__VA_ARGS__)
#else
#define LOG(...) \
  do {           \
  } while (0)
#endif
